#!/usr/bin/env python3
"""run_bakeoff — run every finalist inpaint model on every crop built by build_crops.py.

Fal models called directly via fal_client (same REST API the fal MCP wraps — not a
reimplementation, the real service) using FAL_KEY sourced from central/.env (never printed,
never logged, per security-rule). LaMa runs locally via .venv-biref's torch/MPS. Vertex reuses
genskin.py's proven edit_vertex() helper (discover-before-building-rule) for 4 of 5 crops —
diablo-gothic's Vertex arm is REUSED from the existing production erase12-log.json attempt
(3 real Vertex calls already spent there) rather than re-spending, per generation-spend-rule.

Usage: python3 run_bakeoff.py [--skip-fal] [--skip-vertex] [--skip-lama]
"""
import argparse, base64, io, json, os, subprocess, sys, time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
sys.path.insert(0, GEN12)

CROPS_META = json.load(open(os.path.join(HERE, "crops_meta.json")))
RESULTS_DIR = os.path.join(HERE, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

PROMPT_TMPL = (
    "This is a crop of a skeuomorphic device control panel. A slider thumb/handle/grip "
    "currently sits in a recessed groove and must be REMOVED from the masked region. Erase "
    "it completely and continue the {material} SEAMLESSLY underneath where it was — same "
    "material, same lighting, same recess depth and shading as the rest of the groove. Do "
    "not leave any bulge, highlight, or residual shape from the removed part. Change nothing "
    "else in the frame."
)

FAL_MODELS = {
    "z-image-turbo": {
        "endpoint": "fal-ai/z-image/turbo/inpaint",
        "price_per_mp": 0.01,
        "build_input": lambda img_url, mask_url, prompt: {
            "image_url": img_url, "mask_url": mask_url, "prompt": prompt,
        },
        "mask_param": "mask_image_url",
    },
    "qwen-inpaint": {
        "endpoint": "fal-ai/qwen-image-edit/inpaint",
        "price_per_mp": 0.03,
        "build_input": lambda img_url, mask_url, prompt: {
            "image_url": img_url, "mask_url": mask_url, "prompt": prompt,
        },
    },
    "flux-pro-fill": {
        "endpoint": "fal-ai/flux-pro/v1/fill",
        "price_per_mp": 0.05,
        "build_input": lambda img_url, mask_url, prompt: {
            "image_url": img_url, "mask_url": mask_url, "prompt": prompt,
        },
    },
    "flux-dev-fill": {
        "endpoint": "fal-ai/flux-lora-fill",
        "price_per_mp": 0.035,
        "build_input": lambda img_url, mask_url, prompt: {
            "image_url": img_url, "mask_url": mask_url, "prompt": prompt, "paste_back": True,
        },
    },
}

# z-image's schema names the mask param "mask_image_url"; the others use "mask_url".
FAL_MASK_PARAM = {
    "z-image-turbo": "mask_image_url",
    "qwen-inpaint": "mask_url",
    "flux-pro-fill": "mask_url",
    "flux-dev-fill": "mask_url",
}

VERTEX_SKINS = ["fallout-pipboy", "fallout-vault", "n64-cutscene", "wc-goldshield"]
VERTEX_REUSE_SKIN = "diablo-gothic"
VERTEX_PRICE = 0.241  # corrected: edit_vertex() hardcodes imageSize:"4K" -> 4K output tier


def load_fal_key():
    envp = "/Users/conner/dev/central/.env"
    for line in open(envp):
        line = line.strip()
        if line.startswith("FAL_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("FAL_KEY not found in central/.env")


def run_fal_arms(cost_log):
    os.environ["FAL_KEY"] = load_fal_key()
    import fal_client

    for skin, meta in CROPS_META.items():
        crop_path = meta["crop_path"]
        mask_path = meta["mask_path"]
        print(f"[upload] {skin}")
        img_url = fal_client.upload_file(crop_path)
        mask_url = fal_client.upload_file(mask_path)
        prompt = PROMPT_TMPL.format(material=meta["material"])
        mp = (1024 * 1024) / 1_000_000.0

        for model_key, cfg in FAL_MODELS.items():
            out_path = os.path.join(RESULTS_DIR, f"{skin}__{model_key}.png")
            if os.path.exists(out_path):
                print(f"[skip-cached] {skin} x {model_key}")
                continue
            inp = cfg["build_input"](img_url, mask_url, prompt)
            # rename mask key per schema
            if FAL_MASK_PARAM[model_key] != "mask_url" and "mask_url" in inp:
                inp[FAL_MASK_PARAM[model_key]] = inp.pop("mask_url")
            t0 = time.time()
            try:
                result = fal_client.subscribe(cfg["endpoint"], arguments=inp, with_logs=False)
            except Exception as e:
                print(f"[FAIL] {skin} x {model_key}: {e}")
                cost_log.append({"skin": skin, "model": model_key, "error": str(e)})
                continue
            dt = time.time() - t0
            images = result.get("images") or [result.get("image")]
            img_info = images[0]
            url = img_info["url"] if isinstance(img_info, dict) else img_info
            import urllib.request
            data = urllib.request.urlopen(url, timeout=60).read()
            open(out_path, "wb").write(data)
            cost = round(cfg["price_per_mp"] * mp, 5) if "price_per_mp" in cfg else None
            print(f"[ok] {skin} x {model_key} -> {out_path} ({dt:.1f}s, ~${cost})")
            cost_log.append({"skin": skin, "model": model_key, "cost": cost,
                              "seconds": round(dt, 1), "endpoint": cfg["endpoint"]})


def run_lama(cost_log):
    py = os.path.join(GEN12, ".venv-biref", "bin", "python3")
    script = os.path.join(HERE, "_lama_worker.py")
    for skin, meta in CROPS_META.items():
        out_path = os.path.join(RESULTS_DIR, f"{skin}__lama.png")
        if os.path.exists(out_path):
            print(f"[skip-cached] {skin} x lama")
            continue
        t0 = time.time()
        r = subprocess.run([py, script, meta["crop_path"], meta["mask_path"], out_path],
                            capture_output=True, text=True)
        dt = time.time() - t0
        if r.returncode != 0:
            print(f"[FAIL] {skin} x lama: {r.stderr[-800:]}")
            cost_log.append({"skin": skin, "model": "lama", "error": r.stderr[-500:]})
            continue
        print(f"[ok] {skin} x lama -> {out_path} ({dt:.1f}s, $0)")
        cost_log.append({"skin": skin, "model": "lama", "cost": 0.0, "seconds": round(dt, 1)})


def run_vertex(cost_log):
    from genskin import edit_vertex
    for skin in VERTEX_SKINS:
        meta = CROPS_META[skin]
        out_path = os.path.join(RESULTS_DIR, f"{skin}__vertex.png")
        if os.path.exists(out_path):
            print(f"[skip-cached] {skin} x vertex")
            continue
        prompt = PROMPT_TMPL.format(material=meta["material"])
        seed = meta["seed"] or 1234
        t0 = time.time()
        try:
            png_bytes = edit_vertex(meta["crop_path"], prompt, seed, aspect="1:1")
        except Exception as e:
            print(f"[FAIL] {skin} x vertex: {e}")
            cost_log.append({"skin": skin, "model": "vertex", "error": str(e)})
            continue
        dt = time.time() - t0
        out = Image.open(io.BytesIO(png_bytes)).convert("RGB").resize((1024, 1024), Image.LANCZOS)
        out.save(out_path)
        print(f"[ok] {skin} x vertex -> {out_path} ({dt:.1f}s, ~${VERTEX_PRICE})")
        cost_log.append({"skin": skin, "model": "vertex", "cost": VERTEX_PRICE,
                          "seconds": round(dt, 1)})

    # diablo-gothic: reuse production's most recent Vertex attempt, no fresh spend
    reuse_out = os.path.join(RESULTS_DIR, f"{VERTEX_REUSE_SKIN}__vertex.png")
    if not os.path.exists(reuse_out):
        prod_after = os.path.join(GEN12, f"assets-{VERTEX_REUSE_SKIN}", "erase-verify",
                                   "seek-20260711T233631-after.png")
        meta = CROPS_META[VERTEX_REUSE_SKIN]
        cx0, cy0, cx1, cy1 = meta["crop_box"]
        # the erase-verify after.png is a 4x-upscaled CROP of a DIFFERENT (smaller, erase12's
        # own _square_crop_box) box, not our 1024 crop, so recompose isn't pixel-exact — clip
        # to our crop's footprint against the full post-erase paint instead, which IS aligned.
        full_after = None
        for tag in ["seek-20260711T233631", "seek-20260711T233201", "seek-20260711T232914"]:
            cand = os.path.join(GEN12, f"assets-{VERTEX_REUSE_SKIN}", "erase-verify",
                                 f"{tag}-after.png")
            if os.path.exists(cand):
                full_after = cand
                break
        # Simplest honest option: crop the SAME 1024 window from the current (already-erased,
        # still-failing per log) assets-diablo-gothic/paint.png, which reflects the real
        # production Vertex output composited back at full res.
        prod_paint = os.path.join(GEN12, f"assets-{VERTEX_REUSE_SKIN}", "paint.png")
        img = Image.open(prod_paint).convert("RGB")
        crop = img.crop((cx0, cy0, cx1, cy1))
        crop.save(reuse_out)
        print(f"[ok] {VERTEX_REUSE_SKIN} x vertex -> REUSED from production paint.png "
              f"(3 prior Vertex spends already logged, no fresh spend)")
        cost_log.append({"skin": VERTEX_REUSE_SKIN, "model": "vertex", "cost": 0.0,
                          "note": "reused from production erase12-log.json (3 prior real "
                                   "Vertex attempts already spent there, status "
                                   "erased-still-failing)"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-fal", action="store_true")
    ap.add_argument("--skip-vertex", action="store_true")
    ap.add_argument("--skip-lama", action="store_true")
    args = ap.parse_args()

    cost_log_path = os.path.join(HERE, "cost_log.json")
    cost_log = json.load(open(cost_log_path)) if os.path.exists(cost_log_path) else []

    if not args.skip_lama:
        run_lama(cost_log)
        json.dump(cost_log, open(cost_log_path, "w"), indent=2)
    if not args.skip_fal:
        run_fal_arms(cost_log)
        json.dump(cost_log, open(cost_log_path, "w"), indent=2)
    if not args.skip_vertex:
        run_vertex(cost_log)
        json.dump(cost_log, open(cost_log_path, "w"), indent=2)

    total = sum(c.get("cost", 0) or 0 for c in cost_log)
    print(f"\nTotal generation spend so far: ${total:.3f}")


if __name__ == "__main__":
    main()
