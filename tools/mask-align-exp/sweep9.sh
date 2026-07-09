#!/bin/bash
# Seed sweep: regenerate run9 until a gen passes ALL gates (leak, emptiness [post-repair ok],
# per-cell ring, per-cell shape). Cap 5 generations (~$0.75).
cd /private/tmp/skeuo-maskexp
for SEED in 41 43 47 53 59; do
  echo "=== SWEEP seed=$SEED ==="
  python3 run9.py --seed $SEED 2>&1 | tee /tmp/mx-run-$SEED.log
  python3 extract9.py 2>&1 | tee /tmp/mx-ext-$SEED.log
  if grep -q '\[emptiness gate\] FAIL' /tmp/mx-ext-$SEED.log; then
    echo "--- emptiness FAIL -> erase_baked repair ---"
    python3 erase_baked.py
    python3 extract9.py 2>&1 | tee /tmp/mx-ext-$SEED.log
  fi
  # archive this seed's strip crop for the report
  python3 - <<EOF
from PIL import Image
p=Image.open('assets9/paint.png'); W,H=p.size
s=p.crop((0,int(H*0.75),W,H)); s.resize((s.width//3,s.height//3)).save('/tmp/mx-strip-seed$SEED.png')
EOF
  LEAK=$(grep -c 'leak gate.*→ ok' /tmp/mx-run-$SEED.log)
  EMPT=$(grep -c '\[emptiness gate\] ok' /tmp/mx-ext-$SEED.log)
  RING=$(grep -c '\[ring gate\] PASS' /tmp/mx-ext-$SEED.log)
  SHAP=$(grep -c '\[shape gate\] PASS' /tmp/mx-ext-$SEED.log)
  echo "seed=$SEED verdicts: leak=$LEAK empt=$EMPT ring=$RING shape=$SHAP"
  if [ "$LEAK" = 1 ] && [ "$EMPT" = 1 ] && [ "$RING" = 1 ] && [ "$SHAP" = 1 ]; then
    echo "=== ALL GATES PASS at seed=$SEED ==="
    echo $SEED > /tmp/mx-winner
    exit 0
  fi
done
echo "=== NO SEED PASSED (5 gens spent) ==="
exit 1
