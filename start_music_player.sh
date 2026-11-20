#!/bin/bash
# Wait for system to stabilize
sleep 1

# Paths
PYTHON="/home/tiago/yt-dlp-venv/bin/python3"
SCRIPT="/home/tiago/music-button-pi/play_song.py"
LOG="/home/tiago/music-button-pi/music_player.log"

# Log start time
echo "Starting music player at $(date)" >> $LOG

# Run the script
$PYTHON $SCRIPT >> $LOG 2>&1
