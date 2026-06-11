#!/usr/bin/env python3
"""WILD shapes: let gpt-image-2 freely DESIGN a non-rectangular player (no
blueprint constraint), cut out the background to a real silhouette, and extract
a template so it stays interactive. This is the freeform loop + creative-shape
prompt + cutout.

Usage: python3 wild.py <style> <out_id>
"""
import json, os, sys, time, urllib.request
import generate as G
import freeform as F
from freeform_all import enrich

ROOT = os.path.dirname(G.HERE)
W, H = 1024, 1536

WILD = (
    "Design a CREATIVE, WILDLY NON-RECTANGULAR skeuomorphic MUSIC PLAYER as a single custom-shaped "
    "object with an IRREGULAR, ASYMMETRIC silhouette — absolutely NOT a rectangle or rounded rectangle. "
    "Think a 90s Winamp 'modern' skin, a boombox, a robot/creature face, a spaceship cockpit console, a "
    "hot-rod dashboard: jutting fins, swooping curves, notched and angled edges, antennae or feet. It "
    "must still contain clear, well-separated PHYSICAL controls: a row of transport buttons, one or two "
    "round knobs, a set of vertical EQ faders, a horizontal slider, a couple of toggle/segmented "
    "switches, a dark DISPLAY screen, and a PLAYLIST area — every control a clean separate shape, no "
    "text inside screens. Center the whole device on a FLAT pure-white (#ffffff) background with NO "
    "shadow (for clean masking). Front-on orthographic, no perspective, high detail. MATERIAL/STYLE: "
)
STYLE = {
    "winamp": "late-90s brushed gunmetal and chrome with green-LCD accents, glossy dark plastic.",
    "fantasy": "carved gray-green stone with ornate bright-gold filigree, gemstones and brass — a fantasy-RPG artifact.",
    "hifi": "1970s walnut wood and brushed aluminium with knurled silver knobs and warm amber lamps.",
    "fallout": "scuffed olive-drab riveted metal, retro-futuristic RobCo industrial, monochrome amber-green.",
    "aqua": "glossy translucent white and candy-blue Mac OS X Aqua gel, brushed aluminium.",
    "papercraft": "folded kraft cardboard and cut-paper with marker labels, matte and hand-made.",
}

def gen_wild(style):
    job = G.post("https://queue.fal.run/openai/gpt-image-2", {
        "prompt": WILD + STYLE[style], "image_size": {"width": W, "height": H},
        "quality": "high", "output_format": "png"})
    su, ru = job["status_url"], job["response_url"]
    t0 = time.time()
    while True:
        s = G.get(su).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): raise SystemExit(f"{style} gen FAIL")
        if time.time() - t0 > 500: raise SystemExit("timeout")
        time.sleep(4)
    url = G.get(ru)["images"][0]["url"]
    print(f"[{style}] wild design {time.time()-t0:.0f}s {url}", flush=True)
    return url

def cutout(image_url):
    job = G.post("https://queue.fal.run/fal-ai/birefnet/v2", {
        "image_url": image_url, "model": "General Use (Heavy)",
        "operating_resolution": "2048x2048", "refine_foreground": True, "output_format": "png"})
    su, ru = job["status_url"], job["response_url"]
    t0 = time.time()
    while True:
        s = G.get(su).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): raise SystemExit("cutout FAIL")
        if time.time() - t0 > 300: raise SystemExit("cutout timeout")
        time.sleep(3)
    print(f"cutout {time.time()-t0:.0f}s", flush=True)
    return G.get(ru)["image"]["url"]

def main():
    style = sys.argv[1] if len(sys.argv) > 1 else "winamp"
    out_id = sys.argv[2] if len(sys.argv) > 2 else f"{style}-shaped"
    url = gen_wild(style)
    tpl = enrich(F.to_template(F.extract(url)))
    cut = cutout(url)
    dest = os.path.join(ROOT, "public", "skins", out_id); os.makedirs(dest, exist_ok=True)
    urllib.request.urlretrieve(cut, os.path.join(dest, "frame.png"))
    json.dump(tpl, open(os.path.join(dest, "template.json"), "w"), indent=2)
    # also save the raw (pre-cutout) design for inspection
    urllib.request.urlretrieve(url, os.path.join(G.HERE, "freeform", f"wild-{out_id}-raw.png"))
    print("saved", out_id, f"({len(tpl['regions'])} regions)", flush=True)

if __name__ == "__main__":
    main()
