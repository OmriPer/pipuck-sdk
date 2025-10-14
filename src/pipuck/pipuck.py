"""PiPuck peripherals aggregator (pipuck-sdk)."""

from typing import Optional

from .epuck2 import Epuck2, SensorFrame, ROB_ADDR


class PiPuck:
    def __init__(self, i2c_channel: Optional[int] = None, address: int = ROB_ADDR, auto_fallback: bool = True):
        self.epuck2 = Epuck2(i2c_channel=i2c_channel, address=address, auto_fallback=auto_fallback)

    def open(self) -> None:
        self.epuck2.open()

    def close(self) -> None:
        self.epuck2.close()

    def __enter__(self) -> "PiPuck":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def update(self, *args, **kwargs) -> SensorFrame:
        return self.epuck2.update(*args, **kwargs)
