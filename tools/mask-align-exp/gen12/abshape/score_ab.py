#!/usr/bin/env python3
"""score_ab — run extract12 (pass 1, no matte) on each abshape gen, collect scores, cut socket crops.

Per gen: leak%% (from genskin_ab's gate, results.json), extract12 emptiness gate + controls
detected /10, plus close-up crops of the vol socket and seek slot for the index.html grid.
Writes abshape/scores.json.
"""
import os, sys, json, subprocess, re
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
RUNS = [("A", 121), ("A", 134), ("B", 121), ("B", 134)]

scores = {}
for cond, seed in RUNS:
    tag = f"{cond.lower()}-{seed}"
    d = os.path.join(HERE, f"assets-abshape-{tag}")
    if not os.path.exists(os.path.join(d, "paint.png")):
        print(f"[{tag}] no paint.png — skipping"); continue
    # extract12 pass 1 (no matte / no biref)
    p = subprocess.run([sys.executable, os.path.join(GEN12, "extract12.py"), d],
                       capture_output=True, text=True)
    log = p.stdout + p.stderr
    open(os.path.join(d, "extract.log"), "w").write(log)
    regions = json.load(open(os.path.join(d, "regions.json")))
    gate = regions.get("gate", {})
    res = json.load(open(os.path.join(d, "results.json")))
    # per-socket bright-interior fractions from the emptiness gate lines
    empt = dict(re.findall(r"^  (\w+)\s+bright-interior\s+([\d.]+)%", log, re.M))
    scores[tag] = {
        "cond": cond, "seed": seed,
        "leak_pct": round(100 * (res.get("leak") or 0), 4),
        "empty_ok": gate.get("empty_ok"),
        "empt_interior_pct": {k: float(v) for k, v in empt.items()},
        "controls": gate.get("controls"), "controls_total": gate.get("controls_total"),
        "missing": gate.get("missing"), "seek_cov": gate.get("seek_cov"),
        "reasons": gate.get("reasons"), "dims": res.get("dims"),
    }
    # crops: vol socket + seek slot from paint.png, template frac coords (frac of paint W/H)
    tpl = res["template"]
    paint = Image.open(os.path.join(d, "paint.png")).convert("RGB")
    W, H = paint.size
    for name, (fx, fy), (hw, hh) in [
        ("vol", tpl["vol"], (0.13, 0.13 * W / H)),
        ("seek", tpl["seek"], (0.33, 0.09 * W / H)),
    ]:
        x0 = int((fx - hw) * W); x1 = int((fx + hw) * W)
        y0 = int((fy - hh) * H); y1 = int((fy + hh) * H)
        c = paint.crop((max(0, x0), max(0, y0), min(W, x1), min(H, y1)))
        c = c.resize((c.width * 2, c.height * 2), Image.LANCZOS)
        c.save(os.path.join(d, f"crop-{name}.png"))
    print(f"[{tag}] leak={scores[tag]['leak_pct']}% empty_ok={scores[tag]['empty_ok']} "
          f"controls={scores[tag]['controls']}/{scores[tag]['controls_total']} "
          f"missing={scores[tag]['missing']}")

json.dump(scores, open(os.path.join(HERE, "scores.json"), "w"), indent=1)
print("-> scores.json")
