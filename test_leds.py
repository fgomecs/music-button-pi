import RPi.GPIO as GPIO
import time
from led_spectrum import setup_leds, pulse_leds, cleanup_leds

try:
    setup_leds()
    print("Testing LEDs: each should light up in sequence (green, yellow, red)...")
    for _ in range(3):  # Run 3 cycles
        pulse_leds(duration=0.5)
        time.sleep(0.5)
    print("Test complete.")
except KeyboardInterrupt:
    print("Test stopped.")
finally:
    cleanup_leds()
