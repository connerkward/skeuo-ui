#!/usr/bin/env python3
"""SUPERIOR detection pipeline: prior-guided SAM-3.1 snap.

For each skin, every control's template rect is fed to SAM 3.1 as a BOX PROMPT
(slightly padded to tolerate drift). SAM segments the actual painted control at
that spot and returns a tight, normalized box + a confidence score — robust to
material (works on a dark socket OR a bright painted knob), unlike darkness
thresholding. We then:
  - snap the rect to SAM's box when confidence is high AND the move is plausible
  - keep the template prior when SAM is unsure (never snap to garbage)
  - apply STRUCTURAL constraints to grouped controls (the 5-button row and the
    6-band EQ are evenly spaced; refit the group so a missed/merged member is
    interpolated from its neighbours rather than left wrong)

Outputs a `<id>.snap.json` sidecar (NOT overwriting template.json) + an overlay
PNG comparing prior (red) vs snapped (green) so the result can be reviewed before
it's applied.

Usage: python3 sam_snap.py <id> [<id> ...]
"""
import json, os, sys, time, urllib.request
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = os.path.join(ROOT, "public", "skins")
OUT = "/Users/conner/Desktop/cc-skeuo"
W, H = 1024, 1536
FAL = os.environ.get("FAL_KEY")
SAM = "https://queue.fal.run/fal-ai/sam-3-1/image"
PAD = 0.18          # enlarge the box prompt by this fraction to catch drift
MIN_SCORE = 0.55    # below this, keep the prior
CTRL = {"button", "toggle", "knob", "slider-h", "slider-v", "slider-arc", "slider-path"}


def _req(url, data=None, headers=None, method=None):
    r = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            raw = resp.read().decode().strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        raise SystemExit(f"HTTP {e.code} on {url}\n{body}")
    return json.loads(raw) if raw else {}


def upload(path):
    name = os.path.basename(path)
    init = _req("https://rest.alpha.fal.ai/storage/upload/initiate",
                data=json.dumps({"file_name": name, "content_type": "image/png"}).encode(),
                headers={"Authorization": f"Key {FAL}", "Content-Type": "application/json"})
    with open(path, "rb") as f:
        body = f.read()
    _req(init["upload_url"], data=body, headers={"Content-Type": "image/png"}, method="PUT")
    return init["file_url"]


def composite(skin):
    im = Image.open(os.path.join(SK, skin, "frame.png")).convert("RGBA").resize((W, H))
    bg = Image.new("RGBA", (W, H), (26, 26, 28, 255)); bg.alpha_composite(im)
    p = f"/tmp/sam-{skin}.png"; bg.convert("RGB").save(p); return p


def pad_box(rc):
    px, py = rc["w"]*PAD, rc["h"]*PAD
    x0 = max(0.0, rc["x"]-px); y0 = max(0.0, rc["y"]-py)
    x1 = min(1.0, rc["x"]+rc["w"]+px); y1 = min(1.0, rc["y"]+rc["h"]+py)
    return [round(x0*W), round(y0*H), round(x1*W), round(y1*H)]


def detect(url, regs):
    """One SAM call with a box prompt per control. Returns list aligned to ctrl regs:
    {cx,cy,w,h,score} (normalized) or None."""
    ctrl = [r for r in regs if r["kind"] in CTRL]
    boxes = [pad_box(r["rect"]) for r in ctrl]
    payload = {"image_url": url,
               "box_prompts": [{"x_min": b[0], "y_min": b[1], "x_max": b[2], "y_max": b[3]} for b in boxes],
               "include_boxes": True, "include_scores": True,
               "return_multiple_masks": True, "max_masks": len(boxes), "apply_mask": False}
    sub = _req(SAM, data=json.dumps(payload).encode(),
               headers={"Authorization": f"Key {FAL}", "Content-Type": "application/json"})
    t0 = time.time()
    while True:
        st = _req(sub["status_url"], headers={"Authorization": f"Key {FAL}"})
        if st.get("status") == "COMPLETED": break
        if st.get("status") in ("FAILED", "ERROR") or time.time()-t0 > 120:
            raise SystemExit(f"SAM failed: {st}")
        time.sleep(1.5)
    res = _req(sub["response_url"], headers={"Authorization": f"Key {FAL}"})
    # metadata carries index→box mapping; align back to ctrl order
    out = [None]*len(ctrl)
    for m in res.get("metadata") or []:
        i = m.get("index")
        if i is None or not (0 <= i < len(ctrl)):
            continue
        b = m["box"]            # [cx,cy,w,h] normalized
        out[i] = {"cx": b[0], "cy": b[1], "w": b[2], "h": b[3], "score": m.get("score", 0)}
    return ctrl, out


def plausible(rc, d):
    """Reject SAM boxes that wandered or ballooned — keep the prior instead."""
    if d is None or d["score"] < MIN_SCORE:
        return False
    pcx, pcy = rc["x"]+rc["w"]/2, rc["y"]+rc["h"]/2
    move = ((d["cx"]-pcx)**2 + (d["cy"]-pcy)**2) ** 0.5
    if move > max(rc["w"], rc["h"]) * 1.2:        # moved more than ~one control away
        return False
    aw, ah = d["w"]/rc["w"], d["h"]/rc["h"]
    if not (0.4 < aw < 2.6 and 0.4 < ah < 2.6):   # size sanity
        return False
    return True


def snap(ctrl, det):
    """Per-control snap with fallback, then structural refit of grouped rows."""
    new = []
    flags = []
    for r, d in zip(ctrl, det):
        rc = r["rect"]
        if plausible(rc, d):
            nx = {"x": d["cx"]-d["w"]/2, "y": d["cy"]-d["h"]/2, "w": d["w"], "h": d["h"]}
            new.append(nx); flags.append(("snap", d["score"]))
        else:
            new.append(dict(rc)); flags.append(("keep", d["score"] if d else 0))

    # structural refit: evenly-spaced rows (eqBand×N, the 5 transport buttons)
    def refit_row(pred):
        idx = [i for i, r in enumerate(ctrl) if pred(r)]
        if len(idx) < 3: return
        snapped = [i for i in idx if flags[i][0] == "snap"]
        if len(snapped) < 2: return
        # robust line through snapped centers vs their order; reapply to all in row
        order = sorted(idx, key=lambda i: ctrl[i]["rect"]["x"])
        xs = np.array([new[i]["x"]+new[i]["w"]/2 for i in order])
        pos = np.arange(len(order))
        good = np.array([flags[i][0] == "snap" for i in order])
        if good.sum() < 2: return
        a, b = np.polyfit(pos[good], xs[good], 1)         # cx ≈ a*pos + b
        good_idx = [order[k] for k in range(len(order)) if good[k]]
        cy = float(np.median([new[i]["y"]+new[i]["h"]/2 for i in good_idx]))
        wmd = float(np.median([new[i]["w"] for i in good_idx]))
        hmd = float(np.median([new[i]["h"] for i in good_idx]))
        for k, i in enumerate(order):
            if flags[i][0] == "snap":
                continue
            cx = a*k + b
            new[i] = {"x": cx-wmd/2, "y": cy-hmd/2, "w": wmd, "h": hmd}
            flags[i] = ("refit", flags[i][1])

    refit_row(lambda r: r.get("bind") == "eqBand")
    refit_row(lambda r: r["kind"] == "button" and r.get("bind") in ("prev","play","pause","stop","next"))
    return new, flags


def font(s):
    try: return ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", s)
    except: return ImageFont.load_default()


def process(skin, apply=False):
    tpl = json.load(open(os.path.join(SK, skin, "template.json")))
    regs = tpl["regions"]
    url = upload(composite(skin))
    ctrl, det = detect(url, regs)
    new, flags = snap(ctrl, det)

    # overlay: prior (red) vs snapped (green/amber)
    fr = Image.open(os.path.join(SK, skin, "frame.png")).convert("RGBA").resize((W, H))
    bg = Image.new("RGBA", (W, H), (22, 22, 24, 255)); bg.alpha_composite(fr)
    im = bg.convert("RGB"); g = ImageDraw.Draw(im); f = font(20); lw = 4
    COL = {"snap": (90, 255, 120), "refit": (255, 190, 60), "keep": (120, 120, 130)}
    moves = []
    for r, nx, fl in zip(ctrl, new, flags):
        rc = r["rect"]
        g.rectangle([rc["x"]*W, rc["y"]*H, (rc["x"]+rc["w"])*W, (rc["y"]+rc["h"])*H],
                    outline=(255, 70, 70), width=2)                       # prior = red
        c = COL[fl[0]]
        g.rectangle([nx["x"]*W, nx["y"]*H, (nx["x"]+nx["w"])*W, (nx["y"]+nx["h"])*H],
                    outline=c, width=lw)                                  # snapped = green
        mv = (((rc["x"]+rc["w"]/2)-(nx["x"]+nx["w"]/2))**2 + ((rc["y"]+rc["h"]/2)-(nx["y"]+nx["h"]/2))**2)**0.5
        moves.append((r.get("bind") or r["id"], fl[0], round(fl[1], 2), round(mv*1000)))
    op = os.path.join(OUT, f"2026-06-16-snap-{skin}.png"); im.save(op)

    # write sidecar (or apply)
    snapped_regs = []
    ci = 0
    for r in regs:
        r2 = dict(r)
        if r["kind"] in CTRL:
            r2["rect"] = {k: round(v, 4) for k, v in new[ci].items()}; ci += 1
        snapped_regs.append(r2)
    sidecar = dict(tpl); sidecar["regions"] = snapped_regs
    sp = os.path.join(SK, skin, "template.snap.json")
    json.dump(sidecar, open(sp, "w"), indent=2)
    if apply:
        json.dump(sidecar, open(os.path.join(SK, skin, "template.json"), "w"), indent=2)
    n_snap = sum(1 for _, s, _, _ in moves if s == "snap")
    print(f"[{skin}] {n_snap}/{len(moves)} snapped  overlay={op}")
    for name, st, sc, mv in moves:
        print(f"    {name:9} {st:6} conf {sc:<5} moved {mv}‰")
    return op


if __name__ == "__main__":
    if not FAL: raise SystemExit("FAL_KEY not in env")
    apply = "--apply" in sys.argv
    ids = [a for a in sys.argv[1:] if not a.startswith("--")]
    for sid in ids:
        process(sid, apply=apply)
