#!/usr/bin/env python3
"""knobup/recover_caps.py — $0 recovery of the vol-cap sprite for gens where biref12's
mask-cell island matching failed (knob_zero_deg=None despite a visibly painted cap).

biref12 matches strip islands to MASK strip cells by bbox overlap; when the paint model drifts
the strip layout (or paints a parts-tray card) the overlap gate misses and no vol.png is cut —
but the global matte (already on disk, $0) usually contains the cap as its own island. Recovery,
deterministic and material-agnostic (placement-invariants-rule):

  1. From global-matte.png, take connected components whose centroid sits in the STRIP BAND
     (y > devFrac) and are large enough to be a part (>1500px, biref12's own speck floor).
  2. The vol cap is the most CIRCULAR one: aspect ~1 and high fill vs its circumscribed circle
     (the seek thumb / toggle states are elongated by construction). Geometry only — no
     luminance/colour constants.
  3. Cut the RGBA crop exactly like biref12.save_island, save as <biref>/vol_recovered.png.
  4. If no circular strip CC exists (e.g. a tray card merged everything into one island),
     fall back to cropping the PAINT at the vol mask strip cell (padded) and running the SAME
     local BiRefNet checkpoint biref12 uses on just that crop (still $0, MPS), then cutting the
     largest island of that.

The ANGLE is then measured by the unmodified shared detector (knob_angle.detect_from_sprite) —
recovery changes only sprite ISOLATION (a crop cannot rotate content), never the measurement.
Updates results.json rows in place: knob_zero_deg / abs_error_from_up / compliant_10deg /
recovered_cut=true / knob_zero_geo.

Usage: .venv-biref/bin/python3 recover_caps.py   (torch venv needed only if the fallback fires)
"""
import os, io, sys, json
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
sys.path.insert(0, GEN12)
from knob_angle import detect_from_sprite, angular_error  # noqa: E402

_LOCAL_CKPT, _LOCAL_RES = "ZhengPeng7/BiRefNet_HR", 2048  # same as biref12.py
_LOCAL_MODEL = None


def _local_matte(png_bytes):
    """Verbatim contract of biref12._local_matte (PNG bytes in, RGBA PNG bytes out)."""
    global _LOCAL_MODEL
    import torch
    from torchvision import transforms
    from transformers import AutoModelForImageSegmentation
    if _LOCAL_MODEL is None:
        dev = "mps" if torch.backends.mps.is_available() else "cpu"
        model = AutoModelForImageSegmentation.from_pretrained(_LOCAL_CKPT, trust_remote_code=True)
        model.to(dev, dtype=torch.float32).eval()
        _LOCAL_MODEL = (model, dev)
    model, dev = _LOCAL_MODEL
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB"); W0, H0 = im.size
    tfm = transforms.Compose([transforms.Resize((_LOCAL_RES, _LOCAL_RES)), transforms.ToTensor(),
                               transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
    x = tfm(im).unsqueeze(0).to(dev)
    with torch.no_grad():
        pred = model(x)[-1].sigmoid().cpu().squeeze()
    mask = transforms.ToPILImage()(pred).resize((W0, H0), Image.BICUBIC)
    rgba = im.convert("RGBA"); rgba.putalpha(mask)
    buf = io.BytesIO(); rgba.save(buf, "PNG")
    return buf.getvalue()


def circularity(comp_mask):
    ys, xs = np.where(comp_mask)
    w = xs.max() - xs.min() + 1; h = ys.max() - ys.min() + 1
    aspect = w / h if h else 99
    if not (0.8 <= aspect <= 1.25):
        return 0.0
    Rc = max(w, h) / 2.0
    fill = len(xs) / (np.pi * Rc * Rc)
    # a true disc fills ~0.9-1.0 of its circumscribed circle (knurl teeth shave a little);
    # bars/levers are much lower; a SQUARE-ish blob OVERFILLS (square = 4/pi ~ 1.27) — the
    # myst-202 toggle-button crop scored 1.10 and got wrongly picked before this gate.
    if fill > 1.02:
        return 0.0
    return fill


def recover(assets_dir):
    sid = os.path.basename(assets_dir).replace("assets-", "")
    biref = assets_dir + "_biref"
    matte_p = os.path.join(biref, "global-matte.png")
    paint_p = os.path.join(assets_dir, "paint.png")
    if not (os.path.exists(matte_p) and os.path.exists(paint_p)):
        return None, "no-matte-or-paint"
    paint = Image.open(paint_p).convert("RGB"); PW, PH = paint.size
    res = json.load(open(os.path.join(assets_dir, "results.json")))
    devf = res["devFrac"]
    g = Image.open(matte_p).convert("RGBA").resize((PW, PH))
    A = np.asarray(g)[:, :, 3] > 90
    lbl, n = ndimage.label(A)

    best = (0.0, None)
    for idx in range(1, n + 1):
        comp = lbl == idx
        npx = comp.sum()
        if npx < 1500:
            continue
        ys, xs = np.where(comp)
        cy = ys.mean() / PH
        if cy <= devf:          # device-area islands are not strip parts
            continue
        c = circularity(comp)
        if c > best[0]:
            best = (c, idx)

    dst = os.path.join(biref, "vol_recovered.png")
    # 0.80 bar: a knurled disc fills ~0.95+ of its circumscribed circle; the gear-and-lever
    # shuffle switch measured 0.60 on steam-101 and got wrongly picked at a 0.55 bar (verified
    # by opening the recovered sprite — it was the switch, not the cap). Elongated parts are
    # already aspect-gated; 0.80 keeps discs and rejects square-ish gear clusters.
    if best[1] is not None and best[0] >= 0.80:
        ys, xs = np.where(lbl == best[1])
        crop = g.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
        crop.save(dst)
        return dst, f"strip-island circularity={best[0]:.2f}"

    # ---- fallback: local BiRefNet on the vol mask strip-cell crop of the paint ----
    regs = json.load(open(os.path.join(assets_dir, "regions.json")))
    roles = regs.get("roles", {})
    kn = next((k for k, v in roles.items() if v == "knob"), "vol")
    cells = (regs.get("regions", {}).get(kn) or {}).get("strip") or []
    if not cells or not cells[0]:
        return None, "no-strip-cell"
    x, y, w, h = cells[0]
    pad = 0.35
    x0 = int(max(0, (x - w * pad) * PW)); x1 = int(min(PW, (x + w * (1 + pad)) * PW))
    y0 = int(max(0, (y - h * pad) * PH)); y1 = int(min(PH, (y + h * (1 + pad)) * PH))
    crop = paint.crop((x0, y0, x1, y1))
    buf = io.BytesIO(); crop.save(buf, "PNG")
    rgba = Image.open(io.BytesIO(_local_matte(buf.getvalue())))
    a = np.asarray(rgba)[:, :, 3] > 90
    l2, n2 = ndimage.label(a)
    if n2 == 0:
        return None, "fallback-no-island"
    sizes = ndimage.sum(np.ones_like(l2), l2, range(1, n2 + 1))
    idx = 1 + int(np.argmax(sizes))
    ys, xs = np.where(l2 == idx)
    rgba.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)).save(dst)
    return dst, "fallback-cell-crop-biref"


def main():
    rows_p = os.path.join(HERE, "results.json")
    rows = json.load(open(rows_p))
    for r in rows:
        if r.get("knob_zero_deg") is not None:
            continue
        assets_dir = os.path.join(HERE, f"assets-{r['id']}")
        dst, how = recover(assets_dir)
        print(f"[{r['id']}] recovery: {how}")
        if dst is None:
            r["recovered_cut"] = False
            continue
        zdeg, info, geo = detect_from_sprite(dst)
        err = angular_error(zdeg) if zdeg is not None else None
        r.update({"knob_zero_deg": zdeg, "abs_error_from_up": err,
                  "compliant_10deg": bool(err is not None and err <= 10.0),
                  "recovered_cut": True, "recovery_how": how,
                  "knob_zero_geo": None if geo is None else [round(v, 2) for v in geo]})
        print(f"   -> knob_zero_deg={zdeg} err={err} ({info})")
    json.dump(rows, open(rows_p, "w"), indent=2)
    print("results.json updated")


if __name__ == "__main__":
    main()
