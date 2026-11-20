from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
import time

# Initialize I2C interface and OLED device
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial)  # Auto-detects resolution, but can specify height=32 or 64 if needed

# Draw text
with canvas(device) as draw:
    draw.text((0, 0), "Hello, World!", fill="white")
    draw.text((0, 16), "Pi 3 OLED Test", fill="white")

# Keep the display on for 5 seconds
time.sleep(5)

# Clear the display
with canvas(device) as draw:
    pass  # Empty canvas clears the display
