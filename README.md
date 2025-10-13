# pipuck-sdk

A minimal Pi-puck SDK for controlling the e-puck2 and other peripherals.

## Install (editable)

```bash
pip install -e .
```

Requires `smbus2` and I2C enabled on your Pi.

## Quick start

```python
from pipuck import PiPuck

with PiPuck() as pi:
    ep = pi.epuck2
    ep.set_wheel_speeds(200, 200)
    frame = ep.update()
    print(frame.prox)
```

## Features
- Epuck2 I2C control (actuators/sensors)
- Protocol checksum validation
- Safety limits per GCtronic docs (speed, LEDs, speaker, settings)

## Repo rename
Rename your GitHub repository to `pipuck-sdk`.

Then update the homepage URL in `pyproject.toml` if needed.

## License
MIT
