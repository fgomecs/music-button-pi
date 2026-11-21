#!/usr/bin/env python3
"""
add_songs.py - add songs/stories to the music button, and report the library.

Usage:
    python3 add_songs.py            # show library, then paste "URL Name" rows to add
    python3 add_songs.py --list     # only show library, free space and how many more fit
    python3 add_songs.py --check    # paste rows, report sizes / fit, change nothing

Paste one per line:   https://www.youtube.com/watch?v=abc123 La Patita
(| , ; or tab between URL and name also work; name optional)

The same functions are used by portal.py (the web portal).
"""
import json
import os
import re
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")
PROJECT = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(HOME, "yt-dlp-venv")
YTDLP = os.path.join(VENV, "bin", "yt-dlp")
PIP = os.path.join(VENV, "bin", "pip")
CONFIG = os.path.join(PROJECT, "config.py")
README = os.path.join(PROJECT, "README.md")
SOURCES = os.path.join(PROJECT, "song_sources.json")

MP3_KBPS = 160          # conservative estimate for yt-dlp's default mp3 quality
SRC_KBPS = 160          # downloaded audio kept until converted
SAFETY_MB = 500         # always leave this much free on the SD card
CAPACITY_SIZES = [1, 2, 5, 10, 15, 20]   # "average MB per song/story" scenarios
README_START = "<!-- SONGS:START -->"
README_END = "<!-- SONGS:END -->"

# PuTTY/locale may not be UTF-8: never crash on printing or reading names
for _st in (sys.stdin, sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ENV = dict(os.environ)
ENV["PATH"] = os.path.join(HOME, ".deno", "bin") + os.pathsep + ENV.get("PATH", "")


# ======================================================================
# Library (used by the CLI below and by portal.py)
# ======================================================================
def mb(n_bytes):
    return n_bytes / (1024 * 1024)


def fmt_time(sec):
    sec = int(sec or 0)
    return f"{sec // 60}:{sec % 60:02d}"


def clean_url(url):
    """Drop YouTube tracking junk (&pp=, &si=, ...) and keep just the video id."""
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", url)
    return f"https://www.youtube.com/watch?v={m.group(1)}" if m else url


def parse_rows(text):
    """'URL Name' lines -> [(url, name_or_None)], duplicates removed."""
    out, seen = [], set()
    for line in text.splitlines():
        m = re.match(r"\s*(https?://\S+)\s*[|,;\t-]*\s*(.*)", line)
        if not m:
            continue
        url, name = clean_url(m.group(1)), m.group(2).strip()
        if len(name) > 1 and name[0] == name[-1] == '"':
            name = name[1:-1]
        if url not in seen:
            seen.add(url)
            out.append((url, name or None))
    return out


def split_known(rows):
    """Separate rows whose URL is already in the library (song_sources.json)."""
    known = {u: fn for fn, u in load_sources().items()}
    new = [r for r in rows if r[0] not in known]
    dup = [(u, n, known[u]) for u, n in rows if u in known]
    return new, dup


def deno_ok():
    return bool(shutil.which("deno", path=ENV["PATH"]))


def update_ytdlp():
    r = subprocess.run([PIP, "install", "-q", "-U", "yt-dlp[default]"], env=ENV,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    return r.returncode == 0, r.stderr.strip()[-200:]


def probe(url):
    """Return dict(url,title,duration,mp3,src) or dict(url,error)."""
    r = subprocess.run([YTDLP, "-J", "--no-playlist", "--no-warnings", url], env=ENV,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        err = (r.stderr.strip().splitlines() or ["unknown error"])[-1]
        return {"url": url, "error": err}
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


def free_bytes():
    return shutil.disk_usage(PROJECT).free


def fit_check(probed):
    """probed = successful probe dicts -> dict with totals and verdict."""
    total = sum(s["mp3"] for s in probed)
    peak = total + (max(s["src"] for s in probed) if probed else 0)
    free = free_bytes()
    return {
        "total_mb": mb(total), "peak_mb": mb(peak), "free_mb": mb(free),
        "safety_mb": SAFETY_MB, "fits": mb(peak) + SAFETY_MB <= mb(free),
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
    tmp = CONFIG + ".tmp"
    with open(tmp, "w") as f:
        f.write("\n".join(lines))
    os.replace(tmp, CONFIG)


def load_sources():
    try:
        with open(SOURCES) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def library():
    """Current playlist with file sizes + capacity estimate."""
    _, songs, names = load_config()
    sources = load_sources()
    items, total = [], 0
    for i, (p, n) in enumerate(zip(songs, names)):
        size = os.path.getsize(p) if os.path.exists(p) else 0
        total += size
        fn = os.path.basename(p)
        items.append({"index": i, "file": fn, "name": n, "mb": round(mb(size), 1),
                      "missing": size == 0, "source": sources.get(fn, "")})
    free = mb(free_bytes())
    usable = max(0, free - SAFETY_MB)
    count = len(items)
    return {
        "songs": items,
        "count": count,
        "total_mb": round(mb(total), 1),
        "avg_mb": round(mb(total) / count, 1) if count else 0,
        "free_mb": round(free),
        "usable_mb": round(usable),
        "safety_mb": SAFETY_MB,
        "capacity": [{"avg_mb": s, "more": int(usable // s)} for s in CAPACITY_SIZES],
        "capacity_at_current_avg": int(usable // (mb(total) / count)) if count and total else None,
    }


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
    return out


def download(url, number, log=print):
    """Download one song as songN.mp3. Returns path or None."""
    path = os.path.join(PROJECT, f"song{number}.mp3")
    p = subprocess.Popen([YTDLP, "-x", "--audio-format", "mp3", "--no-playlist", "--no-warnings",
                          "--newline", "-o", os.path.join(PROJECT, f"song{number}.%(ext)s"), url],
                         env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    last = ""
    for line in p.stdout:
        line = line.rstrip()
        if "[download]" in line and "%" in line:
            pct = re.search(r"(\d+(?:\.\d+)?)%", line)
            if pct and pct.group(1).split(".")[0] != last:
                last = pct.group(1).split(".")[0]
                if int(float(last)) % 25 == 0:
                    log(f"    {last}%")
        elif line.startswith("ERROR"):
            log("    " + line)
    p.wait()
    return path if p.returncode == 0 and os.path.exists(path) else None


def update_readme(songs, names, sources):
    if not os.path.exists(README):
        return False
    rows = ["| # | File | Name | Source |", "|---|---|---|---|"]
    for i, (p, n) in enumerate(zip(songs, names), 1):
        fn = os.path.basename(p)
        rows.append(f"| {i} | {fn} | {n} | {sources.get(fn, '')} |")
    block = f"{README_START}\n" + "\n".join(rows) + f"\n{README_END}"
    text = open(README).read()
    if README_START not in text or README_END not in text:
        return False
    text = re.sub(re.escape(README_START) + r".*?" + re.escape(README_END),
                  lambda _: block, text, flags=re.S)
    with open(README, "w") as f:
        f.write(text)
    return True


def add_songs(items, log=print):
    """items = [(url, name)]. Downloads, updates config/README/sources. Returns added list."""
    pin, cfg_songs, cfg_names = load_config()
    if len(cfg_songs) != len(cfg_names):
        raise RuntimeError(f"config.py out of sync ({len(cfg_songs)} SONGS vs {len(cfg_names)} names)")
    sources = load_sources()
    added = []
    for (url, name), n in zip(items, next_numbers(len(items))):
        fn = f"song{n}.mp3"
        log(f"Downloading {name} -> {fn}")
        path = download(url, n, log)
        if path:
            log(f"  OK {mb(os.path.getsize(path)):.1f} MB")
            added.append((path, name))
            sources[fn] = url
        else:
            log("  X failed, skipped")
    if not added:
        return []
    shutil.copy(CONFIG, CONFIG + ".bak")
    cfg_songs += [p for p, _ in added]
    cfg_names += [n for _, n in added]
    write_config(pin, cfg_songs, cfg_names)
    with open(SOURCES, "w") as f:
        json.dump(sources, f, indent=2, ensure_ascii=False)
    update_readme(cfg_songs, cfg_names, sources)
    _, s2, n2 = load_config()
    assert len(s2) == len(n2), "config.py SONGS/SONG_NAMES mismatch after write!"
    return added


def git_push(message, log=print):
    if not os.path.isdir(os.path.join(PROJECT, ".git")):
        log("Not a git repo, skipped push")
        return False
    run = lambda *c: subprocess.run(["git", *c], cwd=PROJECT, env=ENV, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    run("pull", "--no-edit", "-q", "-X", "ours")
    run("add", "config.py", "README.md", "song_sources.json")
    run("commit", "-q", "-m", message)
    r = run("push", "-q", "origin", "HEAD")
    log("Pushed to GitHub" if r.returncode == 0 else "Push failed: " + r.stdout.strip()[-200:])
    return r.returncode == 0


# ======================================================================
# CLI
# ======================================================================
def ask(prompt, default=""):
    try:
        ans = input(prompt).strip()
    except EOFError:
        ans = ""
    return ans or default


def yes(prompt, default=True):
    a = ask(f"{prompt} [{'Y/n' if default else 'y/N'}] ").lower()
    return default if not a else a.startswith("y")


def print_library():
    lib = library()
    print(f"\nLibrary: {lib['count']} songs/stories, {lib['total_mb']} MB "
          f"(avg {lib['avg_mb']} MB each)")
    for s in lib["songs"]:
        flag = "  MISSING FILE" if s["missing"] else ""
        print(f"  {s['index'] + 1:>3}. {s['name'][:45]:<45} {s['file']:<12} {s['mb']:>5} MB{flag}")
    print(f"\nFree on SD card: {lib['free_mb']} MB  (keeping {SAFETY_MB} MB spare -> {lib['usable_mb']} MB usable)")
    print("How many more you can add:")
    for c in lib["capacity"]:
        print(f"  if they average {c['avg_mb']:>2} MB  ->  ~{c['more']:,} more")
    if lib["capacity_at_current_avg"] is not None:
        print(f"  at your current average ({lib['avg_mb']} MB) -> ~{lib['capacity_at_current_avg']:,} more")


def main():
    args = sys.argv[1:]
    print_library()
    if "--list" in args:
        return
    check_only = "--check" in args

    print("\nPaste one per line:  URL Name   (name optional). Empty line when done:")
    lines = []
    while True:
        line = ask("> ")
        if not line:
            break
        lines.append(line)
    rows, dup = split_known(parse_rows("\n".join(lines)))
    for u, n, fn in dup:
        print(f"  skip (already in library as {fn}): {n or u}")
    if not rows:
        print("No URLs given.")
        return

    if not deno_ok():
        print("! deno not found. YouTube needs it:")
        print("    sudo apt install -y unzip && curl -fsSL https://deno.land/install.sh | sh")
        if not yes("Continue anyway?", default=False):
            return
    print("Updating yt-dlp ...", flush=True)
    ok, err = update_ytdlp()
    print("  ok" if ok else f"  update failed (continuing): {err}")

    print(f"\nChecking {len(rows)} video(s) ...")
    names = dict(rows)
    probed = []
    for url, _ in rows:
        r = probe(url)
        if "error" in r:
            print(f"  X {url}\n    {r['error']}")
        else:
            r["name"] = names[url]
            probed.append(r)
    if not probed:
        print("Nothing to add.")
        return

    fc = fit_check(probed)
    print(f"\n{'#':>2}  {'Length':>6}  {'~MB':>5}  Name / YouTube title")
    for i, s in enumerate(probed, 1):
        label = s["name"] or f"(no name) {s['title']}"
        print(f"{i:>2}  {fmt_time(s['duration']):>6}  {mb(s['mp3']):5.1f}  {label[:60]}")
    print(f"\nTotal ~{fc['total_mb']:.1f} MB (peak while downloading ~{fc['peak_mb']:.1f} MB)")
    print(f"Free: {fc['free_mb']:.0f} MB (keeping {SAFETY_MB} MB spare)")
    print("OK - FITS" if fc["fits"] else "NO - DOES NOT FIT. Remove some or free up space.")
    if check_only or not fc["fits"] or not yes("\nAdd these?"):
        return

    missing = [s for s in probed if not s["name"]]
    if missing:
        print("\nName shown on the screen (Enter = keep YouTube title):")
        for s in missing:
            s["name"] = ask(f"  {s['title'][:55]}\n  name> ", default=s["title"])

    added = add_songs([(s["url"], s["name"]) for s in probed])
    if not added:
        print("\nNothing downloaded; nothing changed.")
        return
    print(f"\nOK Added {len(added)}.")
    print_library()

    if yes("\nCommit + push to GitHub?"):
        git_push("Add songs: " + ", ".join(n for _, n in added))
    if yes("\nRestart the player now so the button picks up the new songs?"):
        restart_player()
    else:
        print("New songs load on next restart (sudo reboot).")


def restart_player():
    """Stop play_song.py and start it again via start_music_player.sh (no reboot).
    On V2 (v2/.enabled exists) the kids app just reloads its song list."""
    if os.path.exists(os.path.join(PROJECT, "v2", ".enabled")):
        import musicstate
        musicstate.send_cmd("reload")
        print("V2 app reloaded the song list.")
        return
    subprocess.run(["pkill", "-f", "play_song.py"])
    import time
    time.sleep(2)
    subprocess.Popen(["/bin/bash", os.path.join(PROJECT, "start_music_player.sh")],
                     cwd=PROJECT, start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Player restarted.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
