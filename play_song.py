import RPi.GPIO as GPIO
import subprocess
import time

GPIO.setmode(GPIO.BCM)
BUTTON_PIN = 18
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

SONGS = [
    "/home/tiago/music-button-pi/song.mp3",
    "/home/tiago/music-button-pi/song2.mp3",
    "/home/tiago/music-button-pi/song3.mp3",
    "/home/tiago/music-button-pi/song4.mp3",
    "/home/tiago/music-button-pi/song5.mp3"
]
current_song_index = 0
current_process = None
last_button_state = GPIO.LOW

print("Press the button to play or skip to the next song (Ctrl+C to exit)...")
try:
    while True:
        button_state = GPIO.input(BUTTON_PIN)
        if button_state == GPIO.HIGH and last_button_state == GPIO.LOW:
            # Kill the current song if playing
            if current_process is not None:
                current_process.terminate()
                current_process.wait()  # Ensure it’s dead
            # Move to next song
            song_path = SONGS[current_song_index]
            print(f"Playing song {current_song_index + 1}: {song_path}")
            current_process = subprocess.Popen(["mpv", "--volume=150", song_path])
            current_song_index = (current_song_index + 1) % len(SONGS)
            time.sleep(0.5)  # Debounce
        last_button_state = button_state
        time.sleep(0.1)
except KeyboardInterrupt:
    print("Exiting...")
    if current_process is not None:
        current_process.terminate()
finally:
    GPIO.cleanup()
    subprocess.run(["pkill", "-9", "mpv"])  # Final cleanup
