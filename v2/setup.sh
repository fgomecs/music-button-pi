#!/bin/bash
# setup.sh - one-time setup for Tiago's Music Box V2 (Pi 3 + Waveshare 4.3" DSI touch + camera).
#
#   cd ~/music-button-pi && git pull && bash v2/setup.sh
#
# Safe to run again. It never changes V1: songs are only COPIED from V1 over Wi-Fi.
set -e
V1_IP="${V1_IP:-192.168.50.202}"
P="$HOME/music-button-pi"
CFG=/boot/firmware/config.txt
[ -f "$CFG" ] || CFG=/boot/config.txt
step() { echo; echo "==> $*"; }

step "1/7 Updating code"
cd "$P" && git pull --no-edit -q || echo "   (git pull skipped)"

step "2/7 Installing packages"
sudo apt-get update -qq
sudo apt-get install -y -qq git mpv ffmpeg python3-pygame python3-pil python3-venv python3-pip unzip
sudo apt-get install -y -qq --no-install-recommends python3-picamera2

step "3/7 yt-dlp + deno (for adding songs)"
[ -x "$HOME/yt-dlp-venv/bin/yt-dlp" ] || python3 -m venv "$HOME/yt-dlp-venv"
"$HOME/yt-dlp-venv/bin/pip" install -q -U "yt-dlp[default]"
if ! command -v deno >/dev/null && [ ! -x "$HOME/.deno/bin/deno" ]; then
  curl -fsSL https://deno.land/install.sh | sh -s -- -y >/dev/null || echo "   deno install failed (retry later)"
fi

step "4/7 Screen: Waveshare 4.3\" DSI"
if ! grep -q "vc4-kms-dsi-waveshare-panel" "$CFG"; then
  echo "dtoverlay=vc4-kms-dsi-waveshare-panel,4_3_inch" | sudo tee -a "$CFG" >/dev/null
  echo "   added overlay to $CFG"
else
  echo "   already set"
fi
sudo raspi-config nonint do_blanking 1 2>/dev/null || true   # never blank the screen

step "5/7 Songs from V1 ($V1_IP) - read only, V1 is not changed"
if ls "$P"/song*.mp3 >/dev/null 2>&1; then
  echo "   songs already here ($(ls "$P"/song*.mp3 | wc -l) files) - skipping"
else
  read -r -p "   Copy songs from V1 now? You'll type V1's password. [Y/n] " a
  if [ "${a,,}" != "n" ]; then
    scp "tiago@$V1_IP:/home/tiago/music-button-pi/song*.mp3" \
        "tiago@$V1_IP:/home/tiago/music-button-pi/config.py" \
        "tiago@$V1_IP:/home/tiago/music-button-pi/song_sources.json" "$P/" \
      && echo "   copied $(ls "$P"/song*.mp3 | wc -l) songs" \
      || echo "   copy failed - run again later: bash v2/setup.sh"
  fi
fi
python3 -c "import sys; sys.path.insert(0,'$P'); import config; print(f'   library: {len(config.SONGS)} songs / {len(config.SONG_NAMES)} names')"

step "6/7 Kids app starts at boot"
touch "$P/v2/.enabled"
[ -f "$P/v2/settings.json" ] || echo '{"lang": "en", "video_unlocked": false, "volume": 90, "mpv_args": []}' > "$P/v2/settings.json"
mkdir -p "$HOME/.config/autostart" "$HOME/Pictures/kidbox"
cat > "$HOME/.config/autostart/kidbox.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=KidBox
Exec=/bin/bash -c "sleep 3; /usr/bin/python3 $P/v2/kidbox.py >> $P/v2/kidbox.log 2>&1"
X-GNOME-Autostart-enabled=true
EOF
echo "   autostart: ~/.config/autostart/kidbox.desktop"
# make sure the desktop logs in automatically
sudo raspi-config nonint do_boot_behaviour B4 2>/dev/null || true

step "7/7 Web portal (port 8080)"
python3 "$P/portal.py" --install

IP=$(hostname -I | awk '{print $1}')
echo
echo "Done!  Portal: http://$IP:8080"
echo "Reboot to start the kids app on the touchscreen:  sudo reboot"
