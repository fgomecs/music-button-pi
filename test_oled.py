import Adafruit_SSD1306
from PIL import Image, ImageDraw, ImageFont
import time

# Initialize OLED (try 128x32 first)
RST = None
disp = Adafruit_SSD1306.SSD1306_128_32(rst=RST, i2c_address=0x3C)

# Initialize display
disp.begin()
disp.clear()
disp.display()

# Create image for drawing
width = disp.width
height = disp.height
image = Image.new("1", (width, height))
draw = ImageDraw.Draw(image)
font = ImageFont.load_default()

# Draw text
draw.text((0, 0), "Hello, World!", font=font, fill=255)
draw.text((0, 16), "Pi 3 OLED Test", font=font, fill=255)

# Display image
disp.image(image)
disp.display()
time.sleep(5)

# Clear display
disp.clear()
disp.display()
