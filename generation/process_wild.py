#!/usr/bin/env python3
"""Build a merged template for an existing wild frame WITHOUT regenerating it:
  - SCREENS via CV flatness detection (precise → live content)
  - CONTROLS via gpt-4o extraction (approximate → invisible functional hit-areas)
Controls get behaviour bindings so every control is clickable/draggable.

Usage: python3 process_wild.py public/skins/<id> [public/skins/<id2> ...]
"""
import json, os, sys
import generate as G
import freeform as F
import detect_screens as DS
from freeform_all import bind_for

def controls_from_frame(framepath):
    url = G.upload(framepath)
    regs = F.extract(url)
    out = []
    knob_i = seg_i = vs_i = 0
    # fallback actions so NO control is a no-op
    btn_fallback = ["mute", "presetNext", "volUp", "volDown", "eject", "eqOnToggle"]
    tog_fallback = ["shuffle", "eqOn", "eqAuto", "mute"]
    bf = tf = 0
    for r in regs:
        k = r.get("kind")
        if k == "display" or not k:
            continue
        reg = {"id": r.get("id") or f"c{len(out)}", "kind": k, "content": "sprite",
               "layer": "components",
               "rect": {"x": float(r["x"]), "y": float(r["y"]), "w": float(r["w"]), "h": float(r["h"])},
               "label": r.get("label", "")}
        if k == "button":
            reg["bind"] = bind_for(r.get("label")) or btn_fallback[bf % len(btn_fallback)]
            if not bind_for(r.get("label")): bf += 1
        elif k == "toggle":
            reg["bind"] = bind_for(r.get("label")) or tog_fallback[tf % len(tog_fallback)]
            if not bind_for(r.get("label")): tf += 1
        elif k == "knob":
            reg["bind"] = ["volume", "balance"][min(knob_i, 1)]; knob_i += 1
        elif k == "segmented":
            reg["bind"] = ["repeatMode", "eqPreset"][min(seg_i, 1)]
            reg["options"] = ["OFF", "1", "ALL"] if seg_i == 0 else ["FLAT", "ROCK", "POP", "JAZZ"]; seg_i += 1
        elif k == "slider-h":
            reg["bind"] = "seek"
        elif k == "slider-v":
            reg["bind"] = "eqBand"; reg["group"] = "eq-bands"; reg["index"] = vs_i; vs_i += 1
        out.append(reg)
    return out

def build(dirpath):
    frame = os.path.join(dirpath, "frame.png")
    W, H, boxes = DS.detect(frame)
    screens = []
    for (x0, y0, bw, bh, _), role in DS.assign(boxes):
        screens.append({"id": role, "kind": "display", "content": "dynamic", "layer": "screen",
                        "dynamicType": role,
                        "rect": {"x": x0 / W, "y": y0 / H, "w": bw / W, "h": bh / H}})
    controls = controls_from_frame(frame)
    tpl = {"id": os.path.basename(dirpath), "name": "wild-live",
           "canvas": {"w": W, "h": H}, "regions": screens + controls}
    json.dump(tpl, open(os.path.join(dirpath, "template.json"), "w"), indent=2)
    print(os.path.basename(dirpath), "screens", len(screens), "controls", len(controls), flush=True)

if __name__ == "__main__":
    for d in sys.argv[1:]:
        build(d)
