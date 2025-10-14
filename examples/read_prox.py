from pipuck import PiPuck
import sys
import time
import termios
import tty


UI_INTERVAL = 0.10  # seconds between refreshes


def _configure_terminal():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    return old


def _restore_terminal(old):
    try:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old)
    except Exception:
        pass


def _render_inline(prox, selector, button):
    vals = ", ".join(str(int(x)) for x in prox)
    line = "prox: [{}]  selector: {}  button: {}".format(vals, int(selector), int(button))
    sys.stdout.write("\r" + line + " " * 8)
    sys.stdout.flush()


def main():
    old = _configure_terminal()
    try:
        with PiPuck() as pi:
            bot = pi.epuck2
            bot.set_wheel_speeds(0, 0)
            last_ui = 0.0
            while True:
                frame = bot.update()
                now = time.time()
                if now - last_ui >= UI_INTERVAL:
                    _render_inline(frame.prox, frame.selector, frame.button)
                    last_ui = now
                time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        _restore_terminal(old)
        try:
            sys.stdout.write("\n")
            sys.stdout.flush()
        except Exception:
            pass


if __name__ == "__main__":
    main()
