#!/bin/bash
# Set THIS Claude session's say-notify callsign — overrides the auto "Project N"
# derivation so the spoken/overlay call-sign reflects what the window is actually
# doing (the agent decides, based on the conversation), e.g. a window watching a
# Google Takeout job sets "Takeout Watch" instead of the meaningless "G 1".
#
#   say-callsign.sh "Takeout Watch"     # set this window's callsign
#   say-callsign.sh --reset             # clear it, fall back to /rename / title
#
# Keyed by $CLAUDE_CODE_SESSION_ID (the same id Claude Code passes to the
# Notification/Stop hook), so say-notify.sh picks it up on the next fire. Upserts
# the registry: one callsign per session, last write wins.
#
# A 3rd column records the chat title as it stands right now (the "baseline"). If
# you later rename the chat in Claude (`/rename`), say-notify.sh sees the title no
# longer matches this baseline and lets the rename supersede the override — so the
# most recent naming action wins. Re-running this re-captures a fresh baseline.
set -euo pipefail
name="$*"
reg="$HOME/.claude/say-callsigns.tsv"
sid="${CLAUDE_CODE_SESSION_ID:-}"

[ -n "$name" ] || { echo "usage: say-callsign.sh <callsign>|--reset   (e.g. \"Takeout Watch\")" >&2; exit 2; }
[ -n "$sid" ]  || { echo "say-callsign: \$CLAUDE_CODE_SESSION_ID unset — not inside a Claude Code session, can't bind." >&2; exit 1; }

mkdir -p "$(dirname "$reg")"; touch "$reg"

# --reset / --clear: drop this session's override so the callsign falls back to the
# chat title (/rename) or project name. No baseline capture, no re-add.
case "${1:-}" in
  --reset|--clear)
    tmp="$(mktemp)"; awk -F'\t' -v s="$sid" '$1 != s' "$reg" > "$tmp" && mv "$tmp" "$reg"
    echo "callsign cleared (session ${sid}) — back to chat title / project name."
    exit 0 ;;
esac

# Capture the current Claude chat title (latest ai-title) as the baseline, so a
# later /rename can supersede this override. Transcript is <sid>.jsonl under
# ~/.claude/projects. Empty baseline (no title yet) → override stays sticky.
base=""
tpath="$(find "$HOME/.claude/projects" -name "${sid}.jsonl" -print -quit 2>/dev/null || true)"
[ -n "$tpath" ] && [ -f "$tpath" ] && \
  base="$(grep '"type":"ai-title"' "$tpath" 2>/dev/null | tail -1 | jq -rc '.aiTitle // empty' 2>/dev/null || true)"
base="$(printf '%s' "$base" | tr -d '\t\n')"   # titles never contain tabs; be safe

# GC + upsert in one rewrite: keep only rows whose session transcript still exists
# (drops dead/test rows so the registry doesn't grow forever), drop our own row,
# then append the fresh mapping. One transcript listing, in-memory membership test.
live="$(find "$HOME/.claude/projects" -name '*.jsonl' 2>/dev/null | sed -E 's@.*/([^/]+)\.jsonl$@\1@')"
tmp="$(mktemp)"
while IFS=$'\t' read -r rsid rname rbase; do
  [ -n "$rsid" ] || continue
  [ "$rsid" = "$sid" ] && continue                       # our row — re-added below
  # Prune rows whose session transcript is gone — but only if we actually have a
  # transcript listing (empty $live means the scan failed; don't nuke live rows).
  [ -n "$live" ] && { printf '%s\n' "$live" | grep -qxF "$rsid" || continue; }
  printf '%s\t%s\t%s\n' "$rsid" "$rname" "$rbase" >> "$tmp"
done < "$reg"
printf '%s\t%s\t%s\n' "$sid" "$name" "$base" >> "$tmp"
mv "$tmp" "$reg"
echo "callsign set: \"$name\"  (session ${sid})"
