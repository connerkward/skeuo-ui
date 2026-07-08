#!/usr/bin/env python3
"""Painter drift from template, per model.

For every interactive control: the blueprint drew its socket AT the template rect
center; the painter is supposed to paint the control there. DRIFT = distance from
the rect center to the centroid of the ACTUALLY-painted control (segmented on the
device). For a sprite-well control this is exactly the visible overlay misalignment
(the renderer places the sprite at the rect; the painted well sat elsewhere).

Reported in device-canvas pixels (1024x1536) and as % of device width, per model
(from meta.json) and per kind. Overlays draw rect-center -> painted-centroid so the
numbers are verifiable, not blind.

Run: python drift.py [--overlays DIR] [--limit N]
"""
import sys, os, glob, json, math, statistics as st
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True
sys.path.insert(0, os.path.dirname(__file__))
from shape import segment_control, DEVICE_FRAC, INTERACTIVE, sprite_kind

GEN_W, GEN_H = 1024, 1536
GEN = "public/generated"
MODEL_LABEL = {
    "fal-ai/gemini-3.1-flash-image-preview/edit": "nano-banana-2",
    "fal-ai/gemini-3-pro-image-preview/edit": "nano-banana-pro",
    "openai/gpt-image-2/edit": "gpt-image-2",
}

def centroid(mask, patchbox):
    ys, xs = np.where(mask)
    if len(xs) < 12:
        return None
    px0, py0, _, _ = patchbox
    return px0 + xs.mean(), py0 + ys.mean()

def measure(paint, tpl_path, meta):
    tpl = json.load(open(tpl_path))
    im = Image.open(paint).convert("RGB")
    W, H = im.size
    rgb = np.asarray(im)
    DH = DEVICE_FRAC * H
    base = paint[:-len("-paint.png")]
    layout = json.load(open(base + "-layout.json")) if os.path.exists(base + "-layout.json") else None
    # real device rects for sprite controls from layout (in template order)
    sprite_ctrls = [r for r in tpl["regions"] if r.get("kind") in INTERACTIVE
                    and sprite_kind(r["kind"]) and not r.get("baked")]
    devrect = {}
    if layout and len(layout.get("controls", [])) == len(sprite_ctrls):
        for r, lc in zip(sprite_ctrls, layout["controls"]):
            devrect[r["id"]] = lc["rect"]
    rows = []
    for r in tpl["regions"]:
        if r.get("kind") not in INTERACTIVE:
            continue
        rc = r["rect"]
        dr = devrect.get(r["id"], (rc["x"], rc["y"], rc["w"], rc["h"]))
        box = (int(dr[0] * W), int(dr[1] * DH), int((dr[0] + dr[2]) * W), int((dr[1] + dr[3]) * DH))
        cxr, cyr = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2          # rect center (img px)
        mask, patchbox = segment_control(rgb, box)
        if mask is None:
            rows.append(dict(id=r["id"], kind=r["kind"], drift_px=None, box=box, cen=None, rc=(cxr, cyr)))
            continue
        cen = centroid(mask, patchbox)
        # to device-canvas px (1024x1536): normalize by image, scale to canvas
        dx = (cen[0] - cxr) / W * GEN_W
        dy = (cen[1] - cyr) / DH * GEN_H
        drift = math.hypot(dx, dy)
        rows.append(dict(id=r["id"], kind=r["kind"], drift_px=drift,
                         drift_pctw=100 * abs(cen[0] - cxr) / W if False else 100 * math.hypot((cen[0]-cxr)/W, (cen[1]-cyr)/DH),
                         box=box, cen=cen, rc=(cxr, cyr)))
    return im, rows

def overlay(im, rows, out):
    d = ImageDraw.Draw(im, "RGBA")
    try: f = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 26)
    except: f = ImageFont.load_default()
    for r in rows:
        cxr, cyr = r["rc"]
        d.ellipse([cxr-7, cyr-7, cxr+7, cyr+7], outline=(90,200,255,255), width=4)  # target = rect center
        if r["cen"]:
            cx, cy = r["cen"]
            col = (90,255,120,255) if (r["drift_px"] or 0) < 40 else ((255,210,90,255) if r["drift_px"] < 90 else (255,60,90,255))
            d.line([cxr, cyr, cx, cy], fill=col, width=5)
            d.ellipse([cx-9, cy-9, cx+9, cy+9], outline=col, width=4)            # painted centroid
            d.text((cx+10, cy-12), f'{r["drift_px"]:.0f}px', fill=col, font=f)
    im.save(out)

def main():
    ov_dir = None
    if "--overlays" in sys.argv:
        ov_dir = sys.argv[sys.argv.index("--overlays")+1]; os.makedirs(ov_dir, exist_ok=True)
    limit = int(sys.argv[sys.argv.index("--limit")+1]) if "--limit" in sys.argv else None
    per_model = {}   # model -> list of drift_px
    per_model_kind = {}
    per_gen = []
    metas = sorted(glob.glob(f"{GEN}/*-meta.json"))
    n = 0
    for m in metas:
        base = m[:-len("-meta.json")]
        paint, tpl = base + "-paint.png", base + "-template.json"
        if not (os.path.exists(paint) and os.path.exists(tpl)):
            continue
        try:
            w, h = Image.open(paint).size
        except: continue
        meta = json.load(open(m))
        model = MODEL_LABEL.get(meta.get("model"), meta.get("model", "?"))
        im, rows = measure(paint, tpl, meta)
        drifts = [r["drift_px"] for r in rows if r["drift_px"] is not None]
        miss = sum(1 for r in rows if r["drift_px"] is None)
        if drifts:
            per_model.setdefault(model, []).extend(drifts)
            for r in rows:
                if r["drift_px"] is not None:
                    per_model_kind.setdefault((model, r["kind"]), []).append(r["drift_px"])
            per_gen.append(dict(id=os.path.basename(base), model=model, aspect=round(w/h,3),
                                mean=round(st.mean(drifts),1), median=round(st.median(drifts),1),
                                max=round(max(drifts),1), n=len(drifts), miss=miss))
        if ov_dir and (limit is None or n < limit):
            overlay(im, rows, f"{ov_dir}/{os.path.basename(base)}.png")
        n += 1
    # report
    print("=== PER-MODEL DRIFT (device-canvas px, 1024x1536) ===")
    for model, ds in sorted(per_model.items(), key=lambda kv:-len(kv[1])):
        print(f"  {model:16s}  n_ctrl={len(ds):4d}  mean={st.mean(ds):5.1f}px  median={st.median(ds):5.1f}px  "
              f"p90={np.percentile(ds,90):5.1f}px  %width(mean)={st.mean(ds)/GEN_W*100:.1f}%")
    print("\n=== PER-MODEL × KIND (mean px) ===")
    kinds = sorted({k for _,k in per_model_kind})
    for model in per_model:
        cells = [f'{k}={st.mean(per_model_kind[(model,k)]):.0f}' for k in kinds if (model,k) in per_model_kind]
        print(f"  {model:16s}  " + "  ".join(cells))
    json.dump(dict(per_gen=sorted(per_gen,key=lambda r:-r["mean"]),
                   per_model={m:dict(n=len(d),mean=round(st.mean(d),1),median=round(st.median(d),1),p90=round(float(np.percentile(d,90)),1)) for m,d in per_model.items()}),
              open("/tmp/drift-summary.json","w"), indent=2)
    print("\nworst gens (mean drift):")
    for g in sorted(per_gen,key=lambda r:-r["mean"])[:8]:
        print(f'  {g["mean"]:5.1f}px  {g["id"][:50]:50s} [{g["model"]}]')
    print("best gens:")
    for g in sorted(per_gen,key=lambda r:r["mean"])[:5]:
        print(f'  {g["mean"]:5.1f}px  {g["id"][:50]:50s} [{g["model"]}]')

if __name__ == "__main__":
    main()
