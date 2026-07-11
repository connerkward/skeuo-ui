#!/bin/bash
set -uo pipefail
cd "$(dirname "$0")"
python3 - << 'PYEOF'
from run_manifest import THEMES, ARMS
jobs = []
for sid, (spec, seeds) in THEMES.items():
    for seed in seeds:
        for arm in ARMS:
            jobs.append((spec, seed, arm))
for spec, seed, arm in jobs:
    print(f"JOB\t{spec}\t{seed}\t{arm}")
PYEOF
