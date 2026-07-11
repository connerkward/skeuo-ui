#!/bin/bash
# extract_all — run the standard gen12 extraction pipeline (extract12 pass1 -> biref12 ->
# extract12 pass2) over every driftbisect/assets-bisect-* dir. $0 (BIREF_LOCAL=True in
# ../biref12.py), ~15-20s/matte on MPS. Must run AFTER all 12 paints exist.
set -uo pipefail
cd "$(dirname "$0")"
GEN12=".."
for d in assets-bisect-*; do
  [ -f "$d/paint.png" ] || { echo "SKIP $d (no paint.png)"; continue; }
  echo "=== $(date +%H:%M:%S) extract pass1: $d ==="
  python3 "$GEN12/extract12.py" "$d" > "$d/extract-pass1.log" 2>&1
  echo "=== $(date +%H:%M:%S) biref: $d ==="
  python3 "$GEN12/biref12.py" "$d" > "$d/biref.log" 2>&1
  echo "=== $(date +%H:%M:%S) extract pass2: $d ==="
  python3 "$GEN12/extract12.py" "$d" > "$d/extract-pass2.log" 2>&1
  gate=$(python3 -c "import json;print(json.load(open('$d/regions.json')).get('gate',{}).get('PASS'))" 2>/dev/null)
  echo "=== $(date +%H:%M:%S) done: $d  gate_pass=$gate ==="
done
echo "ALL EXTRACTIONS DONE"
