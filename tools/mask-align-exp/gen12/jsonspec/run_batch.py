#!/usr/bin/env python3
"""Runs the full 2 themes x 2 seeds jsonspec matrix (control+treat per cell = 8 gens),
sequential (avoids per-minute Vertex quota), with a short pause between cells."""
import subprocess, sys, time, os

HERE = os.path.dirname(os.path.abspath(__file__))
THEMES = ["wc-goldshield", "fa-pod"]
SEEDS = [121, 134]

for theme in THEMES:
    for seed in SEEDS:
        print(f"\n########## {theme} seed={seed} ##########", flush=True)
        p = subprocess.run([sys.executable, os.path.join(HERE, "genskin_jsonspec.py"), theme, str(seed)])
        if p.returncode != 0:
            print(f"!!! {theme} seed={seed} FAILED (rc={p.returncode})", flush=True)
        time.sleep(12)
print("\n=== batch done ===")
