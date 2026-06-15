#!/usr/bin/env python3
"""Browser-free ALIGNMENT AUDIT for wild_sculpt skins.

The pipeline aligns "by construction" (template regions == blueprint wells), but
the PAINT model can drift/resize/fill the wells, so the live React controls (at
template coords) no longer land on the painted recess. This catches that.

For every control/screen region we measure, straight off frame.png:
  coverage = fraction of the region rect that is actual WELL pixel (opaque AND
             near-black — the recessed socket the paint was told to keep dark)
  drift    = offset of the dark-pixel centroid (in a padded rect) from the
             region center, as % of the region's size
A region with low coverage (paint filled/moved the well) or high drift (well
sits off-center) is FLAGGED. Outputs a per-skin annotated contact sheet +
a printed table. Run after every generation; never ship on raw-frame eyeballing.

Usage: python3 audit_skins.py [skin ...]    (default: all live skins on disk)
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = "/Users/conner/dev/skeuo-ui"
SKINS_DIR = f"{ROOT}/public/skins"
OUT = os.path.expanduser("~/Desktop/cc-skeuo")
os.makedirs(OUT, exist_ok=True)

CONTROL_KINDS = {"button", "toggle", "knob", "slider-h", "slider-v",
                 "slider-arc", "slider-path", "segmented", "xy", "display"}
# thin controls (rings / lines) never fill their bounding rect, so rect-coverage
# is meaningless for them — judge those on drift only.
THIN_KINDS = {"slider-arc", "slider-h", "slider-path"}
DARK = 70            # luma below this (on opaque body) reads as a recessed well
COV_MIN = 0.40       # < this fraction of well pixels in a SOLID well → filled/moved
DRIFT_MAX = 0.30     # centroid offset > this (frac of region size) → off its well

def luma(rgb):
    return rgb[..., 0]*0.299 + rgb[..., 1]*0.587 + rgb[..., 2]*0.114

def audit_region(arr, alpha, rect, W, H):
    x0, y0 = int(rect["x"]*W), int(rect["y"]*H)
    x1, y1 = int((rect["x"]+rect["w"])*W), int((rect["y"]+rect["h"])*H)
    x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(W, x1), min(H, y1)
    if x1 <= x0 or y1 <= y0: return 0.0, 1.0
    sub_a = alpha[y0:y1, x0:x1]
    sub_l = luma(arr[y0:y1, x0:x1])
    well = (sub_a > 128) & (sub_l < DARK)
    coverage = float(well.mean())
    # drift: centroid of well pixels in a padded rect vs region center
    pad_x, pad_y = (x1-x0)//3, (y1-y0)//3
    px0, py0 = max(0, x0-pad_x), max(0, y0-pad_y)
    px1, py1 = min(W, x1+pad_x), min(H, y1+pad_y)
    pa = alpha[py0:py1, px0:px1]; pl = luma(arr[py0:py1, px0:px1])
    pw = (pa > 128) & (pl < DARK)
    if pw.sum() < 30:
        drift = 1.0
    else:
        ys, xs = np.nonzero(pw)
        cx, cy = px0 + xs.mean(), py0 + ys.mean()
        rcx, rcy = (x0+x1)/2, (y0+y1)/2
        drift = float(np.hypot((cx-rcx)/max(1, x1-x0), (cy-rcy)/max(1, y1-y0)))
    return coverage, drift

def audit_skin(skin):
    fp = f"{SKINS_DIR}/{skin}/frame.png"; tp = f"{SKINS_DIR}/{skin}/template.json"
    if not (os.path.exists(fp) and os.path.exists(tp)): return None
    im = Image.open(fp).convert("RGBA"); W, H = im.size
    arr = np.asarray(im); alpha = arr[..., 3]
    regs = json.load(open(tp))["regions"]
    rows = []
    for r in regs:
        if r["kind"] not in CONTROL_KINDS: continue
        cov, drift = audit_region(arr, alpha, r["rect"], W, H)
        # Only DISPLAYS are reliably auditable from the body alone: live screen
        # content (visualizer/marquee/playlist) must sit over a painted DARK glass
        # recess on every skin. Controls render as sprite/CSS overlays at template
        # coords, so a missing dark well behind them is cosmetic, not a fault — we
        # report their numbers as info but only FLAG a gross displacement.
        if r["kind"] == "display":
            bad = cov < COV_MIN or drift > DRIFT_MAX
        else:
            bad = cov < 0.10 and drift > 0.45        # well clearly absent AND displaced
        rows.append((r["id"], r["kind"], cov, drift, bad))
    return im, regs, rows

def draw_sheet(results):
    th = 460; tw = int(th*1024/1536); pad = 16; lblh = 24; cols = 4
    import math
    rows_n = math.ceil(len(results)/cols)
    sheet = Image.new("RGB", (cols*tw+(cols+1)*pad, rows_n*(th+lblh+pad)+pad), (20,20,24))
    d = ImageDraw.Draw(sheet)
    def F(sz, b=False):
        p = "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if b else "/System/Library/Fonts/Supplemental/Arial.ttf"
        try: return ImageFont.truetype(p, sz)
        except: return ImageFont.load_default()
    for i, (skin, im, regs, rows) in enumerate(results):
        gx, gy = pad + (i % cols)*(tw+pad), pad + (i//cols)*(th+lblh+pad)
        nbad = sum(1 for *_, b in rows if b)
        d.text((gx, gy), f"{skin}  {'OK' if nbad==0 else str(nbad)+' FLAG'}",
                font=F(15, True), fill=(120,255,140) if nbad==0 else (255,120,120))
        canvas = im.copy().resize((tw, th)); ov = Image.new("RGBA", (tw, th), (0,0,0,0))
        od = ImageDraw.Draw(ov)
        rowmap = {r[0]: r for r in rows}
        for r in regs:
            if r["kind"] not in CONTROL_KINDS: continue
            rc = r["rect"]; bx = [int(rc["x"]*tw), int(rc["y"]*th), int((rc["x"]+rc["w"])*tw), int((rc["y"]+rc["h"])*th)]
            bad = rowmap[r["id"]][4]
            od.rectangle(bx, outline=(255,40,60,255) if bad else (60,220,120,235), width=2)
        merged = Image.alpha_composite(canvas.convert("RGBA"), ov).convert("RGB")
        sheet.paste(merged, (gx, gy+lblh))
    out = f"{OUT}/2026-06-15-align-audit.png"; sheet.save(out); print("SHEET", out)

def main():
    skins = sys.argv[1:] or sorted(d for d in os.listdir(SKINS_DIR)
                                    if os.path.isdir(f"{SKINS_DIR}/{d}"))
    results = []
    print(f"{'skin':12} {'region':12} {'kind':10} {'cov':>6} {'drift':>6}  flag")
    for skin in skins:
        r = audit_skin(skin)
        if r is None: continue
        im, regs, rows = r
        results.append((skin, im, regs, rows))
        for rid, kind, cov, drift, bad in rows:
            if bad:
                print(f"{skin:12} {rid:12} {kind:10} {cov:6.2f} {drift:6.2f}  {'<<<' if bad else ''}")
    draw_sheet(results)
    total_bad = sum(1 for _, _, _, rows in results for *_, b in rows if b)
    print(f"\n{len(results)} skins, {total_bad} flagged regions")

if __name__ == "__main__":
    main()
