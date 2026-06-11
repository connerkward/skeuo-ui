#!/usr/bin/env python3
"""Generate control-free FACEPLATE frames: bezel + panel + EMPTY inset screens,
NO buttons/knobs/switches/sliders. The controls are a live CSS layer composited
on top at runtime, so they're real, stateful and animated (flip switches flip).

Renders a faceplate blueprint (FACEPLATE=1) then styles it per skin via Nano
Banana. Overwrites public/skins/<id>/frame.png. Run: python3 gen_faceplate.py [ids]
"""
import os, subprocess, time, urllib.request, concurrent.futures
import generate as G

ROOT = os.path.dirname(G.HERE)

FACE = (
    "Photorealistic 3D-rendered skeuomorphic media-player FACEPLATE — a BLANK control panel, front-on "
    "orthographic view, no perspective, even studio lighting, crisp high detail, fills the frame. "
    "Render ONLY: the outer bezel/frame and a single FLAT BLANK faceplate panel surface, ornamented at "
    "the corners and edges (screws, filigree, trim as fits the material). CRITICAL: the panel interior "
    "is COMPLETELY BLANK and FLAT — do NOT draw ANY screens, displays, buttons, knobs, switches, "
    "sliders, recesses, grilles, logos or text. Just the empty material faceplate (screens and controls "
    "are mounted on top separately). MATERIAL: "
)
MATERIAL = {
    "winamp": "late-1990s Winamp — brushed gunmetal and dark charcoal plastic with polished chrome bevels and tiny phillips corner screws; near-black glass screens.",
    "fallout": "Fallout Pip-Boy / RobCo industrial — scuffed olive-drab riveted metal with worn paint, monochrome amber-green tint; dark curved CRT glass screens.",
    "fantasy": "Baldur's-Gate / Warcraft fantasy — carved cool gray-green dungeon stone framed in ornate bright-gold filigree with gemstones and brass; obsidian glass screens rimmed in gold.",
    "aqua": "Mac OS X Aqua — glossy brushed-aluminium with faint horizontal pinstripes and a bright white highlight; pale glossy light-blue glass screens. Clean and LIGHT.",
    "hifi": "1970s hi-fi receiver — wide brushed-aluminium faceplate framed by warm walnut-veneer wood end-caps; warm fluorescent teal-green tuner glass screens.",
    "papercraft": "hand-made papercraft — folded kraft cardboard and cut-paper with visible creases and corrugated edges, matte, no gloss; plain white paper screens.",
}

def run(skin, control_url):
    job = G.submit(control_url, FACE + MATERIAL[skin])
    su, ru = job["status_url"], job["response_url"]
    t0 = time.time()
    while True:
        s = G.get(su).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): print(f"[{skin}] FAIL", flush=True); return
        if time.time() - t0 > 500: print(f"[{skin}] timeout", flush=True); return
        time.sleep(4)
    url = G.get(ru)["images"][0]["url"]
    out = os.path.join(ROOT, "public", "skins", skin, "frame.png")
    urllib.request.urlretrieve(url, out)
    print(f"[{skin}] faceplate {time.time()-t0:.0f}s -> {out}", flush=True)

def main():
    ids = [a for a in os.sys.argv[1:]] or list(MATERIAL.keys())
    # render the faceplate blueprint (controls omitted)
    ctrl = os.path.join(G.HERE, "faceplate.png")
    subprocess.run(["python3", os.path.join(G.HERE, "render_control.py")],
                   env=dict(os.environ, FACEPLATE="1", CONTROL_OUT=ctrl), check=True)
    cu = G.upload(ctrl)
    print("faceplate blueprint:", cu, flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(lambda s: run(s, cu), ids))
    print("ALL DONE", flush=True)

if __name__ == "__main__":
    main()
