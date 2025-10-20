"""Omnidirectional camera capture and polar-unwrapping utilities.

Intended usage (see examples/omni_preview.py):
  cam = OmniCamera()
  cam.device = "/dev/video0"  # or 0
  cam.width, cam.height, cam.fps = 640, 480, 30
  cam.out_w, cam.out_h = 720, 256
  cam.open()
  cam.calibrate()  # optional; can set center/radius manually
  pano = cam.read_unwrapped()
  cam.close()

Notes:
- Calibration tries to detect the mirror circle in the raw frame using Hough
  transform or largest circular-like contour. If it fails, set center/radius
  manually via set_center_radius.
- Unwrap uses cv2.warpPolar in linear angle mapping, then rotates by
  yaw_offset_deg to align the panorama heading.
"""

from typing import Optional, Tuple, Union
import math

import cv2
import numpy as np


Scalar = Union[int, float]


class OmniCamera:
    def __init__(self):
        # Input capture settings
        self.device = 2  # type: Union[int, str]
        self.width = 480  # type: int
        self.height = 480  # type: int
        self.fps = 30  # type: int

        # Unwrap/output settings
        self.out_w = 720  # type: int
        self.out_h = 256  # type: int
        self.yaw_offset_deg = 0.0  # type: float  # rotate panorama (positive=left/CCW)

        # Mirror geometry (pixels in raw frame)
        self.center = None  # type: Optional[Tuple[float, float]]  # (cx, cy)
        self.radius = None  # type: Optional[float]  # outer mirror radius
        self.rmin_ratio = 0.15  # type: float  # fraction of radius to cut inner blind area

        # Internals
        self._cap = None  # type: Optional[cv2.VideoCapture]

    # Lifecycle -------------------------------------------------------------
    def open(self):
        if self._cap is not None and self._cap.isOpened():
            return

        cap = cv2.VideoCapture(self.device)
        print("OmniCamera: opened device:", self.device)
        if not cap.isOpened():
            raise RuntimeError("Could not open camera: {}".format(self.device))

        # # Set common properties (best-effort)
        if self.width:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(self.width))
        if self.height:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self.height))
        if self.fps:
            cap.set(cv2.CAP_PROP_FPS, float(self.fps))

        self._cap = cap

    def close(self):
        if self._cap is not None:
            try:
                self._cap.release()
            finally:
                self._cap = None

    def __enter__(self):  # type: () -> OmniCamera
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb):  # type: (Optional[type], Optional[BaseException], Optional[object]) -> None
        self.close()

    @property
    def is_open(self):  # type: () -> bool
        return self._cap is not None and bool(self._cap.isOpened())

    # Capture ---------------------------------------------------------------
    def read_raw(self):  # type: () -> np.ndarray
        if not self.is_open:
            self.open()
        assert self._cap is not None
        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise RuntimeError("Failed to read frame from camera")
        return frame

    # Calibration -----------------------------------------------------------
    def calibrate(self, frame=None):  # type: (Optional[np.ndarray]) -> Tuple[Tuple[float, float], float]
        """Calibrate using the black inner disc for center; radius is hardcoded or rim-based.

        Returns ((cx, cy), r).
        """
        if frame is None:
            frame = self.read_raw()
        if frame is None or not getattr(frame, 'size', 0):
            raise ValueError("Invalid frame for calibration")

        h, w = frame.shape[:2]
        m = float(min(h, w))

        # 1) Find the black inner disc to estimate center
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_blur = cv2.GaussianBlur(gray, (9, 9), 2.0)
        circles = cv2.HoughCircles(
            gray_blur, cv2.HOUGH_GRADIENT, dp=1.0, minDist=0.3 * m,
            param1=100, param2=30,
            minRadius=int(0.1 * m), maxRadius=int(0.3 * m)
            )

        if circles is not None and len(circles) > 0:
            cand = np.uint16(np.around(circles[0]))
            # choose darkest candidate with slight center bias
            best, best_score = None, 1e9
            for (x, y, r) in cand: # type: ignore
                mask = np.zeros_like(gray, dtype=np.uint8)
                cv2.circle(mask, (int(x), int(y)), max(1, int(r - 2)), 255, -1)
                mean_int = cv2.mean(gray, mask=mask)[0] # type: ignore
                dist = math.hypot(float(x) - (w * 0.5), float(y) - (h * 0.5)) / m
                score = mean_int + 40.0 * dist
                if score < best_score:
                    best_score, best = score, (float(x), float(y))
            if best is not None:
                cx, cy = best

        self.set_center_radius((cx, cy), r)
        return (cx, cy), r

    def set_center_radius(self, center, radius):  # type: (Tuple[Scalar, Scalar], Scalar) -> None
        cx, cy = float(center[0]), float(center[1])
        r = float(radius)
        if r <= 0:
            raise ValueError("radius must be > 0")
        self.center = (cx, cy)
        self.radius = r

    # Unwrap ---------------------------------------------------------------
    def unwrap(self, frame):  # type: (np.ndarray) -> np.ndarray
        if self.center is None or self.radius is None:
            # Heuristic default: assume centered
            h, w = frame.shape[:2]
            cx, cy = w * 0.5, h * 0.5
            r = min(h, w) * 0.45
            self.center, self.radius = (cx, cy), r

        # Help static type checkers
        assert self.center is not None and self.radius is not None
        cx, cy = self.center
        r_out = float(self.radius)
        r_in = max(0.0, float(self.rmin_ratio) * r_out)

        # Use warpPolar when available (OpenCV 4+), otherwise fall back to remap
        if hasattr(cv2, 'warpPolar'):
            # OpenCV maps angle along width: 0..out_w corresponds to 0..2*pi.
            flags = cv2.WARP_POLAR_LINEAR
            dst_size = (int(self.out_w), int(self.out_h))
            # First warp from 0..r_out, then crop to simulate inner radius
            tmp = cv2.warpPolar(frame, dst_size, (cx, cy), r_out, flags)
            pano = self._rotate_yaw(tmp, self.yaw_offset_deg)
            if r_in > 1e-3:
                y0 = int(round(self.out_h * (r_in / r_out)))
                if y0 < self.out_h:
                    pano = pano[y0:, :, :]
                    if pano.shape[0] != self.out_h:
                        pano = cv2.resize(pano, (self.out_w, self.out_h), interpolation=cv2.INTER_LINEAR)
        else:
            # Build mapping for cv2.remap: map each panorama pixel to source xy
            out_h = int(self.out_h)
            out_w = int(self.out_w)
            yy, xx = np.meshgrid(np.arange(out_h, dtype=np.float32), np.arange(out_w, dtype=np.float32), indexing='ij')
            # Angle in radians across width, apply yaw offset (CCW positive)
            theta = (xx / float(out_w)) * (2.0 * math.pi)
            theta = theta - (self.yaw_offset_deg * math.pi / 180.0)
            # Radius from r_in..r_out across height
            rad = r_in + (yy / max(1.0, float(out_h - 1))) * (r_out - r_in)
            map_x = (cx + rad * np.cos(theta)).astype(np.float32)
            map_y = (cy + rad * np.sin(theta)).astype(np.float32)
            pano = cv2.remap(frame, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

        return pano

    def _rotate_yaw(self, img, yaw_deg):  # type: (np.ndarray, float) -> np.ndarray
        if not img.size:
            return img
        if abs(yaw_deg) < 1e-6:
            return img
        # Horizontal wrap-around rotation by shifting columns
        w = img.shape[1]
        shift = int(round((yaw_deg / 360.0) * w))
        if shift == 0:
            return img
        return np.roll(img, shift=shift, axis=1)

    def read_unwrapped(self):  # type: () -> np.ndarray
        frame = self.read_raw()
        return self.unwrap(frame)

    # Convenience -----------------------------------------------------------
    def snapshot(self):  # type: () -> np.ndarray
        """Alias for read_unwrapped(); kept for potential future expansion."""
        return self.read_unwrapped()

    # Visualization ---------------------------------------------------------
    def draw_calibration_overlay(self, frame, color=(0, 0, 255), thickness=2):  # type: (np.ndarray, Tuple[int, int, int], int) -> np.ndarray
        """Return a copy of frame with the detected mirror circle and center drawn.

        - Draws a red circle (BGR=(0,0,255) by default) for the mirror radius
          and a small filled dot at the center. If center/radius are missing,
          it attempts a quick calibrate() using this frame; if that fails, it
          just returns a copy of the input frame.
        """
        if frame is None or not getattr(frame, 'size', 0):
            return frame

        out = frame.copy()
        cxcy = self.center
        r = self.radius
        if cxcy is None or r is None:
            try:
                self.calibrate(frame)
                cxcy, r = self.center, self.radius
            except Exception:
                cxcy, r = None, None

        if cxcy is None or r is None or r <= 0:
            return out

        cx, cy = int(round(cxcy[0])), int(round(cxcy[1]))
        rad = int(round(r))

        try:
            # Main circle
            cv2.circle(out, (cx, cy), rad, color, thickness)
            # Inner blind radius indicator (if configured)
            if self.rmin_ratio and self.rmin_ratio > 0:
                inner = int(round(rad * float(self.rmin_ratio)))
                if inner > 0:
                    cv2.circle(out, (cx, cy), inner, color, 1)
            # Center dot
            cv2.circle(out, (cx, cy), 3, color, -1)
            # Crosshair for orientation reference
            h, w = out.shape[:2]
            cv2.line(out, (max(0, cx - 20), cy), (min(w - 1, cx + 20), cy), color, 1)
            cv2.line(out, (cx, max(0, cy - 20)), (cx, min(h - 1, cy + 20)), color, 1)
        except Exception:
            # In case OpenCV drawing fails for any reason, return the copy.
            pass

        return out