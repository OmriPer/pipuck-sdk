"""Epuck2 controller for Pi-puck (pipuck-sdk).

High-level I2C control of e-puck2 via Pi-puck.
"""

from dataclasses import dataclass
from typing import List, Optional
from smbus2 import SMBus, i2c_msg

I2C_CHANNEL = 12
LEGACY_I2C_CHANNEL = 4
ROB_ADDR = 0x1F

ACTUATORS_SIZE = 19 + 1
SENSORS_SIZE = 46 + 1


def _to_le_bytes_i16(val: int) -> bytes:
    val &= 0xFFFF
    return bytes((val & 0xFF, (val >> 8) & 0xFF))


def _from_le_u16(lo: int, hi: int) -> int:
    return (hi << 8) | lo


def _xor_checksum(buf: bytearray, length: int) -> int:
    c = 0
    for i in range(length):
        c ^= buf[i]
    return c & 0xFF


@dataclass
class SensorFrame:
    prox: List[int]
    ambient: List[int]
    mic: List[int]
    selector: int
    button: int
    motor_steps: List[int]
    tv: int
    raw: bytes


class Epuck2:
    def __init__(self, i2c_channel: Optional[int] = None, address: int = ROB_ADDR, auto_fallback: bool = True):
        self.address = address
        self._bus: Optional[SMBus] = None
        self._i2c_channel_requested = i2c_channel
        self._auto_fallback = auto_fallback
        self._act = bytearray([0] * ACTUATORS_SIZE)
        self._sens = bytearray([0] * SENSORS_SIZE)
        self._last_frame: Optional[SensorFrame] = None

    def open(self) -> None:
        if self._bus is not None:
            return
        channels = []
        if self._i2c_channel_requested is not None:
            channels = [self._i2c_channel_requested]
            if self._auto_fallback and self._i2c_channel_requested != LEGACY_I2C_CHANNEL:
                channels.append(LEGACY_I2C_CHANNEL)
        else:
            channels = [I2C_CHANNEL]
            if self._auto_fallback:
                channels.append(LEGACY_I2C_CHANNEL)
        last_err: Optional[Exception] = None
        for ch in channels:
            try:
                self._bus = SMBus(ch)
                return
            except Exception as e:
                last_err = e
                self._bus = None
                continue
        if last_err:
            raise RuntimeError(f"Cannot open I2C device on channels {channels}: {last_err}")

    def close(self) -> None:
        if self._bus is not None:
            try:
                self._bus.close()
            finally:
                self._bus = None

    def __enter__(self) -> "Epuck2":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # Actuators
    def set_wheel_speeds(self, left: int, right: int) -> None:
        left = int(max(-2000, min(2000, int(left))))
        right = int(max(-2000, min(2000, int(right))))
        lb = _to_le_bytes_i16(left)
        rb = _to_le_bytes_i16(right)
        self._act[0], self._act[1] = lb[0], lb[1]
        self._act[2], self._act[3] = rb[0], rb[1]

    def set_motor_steps(self, left_steps: int, right_steps: int) -> None:
        ls = int(max(-32768, min(32767, int(left_steps))))
        rs = int(max(-32768, min(32767, int(right_steps))))
        lb = _to_le_bytes_i16(ls)
        rb = _to_le_bytes_i16(rs)
        self._act[0], self._act[1] = lb[0], lb[1]
        self._act[2], self._act[3] = rb[0], rb[1]

    def set_speaker(self, sound_id: int) -> None:
        self._act[4] = max(0, min(2, int(sound_id)))

    def set_ring_leds(self, mask: int) -> None:
        self._act[5] = int(mask) & 0x0F

    def set_rgb_led(self, index: int, r: int, g: int, b: int) -> None:
        offset_map = {2: 6, 4: 9, 6: 12, 8: 15}
        if index not in offset_map:
            raise ValueError("index must be one of 2,4,6,8")
        o = offset_map[index]
        self._act[o] = max(0, min(100, int(r)))
        self._act[o + 1] = max(0, min(100, int(g)))
        self._act[o + 2] = max(0, min(100, int(b)))

    def set_settings(self, value: int) -> None:
        self._act[18] = int(value) & 0x07

    def calibrate_proximity(self, enable: bool = True) -> None:
        self._set_settings_bit(0, enable)

    def set_onboard_avoidance(self, enable: bool) -> None:
        self._set_settings_bit(1, enable)

    def set_steps_mode(self, enable: bool) -> None:
        self._set_settings_bit(2, enable)

    def _set_settings_bit(self, bit_index: int, enable: bool) -> None:
        mask = 1 << bit_index
        cur = self._act[18] & 0x07
        if enable:
            cur |= mask
        else:
            cur &= ~mask & 0x07
        self._act[18] = cur

    # I/O
    def update(self, verify_checksum: bool = True, raise_on_error: bool = False) -> "SensorFrame":
        if self._bus is None:
            self.open()
        self._act[ACTUATORS_SIZE - 1] = _xor_checksum(self._act, ACTUATORS_SIZE - 1)
        try:
            write = i2c_msg.write(self.address, self._act)
            read = i2c_msg.read(self.address, SENSORS_SIZE)
            assert self._bus is not None
            self._bus.i2c_rdwr(write, read)
            data = bytes(read)
        except Exception:
            if raise_on_error:
                raise
            data = bytes(self._sens)
        self._sens[: len(data)] = data
        ok = _xor_checksum(self._sens, SENSORS_SIZE - 1) == self._sens[SENSORS_SIZE - 1]
        if verify_checksum and not ok and raise_on_error:
            raise ValueError("Sensor checksum mismatch")
        frame = self._parse_sensors(self._sens)
        self._last_frame = frame
        return frame

    @property
    def last_frame(self) -> Optional["SensorFrame"]:
        return self._last_frame

    @staticmethod
    def _parse_sensors(buf: bytearray) -> "SensorFrame":
        prox = [_from_le_u16(buf[i * 2], buf[i * 2 + 1]) for i in range(8)]
        base = 16
        ambient = [_from_le_u16(buf[base + i * 2], buf[base + i * 2 + 1]) for i in range(8)]
        base = 32
        mic = [_from_le_u16(buf[base + i * 2], buf[base + i * 2 + 1]) for i in range(4)]
        sel_btn = buf[40]
        selector = sel_btn & 0x0F
        button = (sel_btn >> 4) & 0x0F
        base = 41
        motor_steps = [
            _from_le_u16(buf[base + 0], buf[base + 1]),
            _from_le_u16(buf[base + 2], buf[base + 3]),
        ]
        tv = buf[45]
        return SensorFrame(
            prox=prox,
            ambient=ambient,
            mic=mic,
            selector=selector,
            button=button,
            motor_steps=motor_steps,
            tv=tv,
            raw=bytes(buf[:SENSORS_SIZE]),
        )
