#!/bin/bash
cd "$(dirname "$0")"
run() { echo "=== $* ==="; python3 gen_knobticks.py "$@" 2>&1 | grep -v "^Traceback\|^  File\|^    \|Error" | tail -8; }
run ../theme_specs/fa-pod.json --arm ticks01  --seed 501
run ../theme_specs/fa-pod.json --arm ticks01  --seed 502
run ../theme_specs/fa-pod.json --arm ticks_ctr --seed 501
run ../theme_specs/fa-pod.json --arm ticks_ctr --seed 502
echo "=== BATCH2 DONE ==="
