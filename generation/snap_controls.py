#!/usr/bin/env python3
"""Snap each EXISTING template control onto its skin's REAL painted well, detected
from frame.png. Keeps the control SET + binds (so transport/seek/eq/knobs stay),
only corrects each rect to the pixel-accurate detected slot. Controls with no
confident detected match keep their current rect and are reported, so they can be
handled separately (sprite/inpaint).

Usage: python3 snap_controls.py <id> [<id> ...]    (writes template.json in place)
       python3 snap_controls.py --dry <id> ...     (report matches, write nothing)
"""
import json, os, sys
import detect_wells as DW

def R(c, W, H): return {"x": round(c["x"]/W,4), "y": round(c["y"]/H,4), "w": round(c["w"]/W,4), "h": round(c["h"]/H,4)}
def cx(r): return r["x"]+r["w"]/2
def cy(r): return r["y"]+r["h"]/2

def snap(skin_id, dry=False):
    d = f"public/skins/{skin_id}"
    tpl = json.load(open(f"{d}/template.json"))
    W, H, screens, wells = DW.detect(f"{d}/frame.png")
    wells = DW.classify(wells)
    by = {"slider-v": [], "slider-h": [], "knob": [], "button": []}
    for w in wells: by[w["kind"]].append(w)
    for k in by: by[k].sort(key=lambda c: c["x"])
    # screens biggest first
    scr = sorted(screens, key=lambda c:-c["area"])

    used = set()
    def take(pool, near=None, key=None):
        cand = [w for w in pool if id(w) not in used]
        if not cand: return None
        if near is not None:
            cand.sort(key=lambda w: (R(w,W,H)["x"]+R(w,W,H)["w"]/2-near[0])**2 + (R(w,W,H)["y"]+R(w,W,H)["h"]/2-near[1])**2)
        elif key: cand.sort(key=key)
        used.add(id(cand[0])); return cand[0]

    report = {"snapped": [], "missed": []}
    regs = tpl["regions"]
    # EQ sliders: match detected slider-v left-to-right to the eq regions left-to-right
    eqs = sorted([r for r in regs if r.get("bind")=="eqBand"], key=lambda r: cx(r["rect"]))
    dv = by["slider-v"][:]
    if len(dv) >= max(1,len(eqs))*0.6:           # enough detected slots to trust
        # map each eq region to nearest detected slot in x-order (greedy)
        for r in eqs:
            w = take(dv, near=(cx(r["rect"]),cy(r["rect"])))
            if w: r["rect"]=R(w,W,H); report["snapped"].append(r["id"])
            else: report["missed"].append(r["id"])
    else:
        report["missed"] += [r["id"] for r in eqs]
    # knobs
    for r in [x for x in regs if x.get("kind")=="knob"]:
        w = take(by["knob"], near=(cx(r["rect"]),cy(r["rect"])))
        if w: r["rect"]=R(w,W,H); report["snapped"].append(r["id"])
        else: report["missed"].append(r["id"])
    # transport buttons
    for r in [x for x in regs if x.get("kind")=="button"]:
        w = take(by["button"], near=(cx(r["rect"]),cy(r["rect"])))
        if w: r["rect"]=R(w,W,H); report["snapped"].append(r["id"])
        else: report["missed"].append(r["id"])
    # toggles -> leftover buttons nearest
    for r in [x for x in regs if x.get("kind")=="toggle"]:
        w = take(by["button"], near=(cx(r["rect"]),cy(r["rect"])))
        if w: r["rect"]=R(w,W,H); report["snapped"].append(r["id"])
        else: report["missed"].append(r["id"])
    # seek
    for r in [x for x in regs if x.get("bind")=="seek"]:
        if r["kind"]=="slider-h" and by["slider-h"]:
            w=max(by["slider-h"], key=lambda c:c["w"]); r["rect"]=R(w,W,H); report["snapped"].append(r["id"])
        elif r["kind"]=="slider-arc" and scr:
            # ring the dial: use the smaller (visualizer) screen, expand ~1.25x
            dial = min(scr, key=lambda c:c["area"]) if len(scr)>1 else scr[0]
            rr=R(dial,W,H); s=1.25; w=rr["w"]*s; h=rr["h"]*s
            r["rect"]={"x":round(cx(rr)-w/2,4),"y":round(cy(rr)-h/2,4),"w":round(w,4),"h":round(h,4)}
            report["snapped"].append(r["id"])
        else: report["missed"].append(r["id"])
    if not dry:
        json.dump(tpl, open(f"{d}/template.json","w"), indent=2)
    print(f"{skin_id:11} snapped={len(report['snapped'])} missed={report['missed']}", flush=True)
    return report

if __name__=="__main__":
    args=sys.argv[1:]; dry="--dry" in args; ids=[a for a in args if a!="--dry"]
    for s in ids: snap(s, dry=dry)
