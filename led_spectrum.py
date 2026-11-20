import RPi.GPIO as GPIO
import time
import threading

# LED GPIO pins (in order: 4 green, 2 yellow, 2 red)
LED_PINS = [5, 6, 13, 19, 26, 16, 20, 21]

# Global flag and thread
spectrum_running = False
spectrum_thread = None

def setup_leds():
    """Initialize GPIO pins for LEDs."""
    for pin in LED_PINS:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

def cleanup_leds():
    """Turn off all LEDs and clean up GPIO."""
    global spectrum_running, spectrum_thread
    spectrum_running = False
    if spectrum_thread is not None:
        spectrum_thread.join()
        spectrum_thread = None
    try:
        for pin in LED_PINS:
            GPIO.output(pin, GPIO.LOW)
    except RuntimeError:
        pass  # Ignore if GPIO mode not set
    # Do not call GPIO.cleanup() here to avoid conflicts

def pulse_leds(duration=0.5):
    """Pulse LEDs in a simple pattern (for testing)."""
    try:
        for pin in LED_PINS:
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(duration / len(LED_PINS))
            GPIO.output(pin, GPIO.LOW)
    except Exception as e:
        print(f"LED pulse error: {e}")

def spectrum_loop():
    """Run a dynamic wave-like pattern to simulate audio spectrum."""
    global spectrum_running
    try:
        while spectrum_running:
            # Forward wave (green -> yellow -> red)
            for i in range(len(LED_PINS)):
                if not spectrum_running:
                    break
                GPIO.output(LED_PINS[i], GPIO.HIGH)
                time.sleep(0.1)
                GPIO.output(LED_PINS[i], GPIO.LOW)
            # Backward wave (red -> yellow -> green)
            for i in range(len(LED_PINS) - 1, -1, -1):
                if not spectrum_running:
                    break
                GPIO.output(LED_PINS[i], GPIO.HIGH)
                time.sleep(0.1)
                GPIO.output(LED_PINS[i], GPIO.LOW)
    except Exception as e:
        print(f"Spectrum loop error: {e}")

def start_spectrum():
    """Start the spectrum display in a separate thread."""
    global spectrum_running, spectrum_thread
    if not spectrum_running:
        spectrum_running = True
        spectrum_thread = threading.Thread(target=spectrum_loop)
        spectrum_thread.start()

def stop_spectrum():
    """Stop the spectrum display."""
    global spectrum_running, spectrum_thread
    spectrum_running = False
    if spectrum_thread is not None:
        spectrum_thread.join()
        spectrum_thread = None
