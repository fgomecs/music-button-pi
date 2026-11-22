"""Tiny SVG helpers for Fritzing-style wiring diagrams."""

FONT = "DejaVu Sans, Arial, sans-serif"

WIRE = {
    "red": "#d62828", "black": "#222222", "yellow": "#f2c200", "orange": "#f08a00",
    "brown": "#7a4a1e", "green": "#2a9d3a", "blue": "#1f6fd1", "purple": "#8a3ffc",
    "white": "#bbbbbb", "gray": "#888888", "cyan": "#12a4c4",
}


class SVG:
    def __init__(self, w, h, bg="#f7f5ef"):
        self.w, self.h = w, h
        self.parts = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="{bg}"/>']
        self.wires = []   # drawn under parts? no: drawn last so they're visible

    def add(self, s):
        self.parts.append(s)

    def rect(self, x, y, w, h, fill="#fff", stroke="#333", sw=2, rx=6, extra=""):
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')

    def circle(self, cx, cy, r, fill="#fff", stroke="#333", sw=2):
        self.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def text(self, x, y, s, size=14, color="#222", anchor="start", weight="normal", italic=False):
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        st = ' font-style="italic"' if italic else ""
        self.add(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" fill="{color}" '
                 f'text-anchor="{anchor}" font-weight="{weight}"{st}>{s}</text>')

    def lines(self, x, y, rows, size=14, color="#222", gap=None, anchor="start", weight="normal"):
        gap = gap or int(size * 1.35)
        for i, r in enumerate(rows):
            self.text(x, y + i * gap, r, size, color, anchor, weight)

    def wire(self, pts, color="red", w=5, label=None, label_at=None, label_color=None, dots=True):
        c = WIRE.get(color, color)
        d = " ".join(f"{x},{y}" for x, y in pts)
        # dark outline + colour core, like Fritzing wires
        self.wires.append(f'<polyline points="{d}" fill="none" stroke="#00000055" '
                          f'stroke-width="{w + 2.5}" stroke-linejoin="round" stroke-linecap="round"/>')
        self.wires.append(f'<polyline points="{d}" fill="none" stroke="{c}" '
                          f'stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"/>')
        for (x, y) in ((pts[0], pts[-1]) if dots else ()):
            self.wires.append(f'<circle cx="{x}" cy="{y}" r="{w * 0.8}" fill="{c}" stroke="#000" stroke-width="1"/>')
        if label:
            lx, ly = label_at or pts[len(pts) // 2]
            tw = 7.2 * len(label) + 10
            self.wires.append(f'<rect x="{lx - tw / 2}" y="{ly - 11}" width="{tw}" height="20" rx="4" '
                              f'fill="#ffffffee" stroke="{c}" stroke-width="1.5"/>')
            self.wires.append(f'<text x="{lx}" y="{ly + 4}" font-family="{FONT}" font-size="12" '
                              f'fill="{label_color or "#222"}" text-anchor="middle">{label}</text>')

    def pin(self, x, y, label=None, side="right", fill="#d4af37", size=12):
        self.rect(x - 7, y - 7, 14, 14, fill=fill, stroke="#333", sw=1.5, rx=2)
        if label:
            dx = 14 if side == "right" else -14
            self.text(x + dx, y + 4, label, size, "#fff" if fill == "#d4af37" and False else "#222",
                      "start" if side == "right" else "end")

    def title(self, s, sub=None):
        self.text(30, 44, s, 26, "#111", weight="bold")
        if sub:
            self.text(30, 70, sub, 15, "#555")

    def legend_box(self, x, y, w, rows, head="Notes"):
        h = 34 + 20 * len(rows)
        self.rect(x, y, w, h, fill="#fffbe6", stroke="#c9b458", sw=1.5)
        self.text(x + 12, y + 22, head, 15, "#5a4a00", weight="bold")
        for i, r in enumerate(rows):
            self.text(x + 12, y + 46 + i * 20, r, 13, "#333")

    def save(self, path):
        body = "\n".join(self.parts + self.wires)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
               f'viewBox="0 0 {self.w} {self.h}">\n{body}\n</svg>\n')
        with open(path, "w") as f:
            f.write(svg)


def pi_header(s, x, y, used, title="Raspberry Pi 3 · 40-pin GPIO header", pitch=26):
    """Draw a 2x20 header as a pinout block at (x,y). Odd pins left column, even right.
    used: {pin_number: (label, color)} highlights pins. Returns dict pin -> (cx, cy, side)."""
    names = {
        1: "3.3V", 2: "5V", 3: "GPIO2 SDA", 4: "5V", 5: "GPIO3 SCL", 6: "GND", 7: "GPIO4", 8: "GPIO14 TX",
        9: "GND", 10: "GPIO15 RX", 11: "GPIO17", 12: "GPIO18", 13: "GPIO27", 14: "GND", 15: "GPIO22",
        16: "GPIO23", 17: "3.3V", 18: "GPIO24", 19: "GPIO10", 20: "GND", 21: "GPIO9", 22: "GPIO25",
        23: "GPIO11", 24: "GPIO8", 25: "GND", 26: "GPIO7", 27: "ID_SD", 28: "ID_SC", 29: "GPIO5",
        30: "GND", 31: "GPIO6", 32: "GPIO12", 33: "GPIO13", 34: "GND", 35: "GPIO19", 36: "GPIO16",
        37: "GPIO26", 38: "GPIO20", 39: "GND", 40: "GPIO21",
    }
    bw, bh = 300, 20 * pitch + 60
    s.rect(x, y, bw, bh, fill="#1e7a3c", stroke="#0d4d22", sw=3, rx=10)
    s.text(x + bw / 2, y + 26, title, 13, "#fff", "middle", "bold")
    pos = {}
    for row in range(20):
        for col in range(2):
            n = row * 2 + col + 1
            cx = x + bw / 2 - 16 + col * 32
            cy = y + 50 + row * pitch
            label, color = used.get(n, (None, None))
            fill = "#d4af37" if n in used else "#9a9a9a"
            if names[n] == "GND":
                fill = "#444" if n not in used else "#111"
            s.rect(cx - 9, cy - 9, 18, 18, fill=fill, stroke="#000", sw=1, rx=2)
            s.text(cx, cy + 4, str(n), 9, "#fff" if fill in ("#444", "#111") else "#111", "middle")
            nm = names[n]
            if col == 0:
                s.text(cx - 16, cy + 4, nm, 11, "#fff" if n in used else "#bfe3c9", "end",
                       "bold" if n in used else "normal")
                pos[n] = (x, cy, "left")
            else:
                s.text(cx + 16, cy + 4, nm, 11, "#fff" if n in used else "#bfe3c9", "start",
                       "bold" if n in used else "normal")
                pos[n] = (x + bw, cy, "right")
    return pos
