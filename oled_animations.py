import time
import random
import math
from luma.core.render import canvas
from luma.oled.device import ssd1306
from luma.core.interface.serial import i2c
from PIL import ImageFont

# Initialize OLED (128x64, SSD1306)
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial, height=64)  # Specify 128x64 resolution

# Load default font for text width calculation
font = ImageFont.load_default()

# Sunrise Animation
def sunrise_animation():
    sun_y = 64  # Start at the bottom
    sun_radius = 10
    animation_duration = 4
    frame_delay = 0.1
    frames = int(animation_duration / frame_delay)

    for frame in range(frames):
        with canvas(device) as draw:
            # Draw the sun
            draw.ellipse((64 - sun_radius, sun_y - sun_radius, 64 + sun_radius, sun_y + sun_radius), outline="white", fill="yellow")
            # Draw some simple rays (lines coming out of the sun)
            for angle in range(0, 360, 45):
                dx = int(sun_radius * 1.5 * math.cos(math.radians(angle)))
                dy = int(sun_radius * 1.5 * math.sin(math.radians(angle)))
                draw.line((64, sun_y, 64 + dx, sun_y + dy), fill="yellow")
        
        # Move sun upwards
        sun_y -= (64 / frames)  # Move up a portion of the screen each frame
        time.sleep(frame_delay)

# Clouds Animation
def clouds_animation():
    cloud_x = 0
    cloud_y = 10
    cloud_width = 30
    cloud_height = 15
    cloud_speed = 0.5
    animation_duration = 5
    frame_delay = 0.1
    frames = int(animation_duration / frame_delay)

    for frame in range(frames):
        with canvas(device) as draw:
            # Draw the cloud (simple ellipses)
            draw.ellipse((cloud_x, cloud_y, cloud_x + cloud_width, cloud_y + cloud_height), outline="white", fill="white")
        
        # Move cloud to the right
        cloud_x += cloud_speed
        if cloud_x > 128:  # If it goes off the screen, reset it to the left side
            cloud_x = -cloud_width
        
        time.sleep(frame_delay)

# Starfield Animation
def starfield_animation():
    # Animation parameters
    num_stars = 30
    stars = [[random.randint(0, 128), random.randint(0, 64), random.uniform(0.1, 2)] for _ in range(num_stars)]
    animation_duration = 4
    frame_delay = 0.1
    frames = int(animation_duration / frame_delay)

    for frame in range(frames):
        with canvas(device) as draw:
            # Draw all stars
            for star in stars:
                x, y, speed = star
                draw.point((x, y), fill="white")
                # Update star position
                x -= speed  # Move left
                if x < 0:  # If star goes off the screen, reset it to the right side
                    x = 128
                    y = random.randint(0, 64)
                star[0] = x
                star[1] = y
        
        time.sleep(frame_delay)

# Run the Animations
if __name__ == "__main__":
    print("Running sunrise animation...")
    sunrise_animation()
    # Uncomment the following lines to test other animations:
    clouds_animation()
    starfield_animation()
