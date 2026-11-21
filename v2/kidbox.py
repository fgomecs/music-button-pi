#!/usr/bin/env python3
"""
kidbox.py - Tiago's Music Box V2: touch-only music player + camera + photo gallery.

Screen: 800x480 touch (Waveshare 4.3" DSI). Runs full screen.
  Home    -> big Music / Camera / Photos buttons
  Music   -> playlist from ../config.py, play/pause, previous, next, animations
  Camera  -> live viewfinder, big shutter button, photos saved to ~/Pictures/kidbox
  Photos  -> grid of his pictures, tap to view, swipe for next/previous,
             long-press (2 s) on a photo to delete (parents)

Audio only: video playback is disabled on purpose (settings.json "video_unlocked").
Talks to portal.py through musicstate.py (now playing, commands, screen mirror).

Run:   python3 kidbox.py            (full screen)
       KIDBOX_WINDOW=1 python3 kidbox.py   (windowed, for testing)
"""
import glob
import json
import math
import os
import random
import socket
import subprocess
import sys
import threading
import time

import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, PROJECT)

try:
    import musicstate
except Exception:
    musicstate = None

W, H = 800, 480
FPS = 30
PHOTO_DIR = os.path.expanduser(os.environ.get("KIDBOX_PHOTOS", "~/Pictures/kidbox"))
THUMB_DIR = os.path.join(PHOTO_DIR, ".thumbs")
SETTINGS = os.path.join(HERE, "settings.json")
MPV_SOCK = "/tmp/kidbox-mpv.sock"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# ---------------------------------------------------------------- look & words
BG_TOP, BG_BOT = (24, 32, 74), (64, 22, 92)
WHITE, INK = (255, 255, 255), (20, 24, 48)
PINK, ORANGE, YELLOW, GREEN, CYAN, BLUE, RED = (
    (255, 92, 168), (255, 150, 50), (255, 214, 64), (72, 214, 120),
    (64, 210, 230), (90, 140, 255), (255, 80, 80))

WORDS = {
    "en": {"music": "Music", "camera": "Camera", "photos": "Photos",
           "nothing": "Tap a song!", "no_photos": "No photos yet. Take one!",
           "delete": "Delete this photo?", "no_camera": "Camera not found",
           "saving": "Saving...", "songs": "songs"},
    "es": {"music": "Música", "camera": "Cámara", "photos": "Fotos",
           "nothing": "¡Toca una canción!", "no_photos": "¡Todavía no hay fotos!",
           "delete": "¿Borrar esta foto?", "no_camera": "No hay cámara",
           "saving": "Guardando...", "songs": "canciones"},
}

DEFAULT_SETTINGS = {"lang": "en", "video_unlocked": False, "volume": 90, "mpv_args": []}


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS) as f:
            s.update(json.load(f))
    except (FileNotFoundError, ValueError):
        pass
    return s


def load_library():
    ns = {}
    try:
        with open(os.path.join(PROJECT, "config.py")) as f:
            exec(f.read(), ns)
        return list(zip(ns.get("SONGS", []), ns.get("SONG_NAMES", [])))
    except Exception as e:
        print("config.py error:", e)
        return []


# ---------------------------------------------------------------- audio (mpv)
class Player:
    """mpv in the background, controlled over its JSON IPC socket. Audio only."""

    def __init__(self, settings):
        self.proc = None
        self.index = None
        self.paused = False
        self.pos = 0.0
        self.dur = 0.0
        self.settings = settings
        self._last_poll = 0

    def play(self, index, path):
        self.stop()
        try:
            os.remove(MPV_SOCK)
        except FileNotFoundError:
            pass
        args = ["mpv", "--no-video", "--no-terminal", "--idle=no",
                f"--volume={self.settings.get('volume', 90)}",
                f"--input-ipc-server={MPV_SOCK}", *self.settings.get("mpv_args", []), path]
        try:
            self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.index, self.paused, self.pos, self.dur = index, False, 0.0, 0.0
        except FileNotFoundError:
            print("mpv not installed")
            self.proc = None

    def _ipc(self, *cmd):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(0.15)
            s.connect(MPV_SOCK)
            s.sendall((json.dumps({"command": list(cmd)}) + "\n").encode())
            data = b""
            while b"\n" not in data:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
            s.close()
            for line in data.decode(errors="ignore").splitlines():
                msg = json.loads(line)
                if "error" in msg:
                    return msg.get("data")
        except (OSError, ValueError):
            return None
        return None

    def toggle(self):
        if self.alive():
            self.paused = not self.paused
            self._ipc("set_property", "pause", self.paused)

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
        self.paused = False

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def poll(self):
        """Refresh position/duration a few times per second. Returns False when the song ended."""
        if not self.proc:
            return True
        if self.proc.poll() is not None:
            self.proc = None
            return False
        now = time.time()
        if now - self._last_poll > 0.4:
            self._last_poll = now
            p = self._ipc("get_property", "time-pos")
            d = self._ipc("get_property", "duration")
            self.pos = p if isinstance(p, (int, float)) else self.pos
            self.dur = d if isinstance(d, (int, float)) else self.dur
        return True


# ---------------------------------------------------------------- camera
class Camera:
    """picamera2 wrapper. Opened only on the camera screen (saves battery)."""

    def __init__(self):
        self.cam = None
        self.error = None
        self.busy = False

    def open(self):
        if self.cam:
            return True
        try:
            from picamera2 import Picamera2
            self.cam = Picamera2()
            self.preview_cfg = self.cam.create_preview_configuration(
                main={"size": (640, 480), "format": "BGR888"})  # BGR888 = RGB byte order
            self.still_cfg = self.cam.create_still_configuration()
            self.cam.configure(self.preview_cfg)
            self.cam.start()
            self.error = None
            return True
        except Exception as e:
            self.error = str(e)
            self.cam = None
            print("camera:", e)
            return False

    def frame(self):
        if not self.cam or self.busy:
            return None
        try:
            arr = self.cam.capture_array("main")
            h, w = arr.shape[:2]
            return pygame.image.frombuffer(arr.tobytes(), (w, h), "RGB")
        except Exception as e:
            print("frame:", e)
            return None

    def snap(self, path, done):
        """Full-resolution still in a thread; done(path_or_None) when finished."""
        if not self.cam or self.busy:
            return
        self.busy = True

        def work():
            ok = None
            try:
                self.cam.switch_mode_and_capture_file(self.still_cfg, path)
                ok = path
            except Exception as e:
                print("snap:", e)
            self.busy = False
            done(ok)
        threading.Thread(target=work, daemon=True).start()

    def close(self):
        if self.cam:
            try:
                self.cam.stop()
                self.cam.close()
            except Exception:
                pass
        self.cam = None


# ---------------------------------------------------------------- drawing helpers
_fonts = {}


def font(size):
    if size not in _fonts:
        try:
            _fonts[size] = pygame.font.Font(FONT, size)
        except (FileNotFoundError, OSError):
            _fonts[size] = pygame.font.Font(None, int(size * 1.3))
    return _fonts[size]


def text(surf, s, size, color, center=None, topleft=None, maxw=None):
    f = font(size)
    img = f.render(s, True, color)
    if maxw and img.get_width() > maxw:
        while len(s) > 3 and f.size(s + "…")[0] > maxw:
            s = s[:-1]
        img = f.render(s + "…", True, color)
    r = img.get_rect()
    if center:
        r.center = center
    elif topleft:
        r.topleft = topleft
    surf.blit(img, r)
    return r


def gradient(surf, top, bot):
    for y in range(H):
        t = y / H
        c = [int(top[i] + (bot[i] - top[i]) * t) for i in range(3)]
        pygame.draw.line(surf, c, (0, y), (W, y))


def rbox(surf, color, rect, r=24, shadow=True):
    rect = pygame.Rect(rect)
    if shadow:
        pygame.draw.rect(surf, (0, 0, 0, 90) if surf.get_flags() & pygame.SRCALPHA else (10, 10, 30),
                         rect.move(0, 6), border_radius=r)
    pygame.draw.rect(surf, color, rect, border_radius=r)
    return rect


def icon_note(surf, c, s, color):
    x, y = c
    pygame.draw.ellipse(surf, color, (x - s * .45, y + s * .15, s * .38, s * .28))
    pygame.draw.ellipse(surf, color, (x + s * .05, y + s * .02, s * .38, s * .28))
    pygame.draw.line(surf, color, (x - s * .1, y + s * .25), (x - s * .1, y - s * .4), max(3, int(s * .07)))
    pygame.draw.line(surf, color, (x + s * .4, y + s * .12), (x + s * .4, y - s * .5), max(3, int(s * .07)))
    pygame.draw.polygon(surf, color, [(x - s * .13, y - s * .42), (x + s * .43, y - s * .55),
                                      (x + s * .43, y - s * .38), (x - s * .13, y - s * .25)])


def icon_camera(surf, c, s, color):
    x, y = c
    body = pygame.Rect(0, 0, s * .95, s * .62)
    body.center = (x, y + s * .05)
    pygame.draw.rect(surf, color, body, border_radius=int(s * .1))
    pygame.draw.rect(surf, color, (x - s * .18, y - s * .38, s * .36, s * .16), border_radius=4)
    pygame.draw.circle(surf, INK, (x, y + s * .06), int(s * .22))
    pygame.draw.circle(surf, color, (x, y + s * .06), int(s * .14))


def icon_photo(surf, c, s, color):
    x, y = c
    r = pygame.Rect(0, 0, s * .95, s * .72)
    r.center = c
    pygame.draw.rect(surf, color, r, border_radius=int(s * .08))
    inner = r.inflate(-s * .12, -s * .12)
    pygame.draw.rect(surf, INK, inner, border_radius=int(s * .05))
    pygame.draw.polygon(surf, color, [(inner.left + 4, inner.bottom - 4), (inner.left + inner.w * .35, inner.top + inner.h * .4),
                                      (inner.left + inner.w * .6, inner.bottom - 4)])
    pygame.draw.polygon(surf, color, [(inner.left + inner.w * .45, inner.bottom - 4), (inner.left + inner.w * .7, inner.top + inner.h * .5),
                                      (inner.right - 4, inner.bottom - 4)])
    pygame.draw.circle(surf, YELLOW, (int(inner.right - inner.w * .2), int(inner.top + inner.h * .28)), int(s * .07))


def icon_home(surf, c, s, color):
    x, y = c
    pygame.draw.polygon(surf, color, [(x - s * .5, y), (x, y - s * .45), (x + s * .5, y)])
    pygame.draw.rect(surf, color, (x - s * .35, y - 2, s * .7, s * .45))
    pygame.draw.rect(surf, INK, (x - s * .1, y + s * .12, s * .2, s * .33))


def icon_play(surf, c, s, color):
    x, y = c
    pygame.draw.polygon(surf, color, [(x - s * .3, y - s * .4), (x - s * .3, y + s * .4), (x + s * .4, y)])


def icon_pause(surf, c, s, color):
    x, y = c
    pygame.draw.rect(surf, color, (x - s * .32, y - s * .38, s * .22, s * .76), border_radius=4)
    pygame.draw.rect(surf, color, (x + s * .1, y - s * .38, s * .22, s * .76), border_radius=4)


def icon_skip(surf, c, s, color, back=False):
    x, y = c
    d = -1 if back else 1
    for off in (-0.22, 0.12):
        ox = x + d * off * s
        pygame.draw.polygon(surf, color, [(ox - d * s * .2, y - s * .3), (ox - d * s * .2, y + s * .3), (ox + d * s * .15, y)])
    pygame.draw.rect(surf, color, (x + d * s * .28 - s * .04, y - s * .3, s * .08, s * .6))


def icon_trash(surf, c, s, color):
    x, y = c
    pygame.draw.rect(surf, color, (x - s * .3, y - s * .25, s * .6, s * .65), border_radius=5)
    pygame.draw.rect(surf, color, (x - s * .4, y - s * .4, s * .8, s * .1), border_radius=3)
    pygame.draw.rect(surf, color, (x - s * .1, y - s * .5, s * .2, s * .12), border_radius=3)


# ---------------------------------------------------------------- animated background
class Bubbles:
    def __init__(self, n=18):
        self.b = [self._new(random.uniform(0, H)) for _ in range(n)]

    def _new(self, y=None):
        return [random.uniform(0, W), H + 20 if y is None else y, random.uniform(6, 22),
                random.uniform(20, 60), random.uniform(0, 6.28), random.choice([PINK, CYAN, YELLOW, GREEN, ORANGE])]

    def draw(self, surf, dt, speed=1.0):
        for b in self.b:
            b[1] -= b[3] * dt * speed
            b[4] += dt * 2
            x = b[0] + math.sin(b[4]) * 8
            if b[1] < -30:
                b[:] = self._new()
            pygame.draw.circle(surf, b[5], (int(x), int(b[1])), int(b[2]), 3)
            pygame.draw.circle(surf, WHITE, (int(x - b[2] * .35), int(b[1] - b[2] * .35)), max(2, int(b[2] * .18)))


class Fish:
    def __init__(self):
        self.x, self.y, self.t, self.dir = -80, 400, 0, 1

    def draw(self, surf, dt):
        self.t += dt
        self.x += 70 * dt * self.dir
        if self.x > W + 80 or self.x < -80:
            self.dir *= -1
            self.y = random.randint(330, 440)
        y = self.y + math.sin(self.t * 3) * 10
        d = self.dir
        pygame.draw.ellipse(surf, ORANGE, (self.x - 36, y - 20, 72, 40))
        tail = [(self.x - d * 30, y), (self.x - d * 58, y - 20), (self.x - d * 58, y + 20)]
        pygame.draw.polygon(surf, ORANGE, tail)
        pygame.draw.circle(surf, WHITE, (int(self.x + d * 18), int(y - 6)), 8)
        pygame.draw.circle(surf, INK, (int(self.x + d * 20), int(y - 6)), 4)


# ---------------------------------------------------------------- the app
class KidBox:
    def __init__(self):
        os.makedirs(THUMB_DIR, exist_ok=True)
        pygame.init()
        # SCALED: always draw on an 800x480 canvas and let SDL stretch it to whatever
        # the display really is (the 4.3" panel is 800x480; a headless/HDMI desktop is bigger)
        flags = pygame.SCALED if os.environ.get("KIDBOX_WINDOW") else (pygame.FULLSCREEN | pygame.SCALED)
        self.screen = pygame.display.set_mode((W, H), flags)
        pygame.display.set_caption("KidBox")
        pygame.mouse.set_visible(bool(os.environ.get("KIDBOX_WINDOW")))
        self.clock = pygame.time.Clock()
        self.settings = load_settings()
        self.library = load_library()
        self.player = Player(self.settings)
        self.camera = Camera()
        self.page = "home"
        self.buttons = []           # (rect, action) rebuilt every frame
        self.bg = pygame.Surface((W, H))
        gradient(self.bg, BG_TOP, BG_BOT)
        self.bubbles, self.fish = Bubbles(), Fish()
        self.t = 0
        self.scroll = 0             # music list scroll (px)
        self.photos, self.photo_i, self.grid_page = [], 0, 0
        self.view_img, self.view_path = None, None
        self.confirm_delete = False
        self.flash = 0
        self.press = None           # (pos, time) for swipe / long press
        self.dragging = False
        self.last_mirror = 0
        self.thumb_cache = {}
        self.photos_dirty = False
        self.report(playing=False, index=None, name=None, count=len(self.library), screen="color")

    # ---- words
    def w(self, key):
        return WORDS.get(self.settings.get("lang", "en"), WORDS["en"]).get(key, key)

    # ---- portal state
    def report(self, **kw):
        if musicstate:
            try:
                musicstate.set(**kw)
            except Exception:
                pass

    def mirror(self):
        """Save a small copy of the screen for the portal's live view (1 per second)."""
        if not musicstate or time.time() - self.last_mirror < 1.0:
            return
        self.last_mirror = time.time()
        try:
            small = pygame.transform.smoothscale(self.screen, (400, 240))
            tmp = musicstate.OLED + ".tmp.png"
            pygame.image.save(small, tmp)
            os.replace(tmp, musicstate.OLED)
            musicstate._state["oled_v"] = musicstate._state.get("oled_v", 0) + 1
            musicstate.set()
        except Exception:
            pass

    def portal_commands(self):
        if not musicstate:
            return
        cmd = musicstate.take_cmd()
        if not cmd:
            return
        if cmd == "next":
            self.next_song()
        elif cmd == "stop":
            self.player.stop()
            self.report(playing=False)
        elif cmd.startswith("play "):
            try:
                self.play(int(cmd.split()[1]))
            except ValueError:
                pass
        elif cmd == "reload":
            self.library = load_library()
            self.settings = load_settings()
            self.player.settings = self.settings
            self.report(count=len(self.library))

    # ---- music
    def play(self, i):
        if not self.library:
            return
        i %= len(self.library)
        path, name = self.library[i]
        self.player.play(i, path)
        self.report(playing=True, index=i, name=name, started=time.time(), count=len(self.library))

    def next_song(self):
        cur = self.player.index
        self.play(0 if cur is None else cur + 1)

    def prev_song(self):
        cur = self.player.index
        if cur is None:
            self.play(0)
        elif self.player.pos > 4:
            self.play(cur)           # restart current song, like a CD player
        else:
            self.play(cur - 1)

    def toggle(self):
        if self.player.alive():
            self.player.toggle()
            self.report(playing=not self.player.paused)
        else:
            self.play(self.player.index or 0)

    # ---- photos
    def load_photos(self):
        self.photos = sorted(glob.glob(os.path.join(PHOTO_DIR, "*.jpg")), reverse=True)

    def thumb(self, path):
        if path in self.thumb_cache:
            return self.thumb_cache[path]
        tpath = os.path.join(THUMB_DIR, os.path.basename(path))
        img = None
        try:
            if os.path.exists(tpath):
                img = pygame.image.load(tpath).convert()
            else:
                big = pygame.image.load(path)
                img = pygame.transform.smoothscale(big, (176, 132)).convert()
                pygame.image.save(img, tpath)
        except Exception as e:
            print("thumb:", e)
        self.thumb_cache[path] = img
        return img

    def open_photo(self, i):
        if not self.photos:
            return
        self.photo_i = i % len(self.photos)
        self.view_path = self.photos[self.photo_i]
        try:
            big = pygame.image.load(self.view_path)
            bw, bh = big.get_size()
            scale = min(W / bw, H / bh)
            self.view_img = pygame.transform.smoothscale(big, (int(bw * scale), int(bh * scale))).convert()
        except Exception as e:
            print("open photo:", e)
            self.view_img = None
        self.confirm_delete = False
        self.page = "viewer"

    def delete_photo(self):
        if self.view_path:
            for p in (self.view_path, os.path.join(THUMB_DIR, os.path.basename(self.view_path))):
                try:
                    os.remove(p)
                except FileNotFoundError:
                    pass
            self.thumb_cache.pop(self.view_path, None)
        self.load_photos()
        self.confirm_delete = False
        if self.photos:
            self.open_photo(min(self.photo_i, len(self.photos) - 1))
        else:
            self.go("photos")

    def snap(self):
        if self.camera.busy or not self.camera.cam:
            return
        path = os.path.join(PHOTO_DIR, time.strftime("IMG_%Y%m%d_%H%M%S.jpg"))
        self.flash = 1.0

        def done(p):
            if p:
                self.thumb_cache.pop(p, None)
                self.photos_dirty = True      # reload list on the main thread
        self.camera.snap(path, done)

    # ---- navigation
    def go(self, page):
        if self.page == "camera" and page != "camera":
            self.camera.close()
        if page == "camera":
            self.camera.open()
            self.load_photos()
        if page == "photos":
            self.load_photos()
            self.grid_page = 0
        self.page = page

    # ---- input
    def handle(self, ev):
        if ev.type == pygame.QUIT:
            return False
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE and os.environ.get("KIDBOX_WINDOW"):
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.press = (ev.pos, time.time())
            self.dragging = False
        elif ev.type == pygame.MOUSEMOTION and self.press and ev.buttons[0]:
            dx, dy = ev.pos[0] - self.press[0][0], ev.pos[1] - self.press[0][1]
            if self.page == "music" and abs(dy) > 12:
                self.dragging = True
                self.scroll = max(0, min(self.max_scroll(), self.scroll - ev.rel[1]))
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.press:
            (x0, y0), t0 = self.press
            dx, dy, held = ev.pos[0] - x0, ev.pos[1] - y0, time.time() - t0
            self.press = None
            if self.dragging:
                self.dragging = False
                return True
            if abs(dx) > 80 and abs(dx) > abs(dy):          # swipe
                self.swipe(-1 if dx < 0 else 1)
                return True
            if self.page == "viewer" and held > 1.5 and not self.confirm_delete:   # long press
                self.confirm_delete = True
                return True
            for rect, action in reversed(self.buttons):
                if rect.collidepoint(ev.pos):
                    action()
                    break
        return True

    def swipe(self, d):
        if self.page == "viewer" and self.photos and not self.confirm_delete:
            self.open_photo(self.photo_i - d)
        elif self.page == "photos" and self.photos:
            pages = max(1, math.ceil(len(self.photos) / 8))
            self.grid_page = max(0, min(pages - 1, self.grid_page - d))

    def max_scroll(self):
        return max(0, len(self.library) * 64 - 300)

    def btn(self, rect, action):
        r = pygame.Rect(rect)
        self.buttons.append((r, action))
        return r

    def home_button(self):
        r = self.btn((10, 10, 64, 64), lambda: self.go("home"))
        rbox(self.screen, WHITE, r, 18)
        icon_home(self.screen, r.center, 40, INK)

    # ---- pages
    def draw_home(self, dt):
        s = self.screen
        s.blit(self.bg, (0, 0))
        self.bubbles.draw(s, dt)
        self.fish.draw(s, dt)
        items = [("music", PINK, icon_note), ("camera", CYAN, icon_camera), ("photos", YELLOW, icon_photo)]
        for i, (key, color, icon) in enumerate(items):
            bob = math.sin(self.t * 2 + i) * 6
            r = pygame.Rect(40 + i * 250, 70 + bob, 220, 250)
            self.btn(r, lambda k=key: self.go(k))
            rbox(s, color, r, 36)
            icon(s, (r.centerx, r.top + 105), 120, WHITE)
            text(s, self.w(key), 34, WHITE, center=(r.centerx, r.bottom - 42))
        if self.player.alive() and self.player.index is not None:
            name = self.library[self.player.index][1] if self.player.index < len(self.library) else ""
            r = self.btn((150, 360, 500, 56), lambda: self.go("music"))
            rbox(s, WHITE, r, 28)
            icon_note(s, (r.left + 36, r.centery), 34, PINK)
            text(s, name, 24, INK, topleft=(r.left + 66, r.top + 13), maxw=r.w - 90)

    def draw_music(self, dt):
        s = self.screen
        s.blit(self.bg, (0, 0))
        playing = self.player.alive() and not self.player.paused
        self.bubbles.draw(s, dt, 2.2 if playing else 0.6)
        self.home_button()

        # left: now playing + big controls
        cur = self.player.index
        name = self.library[cur][1] if cur is not None and cur < len(self.library) else self.w("nothing")
        panel = pygame.Rect(90, 14, 380, 452)
        disc_c = (panel.centerx, 128)
        ang = self.t * (90 if playing else 0)
        pygame.draw.circle(s, INK, disc_c, 92)
        for k in range(6):
            a = math.radians(ang + k * 60)
            pygame.draw.circle(s, [PINK, ORANGE, YELLOW, GREEN, CYAN, BLUE][k],
                               (int(disc_c[0] + math.cos(a) * 56), int(disc_c[1] + math.sin(a) * 56)), 18)
        pygame.draw.circle(s, WHITE, disc_c, 26)
        pygame.draw.circle(s, INK, disc_c, 8)

        text(s, name, 28, WHITE, center=(panel.centerx, 296), maxw=panel.w)
        # progress
        bar = pygame.Rect(panel.left + 20, 324, panel.w - 40, 12)
        pygame.draw.rect(s, (90, 86, 140), bar, border_radius=6)
        if self.player.dur:
            done = bar.copy()
            done.w = int(bar.w * min(1, self.player.pos / self.player.dur))
            pygame.draw.rect(s, YELLOW, done, border_radius=6)
        # equalizer bars
        for k in range(10):
            hgt = (abs(math.sin(self.t * (4 + k % 3) + k)) * 40 + 6) if playing else 6
            pygame.draw.rect(s, [PINK, ORANGE, YELLOW, GREEN, CYAN][k % 5],
                             (panel.left + 40 + k * 31, 272 - hgt, 20, hgt), border_radius=4)
        # controls
        cy = 400
        for cx, color, act, ic in [(panel.left + 70, BLUE, self.prev_song, "prev"),
                                   (panel.centerx, GREEN, self.toggle, "play"),
                                   (panel.right - 70, BLUE, self.next_song, "next")]:
            size = 110 if ic == "play" else 84
            r = self.btn((cx - size // 2, cy - size // 2, size, size), act)
            pygame.draw.circle(s, (10, 10, 30), (r.centerx, r.centery + 5), size // 2)
            pygame.draw.circle(s, color, r.center, size // 2)
            if ic == "play":
                (icon_pause if playing else icon_play)(s, r.center, 56, WHITE)
            else:
                icon_skip(s, r.center, 50, WHITE, back=(ic == "prev"))

        # right: song list
        lst = pygame.Rect(490, 14, 300, 452)
        rbox(s, (255, 255, 255), lst, 22, shadow=False)
        text(s, f"{len(self.library)} {self.w('songs')}", 18, (120, 120, 150), topleft=(lst.left + 18, lst.top + 10))
        clip = pygame.Rect(lst.left, lst.top + 40, lst.w, lst.h - 50)
        s.set_clip(clip)
        for i, (_, nm) in enumerate(self.library):
            y = clip.top + i * 64 - self.scroll
            if y < clip.top - 64 or y > clip.bottom:
                continue
            row = pygame.Rect(lst.left + 10, y, lst.w - 20, 56)
            active = i == cur
            pygame.draw.rect(s, PINK if active else (238, 240, 250), row, border_radius=16)
            pygame.draw.circle(s, WHITE if active else [PINK, ORANGE, GREEN, CYAN, BLUE][i % 5], (row.left + 30, row.centery), 18)
            text(s, str(i + 1), 18, INK if active else WHITE, center=(row.left + 30, row.centery))
            text(s, nm, 21, WHITE if active else INK, topleft=(row.left + 58, row.top + 15), maxw=row.w - 68)
            if clip.colliderect(row):
                self.btn(row.clip(clip), lambda k=i: self.play(k))
        s.set_clip(None)

    def draw_camera(self, dt):
        s = self.screen
        s.fill((0, 0, 0))
        if self.camera.busy:
            text(s, self.w("saving"), 40, WHITE, center=(W // 2 - 50, H // 2))
        else:
            fr = self.camera.frame()
            if fr:
                fr = pygame.transform.scale(fr, (640, 480))
                s.blit(fr, (0, 0))
            elif self.camera.error or not self.camera.cam:
                text(s, self.w("no_camera"), 36, WHITE, center=(W // 2 - 50, H // 2))
        # side bar
        side = pygame.Rect(640, 0, 160, H)
        pygame.draw.rect(s, (20, 22, 40), side)
        self.home_button()
        shot = self.btn((side.centerx - 62, H // 2 - 62, 124, 124), self.snap)
        pygame.draw.circle(s, WHITE, shot.center, 62)
        pygame.draw.circle(s, RED if not self.camera.busy else (120, 120, 120), shot.center, 50)
        # last photo preview -> gallery
        if self.photos:
            th = self.thumb(self.photos[0])
            if th:
                r = self.btn((side.centerx - 55, H - 105, 110, 82), lambda: self.open_photo(0))
                s.blit(pygame.transform.smoothscale(th, r.size), r)
                pygame.draw.rect(s, WHITE, r, 3, border_radius=6)
        if self.flash > 0:
            fl = pygame.Surface((640, 480))
            fl.fill(WHITE)
            fl.set_alpha(int(255 * self.flash))
            s.blit(fl, (0, 0))
            self.flash = max(0, self.flash - dt * 3)

    def draw_photos(self, dt):
        s = self.screen
        s.blit(self.bg, (0, 0))
        self.bubbles.draw(s, dt, 0.5)
        self.home_button()
        if not self.photos:
            text(s, self.w("no_photos"), 34, WHITE, center=(W // 2, H // 2 - 20))
            r = self.btn((W // 2 - 90, H // 2 + 30, 180, 80), lambda: self.go("camera"))
            rbox(s, CYAN, r, 24)
            icon_camera(s, r.center, 60, WHITE)
            return
        start = self.grid_page * 8
        for k, path in enumerate(self.photos[start:start + 8]):
            col, row = k % 4, k // 4
            r = pygame.Rect(96 + col * 176, 40 + row * 190, 160, 170)
            self.btn(r, lambda i=start + k: self.open_photo(i))
            rbox(s, WHITE, r, 14)
            th = self.thumb(path)
            if th:
                s.blit(pygame.transform.smoothscale(th, (144, 108)), (r.left + 8, r.top + 8))
            stamp = os.path.basename(path)[4:12]
            text(s, f"{stamp[4:6]}/{stamp[6:8]}", 18, INK, center=(r.centerx, r.bottom - 26))
        pages = max(1, math.ceil(len(self.photos) / 8))
        for p in range(pages):
            pygame.draw.circle(s, WHITE if p == self.grid_page else (120, 110, 160), (W // 2 - (pages - 1) * 12 + p * 24, 455), 7)

    def draw_viewer(self, dt):
        s = self.screen
        s.fill((0, 0, 0))
        if self.view_img:
            s.blit(self.view_img, self.view_img.get_rect(center=(W // 2, H // 2)))
        self.home_button()
        r = self.btn((W - 74, 10, 64, 64), lambda: self.go("photos"))
        rbox(s, YELLOW, r, 18)
        icon_photo(s, r.center, 40, WHITE)
        text(s, f"{self.photo_i + 1}/{len(self.photos)}", 20, WHITE, center=(W // 2, H - 20))
        if self.press and time.time() - self.press[1] > 0.6 and not self.confirm_delete:
            held = min(1, (time.time() - self.press[1] - 0.6) / 0.9)
            pygame.draw.arc(s, RED, (W // 2 - 40, H // 2 - 40, 80, 80), 0, held * 6.28, 8)
        if self.confirm_delete:
            dim = pygame.Surface((W, H))
            dim.set_alpha(170)
            dim.fill((0, 0, 0))
            s.blit(dim, (0, 0))
            box = rbox(s, WHITE, (W // 2 - 220, H // 2 - 110, 440, 220), 26)
            text(s, self.w("delete"), 28, INK, center=(box.centerx, box.top + 50))
            yes = self.btn((box.left + 40, box.bottom - 110, 160, 80), self.delete_photo)
            no = self.btn((box.right - 200, box.bottom - 110, 160, 80), lambda: setattr(self, "confirm_delete", False))
            rbox(s, RED, yes, 20)
            icon_trash(s, yes.center, 50, WHITE)
            rbox(s, GREEN, no, 20)
            text(s, "✕", 44, WHITE, center=no.center)

    # ---- main loop
    def run(self):
        running = True
        last = time.time()
        while running:
            now = time.time()
            dt, last = min(0.1, now - last), now
            self.t += dt
            for ev in pygame.event.get():
                running = self.handle(ev) and running
            if not self.player.poll():                # song finished by itself
                self.report(playing=False)
            self.portal_commands()
            if self.photos_dirty:
                self.photos_dirty = False
                self.load_photos()
            self.buttons = []
            getattr(self, "draw_" + self.page)(dt)
            pygame.display.flip()
            self.mirror()
            self.clock.tick(FPS if self.page != "camera" else 24)
        self.player.stop()
        self.camera.close()
        self.report(playing=False)
        pygame.quit()


if __name__ == "__main__":
    KidBox().run()
