#!/usr/bin/env python3
"""run_arm4 — inpaint bake-off ARM 4: test 3 CHEAPER erase options against arm-3's editors/
results, to settle whether any cheap model is viable for the baked-slider-thumb erase.

Models:
  1. fal-ai/flux-pro/v1/erase       $0.004/MP,  mask-required, NO prompt (dedicated eraser)
  2. fal-ai/object-removal/mask     $0.006/img, mask-required, NO prompt (dedicated eraser)
  3. gemini-2.5-flash-image + glow-preserve clause, direct via Vertex AI ($0.039/img, marginally
     cheaper than fal's fal-ai/gemini-25-flash-image/edit at $0.0398/img, and keeps this off
     fal's billing-state dependency per generation-spend-rule) — arm-3's closest cheap
     candidate (2/3 PASS, failed diablo only by erasing the rune-glow); retried here with an
     explicit instruction to preserve any glowing rune/inlay/emissive detail.

Reuses (does not re-run): arm-3's editors/results/{skin}__vertex.png (reused from parent
inpaintbake/results, itself the production-grade baseline) and
editors/results/{skin}__gemini31-flash.png (arm-3's best cheap instruction-editor candidate).

Reuses the SAME crop_path/mask_path/mask_url already built+uploaded by the parent
inpaintbake/build_crops.py + run_bakeoff.py (crops_meta.json, urls.tsv) — no new uploads, no
new crop/mask generation. Read-only against ../ (parent inpaintbake/), writes only under
arm4/.

Usage: python3 run_arm4.py [--skip-flux-erase] [--skip-object-removal] [--skip-gemini-glow]
"""
import argparse, base64, io, json, os, subprocess, sys, time

import requests
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
INPAINTBAKE = os.path.dirname(HERE)
GEN12 = os.path.dirname(INPAINTBAKE)
sys.path.insert(0, GEN12)

CROPS_META = json.load(open(os.path.join(INPAINTBAKE, "crops_meta.json")))
SKINS = ["diablo-gothic", "wc-goldshield", "fallout-vault"]
RESULTS_DIR = os.path.join(HERE, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# already-uploaded fal CDN URLs for these 3 skins' crop+mask (arm-3's editors/urls.tsv) —
# reused verbatim, no re-upload spend/time.
_URLS_TSV = os.path.join(INPAINTBAKE, "editors", "urls.tsv")
FAL_URLS = {}
for line in open(_URLS_TSV):
    k, v = line.strip().split("\t")
    FAL_URLS[k] = v

GLOW_PROMPT_TMPL = (
    "Remove the slider thumb. PRESERVE any glowing rune/inlay/filament pattern and emissive "
    "highlights exactly. Do NOT add any new object/icon/text; only extend the surrounding "
    "groove material. This is a crop of a skeuomorphic device control panel; the thumb sits in "
    "a recessed groove of {material}. Continue that material seamlessly underneath where the "
    "thumb was removed -- same material, same lighting, same recess depth and shading as the "
    "rest of the groove. Change nothing else in the frame."
)

VERTEX_PROJECT = os.environ.get("VERTEX_PROJECT", "muser-2605300220")
VERTEX_GEMINI25_MODEL = "gemini-2.5-flash-image"
VERTEX_URL = (f"https://aiplatform.googleapis.com/v1/projects/{VERTEX_PROJECT}/locations/global/"
              f"publishers/google/models/{VERTEX_GEMINI25_MODEL}:generateContent")
VERTEX_GEMINI25_PRICE = 0.039  # 1290 output tokens x $30/1M, Vertex pricing page (confirmed live)


def load_fal_key():
    envp = "/Users/conner/dev/central/.env"
    for line in open(envp):
        line = line.strip()
        if line.startswith("FAL_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("FAL_KEY not found in central/.env")


def run_flux_pro_erase(cost_log):
    os.environ["FAL_KEY"] = load_fal_key()
    import fal_client
    mp = (1024 * 1024) / 1_000_000.0
    for skin in SKINS:
        out_path = os.path.join(RESULTS_DIR, f"{skin}__flux-pro-erase.png")
        if os.path.exists(out_path):
            print(f"[skip-cached] {skin} x flux-pro-erase")
            continue
        img_url = FAL_URLS[f"{skin}-crop"]
        mask_url = FAL_URLS[f"{skin}-mask"]
        t0 = time.time()
        try:
            result = fal_client.subscribe(
                "fal-ai/flux-pro/v1/erase",
                arguments={"image_url": img_url, "mask_url": mask_url, "output_format": "png"},
                with_logs=False,
            )
        except Exception as e:
            print(f"[FAIL] {skin} x flux-pro-erase: {e}")
            cost_log.append({"skin": skin, "model": "flux-pro-erase", "error": str(e)})
            continue
        dt = time.time() - t0
        img_info = result["images"][0]
        url = img_info["url"] if isinstance(img_info, dict) else img_info
        import urllib.request
        data = urllib.request.urlopen(url, timeout=60).read()
        open(out_path, "wb").write(data)
        cost = round(0.004 * mp, 5)
        print(f"[ok] {skin} x flux-pro-erase -> {out_path} ({dt:.1f}s, ~${cost})")
        cost_log.append({"skin": skin, "model": "flux-pro-erase", "cost": cost,
                          "seconds": round(dt, 1), "endpoint": "fal-ai/flux-pro/v1/erase"})


def run_object_removal(cost_log):
    os.environ["FAL_KEY"] = load_fal_key()
    import fal_client
    for skin in SKINS:
        out_path = os.path.join(RESULTS_DIR, f"{skin}__object-removal.png")
        if os.path.exists(out_path):
            print(f"[skip-cached] {skin} x object-removal")
            continue
        img_url = FAL_URLS[f"{skin}-crop"]
        mask_url = FAL_URLS[f"{skin}-mask"]
        t0 = time.time()
        try:
            result = fal_client.subscribe(
                "fal-ai/object-removal/mask",
                arguments={"image_url": img_url, "mask_url": mask_url, "model": "best_quality"},
                with_logs=False,
            )
        except Exception as e:
            print(f"[FAIL] {skin} x object-removal: {e}")
            cost_log.append({"skin": skin, "model": "object-removal", "error": str(e)})
            continue
        dt = time.time() - t0
        img_info = result["images"][0]
        url = img_info["url"] if isinstance(img_info, dict) else img_info
        import urllib.request
        data = urllib.request.urlopen(url, timeout=60).read()
        open(out_path, "wb").write(data)
        cost = 0.006
        print(f"[ok] {skin} x object-removal -> {out_path} ({dt:.1f}s, ~${cost})")
        cost_log.append({"skin": skin, "model": "object-removal", "cost": cost,
                          "seconds": round(dt, 1), "endpoint": "fal-ai/object-removal/mask"})


def edit_vertex_gemini25(bp_path, prompt, seed, aspect="1:1", image_size="2K"):
    """Same shape as genskin.py:edit_vertex(), but targets gemini-2.5-flash-image instead of
    gemini-3-pro-image-preview (this arm's whole point is testing the cheaper 2.5-flash model)."""
    tok = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    b64 = base64.b64encode(open(bp_path, "rb").read()).decode()
    body = {
        "contents": [{"role": "user", "parts": [
            {"inline_data": {"mime_type": "image/png", "data": b64}},
            {"text": prompt},
        ]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "seed": seed,
            "candidateCount": 1,
            "imageConfig": {"aspectRatio": aspect, "imageSize": image_size},
        },
    }
    for attempt in range(5):
        r = requests.post(VERTEX_URL, headers={"Authorization": f"Bearer {tok}",
                                                "Content-Type": "application/json"},
                           json=body, timeout=420)
        if r.status_code == 429 and attempt < 4:
            wait = 15 * (attempt + 1)
            print(f"[vertex] 429 rate-limited, retry {attempt+1}/5 in {wait}s", flush=True)
            time.sleep(wait)
            continue
        break
    if r.status_code != 200:
        raise RuntimeError(f"vertex HTTP {r.status_code}: {r.text[:500]}")
    for part in r.json()["candidates"][0]["content"]["parts"]:
        d = part.get("inlineData") or part.get("inline_data") or {}
        if d.get("data"):
            return base64.b64decode(d["data"])
    raise RuntimeError("vertex: no image part in response")


def run_gemini_glow(cost_log):
    for skin in SKINS:
        out_path = os.path.join(RESULTS_DIR, f"{skin}__gemini25-flash-glow.png")
        if os.path.exists(out_path):
            print(f"[skip-cached] {skin} x gemini25-flash-glow")
            continue
        meta = CROPS_META[skin]
        prompt = GLOW_PROMPT_TMPL.format(material=meta["material"])
        seed = meta["seed"] or 1234
        crop_size = Image.open(meta["crop_path"]).size
        t0 = time.time()
        try:
            png_bytes = edit_vertex_gemini25(meta["crop_path"], prompt, seed, aspect="1:1",
                                              image_size="2K")
        except Exception as e:
            print(f"[FAIL] {skin} x gemini25-flash-glow: {e}")
            cost_log.append({"skin": skin, "model": "gemini25-flash-glow", "error": str(e)})
            continue
        dt = time.time() - t0
        out = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        if out.size != tuple(crop_size):
            out = out.resize(crop_size, Image.LANCZOS)
        out.save(out_path)
        print(f"[ok] {skin} x gemini25-flash-glow -> {out_path} ({dt:.1f}s, "
              f"~${VERTEX_GEMINI25_PRICE})")
        cost_log.append({"skin": skin, "model": "gemini25-flash-glow",
                          "cost": VERTEX_GEMINI25_PRICE, "seconds": round(dt, 1),
                          "endpoint": f"vertex:{VERTEX_GEMINI25_MODEL}"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-flux-erase", action="store_true")
    ap.add_argument("--skip-object-removal", action="store_true")
    ap.add_argument("--skip-gemini-glow", action="store_true")
    args = ap.parse_args()

    cost_log_path = os.path.join(HERE, "cost_log.json")
    cost_log = json.load(open(cost_log_path)) if os.path.exists(cost_log_path) else []

    if not args.skip_flux_erase:
        run_flux_pro_erase(cost_log)
        json.dump(cost_log, open(cost_log_path, "w"), indent=2)
    if not args.skip_object_removal:
        run_object_removal(cost_log)
        json.dump(cost_log, open(cost_log_path, "w"), indent=2)
    if not args.skip_gemini_glow:
        run_gemini_glow(cost_log)
        json.dump(cost_log, open(cost_log_path, "w"), indent=2)

    total = sum(c.get("cost", 0) or 0 for c in cost_log)
    print(f"\nTotal arm4 generation spend so far: ${total:.4f}")


if __name__ == "__main__":
    main()
