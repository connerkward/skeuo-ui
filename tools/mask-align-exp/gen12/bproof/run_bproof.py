#!/usr/bin/env python3
"""B-proof: does gen12's heavy constraint load degrade painted-skin quality?

Per theme, ONE froggo-style generation: same model, same seed as the gen12 final
roll, same 4K resolution, same theme_prompt verbatim, same flat backdrop tone —
but a SHORT prompt (roster stated once, zero mask/strip/empty-socket/exact-fit
clauses) and a minimal flat-canvas input. Only the constraint load varies.

Writes: bproof/froggo-<id>.png + froggo-<id>-meta.json + gen12ref/assets-<id>/
(blueprint + prompt_len via genskin --blueprint-only, originals untouched).
"""
import io, json, os, re, sys, time
import requests
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
sys.path.insert(0, GEN12)
import genskin

MODEL = genskin.MODEL  # fal-ai/gemini-3-pro-image-preview/edit
THEMES = ["steam-porthole", "diablo-gothic"]

SHORT_TMPL = (
    "A skeuomorphic media-player device, top-down orthographic, centered on a flat "
    "uniform pale grey-white backdrop: {theme} It has physical controls: five icon "
    "buttons (play/pause, prev, next, repeat, queue), a round volume knob, a "
    "horizontal seek slot, a small toggle switch, an album-art window and a "
    "visualizer window. No text anywhere."
)


def gen12_prompt_len(sid):
    """Run genskin --blueprint-only with HERE redirected under bproof/gen12ref."""
    ref = os.path.join(HERE, "gen12ref")
    os.makedirs(ref, exist_ok=True)
    old_here, old_argv = genskin.HERE, sys.argv
    genskin.HERE = ref
    sys.argv = ["genskin.py", os.path.join(GEN12, "theme_specs", f"{sid}.json"), "--blueprint-only"]
    try:
        genskin.main()
    finally:
        genskin.HERE, sys.argv = old_here, old_argv
    return json.load(open(os.path.join(ref, f"assets-{sid}", "results.json")))["prompt_len"]


def main():
    FAL = genskin.load_fal()
    # flat minimal input canvas — same pale backdrop gen12 used for these dark-material
    # themes (material_is_dark → BG (235,235,238)), 4:5 to approximate the gen12 device
    # area shape (1200x1440 device column = 5:6)
    canvas = os.path.join(HERE, "input-flat.png")
    Image.new("RGB", (1200, 1500), (235, 235, 238)).save(canvas)
    url = genskin.upload(FAL, canvas)

    for sid in THEMES:
        spec = json.load(open(os.path.join(GEN12, "theme_specs", f"{sid}.json")))
        orch = json.load(open(os.path.join(GEN12, f"assets-{sid}", "orch.json")))
        seed = orch["final_seed"]
        prompt = SHORT_TMPL.format(theme=spec["theme_prompt"].strip())
        g12len = gen12_prompt_len(sid)
        print(f"[{sid}] seed={seed} short-prompt {len(prompt)} chars vs gen12 {g12len} chars", flush=True)

        t0 = time.time()
        job = requests.post(f"https://queue.fal.run/{MODEL}",
            headers={"Authorization": f"Key {FAL}", "Content-Type": "application/json"},
            json={"prompt": prompt, "image_urls": [url], "resolution": "4K",
                  "aspect_ratio": "4:5", "output_format": "png", "num_images": 1,
                  "seed": seed}).json()
        if "status_url" not in job:
            print(f"[{sid}] SUBMIT FAILED: {job}", flush=True); continue
        while True:
            s = requests.get(job["status_url"], headers={"Authorization": f"Key {FAL}"}).json().get("status")
            if s == "COMPLETED": break
            if s in ("FAILED", "ERROR") or time.time() - t0 > 420:
                raise RuntimeError(f"{sid} fal {s}")
            time.sleep(4)
        r = requests.get(job["response_url"], headers={"Authorization": f"Key {FAL}"}).json()
        png = requests.get(r["images"][0]["url"]).content
        out = os.path.join(HERE, f"froggo-{sid}.png")
        open(out, "wb").write(png)
        w, h = Image.open(io.BytesIO(png)).size
        meta = {"id": sid, "model": MODEL, "seed": seed, "resolution": "4K",
                "aspect_ratio": "4:5", "dims": [w, h],
                "prompt": prompt, "prompt_chars": len(prompt),
                "gen12_prompt_chars": g12len, "elapsed_s": round(time.time() - t0, 1),
                "input": "flat 1200x1500 RGB(235,235,238) canvas"}
        json.dump(meta, open(os.path.join(HERE, f"froggo-{sid}-meta.json"), "w"), indent=1)
        print(f"[{sid}] done {w}x{h} in {meta['elapsed_s']}s -> {out}", flush=True)


if __name__ == "__main__":
    main()
