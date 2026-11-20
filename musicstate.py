# musicstate.py - shares live player state with portal.py
#
# play_song.py writes:  /dev/shm/musicbox/state.json  (now playing, LEDs, ...)
#                       /dev/shm/musicbox/oled.png    (mirror of the OLED screen)
# portal.py writes:     /dev/shm/musicbox/cmd         ("next" | "stop" | "play N")
# /dev/shm is RAM, so this never wears the SD card.
import json
import os
import threading
import time

DIR = "/dev/shm/musicbox" if os.path.isdir("/dev/shm") else "/tmp/musicbox"
STATE = os.path.join(DIR, "state.json")
OLED = os.path.join(DIR, "oled.png")
CMD = os.path.join(DIR, "cmd")

os.makedirs(DIR, exist_ok=True)
_lock = threading.Lock()
_state = {"playing": False, "index": None, "name": None, "started": None,
          "leds": [0] * 8, "oled_v": 0, "pid": os.getpid(), "updated": time.time()}


def _write():
    _state["updated"] = time.time()
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(_state, f)
    os.replace(tmp, STATE)


def set(**kw):
    with _lock:
        _state.update(kw)
        _write()


def read():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return None


def take_cmd():
    """Return and clear a pending command from the portal, or None."""
    try:
        with open(CMD) as f:
            cmd = f.read().strip()
        os.remove(CMD)
        return cmd or None
    except FileNotFoundError:
        return None


def send_cmd(cmd):
    tmp = CMD + ".tmp"
    with open(tmp, "w") as f:
        f.write(cmd)
    os.replace(tmp, CMD)


def hook_oled(device):
    """Wrap a luma device so every frame is also saved as oled.png."""
    orig = device.display

    def display(image):
        orig(image)
        try:
            tmp = OLED + ".tmp.png"
            image.convert("1").save(tmp)
            os.replace(tmp, OLED)
            with _lock:
                _state["oled_v"] += 1
                _write()
        except Exception:
            pass
    device.display = display


class _GPIOProxy:
    """Stands in for RPi.GPIO inside led_spectrum to record LED on/off."""
    def __init__(self, gpio, pins):
        self._g, self._pins = gpio, list(pins)

    def __getattr__(self, name):
        return getattr(self._g, name)

    def output(self, pin, value):
        self._g.output(pin, value)
        if pin in self._pins:
            with _lock:
                _state["leds"][self._pins.index(pin)] = 1 if value else 0
                _write()


def hook_leds(led_module):
    led_module.GPIO = _GPIOProxy(led_module.GPIO, led_module.LED_PINS)
    _state["leds"] = [0] * len(led_module.LED_PINS)
