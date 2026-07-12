#!/usr/bin/env python3
"""run_arm5 -- inpaint bake-off ARM 5: head-to-head of the two cost-efficient frontrunners from
arm-3 (Gemini 2.5 Flash Image, GPT Image 2) across a BROADER material range (5 skins instead of
arm-3's 3) to see whether arm-3's ranking (Gemini 2/3 soft-fail on rune-glow loss, GPT ~1/3
hard-hallucination) generalizes or was skin-specific.

PROMPT: the plain shipping erase12.py instruction (no glow/rune/inlay/emissive mention). A
PRESERVE-GLOW variant was tried first and discarded per orchestrator directive mid-run: it
over-constrained the model into INVENTING new glow ornamentation (see diablo-gothic's gemini
result under discarded-glowclause/ -- a hallucinated horned-skull medallion with its own glow,
worse than the original miss). Results from that discarded run are archived under
discarded-glowclause/ (real spend, kept for the record) but are NOT part of this arm's verdict.

Models:
  1. Gemini 2.5 Flash Image -- direct via Vertex AI (generation-spend-rule SS3: Google models go
     direct, not fal-wrapped), model id gemini-2.5-flash-image, imageConfig.imageSize="2K" (same
     price as 1K, no 2048px ceiling issue for our 1024 crops -- the exact bug the parent repo's
     most recent commit fixed for erase12's crop repairs). $0.039/call, confirmed in arm4.
  2. GPT Image 2 -- fal openai/gpt-image-2/edit (OpenAI-hosted only via fal, no direct API key
     held here -- legitimate fal-hosted exception per generation-spend-rule). Real cost measured
     via the x-fal-billable-units response header x $1/unit list price ("high" quality measured
     ~$0.22/call live here -- NOT arm-3's stale $0.0612; "medium" quality measured ~$0.055/call,
     matching arm-3's number, so "medium" is what this arm uses).

Both models get the SAME plain instruction on the SAME 1024x1024 crop + mask for a given skin
(parallel-by-default-rule's "write the exact seam contract first").

Usage: python3 run_arm5.py [--skip-gemini] [--skip-gpt] [--only SKIN]
"""
import argparse, base64, json, os, sys, time

import requests
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ARM5_META = json.load(open(os.path.join(HERE, "arm5_crops_meta.json")))
RESULTS_DIR = os.path.join(HERE, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# Plain shipping erase12.py instruction -- verbatim per orchestrator directive. No material
# templating, no glow/rune/inlay mention: let the model handle material continuation naturally.
PROMPT_TMPL = (
    "This is a tight crop of a slider/control's recessed groove/socket from a skeuomorphic "
    "device. A part (thumb/handle/grip/cap) is sitting in it and must be REMOVED. Erase that "
    "part completely and continue the groove/socket's own material. Do not leave a bulge, "
    "pocket, or widened opening shaped like the removed part. Do not add any new object, icon, "
    "or text."
)

VERTEX_PROJECT = os.environ.get("VERTEX_PROJECT", "muser-2605300220")
VERTEX_GEMINI25_MODEL = "gemini-2.5-flash-image"
VERTEX_URL = (f"https://aiplatform.googleapis.com/v1/projects/{VERTEX_PROJECT}/locations/global/"
              f"publishers/google/models/{VERTEX_GEMINI25_MODEL}:generateContent")
VERTEX_GEMINI25_PRICE = 0.039  # confirmed arm4, Vertex pricing page, 2K tier

GPT_IMAGE2_ENDPOINT = "openai/gpt-image-2/edit"


def load_fal_key():
    envp = "/Users/conner/dev/central/.env"
    for line in open(envp):
        line = line.strip()
        if line.startswith("FAL_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("FAL_KEY not found in central/.env")


def edit_vertex_gemini25(bp_path, prompt, seed, aspect="1:1", image_size="2K"):
    """Same shape as arm4/run_arm4.py:edit_vertex_gemini25() (proven, already ran real
    generations there) -- ported verbatim, targets gemini-2.5-flash-image via Vertex direct."""
    import subprocess
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


def run_gemini(skins, cost_log):
    for skin in skins:
        out_path = os.path.join(RESULTS_DIR, f"{skin}__gemini25-flash.png")
        if os.path.exists(out_path):
            print(f"[skip-cached] {skin} x gemini25-flash")
            continue
        meta = ARM5_META[skin]
        prompt = PROMPT_TMPL
        seed = meta["seed"] or 1234
        crop_size = Image.open(meta["crop_path"]).size
        t0 = time.time()
        try:
            png_bytes = edit_vertex_gemini25(meta["crop_path"], prompt, seed, aspect="1:1",
                                              image_size="2K")
        except Exception as e:
            print(f"[FAIL] {skin} x gemini25-flash: {e}")
            cost_log.append({"skin": skin, "model": "gemini25-flash", "error": str(e)})
            continue
        dt = time.time() - t0
        import io
        out = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        if out.size != tuple(crop_size):
            out = out.resize(crop_size, Image.LANCZOS)
        out.save(out_path)
        print(f"[ok] {skin} x gemini25-flash -> {out_path} ({dt:.1f}s, ~${VERTEX_GEMINI25_PRICE})")
        cost_log.append({"skin": skin, "model": "gemini25-flash", "cost": VERTEX_GEMINI25_PRICE,
                          "seconds": round(dt, 1), "endpoint": f"vertex:{VERTEX_GEMINI25_MODEL}"})


def run_gpt_image2(skins, cost_log, quality="medium"):
    fal_key = load_fal_key()
    for skin in skins:
        out_path = os.path.join(RESULTS_DIR, f"{skin}__gpt-image-2.png")
        if os.path.exists(out_path):
            print(f"[skip-cached] {skin} x gpt-image-2")
            continue
        meta = ARM5_META[skin]
        prompt = PROMPT_TMPL

        import fal_client
        os.environ["FAL_KEY"] = fal_key
        img_url = fal_client.upload_file(meta["crop_path"])
        mask_url = fal_client.upload_file(meta["mask_path"])

        payload = {
            "image_urls": [img_url],
            "mask_url": mask_url,
            "prompt": prompt,
            "quality": quality,
            "image_size": "square",  # gpt-image-2's enum ('square_hd'/'square'/'portrait_4_3'/
                                      # 'portrait_16_9'/'landscape_4_3'/'landscape_16_9'/'auto'),
                                      # NOT gpt-image-1.5's "1024x1024" string (verified via a
                                      # live 422 -- this endpoint's schema differs from its
                                      # sibling model despite both being OpenAI GPT-Image editors)
            "output_format": "png",
        }
        t0 = time.time()
        try:
            r = requests.post(
                f"https://fal.run/{GPT_IMAGE2_ENDPOINT}",
                headers={"Authorization": f"Key {fal_key}", "Content-Type": "application/json"},
                json=payload, timeout=180,
            )
            r.raise_for_status()
        except Exception as e:
            print(f"[FAIL] {skin} x gpt-image-2: {e}")
            cost_log.append({"skin": skin, "model": "gpt-image-2", "error": str(e)})
            continue
        dt = time.time() - t0
        billable = r.headers.get("x-fal-billable-units")
        cost = float(billable) * 1.0 if billable else None
        data = r.json()
        img_url_out = data["images"][0]["url"] if isinstance(data["images"][0], dict) else data["images"][0]
        import urllib.request
        img_bytes = urllib.request.urlopen(img_url_out, timeout=60).read()
        open(out_path, "wb").write(img_bytes)
        print(f"[ok] {skin} x gpt-image-2 -> {out_path} ({dt:.1f}s, billable_units={billable}, "
              f"~${cost}, quality={quality})")
        cost_log.append({"skin": skin, "model": "gpt-image-2", "cost": cost,
                          "billable_units_header": billable, "seconds": round(dt, 1),
                          "endpoint": GPT_IMAGE2_ENDPOINT, "quality": quality})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-gemini", action="store_true")
    ap.add_argument("--skip-gpt", action="store_true")
    ap.add_argument("--only", default=None, help="comma-separated skin subset")
    ap.add_argument("--gpt-quality", default="medium", choices=["low", "medium", "high"])
    args = ap.parse_args()

    skins = list(ARM5_META.keys())
    if args.only:
        skins = [s.strip() for s in args.only.split(",")]

    cost_log_path = os.path.join(HERE, "cost_log.json")
    cost_log = json.load(open(cost_log_path)) if os.path.exists(cost_log_path) else []

    if not args.skip_gemini:
        run_gemini(skins, cost_log)
        json.dump(cost_log, open(cost_log_path, "w"), indent=2)
    if not args.skip_gpt:
        run_gpt_image2(skins, cost_log, quality=args.gpt_quality)
        json.dump(cost_log, open(cost_log_path, "w"), indent=2)

    total = sum(c.get("cost", 0) or 0 for c in cost_log)
    print(f"\nTotal arm5 generation spend so far: ${total:.4f}")


if __name__ == "__main__":
    main()
