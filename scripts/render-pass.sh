#!/usr/bin/env bash
# Full export "pass": singles (heroes) + sequences + motion-graphics scenes
# (including the fan-out + held-fan), all 1080×1920. Renders SEQUENTIALLY — the
# live composites are heavy and concurrent captures stomp the shared dev server.
#
# Usage: bash scripts/render-pass.sh [OUTDIR]
#   needs the vite dev server up (default port 5210, see capture.mjs BASE).
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-$HOME/Desktop/skeuo-skins/pass}"
mkdir -p "$OUT"
ts(){ date +%H:%M:%S; }
echo "[$(ts)] PASS → $OUT"

SINGLES="frog bondi burger pebble halo biomech obelisk maw wmp tomato mexico"
SCENES_PLAIN="streams swarm parade cascade fan fanout"   # fan = held+live, fanout = animated deal-out

echo "[$(ts)] === singles (still + mp4 + gif) ==="
for s in $SINGLES; do echo "[$(ts)] single: $s"; node capture.mjs hero "$OUT" "$s" "" 5 2>&1 | grep -E "mp4|gif" || true; done

echo "[$(ts)] === motion graphics (mp4 + gif) ==="
for sc in $SCENES_PLAIN; do echo "[$(ts)] scene: $sc"; node capture.mjs mg "$OUT" "$sc" "" 9 2>&1 | grep mp4 || true; done
node capture.mjs mg "$OUT" orbit "center=maw"    9 mg-orbit-maw    2>&1 | grep mp4 || true
node capture.mjs mg "$OUT" orbit "center=tomato" 9 mg-orbit-tomato 2>&1 | grep mp4 || true

echo "[$(ts)] === sequences (from the fresh hero clips) ==="
python3 make_seq.py "$OUT" seq-A-flow-1.6s 1.6 "frog,bondi,pebble,maw,halo,wmp,obelisk,burger,biomech" 2>&1 | grep -E "mp4|gif" || true
python3 make_seq.py "$OUT" seq-B-mix-2.5s  2.5 "maw,wmp,frog,biomech,pebble,bondi,halo,burger,obelisk" 2>&1 | grep -E "mp4|gif" || true
python3 make_seq.py "$OUT" seq-C-snap-1.2s  1.2 "bondi,obelisk,maw,pebble,wmp,halo,burger,frog,biomech" 2>&1 | grep -E "mp4|gif" || true

echo "[$(ts)] PASS COMPLETE → $OUT"
