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
- Swarm discovery and control over the local network

## Swarm quick start

Start the swarm agent on each Pi-puck (on the robot):

```bash
pipuck-swarm agent --name pipuck-1
```

List available Pi-pucks from a controller machine:

```bash
pipuck-swarm list
```

Send a shared plan (left,right,duration) to the entire swarm:

```bash
pipuck-swarm run --plan "200,200,1.0;0,0,0.5;200,-200,1.0"
```

Send the same plan to a subset by name or IP:

```bash
pipuck-swarm run --targets pipuck-1 192.168.1.42 --step 150,150,2.0 --step 0,0,0.5
```

## Repo rename
Rename your GitHub repository to `pipuck-sdk`.

Then update the homepage URL in `pyproject.toml` if needed.

## License
MIT
