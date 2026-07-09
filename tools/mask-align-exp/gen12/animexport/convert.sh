#!/bin/bash
# convert.sh <framesRoot> <outDir> — numbered-PNG frame dirs (frames-<name>/%05d.png,
# emitted by record.mjs / record_pbr.mjs stepped capture) → H.264 mp4 (30fps,
# crf15 slow, yuv420p, faststart) + a poster PNG per video (~40% in: mid-motion,
# caption on screen, never the loading frame).
set -euo pipefail
REC="$1"; OUT="$2"; mkdir -p "$OUT"
FFMPEG="${FFMPEG:-$HOME/.local/bin/ffmpeg-static}"
command -v "$FFMPEG" >/dev/null 2>&1 || FFMPEG=ffmpeg
for d in "$REC"/frames-*; do
  [ -d "$d" ] || continue
  name=$(basename "$d"); name=${name#frames-}
  "$FFMPEG" -y -loglevel error -framerate 30 -i "$d/%05d.png" \
    -c:v libx264 -crf 15 -preset slow -pix_fmt yuv420p -movflags +faststart \
    "$OUT/$name.mp4"
  count=$(ls "$d" | grep -c '\.png$')
  poster=$(printf "%05d" $(( count * 2 / 5 )))
  cp "$d/$poster.png" "$OUT/$name-poster.png"
  echo "$name.mp4  $count frames"
done
