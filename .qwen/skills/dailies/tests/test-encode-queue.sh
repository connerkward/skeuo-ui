#!/usr/bin/env bash
# Smoke test for encode-queue.sh.
#
# Synthesises a fake scratch dir (solid-color JPEG frames + valid
# scene-timestamps.json), points the queue at a temp $DAILIES_DIR, runs
# `encode`, then asserts:
#   - exactly one mp4 produced per scene
#   - each mp4 plays and has the expected duration (frameCount / fps ± 0.5s)
#   - INDEX.md was created and got one row per scene
#   - the scratch dir was trashed (not present anymore)
#   - queue list reports empty after
#
# Also exercises `share-h264` if the videotoolbox encoder is available
# (Apple Silicon / Intel with VideoToolbox).
#
# Run: bash ~/dev/central/skills/dailies/tests/test-encode-queue.sh
# Exit 0 on success, non-zero on first failed assertion.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUEUE="$HERE/../encode-queue.sh"
[[ -x "$QUEUE" ]] || { echo "encode-queue.sh not found at $QUEUE" >&2; exit 2; }

command -v ffmpeg >/dev/null || { echo "ffmpeg required" >&2; exit 2; }
command -v jq     >/dev/null || { echo "jq required"     >&2; exit 2; }

PASS=0
FAIL=0
trap 'echo; echo "=== summary: $PASS pass, $FAIL fail ==="; [[ $FAIL -eq 0 ]] || exit 1' EXIT

assert() {
  local label="$1"; shift
  if "$@"; then
    PASS=$((PASS+1))
    printf '  ✓ %s\n' "$label"
  else
    FAIL=$((FAIL+1))
    printf '  ✗ %s\n' "$label"
  fi
}

# --- sandbox setup -----------------------------------------------------------
SANDBOX="$(mktemp -d -t dailies-test.XXXXXX)"
SCRATCH_ROOT="$SANDBOX/scratch"
DAILIES_DIR="$SANDBOX/dailies"
mkdir -p "$SCRATCH_ROOT" "$DAILIES_DIR"
SCRATCH="$SCRATCH_ROOT/$(date +%Y-%m-%d-%H%M%S)"
mkdir -p "$SCRATCH/frames"

# Patch the queue's SCRATCH_ROOTS array for this run by forcing a wrapper env.
# encode-queue.sh hardcodes the roots, so we monkey-patch by editing a copy.
QUEUE_PATCHED="$SANDBOX/encode-queue.sh"
sed -e "s|\$HOME/Desktop/dailies-scratch|$SCRATCH_ROOT|" \
    -e "s|\$HOME/.scratch/dailies|$SCRATCH_ROOT/.alt|" \
    "$QUEUE" > "$QUEUE_PATCHED"
chmod +x "$QUEUE_PATCHED"

# --- frame synthesis ---------------------------------------------------------
# 3 scenes, 10 frames each at 30 fps → ~1/3 s each. Use ffmpeg lavfi to make
# solid-color JPEGs with scene number burned in (text helps if anyone opens
# the mp4 by hand).
FPS=30
PER=10
SCENES=("alpha" "beta" "gamma")
COLORS=("0x553333" "0x335533" "0x333355")

idx=0
ts_entries=""
for i in 0 1 2; do
  slug="${SCENES[$i]}"
  color="${COLORS[$i]}"
  start=$idx
  for ((f=0; f<PER; f++)); do
    out=$(printf '%s/frames/frame-%06d.jpg' "$SCRATCH" "$idx")
    ffmpeg -nostdin -y -hide_banner -loglevel error \
      -f lavfi -i "color=c=${color}:s=320x180:d=0.04" \
      -frames:v 1 -q:v 3 "$out"
    idx=$((idx+1))
  done
  entry=$(printf '{"slug":"%s","startFrame":%d,"frameCount":%d,"fps":%d,"wallMs":%d}' \
    "$slug" "$start" "$PER" "$FPS" "$(( PER * 1000 / FPS ))")
  if [[ -z "$ts_entries" ]]; then ts_entries="$entry"; else ts_entries="$ts_entries,$entry"; fi
done
printf '[%s]\n' "$ts_entries" > "$SCRATCH/scene-timestamps.json"

# --- run encode --------------------------------------------------------------
echo "→ encode pass"
DAILIES_DIR="$DAILIES_DIR" DAILIES_REPO="testrepo" CLAUDE_SESSION_ID="testses" \
  bash "$QUEUE_PATCHED" encode > "$SANDBOX/encode.log" 2>&1
ENCODE_RC=$?
assert "encode exits 0" test "$ENCODE_RC" -eq 0
[[ "$ENCODE_RC" -eq 0 ]] || cat "$SANDBOX/encode.log"

# --- assertions --------------------------------------------------------------
echo "→ assertions"
mp4_count=$(find "$DAILIES_DIR" -maxdepth 1 -name '*.mp4' ! -name '*.h264.mp4' | wc -l | tr -d ' ')
assert "produced 3 mp4s" test "$mp4_count" -eq 3

for slug in "${SCENES[@]}"; do
  match=$(find "$DAILIES_DIR" -maxdepth 1 -name "*__${slug}__*.mp4" ! -name '*.h264.mp4' | head -1)
  assert "mp4 for $slug exists"     test -n "$match"
  if [[ -n "$match" ]]; then
    dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$match")
    expected=$(python3 -c "print(${PER}/${FPS})")
    # ±0.5s tolerance
    ok=$(python3 -c "print(abs(${dur:-0} - ${expected}) < 0.5)")
    assert "$slug duration ≈ ${expected}s (got ${dur})" test "$ok" = "True"
  fi
done

assert "INDEX.md created" test -f "$DAILIES_DIR/INDEX.md"
rows=$(grep -c '| video |' "$DAILIES_DIR/INDEX.md" 2>/dev/null || echo 0)
assert "INDEX.md has 3 video rows" test "$rows" -eq 3

assert "scratch dir was trashed (not present)" test ! -d "$SCRATCH"

# Queue should report empty after encode trashed the scratch.
list_out=$(DAILIES_DIR="$DAILIES_DIR" bash "$QUEUE_PATCHED" list 2>&1 || true)
assert "queue list reports empty" bash -c "echo \"$list_out\" | grep -q 'queue: empty'"

# --- share-h264 round-trip ---------------------------------------------------
if ffmpeg -hide_banner -h encoder=h264_videotoolbox 2>/dev/null | grep -q 'Encoder h264_videotoolbox'; then
  echo "→ share-h264 (videotoolbox available)"
  first_mp4=$(find "$DAILIES_DIR" -maxdepth 1 -name "*__alpha__*.mp4" ! -name '*.h264.mp4' | head -1)
  if [[ -n "$first_mp4" ]]; then
    DAILIES_DIR="$DAILIES_DIR" bash "$QUEUE_PATCHED" share-h264 "$first_mp4" \
      > "$SANDBOX/share.log" 2>&1
    SH_RC=$?
    assert "share-h264 exits 0" test "$SH_RC" -eq 0
    [[ "$SH_RC" -eq 0 ]] || cat "$SANDBOX/share.log"
    sidecar="${first_mp4%.mp4}.h264.mp4"
    assert "h264 sidecar produced" test -f "$sidecar"
    if [[ -f "$sidecar" ]]; then
      codec=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$sidecar")
      assert "sidecar codec is h264" test "$codec" = "h264"
    fi
  fi
else
  echo "→ share-h264 SKIPPED (no h264_videotoolbox)"
fi

# Don't trash the sandbox automatically — leave it for inspection on failure.
# On success, point at it for manual cleanup.
echo
echo "sandbox: $SANDBOX"
