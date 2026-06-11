#!/usr/bin/env python3
"""FREE-designed creature bodies (the gorgeous gpt-image-2 silhouettes) made
FUNCTIONAL: empty screens + empty wells in the prompt, BiRefNet cutout, then
pixel-accurate CV well/screen detection (detect_wells) builds the template.

Usage: python3 wild_free.py <id> <style> "<creature brief>"
"""
import os, sys, time, urllib.request
import generate as G
import detect_wells as DW

ROOT = os.path.dirname(G.HERE)
W, H = 1024, 1536

BODY = (
    "Design a breathtaking, WILDLY NON-RECTANGULAR skeuomorphic MP3-player device: {brief}. "
    "Sleek sculpted photoreal hardware, front-on orthographic, centered on a FLAT pure-white "
    "background, no shadow outside the device, extremely high detail. It must contain, integrated "
    "into the body: ONE wide DISPLAY screen in the upper half and ONE large PLAYLIST screen in the "
    "lower half — both COMPLETELY EMPTY switched-off near-black glass (no text, no graphics, no "
    "reflections of content). Plus EMPTY RECESSED MOUNTING WELLS (bare dark sockets, NOTHING mounted "
    "inside them): a neat row of FIVE small rounded-square wells (transport buttons), TWO round "
    "circular wells (knobs), a row of SIX short VERTICAL slot channels (EQ faders), ONE long thin "
    "HORIZONTAL groove (seek), and TWO small vertical rectangular wells (switches). Every well "
    "clearly visible, dark, and empty. MATERIAL: {mat}"
)

def gen(out_id, brief, mat):
    job = G.post("https://queue.fal.run/openai/gpt-image-2", {
        "prompt": BODY.format(brief=brief, mat=mat),
        "image_size": {"width": W, "height": H}, "quality": "high", "output_format": "png"})
    t0 = time.time()
    while True:
        s = G.get(job["status_url"]).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): raise SystemExit("gen FAIL")
        if time.time() - t0 > 520: raise SystemExit("timeout")
        time.sleep(4)
    url = G.get(job["response_url"])["images"][0]["url"]
    print(f"[{out_id}] designed {time.time()-t0:.0f}s", flush=True)
    job = G.post("https://queue.fal.run/fal-ai/birefnet/v2", {
        "image_url": url, "model": "General Use (Heavy)",
        "operating_resolution": "2048x2048", "refine_foreground": True, "output_format": "png"})
    t0 = time.time()
    while True:
        s = G.get(job["status_url"]).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): raise SystemExit("cutout FAIL")
        if time.time() - t0 > 300: raise SystemExit("cutout timeout")
        time.sleep(3)
    cut = G.get(job["response_url"])["image"]["url"]
    dest = os.path.join(ROOT, "public", "skins", out_id)
    os.makedirs(dest, exist_ok=True)
    urllib.request.urlretrieve(cut, os.path.join(dest, "frame.png"))
    DW.build(dest)   # pixel-accurate screens + wells → template.json + _overlay.png
    print(f"[{out_id}] saved", flush=True)

if __name__ == "__main__":
    out_id, style, brief = sys.argv[1], sys.argv[2], sys.argv[3]
    mat = {
        "winamp": "polished chrome and brushed gunmetal over dark charcoal plastic, thin green LED accent lines tracing the curves, tiny screws — late-90s Winamp-skin hardware at its most extreme.",
    }.get(style, "polished chrome")
    gen(out_id, brief, mat)
