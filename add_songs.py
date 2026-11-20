#!/usr/bin/env python3
"""
add_songs.py - add several YouTube songs to the music button in one go.

Usage:
    python3 add_songs.py                 # paste URLs when asked
    python3 add_songs.py URL1 URL2 ...   # or pass them as arguments
    python3 add_songs.py --check URL...  # only check size / free space, change nothing

Steps it runs:
  1. Updates yt-dlp (+ JS challenge solver) in ~/yt-dlp-venv
  2. Reads each video's title + length, estimates mp3 size
  3. Compares total against free space on the SD card -> FITS / DOES NOT FIT
  4. Asks for the display name of each song (Enter = keep YouTube title)
  5. Downloads songN.mp3 for each, skips any that fail
  6. Appends them to SONGS / SONG_NAMES in config.py (backup in config.py.bak)
  7. Rebuilds the song table in README.md, records URLs in song_sources.json
  8. Optionally commits + pushes to GitHub and reboots
"""
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

HOME = os.path.expanduser("~")
PROJECT = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(HOME, "yt-dlp-venv")
YTDLP = os.path.join(VENV, "bin", "yt-dlp")
PIP = os.path.join(VENV, "bin", "pip")
CONFIG = os.path.join(PROJECT, "config.py")
README = os.path.join(PROJECT, "README.md")
SOURCES = os.path.join(PROJECT, "song_sources.json")

MP3_KBPS = 160          # conservative estimate for yt-dlp's default mp3 quality
SRC_KBPS = 160          # downloaded audio (webm/opus) kept until converted
SAFETY_MB = 500         # always leave this much free on the SD card
README_START = "<!-- SONGS:START -->"
README_END = "<!-- SONGS:END -->"

ENV = dict(os.environ)
ENV["PATH"] = os.path.join(HOME, ".deno", "bin") + os.pathsep + ENV.get("PATH", "")


# ---------- helpers ----------
def ask(prompt, default=""):
    try:
        ans = input(prompt).strip()
    except EOFError:
        ans = ""
    return ans or default


def yes(prompt, default=True):
    d = "Y/n" if default else "y/N"
    a = ask(f"{prompt} [{d}] ").lower()
    return default if not a else a.startswith("y")


def mb(n_bytes):
    return n_bytes / (1024 * 1024)


def fmt_time(sec):
    sec = int(sec or 0)
    return f"{sec // 60}:{sec % 60:02d}"


def run(cmd, **kw):
    return subprocess.run(cmd, env=ENV, text=True, **kw)


def check_prereqs():
    if not os.path.exists(YTDLP):
        sys.exit(f"yt-dlp not found at {YTDLP}. Create the venv first (see README).")
    if not shutil.which("deno", path=ENV["PATH"]):
        print("! deno not found. YouTube needs it. Install once with:")
        print("    sudo apt install -y unzip && curl -fsSL https://deno.land/install.sh | sh")
        if not yes("Continue anyway?", default=False):
            sys.exit(1)


def update_ytdlp():
    print("Updating yt-dlp ...", flush=True)
    r = run([PIP, "install", "-q", "-U", "yt-dlp[default]"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    print("  ok" if r.returncode == 0 else f"  update failed (continuing): {r.stderr.strip()[-200:]}")


def probe(url):
    """Return dict(title, duration, url) or None."""
    r = run([YTDLP, "-J", "--no-playlist", "--no-warnings", url],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        err = (r.stderr.strip().splitlines() or ["unknown error"])[-1]
        print(f"  ✗ {url}\n    {err}")
        return None
    info = json.loads(r.stdout)
    dur = info.get("duration") or 0
    src = 0
    for f in info.get("formats", []):
        if f.get("vcodec") == "none" and f.get("acodec") not in (None, "none"):
            src = max(src, f.get("filesize") or f.get("filesize_approx") or 0)
    return {
        "url": url,
        "title": info.get("title") or url,
        "duration": dur,
        "mp3": dur * MP3_KBPS * 1000 / 8,
        "src": src or dur * SRC_KBPS * 1000 / 8,
    }


def load_config():
    ns = {}
    with open(CONFIG) as f:
        exec(f.read(), ns)
    return ns.get("BUTTON_PIN", 18), list(ns["SONGS"]), list(ns["SONG_NAMES"])


def write_config(pin, songs, names):
    q = lambda s: json.dumps(s, ensure_ascii=False)
    lines = ["# config.py", f"BUTTON_PIN = {pin}", "", "SONGS = ["]
    lines += [f"    {q(s)}," for s in songs]
    lines += ["]", "", "SONG_NAMES = ["]
    lines += [f"    {q(n)}," for n in names]
    lines += ["]", ""]
    with open(CONFIG, "w") as f:
        f.write("\n".join(lines))


def next_numbers(count):
    used = set()
    for fn in os.listdir(PROJECT):
        m = re.fullmatch(r"song(\d*)\.mp3", fn)
        if m:
            used.add(int(m.group(1) or 1))
    n, out = 1, []
    while len(out) < count:
        if n not in used:
            out.append(n)
        n += 1
    return [x for x in out]


def load_sources():
    try:
        with open(SOURCES) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def update_readme(songs, names, sources):
    if not os.path.exists(README):
        return
    rows = ["| # | File | Name | Source |", "|---|---|---|---|"]
    for i, (p, n) in enumerate(zip(songs, names), 1):
        fn = os.path.basename(p)
        rows.append(f"| {i} | {fn} | {n} | {sources.get(fn, '')} |")
    block = f"{README_START}\n" + "\n".join(rows) + f"\n{README_END}"
    text = open(README).read()
    if README_START in text and README_END in text:
        text = re.sub(re.escape(README_START) + r".*?" + re.escape(README_END),
                      lambda _: block, text, flags=re.S)
    else:
        print("  (README has no song-table markers; skipped)")
        return
    with open(README, "w") as f:
        f.write(text)


# ---------- main ----------
def main():
    args = sys.argv[1:]
    check_only = "--check" in args
    urls = [a for a in args if a.startswith("http")]

    if not urls:
        print("Paste YouTube URLs, one per line. Empty line when done:")
        while True:
            line = ask("> ")
            if not line:
                break
            urls += [u for u in line.split() if u.startswith("http")]
    urls = list(dict.fromkeys(urls))  # drop duplicates, keep order
    if not urls:
        sys.exit("No URLs given.")

    check_prereqs()
    update_ytdlp()

    # 1. size check
    print(f"\nChecking {len(urls)} video(s) ...")
    songs = [s for s in (probe(u) for u in urls) if s]
    if not songs:
        sys.exit("Nothing to add.")

    free = shutil.disk_usage(PROJECT).free
    total_mp3 = sum(s["mp3"] for s in songs)
    peak = total_mp3 + max(s["src"] for s in songs)  # one temp file at a time
    print(f"\n{'#':>2}  {'Length':>6}  {'≈ MB':>6}  Title")
    for i, s in enumerate(songs, 1):
        print(f"{i:>2}  {fmt_time(s['duration']):>6}  {mb(s['mp3']):6.1f}  {s['title'][:60]}")
    print(f"\nTotal ≈ {mb(total_mp3):.1f} MB  (peak while downloading ≈ {mb(peak):.1f} MB)")
    print(f"Free on SD card: {mb(free):.0f} MB   (keeping {SAFETY_MB} MB spare)")
    fits = mb(peak) + SAFETY_MB <= mb(free)
    print("✅ FITS" if fits else "❌ DOES NOT FIT. Remove some URLs or free up space.")
    if check_only or not fits:
        return
    if not yes("\nAdd these songs?"):
        return

    # 2. names
    print("\nName shown on the screen (Enter = keep YouTube title):")
    for s in songs:
        s["name"] = ask(f"  {s['title'][:55]}\n  name> ", default=s["title"])

    # 3. download
    pin, cfg_songs, cfg_names = load_config()
    if len(cfg_songs) != len(cfg_names):
        sys.exit(f"config.py is out of sync ({len(cfg_songs)} SONGS vs {len(cfg_names)} SONG_NAMES). Fix it first.")
    sources = load_sources()
    added = []
    for s, n in zip(songs, next_numbers(len(songs))):
        fn = f"song{n}.mp3"
        path = os.path.join(PROJECT, fn)
        print(f"\nDownloading {s['name']} → {fn}")
        r = run([YTDLP, "-x", "--audio-format", "mp3", "--no-playlist", "--no-warnings",
                 "-o", os.path.join(PROJECT, f"song{n}.%(ext)s"), s["url"]])
        if r.returncode == 0 and os.path.exists(path):
            print(f"  ✓ {mb(os.path.getsize(path)):.1f} MB")
            added.append((path, s["name"]))
            sources[fn] = s["url"]
        else:
            print("  ✗ failed, skipped")

    if not added:
        sys.exit("\nNo songs downloaded; nothing changed.")

    # 4. config + readme + sources
    shutil.copy(CONFIG, CONFIG + ".bak")
    cfg_songs += [p for p, _ in added]
    cfg_names += [n for _, n in added]
    write_config(pin, cfg_songs, cfg_names)
    with open(SOURCES, "w") as f:
        json.dump(sources, f, indent=2, ensure_ascii=False)
    update_readme(cfg_songs, cfg_names, sources)

    # sanity check
    _, s2, n2 = load_config()
    assert len(s2) == len(n2), "config.py SONGS/SONG_NAMES mismatch after write!"
    print(f"\n✓ Added {len(added)} song(s). Playlist now has {len(s2)} songs:")
    for i, n in enumerate(n2, 1):
        print(f"  {i:>2}. {n}")

    # 5. git + reboot
    if os.path.isdir(os.path.join(PROJECT, ".git")) and yes("\nCommit + push to GitHub?"):
        msg = "Add songs: " + ", ".join(n for _, n in added)
        os.chdir(PROJECT)
        run(["git", "pull", "--no-edit", "-q"])
        run(["git", "add", "config.py", "README.md", "song_sources.json"])
        run(["git", "commit", "-q", "-m", msg])
        r = run(["git", "push", "-q", "origin", "HEAD"])
        print("  ✓ pushed" if r.returncode == 0 else "  ✗ push failed (run: git push)")

    if yes("\nReboot now so the button picks up the new songs?"):
        run(["sudo", "reboot"])
    else:
        print("New songs will load on next reboot (sudo reboot).")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
