"""goCharge skill implementation."""

import time


def go_charge(agent, parameters: dict) -> dict:
    """Navigate to and connect with the charging station."""
    from ..epuck2 import ROB_ADDR
    from ..pipuck import PiPuck

    max_iterations = int(parameters.get("max_iterations", 100))
    proximity_threshold = int(parameters.get("proximity_threshold", 2000))
    alignment_threshold = int(parameters.get("alignment_threshold", 300))
    approach_speed = int(parameters.get("approach_speed", 200))
    dock_timeout = float(parameters.get("dock_timeout", 10.0))

    address = ROB_ADDR if agent.i2c_address is None else agent.i2c_address

    with PiPuck(i2c_channel=agent.i2c_channel, address=address) as pi:
        bot = pi.epuck2

        start_time = time.time()
        found_dock = False

        for iteration in range(max_iterations):
            if time.time() - start_time > dock_timeout:
                bot.set_wheel_speeds(0, 0)
                bot.update()
                raise RuntimeError("Dock detection timeout")

            frame = bot.update()
            if frame is None or not frame.prox:
                time.sleep(0.05)
                continue

            front_left = frame.prox[0]
            front_center_left = frame.prox[1]
            front_center_right = frame.prox[2]
            front_right = frame.prox[3]

            front_max = max(front_left, front_center_left, front_center_right, front_right)

            if front_max > proximity_threshold:
                found_dock = True
                break

            left_front = front_left + front_center_left
            right_front = front_center_right + front_right
            balance = right_front - left_front

            left_speed = approach_speed - (balance // 4)
            right_speed = approach_speed + (balance // 4)

            left_speed = max(-500, min(500, left_speed))
            right_speed = max(-500, min(500, right_speed))

            bot.set_wheel_speeds(left_speed, right_speed)
            time.sleep(0.1)

        if not found_dock:
            bot.set_wheel_speeds(0, 0)
            bot.update()
            raise RuntimeError("Dock not detected")

        align_start = time.time()
        align_timeout = 5.0

        while time.time() - align_start < align_timeout:
            frame = bot.update()
            if frame is None or not frame.prox:
                time.sleep(0.05)
                continue

            front_center_left = frame.prox[1]
            front_center_right = frame.prox[2]
            center_diff = abs(front_center_left - front_center_right)

            if center_diff < alignment_threshold:
                bot.set_wheel_speeds(50, 50)
                time.sleep(0.5)
                bot.set_wheel_speeds(0, 0)
                bot.update()

                try:
                    bot.set_rgb_led(index=2, r=0, g=100, b=0)
                    bot.update()
                except Exception:
                    pass

                return {
                    "phase": "charged",
                    "aligned": True,
                    "iterations": iteration + 1,
                    "total_time": time.time() - start_time,
                }

            balance = front_center_right - front_center_left
            left_speed = 150 - (balance // 6)
            right_speed = 150 + (balance // 6)

            left_speed = max(-300, min(300, left_speed))
            right_speed = max(-300, min(300, right_speed))

            bot.set_wheel_speeds(left_speed, right_speed)
            time.sleep(0.1)

        bot.set_wheel_speeds(0, 0)
        bot.update()

        return {
            "phase": "docked",
            "aligned": False,
            "iterations": iteration + 1,
            "total_time": time.time() - start_time,
            "warning": "Alignment timeout, proceeding with dock connection",
        }
