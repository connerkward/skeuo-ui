#!/bin/bash
set -e
cd "$(dirname "$0")"
run() { echo "=== $* ==="; python3 gen_knobticks.py "$@" 2>&1; }
run ../theme_specs/steam-porthole.json --arm ticks01    --seed 402
run ../theme_specs/steam-porthole.json --arm ticks_ctr   --seed 401
run ../theme_specs/steam-porthole.json --arm ticks_ctr   --seed 402
run ../theme_specs/fa-pod.json         --arm ticks01     --seed 501
run ../theme_specs/fa-pod.json         --arm ticks01     --seed 502
run ../theme_specs/fa-pod.json         --arm ticks_ctr    --seed 501
run ../theme_specs/fa-pod.json         --arm ticks_ctr    --seed 502
echo "=== BATCH DONE ==="
