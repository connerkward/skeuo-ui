#!/usr/bin/env python3
"""run_slotwide — run the WHOLE-SLOT crop+mask through 3 non-hallucinating erasers: LaMa
($0 classical baseline), Bria Eraser ($0.04/call), and Vertex/Gemini-3-Pro-Image (~$0.134/call
at the 2K tier, all 3 crops here have max side <2048px). z-image-turbo and other cheap
hallucinating generative fillers are DELIBERATELY EXCLUDED per the user's correction — this arm
compares Vertex vs Bria as the real question, with LaMa as the free classical floor.

Usage: python3 run_slotwide.py [--skip-lama] [--skip-bria] [--skip-vertex]
"""
import argparse, io, json, os, subprocess, sys, time

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
INPAINTBAKE = os.path.dirname(HERE)
GEN12 = os.path.dirname(INPAINTBAKE)
sys.path.insert(0, GEN12)

META = json.load(open(os.path.join(HERE, "slot_crops_meta.json")))
RESULTS_DIR = os.path.join(HERE, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

PROMPT_TMPL = (
    "This is a crop of a skeuomorphic device control panel showing an ENTIRE slider slot "
    "(the full groove/track). A slider thumb/handle/grip currently sits inside the masked "
    "region and must be REMOVED. Erase it completely and repaint the ENTIRE masked groove as "
    "a clean, uniform, EMPTY track — continuous {material}, same material, same lighting, "
    "same recess depth and shading as the unmasked parts of the same groove visible in this "
    "crop. The groove must read as a single continuous channel with NO bulge, highlight, or "
    "residual shape from the removed part anywhere along its length. Change nothing outside "
    "the masked region."
)

BRIA_PRICE = 0.04
VERTEX_PRICE_2K = 0.134


def load_fal_key():
    envp = "/Users/conner/dev/central/.env"
    for line in open(envp):
        line = line.strip()
        if line.startswith("FAL_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("FAL_KEY not found in central/.env")


def run_lama(cost_log):
    py = os.path.join(GEN12, ".venv-biref", "bin", "python3")
    script = os.path.join(INPAINTBAKE, "_lama_worker.py")
    for skin, meta in META.items():
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


def run_bria(cost_log):
    os.environ["FAL_KEY"] = load_fal_key()
    import fal_client
    for skin, meta in META.items():
        out_path = os.path.join(RESULTS_DIR, f"{skin}__bria.png")
        if os.path.exists(out_path):
            print(f"[skip-cached] {skin} x bria")
            continue
        img_url = fal_client.upload_file(meta["crop_path"])
        mask_url = fal_client.upload_file(meta["mask_path"])
        t0 = time.time()
        try:
            result = fal_client.subscribe(
                "fal-ai/bria/eraser",
                arguments={"image_url": img_url, "mask_url": mask_url, "mask_type": "manual"},
                with_logs=False,
            )
        except Exception as e:
            print(f"[FAIL] {skin} x bria: {e}")
            cost_log.append({"skin": skin, "model": "bria", "error": str(e)})
            continue
        dt = time.time() - t0
        img_info = result.get("image")
        url = img_info["url"] if isinstance(img_info, dict) else img_info
        import urllib.request
        data = urllib.request.urlopen(url, timeout=60).read()
        # save at native crop size (bria may return a different internal size — resize to match)
        out_img = Image.open(io.BytesIO(data)).convert("RGB")
        crop_size = Image.open(meta["crop_path"]).size
        if out_img.size != tuple(crop_size):
            out_img = out_img.resize(crop_size, Image.LANCZOS)
        out_img.save(out_path)
        print(f"[ok] {skin} x bria -> {out_path} ({dt:.1f}s, ~${BRIA_PRICE})")
        cost_log.append({"skin": skin, "model": "bria", "cost": BRIA_PRICE, "seconds": round(dt, 1)})


def run_vertex(cost_log):
    from genskin import edit_vertex
    for skin, meta in META.items():
        out_path = os.path.join(RESULTS_DIR, f"{skin}__vertex.png")
        if os.path.exists(out_path):
            print(f"[skip-cached] {skin} x vertex")
            continue
        prompt = PROMPT_TMPL.format(material=meta["material"])
        seed = meta["seed"] or 1234
        crop_size = Image.open(meta["crop_path"]).size
        max_side = max(crop_size)
        tier = "2K" if max_side <= 2048 else "4K"
        t0 = time.time()
        try:
            png_bytes = edit_vertex(meta["crop_path"], prompt, seed,
                                     aspect=meta["vertex_aspect"], image_size=tier)
        except Exception as e:
            print(f"[FAIL] {skin} x vertex: {e}")
            cost_log.append({"skin": skin, "model": "vertex", "error": str(e)})
            continue
        dt = time.time() - t0
        out = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        if out.size != tuple(crop_size):
            out = out.resize(crop_size, Image.LANCZOS)
        out.save(out_path)
        price = VERTEX_PRICE_2K if tier == "2K" else 0.24
        print(f"[ok] {skin} x vertex -> {out_path} ({dt:.1f}s, aspect={meta['vertex_aspect']}, "
              f"tier={tier}, ~${price})")
        cost_log.append({"skin": skin, "model": "vertex", "cost": price, "seconds": round(dt, 1),
                          "aspect": meta["vertex_aspect"], "tier": tier})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-lama", action="store_true")
    ap.add_argument("--skip-bria", action="store_true")
    ap.add_argument("--skip-vertex", action="store_true")
    args = ap.parse_args()

    cost_log_path = os.path.join(HERE, "cost_log.json")
    cost_log = json.load(open(cost_log_path)) if os.path.exists(cost_log_path) else []

    if not args.skip_lama:
        run_lama(cost_log)
        json.dump(cost_log, open(cost_log_path, "w"), indent=2)
    if not args.skip_bria:
        run_bria(cost_log)
        json.dump(cost_log, open(cost_log_path, "w"), indent=2)
    if not args.skip_vertex:
        run_vertex(cost_log)
        json.dump(cost_log, open(cost_log_path, "w"), indent=2)

    total = sum(c.get("cost", 0) or 0 for c in cost_log)
    print(f"\nTotal slotwide generation spend so far: ${total:.3f}")


if __name__ == "__main__":
    main()
