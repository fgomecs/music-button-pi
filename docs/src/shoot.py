"""Screenshot a page with headless Chrome. Usage: shoot.py URL OUT.png [width] [height|full] [wait_ms]"""
import sys
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
w = int(sys.argv[3]) if len(sys.argv) > 3 else 1280
h = sys.argv[4] if len(sys.argv) > 4 else "full"
wait = int(sys.argv[5]) if len(sys.argv) > 5 else 2500
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": w, "height": 900 if h == "full" else int(h)},
                    device_scale_factor=1 if w > 600 else 2)
    pg.goto(url)
    pg.wait_for_timeout(wait)
    pg.screenshot(path=out, full_page=(h == "full"))
    b.close()
print(out)
