"""Capture and save omnidirectional panorama frames (Python 3.5 compatible).

Examples:
  python examples/omni_preview.py --out omni.png              # save 1 frame
  python examples/omni_preview.py --count 10 --interval 0.5   # save 10 frames
  python examples/omni_preview.py --out "frames/pano_{i:03d}.png" --count 5
"""

from __future__ import print_function

import argparse
import os
import time
import cv2

from pipuck import PiPuck


def build_filename(base, i):
    # Allow placeholders: {i}, {ts}
    ts = int(time.time() * 1000)
    if "{" in base and "}" in base:
        try:
            return base.format(i=i, ts=ts)
        except Exception:
            pass
    root, ext = os.path.splitext(base)
    if i is not None:
        return "{0}_{1:03d}{2}".format(root or "omni_pano", i, ext or ".png")
    return base or "omni_pano.png"


def main():
    parser = argparse.ArgumentParser(description="Save unwrapped omni camera frames")
    parser.add_argument("--device", default="/dev/video2", help="V4L2 device or index")
    parser.add_argument("--out", default="omni_pano.png", help="Output file path or pattern (supports {i},{ts})")
    parser.add_argument("--count", type=int, default=1, help="Number of frames to save")
    parser.add_argument("--interval", type=float, default=0.0, help="Seconds between frames")
    args = parser.parse_args()

    # Ensure output directory exists if a path is provided
    out_dir = os.path.dirname(args.out)
    if out_dir and not os.path.isdir(out_dir):
        try:
            os.makedirs(out_dir)
        except Exception:
            pass

    with PiPuck() as pi:
        cam = pi.omni
        cam.device = args.device
        cam.width = 640
        cam.height = 480
        cam.fps = 30
        cam.out_w = 720
        cam.out_h = 256
        cam.yaw_offset_deg = 0.0

        cam.open()

        saved = 0
        for i in range(args.count):
            try:
                cam.calibrate()
                raw = cam.read_raw()
                raw_overlay = cam.draw_calibration_overlay(raw)
                pano = cam.read_unwrapped()
            except Exception as e:
                print("Read failed: {}".format(e))
                break

            fname = build_filename(args.out, i if args.count > 1 else None)
            raw_name = fname.replace(".png", "_raw.png").replace(".jpg", "_raw.jpg")
            ok = cv2.imwrite(raw_name, raw_overlay if raw_overlay is not None else raw)
            if ok:
                print("Saved {}".format(raw_name))
            else:
                print("Failed to save {}".format(raw_name))
            ok = cv2.imwrite(fname, pano)
            if ok:
                print("Saved {}".format(fname))
                saved += 1
            else:
                print("Failed to save {}".format(fname))

            if args.interval > 0 and i < args.count - 1:
                time.sleep(args.interval)

    if saved == 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
