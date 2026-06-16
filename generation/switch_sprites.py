#!/usr/bin/env python3
"""Regenerate switch-off/on sprites as SLOT-FILLING recessed bezel toggles: the
sprite IS the slot — a recessed rectangular bezel with a toggle lever, filling the
whole frame edge-to-edge, so when it's stretched to fill its region box it reads as
a switch set flush into the body. Two states (OFF lever-down | ON lever-up) side by
side, identical bezel, split at the midline. Material-matched per donor style.

Usage: python3 switch_sprites.py <style> [<style> ...]
"""
import io, os, sys, time, urllib.request, concurrent.futures
from PIL import Image
import generate as G
from gen_sprites import MAT

ROOT = os.path.dirname(G.HERE)

PROMPT = (
    "A horizontal pair of TWO identical hardware TOGGLE-SWITCH panels side by side, touching, on a solid "
    "pure-white background. EACH panel is a RECESSED RECTANGULAR BEZEL that FILLS its half of the image "
    "EDGE TO EDGE (the raised beveled rim is right at the panel border, a dark inset slot inside it) with a "
    "rounded toggle lever centered in the slot. LEFT panel = OFF (lever tilted DOWN, indicator dark). RIGHT "
    "panel = ON (identical panel, lever tilted UP, indicator lit/glowing). Identical size and position, only "
    "the lever and indicator differ. Photoreal, front-on orthographic, even studio light, crisp, no text, "
    "no drop shadow outside the panels. The bezel must be flush and fill the frame — NOT a small object on a "
    "surface. MATERIAL of the bezel and lever: {mat}"
)


def gen(style):
    mat = MAT.get(style, MAT["winamp"])
    job = G.post("https://queue.fal.run/fal-ai/gpt-image-1.5", {
        "prompt": PROMPT.format(mat=mat), "image_size": "1536x1024", "quality": "high",
        "background": "transparent", "output_format": "png"})
    su, ru = job["status_url"], job["response_url"]; t0 = time.time()
    while True:
        s = G.get(su).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): print(f"[{style}] FAIL", flush=True); return
        if time.time() - t0 > 300: print(f"[{style}] timeout", flush=True); return
        time.sleep(3)
    url = G.get(ru)["images"][0]["url"]
    im = Image.open(io.BytesIO(urllib.request.urlopen(url, timeout=120).read())).convert("RGBA")
    W, H = im.size
    mid = W // 2
    off = im.crop((0, 0, mid, H))
    on = im.crop((mid, 0, W, H))
    out = os.path.join(ROOT, "public", "skins", style, "sprites")
    os.makedirs(out, exist_ok=True)
    off.save(os.path.join(out, "switch-off.png"))
    on.save(os.path.join(out, "switch-on.png"))
    print(f"[{style}] slot-filling switch saved ({time.time()-t0:.0f}s)", flush=True)


if __name__ == "__main__":
    styles = sys.argv[1:] or list(MAT.keys())
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(gen, styles))
    print("DONE", flush=True)
