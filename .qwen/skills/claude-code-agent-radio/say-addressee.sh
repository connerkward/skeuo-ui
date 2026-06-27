#!/bin/bash
# Set how the radio addresses YOU (the user) — the "{gf}" placeholder in say-notify.sh's
# openers, e.g. "Godfather, this is Takeout Watch." The default is "Godfather"; this
# helper writes a custom handle to ~/.claude/say-addressee so the chatter calls you what
# you like (or what Claude already knows you by).
#
#   say-addressee.sh "Boss"     bind a literal handle (may contain spaces)
#   say-addressee.sh --auto     derive a name Claude already knows you by, and bind it
#   say-addressee.sh --reset    forget the handle (back to the "Godfather" default)
#   say-addressee.sh            print the current effective addressee + usage
#
# Read by say-notify.sh on the next fire; $SAY_ADDRESSEE (env) overrides this file.
set -euo pipefail
file="$HOME/.claude/say-addressee"

usage() {
  cur="Godfather"
  [ -n "${SAY_ADDRESSEE:-}" ] && cur="$SAY_ADDRESSEE (from \$SAY_ADDRESSEE)"
  [ -z "${SAY_ADDRESSEE:-}" ] && [ -s "$file" ] && cur="$(cat "$file")"
  cat >&2 <<EOF
current addressee: "$cur"
usage:
  say-addressee.sh "Boss"     set a literal handle
  say-addressee.sh --auto     derive a name Claude knows you by
  say-addressee.sh --reset    back to "Godfather" default
EOF
}

# Capitalize first letter, lowercase the rest (bash 3.2: no \${var^}).
cap() { awk '{print toupper(substr($0,1,1)) tolower(substr($0,2))}'; }

case "${1:-}" in
  ""|-h|--help) usage; exit 0 ;;
  --reset)
    rm -f "$file"; echo "addressee reset — radio reverts to \"Godfather\"."; exit 0 ;;
  --auto)
    # Derive from what Claude already knows: git user.name (first word; CamelCase like
    # "ConnerWard" → "Conner"), else $USER capitalized.
    name=""
    gname="$(git config user.name 2>/dev/null || true)"
    if [ -n "$gname" ]; then
      first="$(printf '%s' "$gname" | awk '{print $1}')"            # first whitespace-separated word
      if printf '%s' "$first" | grep -qE '^[A-Z][a-z]+[A-Z]'; then  # CamelCase, no space → split on 2nd cap
        first="$(printf '%s' "$first" | sed -E 's/([a-z])([A-Z].*)$/\1/')"
      fi
      name="$first"
    fi
    [ -z "$name" ] && name="$(printf '%s' "${USER:-}" | cap)"
    [ -n "$name" ] || { echo "say-addressee: couldn't derive a name from git user.name or \$USER." >&2; exit 1; }
    mkdir -p "$(dirname "$file")"
    printf '%s' "$name" > "$file"
    echo "addressee set: \"$name\"  (auto-derived)"
    ;;
  *)
    name="$*"
    mkdir -p "$(dirname "$file")"
    printf '%s' "$name" > "$file"
    echo "addressee set: \"$name\""
    ;;
esac
