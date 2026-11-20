# play_song.py
import RPi.GPIO as GPIO
import subprocess
import time
from config import BUTTON_PIN, SONGS, SONG_NAMES
from animations import fish_splash_screen, display_initial_message, display_song, display_goodbye, clear_display
from led_spectrum import setup_leds, start_spectrum, stop_spectrum, cleanup_leds

# Initialize GPIO
GPIO.setmode(GPIO.BCM)
BUTTON_PIN = 18
try:
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
except Exception as e:
    print(f"GPIO setup failed: {e}")
    exit(1)

# Initialize LEDs
try:
    setup_leds()
except Exception as e:
    print(f"LED setup failed: {e}")
    exit(1)

# Song list

# Main Logic
current_song_index = 0
current_process = None
last_button_state = GPIO.LOW
first_press = True

# Initial splash screen
try:
    fish_splash_screen()
    display_initial_message()
except Exception as e:
    print(f"Display initialization failed: {e}")
    cleanup_leds()
    GPIO.cleanup()
    exit(1)

print("Press the button to start or skip songs (Ctrl+C to exit)...")
try:
    while True:
        button_state = GPIO.input(BUTTON_PIN)
        if button_state == GPIO.HIGH and last_button_state == GPIO.LOW:
            print(f"Button pressed, current song index: {current_song_index}")
            if current_process is not None:
                current_process.kill()
                current_process.wait()
                stop_spectrum()
                print("Previous song process terminated.")
            if first_press:
                first_press = False
            else:
                current_song_index = (current_song_index + 1) % len(SONGS)
            song_path = SONGS[current_song_index]
            print(f"Starting song {current_song_index + 1}: {song_path}")
            try:
                current_process = subprocess.Popen(["mpv", "--volume=100", "--no-terminal", song_path])
                display_song(SONG_NAMES[current_song_index])
                start_spectrum()
            except FileNotFoundError:
                print(f"Error: MPV not found or song file missing: {song_path}")
            except Exception as e:
                print(f"Playback error: {e}")
            time.sleep(0.2)
        last_button_state = button_state
        time.sleep(0.05)
except KeyboardInterrupt:
    print("Manual exit via Ctrl+C...")
    if current_process is not None:
        current_process.kill()
        stop_spectrum()
    display_goodbye()
    time.sleep(2)
except Exception as e:
    print(f"Unexpected error: {e}")
finally:
    cleanup_leds()
    GPIO.cleanup()
    if current_process is not None:
        current_process.kill()
    subprocess.run(["pkill", "-9", "mpv"], check=False)
    clear_display()
