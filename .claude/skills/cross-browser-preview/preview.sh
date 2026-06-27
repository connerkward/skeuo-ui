#!/usr/bin/env bash
# Cross-browser screenshot runner. Snapshots a URL in Chromium and WebKit
# (Safari/iOS engine) at desktop, medium, and iPhone viewports using Playwright.
#
# Usage:
#   bash ~/dev/central/skills/cross-browser-preview/preview.sh                       # http://localhost:4747/
#   bash ~/dev/central/skills/cross-browser-preview/preview.sh https://example.com/
#   bash ~/dev/central/skills/cross-browser-preview/preview.sh /projects/bas/        # → http://localhost:4747/projects/bas/
#
# Outputs PNGs to ./scripts/.preview/<timestamp>/ in the CURRENT WORKING
# DIRECTORY (so each project has its own history). Opens the folder when done.

set -euo pipefail

URL_INPUT="${1:-http://localhost:4747/}"
case "$URL_INPUT" in
  http*) URL="$URL_INPUT" ;;
  /*)    URL="http://localhost:4747${URL_INPUT}" ;;
  *)     URL="http://localhost:4747/${URL_INPUT}" ;;
esac

TS="$(date +%Y%m%d-%H%M%S)"
OUT="scripts/.preview/$TS"
mkdir -p "$OUT"

# name | engine | width | height
VPS=(
  "chromium-wide|chromium|1600|900"
  "chromium-desktop|chromium|1280|800"
  "chromium-medium|chromium|900|800"
  "chromium-narrow|chromium|600|900"
  "webkit-wide|webkit|1600|900"
  "webkit-desktop|webkit|1280|800"
  "webkit-medium|webkit|900|800"
  "webkit-iphone|webkit|393|852"
)

echo "→ $URL"

# Ensure browsers are installed (no-op if already present)
npx -y playwright install --with-deps webkit chromium >/dev/null 2>&1 || true

for vp in "${VPS[@]}"; do
  IFS='|' read -r name engine w h <<< "$vp"
  out="$OUT/$name.png"
  echo "   $name  ($engine, ${w}x${h})  → $out"
  npx -y playwright screenshot \
    --browser="$engine" \
    --viewport-size="${w},${h}" \
    --wait-for-timeout=900 \
    --full-page \
    "$URL" "$out" >/dev/null 2>&1
done

echo
echo "✓ done: $OUT"
ls -lh "$OUT" | awk 'NR>1 {printf "  %-32s  %s\n", $9, $5}'

# Note: NOT opening Finder. Read screenshots inline (Claude Read tool),
# and `rm -rf scripts/.preview` once the verification work is finished.
