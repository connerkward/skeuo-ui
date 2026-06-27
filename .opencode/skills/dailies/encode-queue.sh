#!/usr/bin/env bash
# encode-queue — process deferred dailies captures.
#
# A "queue item" is any directory under one of the watched scratch roots
# that contains `scene-timestamps.json` + `frames/` (the output of the
# Playwright CDP screencast driver). No separate state file — the
# filesystem IS the queue.
#
# Subcommands:
#   list                          — show pending captures
#   encode                        — encode all pending captures now (libx265 CRF 18)
#   encode-when-ready [idleSecs]  — poll until on AC + idle ≥N (default 600), then encode
#   share-h264 <hevc.mp4|slug>    — produce an H.264 sidecar (.h264.mp4) playable in
#                                    Slack/Teams/GitHub/Twitter/Notion where HEVC isn't.
#                                    Accepts a path OR a slug fragment to glob $DAILIES_DIR.
#                                    Hardware-encoded via h264_videotoolbox (no CPU cost).
#
# Output mp4s land in $DAILIES_DIR (default ~/ideas-syncthing/proj-dailies/)
# following the canonical naming scheme; the scratch dir is trashed after
# a successful encode (per the media-rm rule).
#
# Encoder: libx265 -crf 18 -preset slow -tune animation + psy-rd 2.5 (the
# 2026-06-04 settled recipe — visually transparent on screen content with
# text, plays in macOS Preview/QuickLook/Safari).

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAILIES_DIR="${DAILIES_DIR:-$HOME/ideas-syncthing/proj-dailies}"
INDEX_FILE="$DAILIES_DIR/INDEX.md"
SESSION="${CLAUDE_SESSION_ID:-default}"
SESSION_SHORT="$(printf '%s' "$SESSION" | head -c 6)"
REPO="${DAILIES_REPO:-$(basename "$(git -C . rev-parse --show-toplevel 2>/dev/null || pwd)")}"

# Watched scratch roots — first match wins per dir; combine all.
SCRATCH_ROOTS=(
  "$HOME/Desktop/dailies-scratch"
  "$HOME/.scratch/dailies"
)

die() { echo "encode-queue: $*" >&2; exit 1; }
log() { printf '%s\n' "$*" >&2; }

# Enumerate valid queue items: dirs that have scene-timestamps.json + frames/
find_queue_items() {
  for root in "${SCRATCH_ROOTS[@]}"; do
    [[ -d "$root" ]] || continue
    find "$root" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | while read -r d; do
      if [[ -f "$d/scene-timestamps.json" && -d "$d/frames" ]]; then
        echo "$d"
      fi
    done
  done
}

cmd_list() {
  local items=()
  while IFS= read -r d; do items+=("$d"); done < <(find_queue_items)
  if [[ ${#items[@]} -eq 0 ]]; then
    log "queue: empty"
    return 0
  fi
  log "queue: ${#items[@]} pending"
  for d in "${items[@]}"; do
    local nframes scenes when
    nframes=$(ls "$d/frames" 2>/dev/null | wc -l | tr -d ' ')
    scenes=$(jq 'length' "$d/scene-timestamps.json" 2>/dev/null || echo "?")
    when=$(stat -f '%Sm' -t '%Y-%m-%d %H:%M' "$d/scene-timestamps.json" 2>/dev/null || echo "?")
    printf '  %s  %4s frames  %s scenes  %s\n' "$when" "$nframes" "$scenes" "$d"
  done
}

encode_one() {
  local scratch="$1"
  local stamp when
  stamp="$(date +%Y-%m-%d-%H%M)"
  when="$(date '+%Y-%m-%d %H:%M')"
  local ts_json="$scratch/scene-timestamps.json"
  local frames="$scratch/frames"

  mkdir -p "$DAILIES_DIR"
  [[ -f "$INDEX_FILE" ]] || cat > "$INDEX_FILE" <<EOF
# Dailies index — auto-appended by ~/dev/central/skills/dailies/dailies.sh

| When | Repo | Topic | Type | Session | File |
|---|---|---|---|---|---|
EOF

  log "── encoding $scratch ──"
  local entries; entries=$(mktemp -t dailies-q.XXXXXX)
  jq -c '.[]' "$ts_json" > "$entries"

  local failed=0
  while IFS= read -r entry <&3; do
    local slug startFrame nFrames fps base out_mp4
    slug=$(jq -r '.slug' <<<"$entry")
    startFrame=$(jq -r '.startFrame' <<<"$entry")
    nFrames=$(jq -r '.frameCount' <<<"$entry")
    fps=$(jq -r '.fps' <<<"$entry")
    base="${REPO}__${slug}__${stamp}__${SESSION_SHORT}"
    out_mp4="$DAILIES_DIR/${base}.mp4"

    log "  scene: $slug  ${nFrames}f @ ${fps}fps"
    if ! ffmpeg -nostdin -y -hide_banner -loglevel error \
        -framerate "$fps" -start_number "$startFrame" \
        -i "$frames/frame-%06d.jpg" \
        -frames:v "$nFrames" \
        -an -vf "scale=1920:-2:flags=lanczos" \
        -c:v libx265 -preset slow -crf 18 -pix_fmt yuv420p10le \
        -tune animation \
        -x265-params "psy-rd=2.5:psy-rdoq=2.0:rect=1:aq-mode=3:aq-strength=0.9:strong-intra-smoothing=0" \
        -tag:v hvc1 -movflags +faststart \
        "$out_mp4"; then
      log "    ERR: ffmpeg failed for $slug"
      failed=$((failed+1))
      continue
    fi

    local size; size=$(ls -lh "$out_mp4" | awk '{print $5}')
    log "    → $size  $(basename "$out_mp4")"
    printf '| %s | %s | %s | %s | %s | [%s](%s) |\n' \
      "$when" "$REPO" "$slug" "video" "$SESSION_SHORT" \
      "${base}.mp4" "${base}.mp4" \
      >> "$INDEX_FILE"
  done 3<"$entries"
  rm -f "$entries"

  if [[ "$failed" -eq 0 ]]; then
    log "  trashing scratch: $scratch"
    /usr/bin/trash "$scratch"
  else
    log "  $failed scene(s) failed — scratch NOT trashed: $scratch"
    return 1
  fi
}

cmd_encode() {
  local items=()
  while IFS= read -r d; do items+=("$d"); done < <(find_queue_items)
  if [[ ${#items[@]} -eq 0 ]]; then
    log "queue: empty — nothing to encode"
    return 0
  fi
  log "encoding ${#items[@]} queue item(s)"
  local count=0
  for d in "${items[@]}"; do
    if encode_one "$d"; then
      count=$((count+1))
    fi
  done
  log "done: $count encoded"
}

# Returns 0 if on AC power, 1 if on battery.
on_ac_power() {
  pmset -g batt | grep -q "AC Power"
}

# Seconds since last user input event (mouse/keyboard).
idle_seconds() {
  ioreg -c IOHIDSystem 2>/dev/null \
    | awk '/HIDIdleTime/ {print int($NF / 1000000000); exit}'
}

cmd_when_ready() {
  local min_idle="${1:-600}"  # default 10 min idle
  log "encode-when-ready: waiting for AC power + idle ≥ ${min_idle}s …"
  while true; do
    if on_ac_power; then
      local idle; idle=$(idle_seconds)
      if [[ -n "$idle" && "$idle" -ge "$min_idle" ]]; then
        log "  ready: on AC, idle ${idle}s"
        break
      fi
      log "  on AC but idle only ${idle}s; waiting…"
    else
      log "  on battery; waiting for AC…"
    fi
    sleep 60
  done
  cmd_encode
}

cmd_share_h264() {
  local arg="${1:-}"
  [[ -n "$arg" ]] || die "share-h264 needs a path or slug fragment"

  local src=""
  if [[ -f "$arg" ]]; then
    src="$arg"
  else
    # Treat as slug glob inside $DAILIES_DIR. Exclude existing .h264.mp4 sidecars.
    local matches=()
    while IFS= read -r f; do matches+=("$f"); done < <(
      find "$DAILIES_DIR" -maxdepth 1 -type f -name "*${arg}*.mp4" ! -name "*.h264.mp4" 2>/dev/null | sort
    )
    if [[ ${#matches[@]} -eq 0 ]]; then
      die "no mp4 matched '*${arg}*.mp4' in $DAILIES_DIR"
    elif [[ ${#matches[@]} -gt 1 ]]; then
      log "share-h264: '$arg' matched multiple files:"
      for f in "${matches[@]}"; do log "  $f"; done
      die "narrow your match"
    fi
    src="${matches[0]}"
  fi

  local dir base name out
  dir="$(dirname "$src")"
  base="$(basename "$src" .mp4)"
  # Strip an existing .h264 marker to avoid .h264.h264.mp4 etc.
  name="${base%.h264}"
  out="$dir/${name}.h264.mp4"

  log "share-h264: $src → $(basename "$out")"
  if ! ffmpeg -nostdin -y -hide_banner -loglevel error \
      -i "$src" \
      -c:v h264_videotoolbox -b:v 6M -tag:v avc1 \
      -pix_fmt yuv420p -an \
      -movflags +faststart \
      "$out"; then
    die "ffmpeg failed encoding $src"
  fi
  local size; size=$(ls -lh "$out" | awk '{print $5}')
  log "  → $size  $out"
}

mode="${1:-}"
shift || true
case "$mode" in
  list)              cmd_list ;;
  encode)            cmd_encode ;;
  encode-when-ready) cmd_when_ready "$@" ;;
  share-h264)        cmd_share_h264 "$@" ;;
  ""|-h|--help)      sed -n '2,22p' "$0" ;;
  *)                 die "unknown subcommand: $mode" ;;
esac
