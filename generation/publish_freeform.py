#!/usr/bin/env python3
"""Make the freeform-extracted skin usable LIVE in the app: infer behaviour
bindings + dynamic-content types from the extracted labels/kinds, then copy the
template + a reskinned frame into public/skins/freeform/."""
import json, os, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
FF = os.path.join(HERE, "freeform")
ROOT = os.path.dirname(HERE)
DEST = os.path.join(ROOT, "public", "skins", "freeform")
os.makedirs(DEST, exist_ok=True)

tpl = json.load(open(os.path.join(FF, "template.json")))

def bind_for(label):
    l = (label or "").lower()
    if "previous" in l or "prev" in l or "back" in l: return "prev"
    if "playlist" in l: return None
    if "play" in l: return "play"
    if "pause" in l: return "pause"
    if "stop" in l: return "stop"
    if "next" in l or "forward" in l or "skip" in l: return "next"
    if "eject" in l: return "eject"
    if "shuffle" in l: return "shuffle"
    return None

knob_i = 0; seg_i = 0; vslider_i = 0
displays = [r for r in tpl["regions"] if r["kind"] == "display"]
# tallest/largest display → playlist; the rest → marquee then time
displays_sorted = sorted(displays, key=lambda r: r["rect"]["w"] * r["rect"]["h"], reverse=True)
dyn_assign = {}
if displays_sorted:
    dyn_assign[id(displays_sorted[0])] = "playlist"
for r in displays_sorted[1:]:
    # topmost remaining → marquee, then time
    dyn_assign[id(r)] = None
tops = sorted(displays_sorted[1:], key=lambda r: r["rect"]["y"])
if tops: dyn_assign[id(tops[0])] = "marquee"
if len(tops) > 1: dyn_assign[id(tops[1])] = "time"

for r in tpl["regions"]:
    k = r["kind"]
    if k in ("button", "toggle"):
        b = bind_for(r.get("label"))
        if b: r["bind"] = b
    elif k == "knob":
        r["bind"] = ["volume", "balance"][min(knob_i, 1)]; knob_i += 1
    elif k == "segmented":
        r["bind"] = ["repeatMode", "eqPreset"][min(seg_i, 1)]; seg_i += 1
        r.setdefault("options", ["OFF", "1", "ALL"] if r["bind"] == "repeatMode" else ["FLAT", "ROCK", "POP", "JAZZ"])
    elif k == "slider-h":
        r["bind"] = "seek"
    elif k == "slider-v":
        r["bind"] = "eqBand"; r["group"] = "eq-bands"; r["index"] = vslider_i; vslider_i += 1
    elif k == "display":
        dt = dyn_assign.get(id(r))
        if dt:
            r["content"] = "dynamic"; r["layer"] = "screen"; r["dynamicType"] = dt
        else:
            r["content"] = "sprite"; r["layer"] = "screen"

json.dump(tpl, open(os.path.join(DEST, "template.json"), "w"), indent=2)
# use the winamp reskin as the frame (clean + legible for live text)
src_frame = os.path.join(FF, "reskin-winamp.png")
shutil.copy(src_frame, os.path.join(DEST, "frame.png"))
# also publish the donor + overlay so the pipeline can be shown in-app
for f in ("donor.png", "overlay.png"):
    p = os.path.join(FF, f)
    if os.path.exists(p): shutil.copy(p, os.path.join(DEST, f))
print("published freeform skin ->", DEST)
print("bindings:", sum(1 for r in tpl["regions"] if r.get("bind")), "dynamic:",
      sum(1 for r in tpl["regions"] if r.get("dynamicType")))
