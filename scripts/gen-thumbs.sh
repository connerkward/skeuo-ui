#!/usr/bin/env bash
# Generate small WebP thumbnails of each skin's frame for the mobile filmstrip.
# The full frame.png is 2–5 MB; the strip shows dozens of ~56px minis, so loading
# full frames is catastrophically slow. A 256px WebP is ~5–15 KB and plenty for a
# thumbnail. Run from the repo root: scripts/gen-thumbs.sh
set -euo pipefail
cd "$(dirname "$0")/.."
n=0
for f in public/skins/*/frame.png; do
  dir="$(dirname "$f")"
  out="$dir/thumb.webp"
  magick "$f" -resize 256x -quality 82 -define webp:method=6 "$out"
  n=$((n+1))
done
echo "generated $n thumbnails"
du -ch public/skins/*/thumb.webp | tail -1
