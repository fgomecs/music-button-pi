import sys
from svglib import SVG, pi_header

s = SVG(1500, 1180)
s.title("Tiago's Music Button V1 · wiring",
        "Raspberry Pi 3 · big push button (GPIO18) · SSD1306 128×64 I2C OLED (0x3C) · 8-LED spectrum · 3.5 mm audio")

HX, HY = 600, 150
used = {1: 1, 3: 1, 5: 1, 6: 1, 12: 1, 29: 1, 31: 1, 33: 1, 35: 1, 37: 1, 39: 1, 34: 1, 36: 1, 38: 1, 40: 1}
P = pi_header(s, HX, HY, {k: ("", "") for k in used}, pitch=34)
L, R = HX, HX + 300


def y(n):
    return P[n][1]


# ---------------- OLED ----------------
s.rect(130, HY, 250, 170, fill="#1a1a1a", stroke="#000", sw=2, rx=6)
s.rect(150, HY + 18, 170, 134, fill="#0b2a4a", stroke="#335", rx=3)
s.text(235, HY + 80, "SSD1306", 14, "#7fd1ff", "middle", "bold")
s.text(235, HY + 100, "128×64 · I2C 0x3C", 11, "#7fd1ff", "middle")
s.text(255, HY - 10, "OLED display", 14, "#222", "middle", "bold")
for lab, n in (("GND", None), ("VCC", 1), ("SDA", 3), ("SCL", 5)):
    yy = y(n) if n else y(1) - 30
    s.pin(380, yy)
    s.text(366, yy + 4, lab, 11, "#fff", "end")
s.wire([(380, y(1) - 30), (450, y(1) - 30), (450, HY - 22), (940, HY - 22), (940, y(6)), (R, y(6))], "black", 4, "GND → pin 6", (700, HY - 22))
s.wire([(380, y(1)), (L, y(1))], "red", 4, "3.3V → pin 1", (480, y(1)))
s.wire([(380, y(3)), (L, y(3))], "blue", 4, "SDA → pin 3", (480, y(3)))
s.wire([(380, y(5)), (L, y(5))], "yellow", 4, "SCL → pin 5", (480, y(5)))

# ---------------- button + pull-down ----------------
BX, BY = 1180, y(12) - 40
s.rect(BX, BY, 110, 80, fill="#333", stroke="#000", sw=2, rx=8)
s.circle(BX + 55, BY + 40, 28, fill="#e63946", stroke="#7a1018")
s.text(BX + 55, BY - 10, "Big push button", 14, "#222", "middle", "bold")
s.pin(BX, BY + 15)
s.pin(BX, y(12))
s.wire([(BX, BY + 15), (1100, BY + 15), (1100, HY - 46), (560, HY - 46), (560, y(1))], "red", 4,
       "button leg A → 3.3V (pin 1)", (820, HY - 46))
s.circle(560, y(1), 6, fill="#d62828", stroke="#000", sw=1)
s.wire([(BX, y(12)), (R, y(12))], "green", 4, "leg B → GPIO18 (pin 12)", (1080, y(12)))
# 10k pull-down from GPIO18 node to GND (pin 6)
RY = (y(6) + y(12)) // 2 - 20
s.wire([(985, y(12)), (985, RY + 40)], "green", 3)
s.rect(975, RY, 20, 40, fill="#e8d4a8", stroke="#7a5a1e", sw=1.5, rx=4)
for i, c in enumerate(("#7a4a1e", "#111", "#f08a00")):
    s.rect(975, RY + 6 + i * 9, 20, 4, fill=c, stroke=c, sw=0, rx=0)
s.wire([(985, RY), (985, y(6)), (940, y(6))], "black", 3)
s.circle(940, y(6), 6, fill="#222", stroke="#000", sw=1)
s.text(1003, RY + 18, "10kΩ pull-down", 12, "#333")
s.text(1003, RY + 33, "GPIO18 → GND", 11, "#666")

# ---------------- LEDs ----------------
COL = {"G": "#2a9d3a", "Y": "#f2c200", "R": "#d62828"}


def led_row(pin, label, col, side):
    yy = y(pin)
    c = COL[col]
    if side == "left":
        led_x, res_x, rail_x = 430, 300, 210
        s.wire([(L, yy), (452, yy)], "white" if col == "Y" else ("green" if col == "G" else "red"), 3)
        s.circle(led_x, yy, 10, fill=c, stroke="#333")
        s.wire([(408, yy), (350, yy)], "gray", 3)
        s.rect(res_x, yy - 7, 50, 14, fill="#e8d4a8", stroke="#7a5a1e", sw=1.5, rx=5)
        s.wire([(res_x, yy), (rail_x, yy)], "black", 3)
        s.text(led_x, yy - 14, label, 10, "#333", "middle")
    else:
        led_x, res_x, rail_x = 1070, 1150, 1290
        s.wire([(R, yy), (1048, yy)], "white" if col == "Y" else "red", 3)
        s.circle(led_x, yy, 10, fill=c, stroke="#333")
        s.wire([(1092, yy), (res_x, yy)], "gray", 3)
        s.rect(res_x, yy - 7, 50, 14, fill="#e8d4a8", stroke="#7a5a1e", sw=1.5, rx=5)
        s.wire([(res_x + 50, yy), (rail_x, yy)], "black", 3)
        s.text(led_x, yy - 14, label, 10, "#333", "middle")


for pin, lab, col in ((29, "LED1 GPIO5", "G"), (31, "LED2 GPIO6", "G"), (33, "LED3 GPIO13", "G"),
                      (35, "LED4 GPIO19", "G"), (37, "LED5 GPIO26", "Y")):
    led_row(pin, lab, col, "left")
for pin, lab, col in ((36, "LED6 GPIO16", "Y"), (38, "LED7 GPIO20", "R"), (40, "LED8 GPIO21", "R")):
    led_row(pin, lab, col, "right")

s.wire([(210, y(29)), (210, y(39) + 60), (570, y(39) + 60), (570, y(39)), (L, y(39))], "black", 4, "LED GND rail → pin 39", (390, y(39) + 60))
s.wire([(1290, y(40)), (1290, y(34) - 40), (950, y(34) - 40), (950, y(34)), (R, y(34))], "black", 4, "LED GND rail → pin 34", (1120, y(34) - 40))
s.text(275, y(29) - 30, "each: GPIO → LED → resistor → GND", 12, "#555", "middle", italic=True)

# ---------------- audio + power ----------------
s.rect(1020, 960, 220, 70, fill="#eee", stroke="#555", sw=1.5, rx=8)
s.text(1130, 990, "3.5 mm jack (on the Pi)", 13, "#222", "middle", "bold")
s.text(1130, 1010, "→ small speaker / headphones", 12, "#444", "middle")
s.rect(1020, 1050, 220, 50, fill="#eee", stroke="#555", sw=1.5, rx=8)
s.text(1130, 1080, "Power: micro-USB 5 V / 2.5 A", 13, "#222", "middle")

s.legend_box(60, 960, 900, [
    "• Pins from code: BUTTON_PIN = 18 (BCM, config.py), LED_PINS = [5, 6, 13, 19, 26, 16, 20, 21] (led_spectrum.py).",
    "• OLED: luma.oled ssd1306 on I2C bus 1, address 0x3C. Enable I2C with raspi-config.",
    "• Button reads HIGH when pressed (pull-down keeps it LOW when released).",
    "• LED resistors: 220–330 Ω each. LED ground can go to ANY GND pin (6, 9, 14, 20, 25, 30, 34, 39).",
    "• Pin numbers in the squares are PHYSICAL pins; labels are BCM GPIO names.",
], "Notes")

s.save(sys.argv[1])
