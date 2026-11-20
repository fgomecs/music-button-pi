from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306

# Initialize OLED (128x32, SSD1306)
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial)

# Test display
with canvas(device) as draw:
    draw.text((0, 0), "Hello, World!", fill="white")
    draw.text((0, 16), "Pi 3 OLED Test", fill="white")

import time
time.sleep(5)
