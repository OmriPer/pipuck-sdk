import pipuck
import time

def argmax(lst):
    max_index = 0
    max_value = lst[0]
    for i in range(1, len(lst)):
        if lst[i] > max_value:
            max_value = lst[i]
            max_index = i
    return max_index

def main():
    with pipuck.PiPuck() as pi:
        print("PiPuck connected.")
        try:
            while True:
                sensor_data = pi.update()
                if (max(sensor_data.prox) < 50):
                    pi.epuck2.set_rgb_leds(r=0, g=0, b=0)
                    time.sleep(0.01)
                    continue
                
                max_prox_direction = argmax(sensor_data.prox)

                if max_prox_direction == 0:
                    pi.epuck2.set_rgb_leds(r=100, g=0, b=0)
                elif max_prox_direction == 1:
                    pi.epuck2.set_rgb_leds(r=100, g=50, b=0)
                elif max_prox_direction == 2:
                    pi.epuck2.set_rgb_leds(r=100, g=100, b=0)
                elif max_prox_direction == 3:
                    pi.epuck2.set_rgb_leds(r=0, g=100, b=0)
                elif max_prox_direction == 4:
                    pi.epuck2.set_rgb_leds(r=0, g=0, b=100)
                elif max_prox_direction == 5:
                    pi.epuck2.set_rgb_leds(r=75, g=0, b=100)
                elif max_prox_direction == 6:
                    pi.epuck2.set_rgb_leds(r=150, g=0, b=100)
                elif max_prox_direction == 7:
                    pi.epuck2.set_rgb_leds(r=100, g=0, b=50)

                time.sleep(0.01)
        except KeyboardInterrupt:
            print("Exiting...")
if __name__ == "__main__":
    main()