from pipuck import PiPuck
import time

with PiPuck() as pi:
    bot = pi.epuck2
    bot.set_wheel_speeds(0, 0)
    for _ in range(40):
        frame = bot.update()
        print("prox:", frame.prox, "selector:", frame.selector, "button:", frame.button)
        time.sleep(0.05)
