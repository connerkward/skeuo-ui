#!/bin/bash
# Re-run extraction + cutting + player build over every generated skin (no fal spend: biref12
# reuses each skin's existing global-matte). Use after pipeline fixes to re-apply them batch-wide.
cd "$(dirname "$0")"
for d in assets-*/; do d=${d%/}; [ "${d%_biref}" = "$d" ] || continue; id=${d#assets-}
  [ -f "$d/paint.png" ] || continue
  timeout 60 python3 extract12.py "$d" >/dev/null 2>&1
  timeout 90 python3 biref12.py "$d" >/dev/null 2>&1
  timeout 60 python3 extract12.py "$d" >/dev/null 2>&1
  timeout 30 python3 build_player.py "$d" >/dev/null 2>&1
  echo "recut $id"
done
python3 build_dashboard.py 2>&1 | tail -1
echo "RECUT-DONE"
