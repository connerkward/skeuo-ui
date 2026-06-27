#!/usr/bin/env bash
# screencast — record a short video (or still) of a window/region/screen on macOS.
# See SKILL.md for usage.
#
# Flags:
#   --window               interactive window pick (default)
#   --region               interactive drag-to-select region
#   --screen               main display, non-interactive
#   --window-id <id>       non-interactive still by window id (`screencapture -l`)
#   --still                single PNG still instead of video
#   --seconds <N>          cap video duration (0 = until stop button)
#   --out <path>           override default ~/Desktop output path
#   --no-reveal            skip the post-capture `open -R`
#   --demo                 SOCIAL/PUBLIC-grade capture: log input events alongside
#                          the recording, then auto-polish (idle speed-up, auto-zoom
#                          on clicks, keystroke chips) AND produce a 9:16 vertical —
#                          via central/skills/screenstudio-alt
#   --                     remaining args = description text (becomes slug)
# Positional: description text → slug.
# Output: prints the saved file path on stdout (LAST line) for orchestrators.

set -euo pipefail

mode="window"
seconds=""
desc=""
win_id=""
still=0
custom_out=""
no_reveal=0
audio=0
mp4=0
demo=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)    mode="region";   shift ;;
    --screen)    mode="screen";   shift ;;
    --window)    mode="window";   shift ;;
    --window-id) win_id="${2:-}"; shift 2 ;;
    --still)     still=1;         shift ;;
    --seconds)   seconds="${2:-}"; shift 2 ;;
    --seconds=*) seconds="${1#*=}"; shift ;;
    --audio)     audio=1;          shift ;;   # capture default audio INPUT (-g)
    --mp4)       mp4=1;            shift ;;   # transcode to a shareable H.264 mp4
    --out)       custom_out="${2:-}"; shift 2 ;;
    --no-reveal) no_reveal=1;     shift ;;
    --demo)      demo=1;          shift ;;
    -h|--help)
      sed -n '2,17p' "$0"; exit 0 ;;
    --)          shift; desc="$*"; break ;;
    -*)          echo "screencast: unknown flag '$1'" >&2; exit 2 ;;
    *)           desc="${desc:+$desc }$1"; shift ;;
  esac
done

# Slugify description: lowercase, non-alnum → '-', collapse, trim.
slugify() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | LC_ALL=C sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'
}

slug="$(slugify "${desc:-clip}")"
[[ -z "$slug" ]] && slug="clip"

stamp="$(date +%Y-%m-%d-%H%M)"
ext="mov"
[[ "$still" == "1" ]] && ext="png"
default_out="$HOME/Desktop/screencast-${stamp}-${slug}.${ext}"
outfile="${custom_out:-$default_out}"
mkdir -p "$(dirname "$outfile")"

# Build screencapture args.
args=()
if [[ "$still" == "1" ]]; then
  # Still image. -x = no sound shutter, -o = no shadow.
  args+=(-x)
  if [[ -n "$win_id" ]]; then
    args+=(-l "$win_id" -o)
  else
    case "$mode" in
      window) args+=(-W -o) ;;
      region) args+=(-i -s) ;;
      screen) args+=(-D 1) ;;
    esac
  fi
else
  # Video. -v = video mode. macOS treats -v as already interactive (asks the
  # user to pick window/region/screen on its own), and REJECTS -W (-W implies
  # -i which conflicts with -v). So the mode argument only adjusts non-pick
  # flags here.
  args+=(-v)
  if [[ -n "$win_id" ]]; then
    echo "screencast: --window-id ignored for video (macOS limitation); pick window manually" >&2
  fi
  case "$mode" in
    screen) args+=(-D 1) ;;   # main display, non-interactive
    *)      : ;;              # window/region: -v handles the picker itself
  esac
  [[ -n "$seconds" ]] && args+=(-V "$seconds")
  # -g captures the default audio INPUT. For MIC that's automatic; for SYSTEM audio
  # the default input must be a loopback (BlackHole) fed by the system output — see
  # SKILL.md "Capturing audio". Without a loopback this records the mic.
  [[ "$audio" == "1" ]] && args+=(-g)
fi

echo "screencast: mode=$mode still=$still${seconds:+ seconds=$seconds} → $outfile" >&2
if [[ "$still" != "1" ]]; then
  case "$mode" in
    window) echo "  click the window you want to record. stop from the menu-bar stop button when done." >&2 ;;
    region) echo "  drag the region you want to record. stop from the menu-bar stop button when done." >&2 ;;
    screen) echo "  recording main display. stop from the menu-bar stop button when done." >&2 ;;
  esac
fi

# --demo: log input events (clicks/keys/cursor) alongside the capture, for the
# polish pass (auto-zoom needs capture-time data — it can't be recovered later).
POLISH_REPO="$HOME/dev/central/skills/screenstudio-alt"
logger_pid=""
if [[ "$demo" == "1" && "$still" != "1" ]]; then
  evbin="$POLISH_REPO/events-log"
  [[ -x "$evbin" ]] || swiftc -O "$POLISH_REPO/events-log.swift" -o "$evbin" 2>/dev/null || true
  if [[ -x "$evbin" ]]; then
    evfile="${outfile%.*}.events.jsonl"
    "$evbin" "$evfile" & logger_pid=$!
    echo "screencast: --demo event logging → $evfile" >&2
  else
    echo "screencast: --demo events-log unavailable (clone github.com/connerkward repo to $POLISH_REPO); polish will be speed-up only" >&2
  fi
fi

screencapture "${args[@]}" "$outfile"
[[ -n "$logger_pid" ]] && kill "$logger_pid" 2>/dev/null && wait "$logger_pid" 2>/dev/null || true

if [[ ! -s "$outfile" ]]; then
  echo "screencast: no file produced (cancelled?)" >&2
  exit 1
fi

bytes=$(stat -f %z "$outfile" 2>/dev/null || echo "?")
echo "screencast: saved $outfile ($bytes bytes)" >&2

# Optional good-quality transcode to mp4 (the raw .mov is large retina; keep quality
# high — crf 20, only downscale if very wide — so it stays shareable but crisp).
if [[ "$mp4" == "1" && "$still" != "1" ]] && command -v ffmpeg >/dev/null 2>&1; then
  mp4out="${outfile%.*}.mp4"
  ffmpeg -y -loglevel error -i "$outfile" \
    -vf "scale='min(1920,iw)':-2:flags=lanczos" -c:v libx264 -crf 20 -preset medium \
    -pix_fmt yuv420p -movflags +faststart -c:a aac -b:a 160k "$mp4out" 2>/dev/null \
  && { echo "screencast: transcoded → $mp4out ($(stat -f %z "$mp4out" 2>/dev/null) bytes)" >&2; outfile="$mp4out"; }
fi
# --demo: polish pass — idle speed-up + auto-zoom + keystroke chips, horizontal
# AND 9:16 vertical (vertical is default-on for anything social-facing).
if [[ "$demo" == "1" && "$still" != "1" ]]; then
  evfile="${outfile%.*}.events.jsonl"
  pol="${outfile%.*}-polished.mp4"; vert="${outfile%.*}-vertical.mp4"
  evargs=(); [[ -s "$evfile" ]] && evargs=(--events "$evfile" --zoom --keys --vertical --vertical-out "$vert")
  if python3 "$POLISH_REPO/polish.py" "$outfile" --speedup "${evargs[@]}" --out "$pol" >&2; then
    echo "screencast: polished → $pol${evargs:+ + $vert}" >&2
    outfile="$pol"
  else
    echo "screencast: polish failed; raw capture kept" >&2
  fi
fi
[[ "$no_reveal" == "0" ]] && (open -R "$outfile" 2>/dev/null || true)
# Final stdout line = path, for piping into transcoders / index updaters.
printf '%s\n' "$outfile"
