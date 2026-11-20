#!/usr/bin/env python3
"""
portal.py - web portal for the music button.

    python3 portal.py              # run on port 8080 -> http://tiagosmusicbox.local:8080
    python3 portal.py --install    # also start it automatically at every boot (crontab)

Shows what is playing (with a live mirror of the OLED screen and LEDs), lets you
play / skip / stop, lists the library with sizes and free space, and adds new
songs/stories from "URL Name" rows (same engine as add_songs.py).
Only Python's standard library is used. Anyone on your home Wi-Fi can open it.
"""
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import add_songs as lib
import musicstate

PORT = int(os.environ.get("PORTAL_PORT", "8080"))
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- jobs
JOB = {"id": 0, "kind": None, "running": False, "log": [], "result": None, "error": None}
JOB_LOCK = threading.Lock()


def start_job(kind, fn, *args):
    with JOB_LOCK:
        if JOB["running"]:
            return False
        JOB.update(id=JOB["id"] + 1, kind=kind, running=True, log=[], result=None, error=None)

    def log(msg):
        JOB["log"].append(str(msg))

    def runner():
        try:
            JOB["result"] = fn(log, *args)
        except Exception as e:
            JOB["error"] = str(e)
            log(f"ERROR: {e}")
        finally:
            JOB["running"] = False
    threading.Thread(target=runner, daemon=True).start()
    return True


def job_check(log, text):
    rows, dup = lib.split_known(lib.parse_rows(text))
    for u, n, fn in dup:
        log(f"Skip (already in library as {fn}): {n or u}")
    if not rows:
        raise ValueError("No new YouTube URLs found")
    if not lib.deno_ok():
        log("Warning: deno not installed, YouTube downloads will likely fail")
    log("Updating yt-dlp ...")
    ok, err = lib.update_ytdlp()
    log("  ok" if ok else f"  update failed (continuing): {err}")
    probed, failed = [], []
    for i, (url, name) in enumerate(rows, 1):
        log(f"Checking {i}/{len(rows)}: {name or url}")
        r = lib.probe(url)
        if "error" in r:
            log(f"  X {r['error']}")
            failed.append(r)
        else:
            r["name"] = name or r["title"]
            r["mp3_mb"] = round(lib.mb(r["mp3"]), 1)
            r["length"] = lib.fmt_time(r["duration"])
            log(f"  OK {r['length']}  ~{r['mp3_mb']} MB")
            probed.append(r)
    fit = lib.fit_check(probed) if probed else None
    if fit:
        log("FITS" if fit["fits"] else "DOES NOT FIT")
    return {"probed": probed, "failed": failed, "fit": fit}


def job_add(log, items, push):
    added = lib.add_songs([(i["url"], i["name"]) for i in items], log)
    if not added:
        log("Nothing downloaded; nothing changed.")
        return {"added": 0}
    log(f"Added {len(added)}. Updated config.py, README.md, song_sources.json")
    if push:
        lib.git_push("Add songs: " + ", ".join(n for _, n in added), log)
    log("Restarting player ...")
    restart_player()
    log("Done.")
    return {"added": len(added)}


# ---------------------------------------------------------------- player
def player_status():
    st = musicstate.read() or {}
    alive = False
    pid = st.get("pid")
    if pid:
        try:
            os.kill(pid, 0)
            alive = True
        except OSError:
            alive = False
    st["alive"] = alive
    if st.get("playing") and st.get("started"):
        st["elapsed"] = int(time.time() - st["started"])
    return st


def restart_player():
    subprocess.run(["pkill", "-f", "play_song.py"])
    for _ in range(30):
        if subprocess.run(["pgrep", "-f", "play_song.py"], stdout=subprocess.DEVNULL).returncode:
            break
        time.sleep(0.2)
    subprocess.run(["pkill", "-9", "mpv"])
    subprocess.Popen(["/bin/bash", os.path.join(HERE, "start_music_player.sh")], cwd=HERE,
                     start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------------------------------------------------------------- http
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        if not isinstance(body, (bytes, bytearray)):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            self.send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif path == "/api/state":
            self.send(200, {"player": player_status(),
                            "job": {k: JOB[k] for k in ("id", "kind", "running", "error")}
                                   | {"log_len": len(JOB["log"])}})
        elif path == "/api/library":
            try:
                self.send(200, lib.library())
            except Exception as e:
                self.send(500, {"error": str(e)})
        elif path == "/api/job":
            self.send(200, JOB)
        elif path == "/oled.png":
            try:
                with open(musicstate.OLED, "rb") as f:
                    self.send(200, f.read(), "image/png")
            except FileNotFoundError:
                self.send(404, {"error": "no frame yet"})
        else:
            self.send(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            data = self.body()
        except ValueError:
            return self.send(400, {"error": "bad json"})
        if path == "/api/cmd":
            cmd = str(data.get("cmd", ""))
            if cmd in ("next", "stop") or (cmd.startswith("play ") and cmd[5:].isdigit()):
                musicstate.send_cmd(cmd)
                return self.send(200, {"ok": True})
            return self.send(400, {"error": "bad cmd"})
        if path == "/api/restart":
            threading.Thread(target=restart_player, daemon=True).start()
            return self.send(200, {"ok": True})
        if path == "/api/check":
            ok = start_job("check", job_check, data.get("text", ""))
            return self.send(200 if ok else 409, {"ok": ok, "error": None if ok else "busy"})
        if path == "/api/add":
            items = [i for i in data.get("items", []) if i.get("url") and i.get("name")]
            if not items:
                return self.send(400, {"error": "nothing to add"})
            ok = start_job("add", job_add, items, bool(data.get("push")))
            return self.send(200 if ok else 409, {"ok": ok, "error": None if ok else "busy"})
        self.send(404, {"error": "not found"})


def install_cron():
    line = f"@reboot sleep 15 && /usr/bin/python3 {os.path.abspath(__file__)} --serve >> {HERE}/portal.log 2>&1"
    cur = subprocess.run(["crontab", "-l"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout
    if "portal.py" in cur:
        print("Already in crontab.")
        return
    subprocess.run(["crontab", "-"], input=cur.rstrip("\n") + "\n" + line + "\n", text=True, check=True)
    print("Added to crontab: portal starts at every boot.")


PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tiago's Music Box</title>
<style>
:root{--bg:#0f1220;--card:#171b2e;--line:#262b45;--txt:#e8eaf6;--mut:#8b90b3;--acc:#5b8cff;--ok:#2ecc71;--bad:#ff5c6c;--warn:#f5c542}
*{box-sizing:border-box}body{margin:0;font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--txt)}
header{display:flex;align-items:center;gap:12px;padding:16px 22px;border-bottom:1px solid var(--line)}
header h1{font-size:19px;margin:0;font-weight:650}.pill{font-size:12px;padding:3px 10px;border-radius:99px;background:#222842;color:var(--mut)}
.pill.on{background:rgba(46,204,113,.15);color:var(--ok)}.pill.off{background:rgba(255,92,108,.15);color:var(--bad)}
main{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:18px;padding:18px 22px;max-width:1250px;margin:auto}
@media(max-width:900px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}
.card h2{margin:0 0 12px;font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);font-weight:600}
.now{display:flex;gap:22px;align-items:center;flex-wrap:wrap}
.oled{background:#000;border-radius:10px;padding:10px;border:2px solid #2a2f4d;box-shadow:inset 0 0 18px rgba(91,140,255,.12)}
.oled img{display:block;width:384px;max-width:100%;height:auto;image-rendering:pixelated;filter:drop-shadow(0 0 2px rgba(140,190,255,.7)) sepia(1) hue-rotate(170deg) saturate(3) brightness(1.15)}
.title{font-size:22px;font-weight:650;margin:2px 0}.sub{color:var(--mut);font-size:13px}
.leds{display:flex;gap:9px;margin:16px 0 4px}.led{width:20px;height:20px;border-radius:50%;opacity:.18;transition:opacity .08s,box-shadow .08s}
.led.g{background:#2ecc71}.led.y{background:#f5c542}.led.r{background:#ff4d4d}.led.on{opacity:1;box-shadow:0 0 12px currentColor}
.led.g.on{color:#2ecc71}.led.y.on{color:#f5c542}.led.r.on{color:#ff4d4d}
.btns{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}
button{font:inherit;border:1px solid var(--line);background:#20253d;color:var(--txt);padding:8px 14px;border-radius:9px;cursor:pointer}
button:hover{border-color:var(--acc)}button.pri{background:var(--acc);border-color:var(--acc);color:#fff}button:disabled{opacity:.45;cursor:default}
table{width:100%;border-collapse:collapse}td,th{padding:7px 6px;border-bottom:1px solid var(--line);text-align:left;font-size:14px}
th{color:var(--mut);font-weight:500;font-size:12px}td.n{color:var(--mut);width:32px}td.mb{text-align:right;color:var(--mut);white-space:nowrap}
tr.cur td{background:rgba(91,140,255,.12)}tr.cur td:nth-child(2){font-weight:650;color:#fff}
.play{padding:2px 9px;font-size:12px}.miss{color:var(--bad);font-size:12px}
.lib{max-height:430px;overflow:auto}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px}
.stat{background:#1d2238;border-radius:10px;padding:10px 12px}.stat b{display:block;font-size:20px}.stat span{color:var(--mut);font-size:12px}
.cap{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}.cap div{background:#1d2238;border-radius:10px;padding:8px;text-align:center}
.cap b{display:block;font-size:17px}.cap span{font-size:11px;color:var(--mut)}
textarea{width:100%;min-height:120px;background:#0f1324;color:var(--txt);border:1px solid var(--line);border-radius:10px;padding:10px;font:13px ui-monospace,Menlo,Consolas,monospace}
input.nm{width:100%;background:#0f1324;color:var(--txt);border:1px solid var(--line);border-radius:7px;padding:5px 7px;font:inherit}
.log{background:#0b0e1a;border-radius:10px;padding:10px;font:12px/1.5 ui-monospace,Menlo,Consolas,monospace;color:#a9b0d6;max-height:220px;overflow:auto;white-space:pre-wrap;margin-top:12px}
.verdict{margin:12px 0;padding:10px 12px;border-radius:10px;font-weight:600}.verdict.ok{background:rgba(46,204,113,.12);color:var(--ok)}.verdict.no{background:rgba(255,92,108,.12);color:var(--bad)}
.full{grid-column:1/-1}.hide{display:none}.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:10px}
label{color:var(--mut);font-size:13px}
</style></head><body>
<header><h1>🎵 Tiago's Music Box</h1><span id="pill" class="pill">connecting…</span></header>
<main>
 <section class="card">
  <h2>Now playing</h2>
  <div class="now">
   <div class="oled"><img id="oled" alt="OLED screen" width="128" height="64"></div>
   <div>
    <div class="sub" id="pos">—</div>
    <div class="title" id="name">Nothing playing</div>
    <div class="sub" id="elapsed"></div>
    <div class="leds" id="leds"></div>
   </div>
  </div>
  <div class="btns">
   <button class="pri" onclick="cmd('next')">⏭ Next (like the button)</button>
   <button onclick="cmd('stop')">⏹ Stop</button>
   <button onclick="restart()">↻ Restart player</button>
  </div>
 </section>

 <section class="card">
  <h2>Storage</h2>
  <div class="stats">
   <div class="stat"><b id="sCount">–</b><span>songs &amp; stories</span></div>
   <div class="stat"><b id="sTotal">–</b><span>library size</span></div>
   <div class="stat"><b id="sFree">–</b><span>free on SD card</span></div>
  </div>
  <div class="sub" style="margin-bottom:8px">How many more fit (keeping <span id="sSafe"></span> MB spare), by average size each:</div>
  <div class="cap" id="cap"></div>
  <div class="sub" id="capAvg" style="margin-top:8px"></div>
 </section>

 <section class="card">
  <h2>Library</h2>
  <div class="lib"><table><thead><tr><th>#</th><th>Name</th><th style="text-align:right">Size</th><th></th></tr></thead><tbody id="lib"></tbody></table></div>
 </section>

 <section class="card">
  <h2>Add songs &amp; stories</h2>
  <div class="sub">One per line: <code>YouTube-URL Name</code></div>
  <textarea id="rows" placeholder="https://www.youtube.com/watch?v=abc123 Leaf Thief&#10;https://www.youtube.com/watch?v=def456 Snow Thief"></textarea>
  <div class="row"><button class="pri" id="bCheck" onclick="check()">Check size &amp; space</button><span class="sub" id="jobmsg"></span></div>
  <div id="checkOut" class="hide">
   <div id="verdict" class="verdict"></div>
   <table><thead><tr><th>Name on screen</th><th>Length</th><th style="text-align:right">~Size</th></tr></thead><tbody id="probed"></tbody></table>
   <div class="row"><button class="pri" id="bAdd" onclick="add()">Download &amp; add</button>
    <label><input type="checkbox" id="push" checked> push to GitHub</label></div>
  </div>
  <div class="log hide" id="log"></div>
 </section>
</main>
<script>
const $=id=>document.getElementById(id);
const COLORS=['g','g','g','g','y','y','r','r'];
let lastOled=-1,lastJob=0,curIndex=null,lastAlive=null,checkResult=null;
$('leds').innerHTML=COLORS.map(c=>`<div class="led ${c}"></div>`).join('');
const api=(p,b)=>fetch(p,b?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}:{}).then(r=>r.json());
const fmt=s=>`${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

async function tick(){
 try{
  const s=await api('/api/state'),p=s.player;
  $('pill').textContent=p.alive?(p.playing?'▶ playing':'● ready'):'player not running';
  $('pill').className='pill '+(p.alive?'on':'off');
  if(p.oled_v!==lastOled){lastOled=p.oled_v;$('oled').src='/oled.png?v='+p.oled_v;}
  [...$('leds').children].forEach((d,i)=>d.classList.toggle('on',!!(p.leds||[])[i]));
  $('name').textContent=p.playing?p.name:(p.name?p.name+' (stopped)':'Nothing playing');
  $('pos').textContent=p.index!=null?`#${p.index+1} of ${p.count||'?'}`:'—';
  $('elapsed').textContent=p.playing&&p.elapsed!=null?'⏱ '+fmt(p.elapsed):'';
  if(p.index!==curIndex){curIndex=p.index;markCurrent();}
  if(lastAlive===false&&p.alive)loadLib();lastAlive=p.alive;
  if(s.job.id&&(s.job.running||s.job.id!==lastJob))pollJob();
 }catch(e){$('pill').textContent='portal offline';$('pill').className='pill off';}
}
function markCurrent(){document.querySelectorAll('#lib tr').forEach((tr,i)=>tr.classList.toggle('cur',i===curIndex));}
async function loadLib(){
 const L=await api('/api/library');
 $('sCount').textContent=L.count;$('sTotal').textContent=L.total_mb+' MB';
 $('sFree').textContent=(L.free_mb/1024).toFixed(1)+' GB';$('sSafe').textContent=L.safety_mb;
 $('cap').innerHTML=L.capacity.map(c=>`<div><b>${c.more.toLocaleString()}</b><span>@ ${c.avg_mb} MB</span></div>`).join('');
 $('capAvg').textContent=L.capacity_at_current_avg!=null?`At your current average (${L.avg_mb} MB): ~${L.capacity_at_current_avg.toLocaleString()} more`:'';
 $('lib').innerHTML=L.songs.map(s=>`<tr><td class="n">${s.index+1}</td><td>${esc(s.name)}${s.missing?' <span class="miss">missing file</span>':''}${s.source?` <a href="${esc(s.source)}" target="_blank" style="color:var(--mut);text-decoration:none">↗</a>`:''}</td><td class="mb">${s.mb} MB</td><td><button class="play" onclick="cmd('play ${s.index}')">▶</button></td></tr>`).join('');
 markCurrent();
}
function cmd(c){api('/api/cmd',{cmd:c});}
function restart(){api('/api/restart',{});$('pill').textContent='restarting…';}
async function check(){
 const r=await api('/api/check',{text:$('rows').value});
 if(!r.ok){$('jobmsg').textContent=r.error;return;}
 $('checkOut').classList.add('hide');checkResult=null;pollJob();
}
async function add(){
 const items=checkResult.probed.map((p,i)=>({url:p.url,name:document.querySelectorAll('#probed input')[i].value.trim()||p.title}));
 const r=await api('/api/add',{items,push:$('push').checked});
 if(!r.ok){$('jobmsg').textContent=r.error;return;}
 $('bAdd').disabled=true;pollJob();
}
async function pollJob(){
 const j=await api('/api/job');lastJob=j.id;
 $('log').classList.remove('hide');$('log').textContent=j.log.join('\n');$('log').scrollTop=1e9;
 $('bCheck').disabled=j.running;$('jobmsg').textContent=j.running?(j.kind==='add'?'Downloading…':'Checking…'):'';
 if(j.running)return;
 if(j.kind==='check'&&j.result&&!checkResult){
  checkResult=j.result;const f=j.result.fit;
  $('probed').innerHTML=j.result.probed.map(p=>`<tr><td><input class="nm" value="${esc(p.name)}"></td><td>${p.length}</td><td class="mb">${p.mp3_mb} MB</td></tr>`).join('');
  if(f){$('verdict').className='verdict '+(f.fits?'ok':'no');
   $('verdict').textContent=(f.fits?'✅ Fits: ':'❌ Does not fit: ')+`~${f.total_mb.toFixed(1)} MB needed, ${Math.round(f.free_mb)} MB free`+(j.result.failed.length?` · ${j.result.failed.length} link(s) failed`:'');
   $('bAdd').disabled=!f.fits;$('checkOut').classList.remove('hide');}
 }
 if(j.kind==='add'&&j.result){$('bAdd').disabled=false;$('checkOut').classList.add('hide');$('rows').value='';loadLib();}
}
loadLib();tick();setInterval(tick,300);setInterval(loadLib,15000);
</script></body></html>
"""


def main():
    if "--install" in sys.argv:
        install_cron()
        subprocess.run(["pkill", "-f", "portal.py --serve"])
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "--serve"], cwd=HERE,
                         start_new_session=True, stdout=open(os.path.join(HERE, "portal.log"), "a"),
                         stderr=subprocess.STDOUT)
        print(f"Portal running: http://{os.uname().nodename}.local:{PORT}")
        return
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Portal on http://{os.uname().nodename}.local:{PORT}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
