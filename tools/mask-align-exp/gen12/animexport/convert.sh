#!/bin/bash
# convert.sh <recDir> <outDir> — Playwright .webm → shareable H.264 mp4 (30fps,
# yuv420p for universal playback) + a poster PNG per video (~30% in: the algorithm
# is visibly mid-sweep with a phase caption on screen, not the loading frame).
set -euo pipefail
REC="$1"; OUT="$2"; mkdir -p "$OUT"
for f in "$REC"/*.webm; do
  name=$(basename "$f" .webm)
  ffmpeg -y -loglevel error -i "$f" -r 30 -c:v libx264 -crf 18 -preset medium \
         -pix_fmt yuv420p -movflags +faststart "$OUT/$name.mp4"
  dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/$name.mp4")
  ffmpeg -y -loglevel error -ss "$(echo "$dur * 0.3" | bc)" -i "$OUT/$name.mp4" \
         -frames:v 1 "$OUT/$name-poster.png"
  echo "$name.mp4  ${dur}s"
done
