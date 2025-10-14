"""Drive the Pi-puck/e-puck2 with WASD keys.

Controls:
  w = forward
  s = backward
  a = rotate left
  d = rotate right
    + or = = faster
    - or _ = slower
  space = stop
  q = quit

Notes:
- Run this on the Pi-puck over an interactive terminal (local or SSH).
- Ensure I2C is enabled and the robot is powered on.
"""

import sys
import time
import select
import termios
import tty
from typing import Optional

from pipuck import PiPuck


SPEED_FWD = 300
SPEED_TURN = 250
MIN_SPEED = 50
MAX_SPEED = 800
SPEED_STEP = 50


def _configure_terminal() -> list:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    return old


def _restore_terminal(old_settings: list) -> None:
    try:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
    except Exception:
        pass


def _read_key(timeout: float = 0.05) -> Optional[str]:
    """Read a single key if available within timeout; return None otherwise."""
    dr, _, _ = select.select([sys.stdin], [], [], timeout)
    if not dr:
        return None
    ch = sys.stdin.read(1)
    return ch


def _print_menu(base_speed: int, turn_speed: int) -> None:
    print(
        "\nControls: WASD to drive | +/= faster | -/_ slower | space stop | q quit"
    )
    print("Speed: base={} turn={}".format(base_speed, turn_speed))


def main() -> None:
    print(__doc__)
    old_tio = _configure_terminal()
    try:
        with PiPuck() as pi:
            bot = pi.epuck2
            left, right = 0, 0
            base_speed = SPEED_FWD
            turn_speed = SPEED_TURN
            mode = "stop"  # one of: stop, forward, backward, left, right
            bot.set_wheel_speeds(left, right)
            # Send first command and read sensors
            bot.update()

            _print_menu(base_speed, turn_speed)
            while True:
                key = _read_key(0.05)
                if key is not None:
                    k = key.lower()
                    if k == "q":
                        break
                    elif k == "w":
                        mode = "forward"
                        left, right = base_speed, base_speed
                    elif k == "s":
                        mode = "backward"
                        left, right = -base_speed, -base_speed
                    elif k == "a":
                        mode = "left"
                        left, right = -turn_speed, turn_speed
                    elif k == "d":
                        mode = "right"
                        left, right = turn_speed, -turn_speed
                    elif k == " ":
                        mode = "stop"
                        left, right = 0, 0
                    elif k in "+=":
                        base_speed = min(MAX_SPEED, base_speed + SPEED_STEP)
                        turn_speed = min(MAX_SPEED, turn_speed + SPEED_STEP)
                        _print_menu(base_speed, turn_speed)
                        # Recompute based on current mode
                        if mode == "forward":
                            left, right = base_speed, base_speed
                        elif mode == "backward":
                            left, right = -base_speed, -base_speed
                        elif mode == "left":
                            left, right = -turn_speed, turn_speed
                        elif mode == "right":
                            left, right = turn_speed, -turn_speed
                    elif k in "-_":
                        base_speed = max(MIN_SPEED, base_speed - SPEED_STEP)
                        turn_speed = max(MIN_SPEED, turn_speed - SPEED_STEP)
                        _print_menu(base_speed, turn_speed)
                        if mode == "forward":
                            left, right = base_speed, base_speed
                        elif mode == "backward":
                            left, right = -base_speed, -base_speed
                        elif mode == "left":
                            left, right = -turn_speed, turn_speed
                        elif mode == "right":
                            left, right = turn_speed, -turn_speed

                    bot.set_wheel_speeds(left, right)

                # Keep sending actuator state and optionally read sensors
                frame = bot.update()
                time.sleep(0.02)

    except KeyboardInterrupt:
        pass
    finally:
        try:
            with PiPuck() as pi:
                pi.epuck2.set_wheel_speeds(0, 0)
                pi.epuck2.update()
                time.sleep(0.05)
        except Exception:
            pass
        _restore_terminal(old_tio)
        print("\nExited.")


if __name__ == "__main__":
    main()
