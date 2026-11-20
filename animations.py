# animations.py
import random
import math
import time
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import ImageFont

# Initialize OLED (128x64, SSD1306)
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial, height=64)

# Load fonts
normal_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)

def fish_splash_screen(duration=5):
    display_width = 128
    display_height = 64
    fish_y = display_height - 20  # Fish near bottom
    frame_delay = 0.1
    frames = int(duration / frame_delay)
    bubbles = []

    for frame in range(frames):
        fish_x = (frame * 3) % (display_width + 40) - 20
        fish_y_offset = int(math.sin(frame * 0.2) * 3)

        with canvas(device) as draw:
            # "SANTI DIVER" at top
            text = "SANTI DIVER"
            bbox = normal_font.getbbox(text)
            x_pos = (128 - bbox[2]) // 2
            draw.text((x_pos, 5), text, font=normal_font, fill="white")

            # Fish animation
            fish_shape = [
                (fish_x, fish_y + fish_y_offset + 5),
                (fish_x + 5, fish_y + fish_y_offset),
                (fish_x + 15, fish_y + fish_y_offset),
                (fish_x + 20, fish_y + fish_y_offset + 5),
                (fish_x + 15, fish_y + fish_y_offset + 10),
                (fish_x + 5, fish_y + fish_y_offset + 10),
            ]
            for i in range(len(fish_shape)):
                draw.line((fish_shape[i], fish_shape[(i + 1) % len(fish_shape)]), fill="white")

            eye_x = fish_x + 12
            eye_y = fish_y + fish_y_offset + 3
            draw.ellipse((eye_x, eye_y, eye_x + 2, eye_y + 2), fill="white")

            tail_x = fish_x - 5
            draw.line((tail_x, fish_y + fish_y_offset + 5, tail_x - 5, fish_y + fish_y_offset + 2), fill="white")
            draw.line((tail_x, fish_y + fish_y_offset + 5, tail_x - 5, fish_y + fish_y_offset + 8), fill="white")

            for bubble in bubbles[:]:
                bx, by = bubble
                draw.ellipse((bx, by, bx + 3, by + 3), outline="white")
                bubble[1] -= 1
                if bubble[1] < 0:
                    bubbles.remove(bubble)

            if random.random() < 0.2:
                bubbles.append([fish_x + 16, fish_y + fish_y_offset])

        time.sleep(frame_delay)

def display_initial_message():
    with canvas(device) as draw:
        text = "Press button to"
        bbox = normal_font.getbbox(text)
        x_pos = (128 - bbox[2]) // 2
        draw.text((x_pos, 10), text, font=normal_font, fill="white")
        text = "start playing"
        bbox = normal_font.getbbox(text)
        x_pos = (128 - bbox[2]) // 2
        draw.text((x_pos, 30), text, font=normal_font, fill="white")

def display_song(song_name):
    with canvas(device) as draw:
        text = "Now Playing"
        bbox = normal_font.getbbox(text)
        x_pos = (128 - bbox[2]) // 2
        draw.text((x_pos, 10), text, font=normal_font, fill="white")

        bbox = small_font.getbbox(song_name)
        text_width = bbox[2]
        if text_width <= 128:
            x_pos = (128 - text_width) // 2
            draw.text((x_pos, 30), song_name, font=small_font, fill="white")
        else:
            words = song_name.split()
            line1 = ""
            line2 = ""
            for word in words:
                test_line = f"{line1} {word}".strip()
                if small_font.getbbox(test_line)[2] <= 128 and not line2:
                    line1 = test_line
                else:
                    line2 = f"{line2} {word}".strip() if line2 else word
            bbox1 = small_font.getbbox(line1)
            bbox2 = small_font.getbbox(line2)
            x_pos1 = (128 - bbox1[2]) // 2
            x_pos2 = (128 - bbox2[2]) // 2
            draw.text((x_pos1, 25), line1, font=small_font, fill="white")
            draw.text((x_pos2, 40), line2, font=small_font, fill="white")

def display_goodbye():
    with canvas(device) as draw:
        draw.text((40, 20), "Goodbye!", font=normal_font, fill="white")

def clear_display():
    with canvas(device) as draw:
        pass  # Clear the display
