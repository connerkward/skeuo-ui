#!/usr/bin/env bash
# Sync skeuo-ui generated skin components to Google Drive (secondary/portable backup).
#
# Source: ~/dev/skeuo-ui/public/generated/  (local dev artifacts per skin <id>:
#   <id>-paint.png, -frame.png, -template.json, -meta.json, -layout.json, -sprite-*.png)
# Dest:   gdrive:skeuo-skins/
#
# NOTE: the CANONICAL cloud archive is Cloudflare R2 (skins/<id>/ in prod).
#       Google Drive is a SECONDARY, portable backup — not the source of truth.
#
# Requires the `gdrive` rclone remote to be authorized once:
#   rclone config reconnect gdrive:
#
# Usage:
#   backup-skeuo-skins.sh            # sync (mirror: deletes Drive files no longer local)
#   backup-skeuo-skins.sh --copy     # copy only (never deletes on Drive)
#   backup-skeuo-skins.sh --dry-run  # show what would change, do nothing
set -euo pipefail

SRC="${SKEUO_GENERATED_DIR:-$HOME/dev/skeuo-ui/public/generated}"
DEST="gdrive:skeuo-skins"
RCLONE="${RCLONE:-$(command -v rclone || echo /opt/homebrew/bin/rclone)}"

OP="sync"          # default: mirror
EXTRA=()
for arg in "$@"; do
  case "$arg" in
    --copy)    OP="copy" ;;
    --dry-run) EXTRA+=("--dry-run") ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

if [[ ! -d "$SRC" ]]; then
  echo "ERROR: source dir not found: $SRC" >&2
  exit 1
fi

# Fail loud + actionable if the remote isn't authorized yet.
if ! "$RCLONE" about gdrive: >/dev/null 2>&1; then
  echo "ERROR: rclone remote 'gdrive:' is not authorized." >&2
  echo "  Finish auth once (opens a browser):  rclone config reconnect gdrive:" >&2
  exit 1
fi

echo "[$(date '+%H:%M:%S')] rclone $OP  $SRC  ->  $DEST"
"$RCLONE" "$OP" "$SRC" "$DEST" \
  --progress \
  --transfers 8 \
  --checkers 16 \
  "${EXTRA[@]}"

echo "[$(date '+%H:%M:%S')] done. Verify:  rclone ls $DEST | head"
