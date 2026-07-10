#!/usr/bin/env python3
"""B-proof scale-up: 4 more themes (fa-pod, fallout-vault, wc-goldshield, claymation),
same design as run_bproof_vertex.py — froggo-style light prompt (~600 chars) vs gen12's
heavy constraint prompt, same base model, same seed as gen12's final passing roll.

fal balance is still exhausted (verified live before this run: queue.fal.run returns
"User is locked. Reason: Exhausted balance."), so this goes through Vertex AI directly,
same as the first 2 themes.
"""
import base64, io, json, os, subprocess, sys, time
import requests
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
sys.path.insert(0, GEN12)
import genskin  # for prompt-length reference build only (no fal calls)

PROJ = "muser-2605300220"
VMODEL = "gemini-3-pro-image-preview"
URL = (f"https://aiplatform.googleapis.com/v1/projects/{PROJ}/locations/global/"
       f"publishers/google/models/{VMODEL}:generateContent")
THEMES = ["fa-pod", "fallout-vault", "wc-goldshield", "claymation"]

SHORT_TMPL = (
    "A skeuomorphic media-player device, top-down orthographic, centered on a flat "
    "uniform pale grey-white backdrop: {theme} It has physical controls: five icon "
    "buttons (play/pause, prev, next, repeat, queue), a round volume knob, a "
    "horizontal seek slot, a small toggle switch, an album-art window and a "
    "visualizer window. No text anywhere."
)


def gen12_prompt_len(sid):
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
    tok = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    canvas = os.path.join(HERE, "input-flat.png")
    if not os.path.exists(canvas):
        Image.new("RGB", (1200, 1500), (235, 235, 238)).save(canvas)
    b64 = base64.b64encode(open(canvas, "rb").read()).decode()

    for sid in THEMES:
        out = os.path.join(HERE, f"froggo-{sid}.png")
        if os.path.exists(out):
            print(f"[{sid}] already have {out}, skipping", flush=True)
            continue
        spec = json.load(open(os.path.join(GEN12, "theme_specs", f"{sid}.json")))
        orch = json.load(open(os.path.join(GEN12, f"assets-{sid}", "orch.json")))
        seed = orch["final_seed"]
        prompt = SHORT_TMPL.format(theme=spec["theme_prompt"].strip())
        g12len = gen12_prompt_len(sid)
        print(f"[{sid}] seed={seed} short {len(prompt)} chars vs gen12 {g12len} chars", flush=True)

        body = {
            "contents": [{"role": "user", "parts": [
                {"inline_data": {"mime_type": "image/png", "data": b64}},
                {"text": prompt},
            ]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "seed": seed,
                "candidateCount": 1,
                "imageConfig": {"aspectRatio": "4:5", "imageSize": "4K"},
            },
        }
        t0 = time.time()
        r = requests.post(URL, headers={"Authorization": f"Bearer {tok}",
                                        "Content-Type": "application/json"},
                          json=body, timeout=420)
        if r.status_code != 200:
            print(f"[{sid}] HTTP {r.status_code}: {r.text[:400]}", flush=True)
            continue
        resp = r.json()
        img_b64 = None
        for part in resp["candidates"][0]["content"]["parts"]:
            d = part.get("inlineData") or part.get("inline_data") or {}
            if d.get("data"):
                img_b64 = d["data"]; break
        if not img_b64:
            print(f"[{sid}] no image part: {json.dumps(resp)[:400]}", flush=True)
            continue
        png = base64.b64decode(img_b64)
        open(out, "wb").write(png)
        w, h = Image.open(io.BytesIO(png)).size
        meta = {"id": sid, "model": f"{VMODEL} (Vertex AI, global; same model fal proxies)",
                "seed": seed, "resolution": "4K", "aspect_ratio": "4:5", "dims": [w, h],
                "prompt": prompt, "prompt_chars": len(prompt),
                "gen12_prompt_chars": g12len, "elapsed_s": round(time.time() - t0, 1),
                "input": "flat 1200x1500 RGB(235,235,238) canvas"}
        json.dump(meta, open(os.path.join(HERE, f"froggo-{sid}-meta.json"), "w"), indent=1)
        print(f"[{sid}] done {w}x{h} in {meta['elapsed_s']}s -> {out}", flush=True)


if __name__ == "__main__":
    main()
