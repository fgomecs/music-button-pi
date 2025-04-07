import RPi.GPIO as GPIO
import subprocess
import time

GPIO.setmode(GPIO.BCM)
BUTTON_PIN = 18
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
SONG_PATH = "/home/tiago/music-button-pi/song.mp3"

print("Press the button to play the song (Ctrl+C to exit)...")
try:
    while True:
        if GPIO.input(BUTTON_PIN) == GPIO.HIGH:
            print("Button pressed! Playing song...")
            subprocess.run(["mpv", "--no-video", SONG_PATH])
            print("Song finished.")
            time.sleep(0.2)
        time.sleep(0.1)
except KeyboardInterrupt:
    print("Exiting...")
finally:
    GPIO.cleanup()
