### Raspberry Pi 3 Music Button Project Summary
- **Goal**: Play "https://www.youtube.com/watch?v=l82wUVuzegY" through the headphone jack when my son presses a button on a breadboard.
- **Hardware**: Raspberry Pi 3, breadboard, push button, 10kΩ resistor, jumper wires, headphones.
- **Date**: April 2025

#### 1. Installed Raspberry Pi OS
- Installed Raspberry Pi OS (Bookworm-based) on a 32GB SD card.
- Fresh install with `mpv 0.35.1` and basic audio tools pre-installed.
- Verified by booting and logging in as `tiago@tiagosmusicbox`.

#### 2. Updated and Upgraded the System
- Ran:
  ```
  sudo apt update
  sudo apt upgrade -y
  sudo apt full-upgrade -y
  sudo apt autoremove -y
  sudo apt autoclean
  ```
- Upgraded 189 packages to ensure stability and compatibility.

#### 3. Set Up Virtual Environment for yt-dlp
- Installed `python3-venv`:
  ```
  sudo apt install python3-venv -y
  ```
- Created and activated virtual environment:
  ```
  python3 -m venv ~/yt-dlp-venv
  source ~/yt-dlp-venv/bin/activate
  ```
- Purpose: Isolated `yt-dlp` installation to avoid system Python conflicts.

#### 4. Installed mpv and yt-dlp, Configured Audio
- **mpv**: Confirmed pre-installed `0.35.1` (`mpv --version`), reinstalled if needed:
  ```
  sudo apt install mpv -y
  ```
- **yt-dlp**:
  - Initial attempt: `sudo apt install yt-dlp -y` (got outdated `2023.03.04-1`).
  - Installed latest version in virtual environment:
    ```
    source ~/yt-dlp-venv/bin/activate
    pip install -U yt-dlp
    deactivate
    ```
  - Verified: `~/yt-dlp-venv/bin/yt-dlp --version`.
- Configured `mpv`:
  ```
  nano ~/.config/mpv/mpv.conf
  ```
  Added:
  ```
  script-opts=ytdl_hook-ytdl_path=/home/tiago/yt-dlp-venv/bin/yt-dlp
  ytdl-format=bestaudio
  ```
- Tested audio:
  ```
  mpv --no-video "https://www.youtube.com/watch?v=l82wUVuzegY"
  ```
- Fixed headphone output:
  ```
  pactl set-default-sink alsa_output.platform-bcm2835_audio.stereo-fallback
  pactl set-sink-volume alsa_output.platform-bcm2835_audio.stereo-fallback 100%
  pactl set-sink-mute alsa_output.platform-bcm2835_audio.stereo-fallback 0
  ```
- Result: Song played through headphone jack.

#### 5. Wired and Tested the Button
- **Wiring**:
  - Button: GPIO 18 (pin 12) to 3.3V (pin 1).
  - 10kΩ pull-down resistor: GPIO 18 to GND (pin 6).
- **Test Script** (`button_test.py`):
  ```python
  import RPi.GPIO as GPIO
  import time

  GPIO.setmode(GPIO.BCM)
  BUTTON_PIN = 18
  GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

  print("Press the button (Ctrl+C to exit)...")
  try:
      while True:
          if GPIO.input(BUTTON_PIN) == GPIO.HIGH:
              print("Button pressed!")
              time.sleep(0.2)
          time.sleep(0.1)
  except KeyboardInterrupt:
      print("Exiting...")
  finally:
      GPIO.cleanup()
  ```
- Installed GPIO library: `sudo apt install python3-rpi.gpio -y`.
- Ran: `python3 button_test.py`.
- Result: Button press detected successfully.

#### 6. Created and Automated the Song Playback Script (Streaming Version)
- **Script** (`play_song.py`):
  ```python
  import RPi.GPIO as GPIO
  import subprocess
  import time

  GPIO.setmode(GPIO.BCM)
  BUTTON_PIN = 18
  GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
  SONG_URL = "https://www.youtube.com/watch?v=l82wUVuzegY"

  print("Press the button to play the song (Ctrl+C to exit)...")
  try:
      while True:
          if GPIO.input(BUTTON_PIN) == GPIO.HIGH:
              print("Button pressed! Playing song...")
              subprocess.run(["mpv", "--no-video", SONG_URL])
              print("Song finished.")
              time.sleep(0.2)
          time.sleep(0.1)
  except KeyboardInterrupt:
      print("Exiting...")
  finally:
      GPIO.cleanup()
  ```
- **Autostart**:
  - Edited crontab: `crontab -e`.
  - Added: `@reboot /usr/bin/python3 /home/tiago/play_song.py`.
- Result: Button press streamed the song on boot.

#### 7. Downloaded the Song and Modified the Script
- **Downloaded the Song**:
  - Used `yt-dlp` to save the audio locally:
    ```
    source ~/yt-dlp-venv/bin/activate
    ~/yt-dlp-venv/bin/yt-dlp -x --audio-format mp3 -o "/home/tiago/song.mp3" "https://www.youtube.com/watch?v=l82wUVuzegY"
    deactivate
    ```
  - Result: Saved `song.mp3` in `/home/tiago/`.
- **Modified Script** (`play_song.py`):
  - Updated to play the local file instead of streaming:
    ```python
    import RPi.GPIO as GPIO
    import subprocess
    import time

    GPIO.setmode(GPIO.BCM)
    BUTTON_PIN = 18
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    SONG_PATH = "/home/tiago/song.mp3"

    print("Press the button to play the song (Ctrl+C to exit)...")
    try:
        while True:
            if GPIO.input(BUTTON_PIN) == GPIO.HIGH:
                print("Button pressed! Playing song...")
                subprocess.run(["mpv", SONG_PATH])
                print("Song finished.")
                time.sleep(0.2)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        GPIO.cleanup()
    ```
- **Updated Autostart**:
  - Ensured crontab still points to the modified script: `@reboot /usr/bin/python3 /home/tiago/play_song.py`.
- Result: Button press now plays the local `song.mp3` file, reducing latency and eliminating internet dependency.

#### Additional Tools Installed
- `ffmpeg`: `sudo apt install ffmpeg -y`.
- `pipewire-audio-client-libraries`: `sudo apt install pipewire-audio-client-libraries -y`.
- `alsa-utils`: `sudo apt install alsa-utils -y`.
- `mlocate`: `sudo apt install mlocate -y`.

#### Verification Commands Used
- `mpv --version`
- `source ~/yt-dlp-venv/bin/activate; yt-dlp --version; deactivate`
- `python3 -c "import RPi.GPIO; print(RPi.GPIO.VERSION)"`
- `ffmpeg -version`
- `pw-play --version`
- `aplay --version`

---

### Current Status
- The project now uses a locally stored `song.mp3` instead of streaming, triggered by the button press via GPIO 18.
- It autostarts on boot, plays through the headphone jack, and is fully functional for your son to use.
- This update reflects downloading the song and modifying `play_song.py` as you mentioned.

Does this match what you’ve done? If I got the timing or details of the download step wrong, let me know, and I’ll adjust it. Also, since you asked about removing the desktop overhead earlier, do you want to revisit that optimization now that the core project is working?
=======
# Raspberry Pi 3 Music Button Project

**Goal**: Play "https://www.youtube.com/watch?v=l82wUVuzegY" via headphone jack when my son presses a button on a breadboard.  
**Hardware**: Raspberry Pi 3, breadboard, push button, 10kΩ resistor, jumper wires, headphones.  
**Date**: April 2025  

---

# 1. Installed Raspberry Pi OS
- **Action**: Installed Raspberry Pi OS (Bookworm-based) on a 32GB SD card.
- **Details**: Fresh install, assumed pre-installed with `mpv 0.35.1` and basic audio tools from initial checks.
- **Verification**: Booted and logged in as `tiago@tiagosmusicbox`.

# 2. Updated and Upgraded the System
- **Commands**:

sudo apt update
sudo apt upgrade -y
sudo apt full-upgrade -y
sudo apt autoremove -y
sudo apt autoclean

- **Details**: Refreshed package lists (189 packages upgraded), updated all software to ensure compatibility and stability.
- **Purpose**: Fixed potential package issues (e.g., broken `youtube-dl` installs).

# 3. Created a Virtual Environment for yt-dlp
- **Commands**:

sudo apt install python3-venv -y
python3 -m venv ~/yt-dlp-venv
source ~/yt-dlp-venv/bin/activate

- **Details**: Created `~/yt-dlp-venv` to bypass PEP 668 restrictions on system Python.
- **Purpose**: Allowed installing the latest `yt-dlp` without breaking system packages.

# 4. Installed mpv and yt-dlp and Tested Audio
- **mpv Installation**:
- Command: `sudo apt install mpv -y`
- Version: Confirmed `0.35.1` (pre-installed, verified with `mpv --version`).
- Purpose: Plays YouTube audio streams.
- **yt-dlp Installation**:
- Initial Attempt: `sudo apt install yt-dlp -y` (installed `2023.03.04-1`, outdated).
- Final Install:

source ~/yt-dlp-venv/bin/activate
pip install -U yt-dlp
deactivate

- Version: Latest (e.g., `2025.x.x`), checked with `~/yt-dlp-venv/bin/yt-dlp --version`.
- Purpose: Downloads YouTube streams for `mpv`.
- **Testing**:
- Configured `mpv`:

nano ~/.config/mpv/mpv.conf

Added:

script-opts=ytdl_hook-ytdl_path=/home/tiago/yt-dlp-venv/bin/yt-dlp
ytdl-format=bestaudio

- Tested: `mpv --no-video "https://www.youtube.com/watch?v=l82wUVuzegY"`
- Audio Fix: Set headphone jack as default sink and boosted volume:

pactl set-default-sink alsa_output.platform-bcm2835_audio.stereo-fallback
pactl set-sink-volume alsa_output.platform-bcm2835_audio.stereo-fallback 100%
pactl set-sink-mute alsa_output.platform-bcm2835_audio.stereo-fallback 0

- Result: Song played through headphone jack.

# 5. Created Wiring for the Button and Tested
- **Wiring**:
- Button: Connected to GPIO 18 (pin 12) and 3.3V (pin 1).
- Pull-down Resistor: 10kΩ from GPIO 18 to GND (pin 6).
- Diagram:

Pi 3.3V (pin 1) ---- Button ---- GPIO 18 (pin 12)
|
10kΩ Resistor
|
GND (pin 6)

- **Test Script**:
- Installed GPIO library: `sudo apt install python3-rpi.gpio -y`
- Created `button_test.py`:
```python
import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
BUTTON_PIN = 18
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

print("Press the button (Ctrl+C to exit)...")
try:
    while True:
        if GPIO.input(BUTTON_PIN) == GPIO.HIGH:
            print("Button pressed!")
            time.sleep(0.2)
        time.sleep(0.1)
except KeyboardInterrupt:
    print("Exiting...")
finally:
    GPIO.cleanup()


>>>>>>> d383860 (Updated README with detailed project summary)
