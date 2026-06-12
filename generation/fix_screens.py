#!/usr/bin/env python3
"""Repair a body whose screens came out irregular: DRAW clean rectangular
screens onto the body at exact coords, let Nano Banana EDIT integrate them
(material frames them), keep the original alpha, and write the screens into
the template at the drawn coordinates — known by construction, no detection.
Usage: fix_screens.py <id>"""
import json, os, sys, time, urllib.request
from PIL import Image, ImageDraw
import generate as G

ROOT = os.path.dirname(G.HERE)

# target screens (normalized) — tuned to sit in the body's cavity zones
SCREENS = {
    "visualizer": {"x": 0.24, "y": 0.145, "w": 0.52, "h": 0.135},
    "marquee":    {"x": 0.26, "y": 0.300, "w": 0.48, "h": 0.030},
    "playlist":   {"x": 0.21, "y": 0.560, "w": 0.58, "h": 0.235},
}

PROMPT = (
    "This device has had flat dark rectangles pasted onto it. Integrate them: make each pasted "
    "rectangle a real RECESSED rectangular SCREEN of flat, empty, switched-off dark obsidian glass, "
    "with the device's material forming a neat organic frame AROUND each screen edge (growing around, "
    "never over the glass). Keep each screen EXACTLY where the rectangle is, same size, same shape. "
    "Keep the silhouette, material, style and every other detail of the device EXACTLY the same — "
    "including every recessed control socket, well, slot and groove. Background stays pure white."
)

def main(skin):
    d = os.path.join(ROOT, "public", "skins", skin)
    src = os.path.join(d, "frame.png")
    im = Image.open(src).convert("RGBA")
    W, H = im.size
    bg = Image.new("RGBA", (W, H), (255, 255, 255, 255)); bg.alpha_composite(im)
    dr = ImageDraw.Draw(bg)
    for r in SCREENS.values():
        x0, y0 = r["x"]*W, r["y"]*H; x1, y1 = x0+r["w"]*W, y0+r["h"]*H
        dr.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=(14, 16, 14), outline=(70, 74, 68), width=5)
    flat = os.path.join(G.HERE, f"_fix-{skin}.png"); bg.convert("RGB").save(flat)
    cu = G.upload(flat)
    job = G.submit(cu, PROMPT)
    t0 = time.time()
    while True:
        s = G.get(job["status_url"]).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): raise SystemExit("edit FAIL")
        if time.time() - t0 > 500: raise SystemExit("timeout")
        time.sleep(4)
    url = G.get(job["response_url"])["images"][0]["url"]
    print(f"[{skin}] edited {time.time()-t0:.0f}s", flush=True)
    tmp = os.path.join(G.HERE, f"_fix-{skin}-out.png")
    urllib.request.urlretrieve(url, tmp)
    edited = Image.open(tmp).convert("RGBA").resize(im.size)
    edited.putalpha(im.getchannel("A"))          # original silhouette preserved
    edited.save(src)
    # template: screens at the DRAWN coords; keep existing control regions
    tp = os.path.join(d, "template.json")
    t = json.load(open(tp))
    t["regions"] = [r for r in t["regions"] if r["kind"] != "display"]
    for role, rect in SCREENS.items():
        ins = 0.94  # tiny margin inside the drawn rect
        t["regions"].insert(0, {"id": role, "kind": "display", "content": "dynamic",
            "layer": "screen", "dynamicType": role,
            "rect": {"x": rect["x"]+rect["w"]*(1-ins)/2, "y": rect["y"]+rect["h"]*(1-ins)/2,
                     "w": rect["w"]*ins, "h": rect["h"]*ins}})
    json.dump(t, open(tp, "w"), indent=2)
    print(f"[{skin}] rebuilt (screens at drawn coords)", flush=True)

if __name__ == "__main__":
    main(sys.argv[1])
