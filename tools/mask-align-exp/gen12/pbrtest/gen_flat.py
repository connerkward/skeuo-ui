#!/usr/bin/env python3
"""pbrtest step 1 — generate a FLAT-ALBEDO skin (steam-porthole theme) via Vertex AI.

Call pattern copied from bproof/run_bproof_vertex.py (fal is 403/balance-exhausted).
Model: gemini-3-pro-image-preview, project muser-2605300220, location global.
The prompt forces flat/uniform diffuse lighting (pure albedo, no baked speculars /
shadows / AO) so a normal map can relight it dynamically in WebGL.
"""
import base64, io, json, os, subprocess, sys, time
import requests
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)

PROJ = "muser-2605300220"
VMODEL = "gemini-3-pro-image-preview"
URL = (f"https://aiplatform.googleapis.com/v1/projects/{PROJ}/locations/global/"
       f"publishers/google/models/{VMODEL}:generateContent")

# steam-porthole theme_prompt with the baked-lighting phrases stripped
# ("rich reflections" directly contradicts a flat albedo read).
THEME = ("STEAMPUNK BRASS nautilus / diving-bell media player: riveted polished "
         "BRASS and COPPER housing with a big round porthole, pressure-gauge dials, "
         "engraved filigree, patina, glass tubes and a teal-glass display. "
         "Victorian submarine machinery — ornate, mechanical, warm metal.")

FLAT_CLAUSE = (
    " Rendered with FLAT EVEN DIFFUSE LIGHTING ONLY — this is a pure albedo/diffuse "
    "texture map for a PBR pipeline: ZERO specular highlights, ZERO baked shadows, "
    "no ambient occlusion, no glow, no reflections, no rim light, no gradients from "
    "lighting; every surface shows only its intrinsic flat material color, uniform "
    "studio-flat illumination as if photographed inside an integrating sphere. "
    "Depth is conveyed by shape and material color only, never by shading.")

PROMPT = (
    "A skeuomorphic media-player device, top-down orthographic, centered on a flat "
    "uniform pale grey-white backdrop: " + THEME + " It has physical controls: five "
    "icon buttons (play/pause, prev, next, repeat, queue), a round volume knob, a "
    "horizontal seek slot, a small toggle switch, an album-art window and a "
    "visualizer window. No text anywhere." + FLAT_CLAUSE)


def main():
    rolls = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    tok = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    canvas = os.path.join(HERE, "input-flat.png")
    Image.new("RGB", (1200, 1500), (235, 235, 238)).save(canvas)
    b64 = base64.b64encode(open(canvas, "rb").read()).decode()

    for i in range(rolls):
        seed = 84 + i * 1000
        body = {
            "contents": [{"role": "user", "parts": [
                {"inline_data": {"mime_type": "image/png", "data": b64}},
                {"text": PROMPT},
            ]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "seed": seed,
                "candidateCount": 1,
                "imageConfig": {"aspectRatio": "4:5", "imageSize": "2K"},
            },
        }
        t0 = time.time()
        r = requests.post(URL, headers={"Authorization": f"Bearer {tok}",
                                        "Content-Type": "application/json"},
                          json=body, timeout=420)
        if r.status_code != 200:
            print(f"[roll{i}] HTTP {r.status_code}: {r.text[:400]}", flush=True)
            continue
        resp = r.json()
        img_b64 = None
        for part in resp["candidates"][0]["content"]["parts"]:
            d = part.get("inlineData") or part.get("inline_data") or {}
            if d.get("data"):
                img_b64 = d["data"]; break
        if not img_b64:
            print(f"[roll{i}] no image part: {json.dumps(resp)[:400]}", flush=True)
            continue
        png = base64.b64decode(img_b64)
        out = os.path.join(HERE, f"albedo-roll{i}.png")
        open(out, "wb").write(png)
        w, h = Image.open(io.BytesIO(png)).size
        meta = {"roll": i, "model": f"{VMODEL} (Vertex AI, global)", "seed": seed,
                "resolution": "2K", "aspect_ratio": "4:5", "dims": [w, h],
                "prompt": PROMPT, "elapsed_s": round(time.time() - t0, 1)}
        json.dump(meta, open(os.path.join(HERE, f"albedo-roll{i}-meta.json"), "w"), indent=1)
        print(f"[roll{i}] done {w}x{h} seed={seed} in {meta['elapsed_s']}s -> {out}", flush=True)


if __name__ == "__main__":
    main()
