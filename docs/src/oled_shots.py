"""Render the real V1 OLED screens (animations.py) to PNGs using a luma dummy device.
Usage: python3 oled_shots.py <music-button-pi dir> <out dir>"""
import os
import sys
import random

repo, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
sys.path.insert(0, repo)

# Swap the real I2C OLED for an in-memory one before animations.py is imported.
import luma.core.interface.serial as ser
import luma.oled.device as dev
from luma.core.device import dummy

ser.i2c = lambda *a, **k: None
dev.ssd1306 = lambda serial=None, height=64, **k: dummy(width=128, height=height, mode="1")

import time
time.sleep = lambda *_: None          # animations sleep between frames
import animations                     # noqa: E402
from PIL import Image, ImageDraw, ImageFont   # noqa: E402

D = animations.device
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)


def framed(img, caption, scale=4):
    """Upscale a 128x64 1-bit frame and put it in an OLED module bezel."""
    px = img.convert("L").resize((128 * scale, 64 * scale), Image.NEAREST)
    on = Image.new("RGB", px.size, (210, 240, 255))           # SSD1306 white/ice-blue pixels
    off = Image.new("RGB", px.size, (6, 10, 18))
    screen = Image.composite(on, off, px)
    W, H = screen.width + 80, screen.height + 120
    card = Image.new("RGB", (W, H), (247, 245, 239))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((10, 10, W - 10, H - 50), 18, fill=(28, 70, 130), outline=(14, 40, 80), width=3)
    for i, lab in enumerate(("GND", "VCC", "SCL", "SDA")):
        x = W // 2 - 66 + i * 44
        d.rectangle((x - 8, 18, x + 8, 34), fill=(212, 175, 55), outline=(0, 0, 0))
        d.text((x, 40), lab, fill=(220, 230, 255), anchor="mt", font=ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11))
    card.paste(screen, (40, 60))
    d.text((W // 2, H - 26), caption, fill=(40, 40, 40), anchor="mm", font=FONT)
    return card


shots = []

# 1. Fish splash: capture a mid-animation frame
random.seed(7)
frames = []
orig_display = D.display
D.display = lambda im: (frames.append(im.copy()), orig_display(im))
animations.fish_splash_screen(duration=3.2)
D.display = orig_display
shots.append(("oled-1-splash.png", frames[18], "Boot: fish splash (animated)"))

animations.display_initial_message()
shots.append(("oled-2-ready.png", D.image.copy(), "Ready: waiting for the button"))

animations.display_song("Soy un Pez!")
shots.append(("oled-3-now-playing.png", D.image.copy(), "Button pressed: song name"))

animations.display_song("Caminito de la Escuela")
shots.append(("oled-4-long-name.png", D.image.copy(), "Long names wrap to 2 lines"))

animations.display_goodbye()
shots.append(("oled-5-goodbye.png", D.image.copy(), "Shutdown"))

for name, im, cap in shots:
    framed(im, cap).save(os.path.join(out, name))
    im.save(os.path.join(out, "raw-" + name))     # plain 128x64 frame (for the portal mirror)
print("\n".join(s[0] for s in shots))
