import time
import random
import math  # Added missing import
from luma.core.render import canvas
from luma.oled.device import ssd1306
from luma.core.interface.serial import i2c
from PIL import ImageFont

# Initialize OLED (128x64, SSD1306)
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial, height=64)

# Load fonts
font = ImageFont.load_default()
big_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)

# Scrolling Text Animation
def scroll_text(text, font, display_width=128, display_height=64, scroll_speed=0.02):  # Faster scroll speed
    # Calculate text dimensions
    bbox = font.getbbox(text)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Center vertically
    y_pos = (display_height - text_height) // 2
    
    if text_width <= display_width:
        # Static centered text if it fits
        with canvas(device) as draw:
            x_pos = (display_width - text_width) // 2
            draw.text((x_pos, y_pos), text, font=font, fill="white")
        time.sleep(2)
        return

    # Scroll text
    x = display_width
    total_distance = text_width + display_width
    
    while x > -text_width:
        with canvas(device) as draw:
            draw.text((x, y_pos), text, font=font, fill="white")
        x -= 2
        time.sleep(scroll_speed)  # Reduced from 0.05 to 0.02 for faster scrolling
    
    # Brief pause at end
    time.sleep(1)

# Fish Animation
def fish_animation():
    display_width = 128
    display_height = 64
    fish_y = display_height - 20  # Near bottom of screen
    
    # Animation parameters
    animation_duration = 10
    frame_delay = 0.1
    frames = int(animation_duration / frame_delay)
    bubbles = []
    
    for frame in range(frames):
        # Calculate fish position with slight vertical movement
        fish_x = (frame * 3) % (display_width + 40) - 20  # Smooth horizontal movement
        fish_y_offset = int(math.sin(frame * 0.2) * 3)  # Gentle bobbing
        
        with canvas(device) as draw:
            # Define fish shape (updated with each frame)
            fish_shape = [
                (fish_x, fish_y + fish_y_offset + 5),        # Tail start
                (fish_x + 5, fish_y + fish_y_offset),        # Top
                (fish_x + 15, fish_y + fish_y_offset),       # Top right
                (fish_x + 20, fish_y + fish_y_offset + 5),   # Right end
                (fish_x + 15, fish_y + fish_y_offset + 10),  # Bottom right
                (fish_x + 5, fish_y + fish_y_offset + 10),   # Bottom left
            ]
            
            # Draw fish body
            for i in range(len(fish_shape)):
                draw.line((fish_shape[i], fish_shape[(i + 1) % len(fish_shape)]), fill="white")
            
            # Draw eye
            eye_x = fish_x + 12
            eye_y = fish_y + fish_y_offset + 3
            draw.ellipse((eye_x, eye_y, eye_x + 2, eye_y + 2), fill="white")
            
            # Draw tail fin
            tail_x = fish_x - 5
            draw.line((tail_x, fish_y + fish_y_offset + 5, 
                      tail_x - 5, fish_y + fish_y_offset + 2), fill="white")
            draw.line((tail_x, fish_y + fish_y_offset + 5, 
                      tail_x - 5, fish_y + fish_y_offset + 8), fill="white")
            
            # Handle bubbles
            for bubble in bubbles[:]:
                bx, by = bubble
                draw.ellipse((bx, by, bx + 3, by + 3), outline="white")
                bubble[1] -= 1  # Move bubble up
                if bubble[1] < 0:
                    bubbles.remove(bubble)
            
            # Add new bubble randomly
            if random.random() < 0.2:
                bubbles.append([fish_x + 16, fish_y + fish_y_offset])
        
        time.sleep(frame_delay)

# Main execution
if __name__ == "__main__":
    scroll_text("Tiago My Son", big_font)
    fish_animation()
