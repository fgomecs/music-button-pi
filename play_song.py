# play_song.py
import signal
import subprocess
import sys
import time

import RPi.GPIO as GPIO

import animations
import led_spectrum
from animations import fish_splash_screen, display_initial_message, display_song, display_goodbye, clear_display
from config import BUTTON_PIN, SONGS, SONG_NAMES
from led_spectrum import setup_leds, start_spectrum, stop_spectrum, cleanup_leds

# Live state for the web portal (optional: player works without it)
try:
    import musicstate
    musicstate.hook_oled(animations.device)
    musicstate.hook_leds(led_spectrum)
    musicstate.set(playing=False, index=None, name=None, count=len(SONGS))
except Exception as e:
    print(f"Portal state disabled: {e}")
    musicstate = None


def report(**kw):
    if musicstate:
        try:
            musicstate.set(**kw)
        except Exception:
            pass


# Stop cleanly (mpv + LEDs + screen) when killed by a restart
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

# Initialize GPIO
GPIO.setmode(GPIO.BCM)
try:
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
except Exception as e:
    print(f"GPIO setup failed: {e}")
    sys.exit(1)

# Initialize LEDs
try:
    setup_leds()
except Exception as e:
    print(f"LED setup failed: {e}")
    sys.exit(1)

# Main Logic
current_song_index = 0
current_process = None
last_button_state = GPIO.LOW
first_press = True


def stop_current():
    global current_process
    if current_process is not None:
        current_process.kill()
        current_process.wait()
        current_process = None
        stop_spectrum()
        print("Previous song process terminated.")
    report(playing=False)


def play(index):
    global current_process, current_song_index
    stop_current()
    current_song_index = index % len(SONGS)
    song_path = SONGS[current_song_index]
    print(f"Starting song {current_song_index + 1}: {song_path}")
    try:
        current_process = subprocess.Popen(["mpv", "--volume=100", "--no-terminal", song_path])
        report(playing=True, index=current_song_index, name=SONG_NAMES[current_song_index],
               started=time.time())
        display_song(SONG_NAMES[current_song_index])
        start_spectrum()
    except FileNotFoundError:
        print(f"Error: MPV not found or song file missing: {song_path}")
    except Exception as e:
        print(f"Playback error: {e}")


def next_song():
    global first_press
    if first_press:
        first_press = False
        play(current_song_index)
    else:
        play(current_song_index + 1)


# Initial splash screen
try:
    fish_splash_screen()
    display_initial_message()
except Exception as e:
    print(f"Display initialization failed: {e}")
    cleanup_leds()
    GPIO.cleanup()
    sys.exit(1)

print("Press the button to start or skip songs (Ctrl+C to exit)...")
try:
    while True:
        button_state = GPIO.input(BUTTON_PIN)
        if button_state == GPIO.HIGH and last_button_state == GPIO.LOW:
            print(f"Button pressed, current song index: {current_song_index}")
            next_song()
            time.sleep(0.2)
        last_button_state = button_state

        # Commands from the web portal
        cmd = musicstate.take_cmd() if musicstate else None
        if cmd == "next":
            next_song()
        elif cmd == "stop":
            stop_current()
            display_initial_message()
        elif cmd and cmd.startswith("play "):
            try:
                first_press = False
                play(int(cmd.split()[1]))
            except ValueError:
                pass

        # Song finished by itself: stop LEDs, show it on the portal
        if current_process is not None and current_process.poll() is not None:
            current_process = None
            stop_spectrum()
            report(playing=False)

        time.sleep(0.05)
except KeyboardInterrupt:
    print("Manual exit via Ctrl+C...")
    stop_current()
    display_goodbye()
    time.sleep(2)
except Exception as e:
    print(f"Unexpected error: {e}")
finally:
    report(playing=False)
    cleanup_leds()
    GPIO.cleanup()
    if current_process is not None:
        current_process.kill()
    subprocess.run(["pkill", "-9", "mpv"], check=False)
    clear_display()
