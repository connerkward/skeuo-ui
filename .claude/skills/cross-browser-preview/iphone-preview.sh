#!/usr/bin/env bash
# Boot iOS Simulator → open Safari → screenshot. Closer to real iPhone Safari
# than Playwright WebKit. Requires full Xcode install (not Command Line Tools).
#
# Usage:
#   bash ~/dev/central/skills/cross-browser-preview/iphone-preview.sh
#   bash ~/dev/central/skills/cross-browser-preview/iphone-preview.sh https://example.com/
#   bash ~/dev/central/skills/cross-browser-preview/iphone-preview.sh /me/
#
# Outputs to ./scripts/.preview-iphone/<timestamp>.png in cwd.

set -euo pipefail

# Auto-detect Xcode without requiring sudo xcode-select. If full Xcode.app is
# present but xcode-select still points at CommandLineTools, route around it.
if [ -d /Applications/Xcode.app/Contents/Developer ]; then
  export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
elif command -v xcode-select >/dev/null 2>&1; then
  CUR_DEV="$(xcode-select -p 2>/dev/null || true)"
  if [ -n "$CUR_DEV" ] && [ -d "$CUR_DEV/Applications/Simulator.app" ]; then
    export DEVELOPER_DIR="$CUR_DEV"
  fi
fi

if ! command -v xcrun >/dev/null 2>&1; then
  echo "ERROR: xcrun not on PATH. Install full Xcode from the Mac App Store."
  exit 1
fi

probe=$(xcrun simctl list devicetypes 2>&1 || true)
if echo "$probe" | grep -qi 'license'; then
  cat <<'EOF'
ERROR: Xcode license not accepted yet (one-time, requires sudo).

Run this once, then re-invoke the script:
  sudo xcodebuild -license accept

(Or interactively review/agree:  sudo xcodebuild -license)
EOF
  exit 1
fi
if ! echo "$probe" | grep -q 'iPhone'; then
  cat <<EOF
ERROR: simctl unavailable. Install full Xcode (Mac App Store, ~12 GB).
If installed but xcode-select still points at CommandLineTools, this script
auto-detects /Applications/Xcode.app — make sure that folder exists.

Or fall back to Playwright WebKit (same engine as Safari):
  bash ~/dev/central/skills/cross-browser-preview/preview.sh "\$URL"
EOF
  exit 1
fi

# Xcode 16+ ships without an iOS simulator runtime; user must download once.
RUNTIMES="$(xcrun simctl list runtimes 2>&1 || true)"
if ! echo "$RUNTIMES" | grep -qi 'iOS'; then
  cat <<'EOF'
ERROR: no iOS simulator runtime installed.

Xcode 16+ ships without one. Download it once (~6–10 GB):

  sudo /Applications/Xcode.app/Contents/Developer/usr/bin/xcodebuild -downloadPlatform iOS

…or do it via Xcode → Settings → Platforms → iOS (Get).
EOF
  exit 1
fi

URL_INPUT="${1:-http://localhost:4747/}"
case "$URL_INPUT" in
  http*) URL="$URL_INPUT" ;;
  /*)    URL="http://localhost:4747${URL_INPUT}" ;;
  *)     URL="http://localhost:4747/${URL_INPUT}" ;;
esac

# Pick device set: by default capture three common iPhones. Override with the
# second argument as a comma-separated list of device names.
DEVICE_NAMES_INPUT="${2:-iPhone 16e,iPhone 16,iPhone 16 Pro Max}"
IFS=',' read -ra WANTED <<< "$DEVICE_NAMES_INPUT"

# Discover available UDIDs that match the wanted names (newest runtime wins).
discover() {
  local target="$1"
  xcrun simctl list devices available -j 2>/dev/null | python3 -c "
import json, sys
target = sys.argv[1]
data = json.load(sys.stdin)
hits = []
for runtime, devs in data['devices'].items():
    if 'iOS' not in runtime: continue
    for d in devs:
        if d.get('isAvailable') and d['name'] == target:
            hits.append((runtime, d['udid']))
hits.sort(reverse=True)
print(hits[0][1] if hits else '')
" "$target"
}

TS="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="scripts/.preview-iphone/$TS"
mkdir -p "$OUT_DIR"

echo "→ url: $URL"

CAPTURED=0
for NAME in "${WANTED[@]}"; do
  NAME_TRIM="$(echo "$NAME" | sed -E 's/^ +//;s/ +$//')"
  DEVICE_ID="$(discover "$NAME_TRIM")"
  if [ -z "$DEVICE_ID" ]; then
    echo "   skip: $NAME_TRIM (no available simulator with that name)"
    continue
  fi

  SAFE="$(echo "$NAME_TRIM" | python3 -c "import sys,re; print(re.sub(r'[^a-z0-9]+','-',sys.stdin.read().strip().lower()).strip('-'))")"
  OUT="$OUT_DIR/$SAFE.png"

  echo "   $NAME_TRIM  ($DEVICE_ID)  → $OUT"

  xcrun simctl boot "$DEVICE_ID" 2>/dev/null || true
  open -a Simulator >/dev/null 2>&1
  sleep 2

  # Pre-warm Safari so we don't catch the privacy/new-tab splash
  xcrun simctl launch "$DEVICE_ID" com.apple.mobilesafari >/dev/null 2>&1 || true
  sleep 2
  xcrun simctl openurl "$DEVICE_ID" "$URL"
  sleep 10

  xcrun simctl io "$DEVICE_ID" screenshot "$OUT" 2>&1 | grep -v 'Detected file type' || true
  CAPTURED=$((CAPTURED + 1))

  # Shut down to free RAM; the next iteration will boot the next one
  xcrun simctl shutdown "$DEVICE_ID" 2>/dev/null || true
done

if [ "$CAPTURED" -eq 0 ]; then
  echo
  echo "ERROR: no screenshots captured. List installed devices with:"
  echo "  xcrun simctl list devices available | grep iPhone"
  exit 1
fi

echo
echo "✓ $OUT_DIR  ($CAPTURED screenshots)"
# Note: NOT opening Finder. Read screenshots inline (Claude Read tool),
# and `rm -rf scripts/.preview-iphone` once the verification work is finished.
