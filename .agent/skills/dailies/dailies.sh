#!/usr/bin/env bash
# dailies — autonomous dev-work documentation. See SKILL.md for policy.
# Sub-commands:
#   capture <topic> [--still | --seconds N]
#   capture-pair before|after <topic>
#   save-last
#   digest [--summary "<markdown>"]
# Files land in ~/ideas-syncthing/proj-dailies/ (see DAILIES_DIR).

set -euo pipefail

DAILIES_DIR="${DAILIES_DIR:-$HOME/ideas-syncthing/proj-dailies}"
KEEPERS_DIR="$DAILIES_DIR/keepers"
INDEX_FILE="$DAILIES_DIR/INDEX.md"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Honour env overrides so the script can be re-routed for tests / portability.
SCREENCAST="${SCREENCAST:-$HOME/dev/central/skills/screencast/screencast.sh}"
TRANSCODE="${TRANSCODE:-$HERE/transcode.sh}"

SESSION_HASH="${CLAUDE_SESSION_ID:-$(echo "$$" | shasum | head -c 6)}"
# Hash for FILE NAMING is truncated to 6 chars (compact filenames). But the
# session IDENTITY for disable/state files uses the FULL session value so
# user-set kill switches with the full id work as expected.
SESSION_HASH_SHORT="$(printf '%s' "$SESSION_HASH" | head -c 6)"
STATE_FILE="/tmp/dailies-state-${SESSION_HASH}.json"
DISABLE_SESSION="/tmp/dailies-disabled-${SESSION_HASH}"
DISABLE_GLOBAL="$HOME/.claude/no-dailies"

mkdir -p "$DAILIES_DIR" "$KEEPERS_DIR"
[[ -f "$INDEX_FILE" ]] || cat > "$INDEX_FILE" <<EOF
# Dailies index — auto-appended by ~/dev/central/skills/dailies/dailies.sh

| When | Repo | Topic | Type | Session | File |
|---|---|---|---|---|---|
EOF

# ── helpers ───────────────────────────────────────────────────────────

die() { echo "dailies: $*" >&2; exit 1; }
log() { echo "dailies: $*" >&2; }

slugify() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | LC_ALL=C sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'
}

repo_name() {
  local r b
  r=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
  b=$(basename "$r")
  # Sanitise: if invoked from / or some odd cwd, basename can return / or
  # other garbage that breaks filenames. Slugify and fall back.
  b=$(slugify "$b")
  [[ -z "$b" ]] && b="unknown-repo"
  printf '%s' "$b"
}

now_stamp()      { date +%Y-%m-%d-%H%M; }
now_epoch()      { date +%s; }
disabled_check() {
  [[ -e "$DISABLE_GLOBAL"  ]] && { log "globally disabled (~/.claude/no-dailies)"; return 0; }
  [[ -e "$DISABLE_SESSION" ]] && { log "session disabled"; return 0; }
  return 1
}

# Read state field with default; uses jq if available, falls back to grep.
state_get() {
  local key="$1" default="$2"
  if [[ -f "$STATE_FILE" ]] && command -v jq >/dev/null 2>&1; then
    jq -r --arg k "$key" --arg d "$default" '.[$k] // $d' "$STATE_FILE" 2>/dev/null || echo "$default"
  else
    echo "$default"
  fi
}
state_set() {
  local key="$1" val="$2"
  command -v jq >/dev/null 2>&1 || { echo "{}" > "$STATE_FILE"; return; }
  [[ -f "$STATE_FILE" ]] || echo "{}" > "$STATE_FILE"
  local tmp; tmp=$(mktemp)
  jq --arg k "$key" --arg v "$val" '.[$k] = $v' "$STATE_FILE" > "$tmp" && mv "$tmp" "$STATE_FILE"
}

append_index() {
  # $1 type (video|still|before|after|paired), $2 topic, $3 repo, $4 file
  local typ="$1" topic="$2" repo="$3" file="$4"
  local stamp="$(date '+%Y-%m-%d %H:%M')"
  local short_path="${file#$DAILIES_DIR/}"
  printf '| %s | %s | %s | %s | %s | [%s](%s) |\n' \
    "$stamp" "$repo" "$topic" "$typ" "$SESSION_HASH_SHORT" \
    "$short_path" "$short_path" \
    >> "$INDEX_FILE"
}

# Cooldown gate. Order matters:
#   1. Time-cooldown (≥90s since last ATTEMPT, whether captured or dice-skipped).
#      We persist last_epoch on EVERY attempt — including dice-skipped ones —
#      so a probability skip still locks out the next 90s. Otherwise the
#      effective sample rate would creep up to 1.0 as the gate is re-rolled.
#   2. Dice (55% probability). Only rolled if time-cooldown passed.
cooldown_passes() {
  local last; last=$(state_get last_epoch 0)
  local now;  now=$(now_epoch)
  local age=$(( now - last ))
  if (( age < 90 )); then
    log "cooldown: ${age}s since last (need 90s)"
    return 1
  fi
  # Lock the next 90s NOW, before the dice roll, so a dice-skip still gates.
  state_set last_epoch "$now"
  # FORCE_CAPTURE=1 in env bypasses the dice — for tests, or for explicit
  # user-driven "capture this NOW" invocations where probability is wrong.
  if [[ "${FORCE_CAPTURE:-0}" != "1" ]]; then
    if (( RANDOM % 100 > 55 )); then
      log "dice: skipped this moment (probability gate)"
      return 1
    fi
  fi
  return 0
}

# Window auto-filtering: macOS screencapture has no programmatic way to list
# windows with titles + app names (the -l flag captures BY id but doesn't
# enumerate). True filtering would need Quartz Window Services via a small
# Swift/Obj-C helper. Out of scope for v1 — Claude is responsible for not
# invoking dailies when the active window is Playwright / a terminal /
# system UI (see SKILL.md "NEVER record").

# ── sub-commands ──────────────────────────────────────────────────────

cmd_capture() {
  local topic="${1:-clip}"; shift || true
  local still=0
  local seconds="6"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --still)     still=1; shift ;;
      --seconds)   seconds="$2"; shift 2 ;;
      --seconds=*) seconds="${1#*=}"; shift ;;
      *)           shift ;;
    esac
  done

  disabled_check && exit 0

  if ! cooldown_passes; then
    exit 0
  fi

  local repo; repo=$(repo_name)
  local stamp; stamp=$(now_stamp)
  local topic_slug; topic_slug=$(slugify "$topic")
  [[ -z "$topic_slug" ]] && topic_slug="clip"  # non-ASCII / emoji-only topic → safe fallback
  local base="${repo}__${topic_slug}__${stamp}__${SESSION_HASH_SHORT}"

  if [[ "$still" == "1" ]]; then
    local tmp_png="/tmp/dailies-${SESSION_HASH}-${stamp}.png"
    "$SCREENCAST" --still --no-reveal --out "$tmp_png" -- "$topic"
    local out_avif="$DAILIES_DIR/${base}.avif"
    "$TRANSCODE" still "$tmp_png" "$out_avif" || die "transcode (still) failed"
    rm -f "$tmp_png"
    append_index "still" "$topic_slug" "$repo" "$out_avif"
    log "saved $out_avif"
    echo "[shot:   $repo / $topic_slug]"
    state_set last_path "$out_avif"
  else
    local tmp_mov="/tmp/dailies-${SESSION_HASH}-${stamp}.mov"
    "$SCREENCAST" --seconds "$seconds" --no-reveal --out "$tmp_mov" -- "$topic"
    local out_mp4="$DAILIES_DIR/${base}.mp4"
    local out_thumb="$DAILIES_DIR/${base}.thumb.avif"
    "$TRANSCODE" video "$tmp_mov" "$out_mp4" "$out_thumb" "$seconds" || die "transcode (video) failed"
    rm -f "$tmp_mov"
    append_index "video" "$topic_slug" "$repo" "$out_mp4"
    log "saved $out_mp4 (+ thumb)"
    echo "[record: $repo / $topic_slug / ${seconds}s]"
    state_set last_path "$out_mp4"
  fi
  # last_epoch was set inside cooldown_passes() so dice-skips also gate.
}

cmd_capture_pair() {
  local phase="${1:-}"; shift || die "capture-pair needs 'before' or 'after'"
  local topic="${1:-pair}"; shift || true
  local repo; repo=$(repo_name)
  local topic_slug; topic_slug=$(slugify "$topic")
  [[ -z "$topic_slug" ]] && topic_slug="pair"
  local pair_marker="/tmp/dailies-pair-${SESSION_HASH}-${topic_slug}.json"

  case "$phase" in
    before)
      local stamp; stamp=$(now_stamp)
      local base="${repo}__${topic_slug}__${stamp}__${SESSION_HASH_SHORT}"
      local tmp="/tmp/dailies-${SESSION_HASH}-${stamp}-before.png"
      "$SCREENCAST" --still --no-reveal --out "$tmp" -- "$topic before"
      local out="$DAILIES_DIR/${base}__before.avif"
      "$TRANSCODE" still "$tmp" "$out" || die "transcode failed"
      rm -f "$tmp"
      # Write marker so 'after' can find the base name.
      echo "{\"base\":\"${base}\",\"before\":\"${out}\"}" > "$pair_marker"
      append_index "before" "$topic_slug" "$repo" "$out"
      log "paired BEFORE → $out"
      echo "[pair-before: $repo / $topic_slug]"
      ;;
    after)
      [[ -f "$pair_marker" ]] || die "no matching 'before' found for topic '$topic_slug'"
      local base; base=$(jq -r .base "$pair_marker" 2>/dev/null || echo "")
      [[ -z "$base" ]] && die "pair marker corrupt"
      local stamp; stamp=$(now_stamp)
      local tmp="/tmp/dailies-${SESSION_HASH}-${stamp}-after.png"
      "$SCREENCAST" --still --no-reveal --out "$tmp" -- "$topic after"
      local out="$DAILIES_DIR/${base}__after.avif"
      "$TRANSCODE" still "$tmp" "$out" || die "transcode failed"
      rm -f "$tmp"
      append_index "after" "$topic_slug" "$repo" "$out"
      rm -f "$pair_marker"
      log "paired AFTER → $out"
      echo "[pair-after:  $repo / $topic_slug]"
      ;;
    *) die "capture-pair: phase must be 'before' or 'after'" ;;
  esac
}

cmd_save_last() {
  local last; last=$(state_get last_path "")
  [[ -z "$last" || ! -f "$last" ]] && die "no recent dailies to save"
  local base; base=$(basename "$last")
  local star="★${base}"
  local dst="$KEEPERS_DIR/$star"
  cp "$last" "$dst"
  # Also copy companion files (thumb, gif) if they exist.
  for ext in .thumb.avif .gif; do
    local pre="${last%.*}"
    if [[ -f "${pre}${ext}" ]]; then
      cp "${pre}${ext}" "$KEEPERS_DIR/★$(basename "${pre}${ext}")"
    fi
  done
  log "kept → $dst"
  echo "[★ saved: $(basename "$dst")]"
}

cmd_digest() {
  local summary_md=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --summary) summary_md="$2"; shift 2 ;;
      --summary=*) summary_md="${1#*=}"; shift ;;
      *) shift ;;
    esac
  done

  # Find every file with this session hash.
  local hits=()
  while IFS= read -r f; do hits+=("$f"); done < <(
    find "$DAILIES_DIR" -maxdepth 1 -type f \
      -name "*__${SESSION_HASH_SHORT}*" \
      ! -name "*.thumb.avif" \
      | sort
  )

  if (( ${#hits[@]} == 0 )); then
    log "no dailies for session $SESSION_HASH_SHORT yet"
    exit 0
  fi

  local out="$HOME/Desktop/dailies-session-${SESSION_HASH_SHORT}-$(date +%Y-%m-%d-%H%M).html"
  {
    echo '<!doctype html><html><head><meta charset="utf-8">'
    echo '<title>Dailies — session '"$SESSION_HASH_SHORT"'</title>'
    cat <<'CSS'
<style>
  :root { --paper: #ebe8df; --ink: #0a0806; --ink-soft: #555; --line: #d0ccc0; }
  html,body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.5 ui-monospace,Menlo,monospace}
  body{max-width:1100px;margin:0 auto;padding:40px 32px}
  h1{font:600 22px/1.3 ui-monospace,Menlo,monospace;letter-spacing:.04em;margin:0 0 6px}
  h1 small{font-weight:400;color:var(--ink-soft)}
  .summary{background:#efebe1;border:1px solid var(--line);padding:18px 22px;margin:22px 0 36px;border-radius:2px}
  .summary h2{font-size:11px;text-transform:uppercase;letter-spacing:.14em;color:var(--ink-soft);margin:0 0 10px}
  .summary p{margin:6px 0}
  .summary ul{margin:6px 0 6px 18px;padding:0}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:18px}
  figure{margin:0;background:#efebe1;border:1px solid var(--line);padding:10px}
  figure video,figure img{display:block;width:100%;height:auto;background:#000}
  figcaption{font-size:11px;color:var(--ink-soft);padding-top:8px;line-height:1.4}
  figcaption b{color:var(--ink);font-weight:600}
</style>
CSS
    echo '</head><body>'
    echo "<h1>Dailies <small>session $SESSION_HASH_SHORT · $(date '+%a %b %-d, %Y · %-I:%M %p')</small></h1>"
    if [[ -n "$summary_md" ]]; then
      echo '<div class="summary"><h2>Session summary</h2>'
      printf '%s' "$summary_md" | python3 -c "
import sys, html
md = sys.stdin.read()
# tiny markdown: paragraphs + bullets + bold
out = []
for blk in md.strip().split('\n\n'):
    if blk.strip().startswith('-'):
        out.append('<ul>')
        for line in blk.splitlines():
            line = line.strip()
            if line.startswith('-'): out.append('<li>'+ html.escape(line[1:].strip()) +'</li>')
        out.append('</ul>')
    else:
        out.append('<p>'+ html.escape(blk.strip()) +'</p>')
text = '\n'.join(out)
# bold **x**
import re
text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
print(text)
" 2>/dev/null || printf '<pre>%s</pre>' "$summary_md"
      echo '</div>'
    fi
    echo '<div class="grid">'
    for f in "${hits[@]}"; do
      local name; name=$(basename "$f")
      local ext="${f##*.}"
      local repo topic stamp
      # repo__topic__stamp__hash[.suffix].ext
      repo=$(echo "$name" | awk -F'__' '{print $1}')
      topic=$(echo "$name" | awk -F'__' '{print $2}')
      stamp=$(echo "$name" | awk -F'__' '{print $3}')
      case "$ext" in
        mp4|mov|webm)
          echo "<figure><video src=\"file://$f\" controls loop muted></video>"
          echo "<figcaption><b>$topic</b><br>$repo · $stamp · <code>$name</code></figcaption></figure>"
          ;;
        avif|webp|png|jpg|jpeg|gif)
          echo "<figure><img src=\"file://$f\" alt=\"$topic\">"
          echo "<figcaption><b>$topic</b><br>$repo · $stamp · <code>$name</code></figcaption></figure>"
          ;;
      esac
    done
    echo '</div>'
    echo '</body></html>'
  } > "$out"

  log "digest → $out (${#hits[@]} items)"
  echo "$out"
  open "$out" 2>/dev/null || true
}

# ── dispatch ──────────────────────────────────────────────────────────

cmd="${1:-}"; shift || true
case "$cmd" in
  capture)      cmd_capture "$@" ;;
  capture-pair) cmd_capture_pair "$@" ;;
  save-last)    cmd_save_last "$@" ;;
  digest)       cmd_digest "$@" ;;
  ""|-h|--help)
    sed -n '2,9p' "$0"
    exit 0 ;;
  *) die "unknown sub-command: $cmd" ;;
esac
