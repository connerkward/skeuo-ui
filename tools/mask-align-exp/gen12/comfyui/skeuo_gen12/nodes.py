"""skeuo_gen12 node classes.

The gen12 pipeline is a set of standalone, argv-driven scripts that pass data between
stages via a shared assets directory on disk (assets-<id>/ and assets-<id>_biref/). These
nodes preserve that contract exactly: they run the REAL scripts as subprocesses and move a
small "job" dict (spec path + assets dir) along the graph edges, converting the PNG artifacts
each stage writes into ComfyUI IMAGE tensors for preview/save.

Why subprocess instead of import: extract12.py / biref12.py execute all their logic at module
top-level (driven by sys.argv + files), so importing them would run them. Subprocessing the
unmodified scripts is the faithful "wrap, don't reimplement" path and runs the exact shipping
code (verify-rule real-runtime). A deps-complete interpreter is auto-selected (needs scipy /
requests / PIL / numpy) so the gen12 scripts run regardless of ComfyUI's bundled python env.
"""
import os
import sys
import json
import shutil
import tempfile
import subprocess

import numpy as np
from PIL import Image

try:
    import torch
    _HAVE_TORCH = True
except Exception:  # allows structural import checks outside ComfyUI
    _HAVE_TORCH = False

CATEGORY = "skeuo/gen12"
DEFAULT_GEN12_DIR = "/Users/conner/dev/skeuo-ui/tools/mask-align-exp/gen12"


# ----------------------------------------------------------------- interpreter selection
def _pick_python():
    """First interpreter that can import the gen12 deps (scipy/requests/PIL/numpy)."""
    cands = [sys.executable, shutil.which("python3"),
             "/opt/homebrew/bin/python3", "/usr/bin/python3"]
    seen = set()
    for c in cands:
        if not c or c in seen:
            continue
        seen.add(c)
        try:
            r = subprocess.run([c, "-c", "import scipy,requests,PIL,numpy"],
                               capture_output=True, timeout=40)
            if r.returncode == 0:
                return c
        except Exception:
            continue
    return sys.executable


PYBIN = _pick_python()


# ----------------------------------------------------------------- image <-> tensor helpers
def _to_image(path, alpha_as_gray=False):
    """Load a PNG into a ComfyUI IMAGE tensor [1,H,W,3], 0..1 RGB."""
    if alpha_as_gray:
        a = np.asarray(Image.open(path).convert("RGBA"))[:, :, 3]
        arr = np.stack([a, a, a], axis=-1).astype(np.float32) / 255.0
    else:
        arr = np.asarray(Image.open(path).convert("RGB")).astype(np.float32) / 255.0
    if _HAVE_TORCH:
        return torch.from_numpy(arr)[None, ...]
    return arr[None, ...]


def _save_image(tensor, path):
    t = tensor[0]
    arr = t.cpu().numpy() if hasattr(t, "cpu") else np.asarray(t)
    arr = (arr * 255.0).clip(0, 255).astype(np.uint8)
    Image.fromarray(arr).save(path)


def _run(script, args, gen12_dir, timeout=1200):
    cmd = [PYBIN, os.path.join(gen12_dir, script)] + [str(a) for a in args]
    r = subprocess.run(cmd, cwd=gen12_dir, capture_output=True, text=True,
                       timeout=timeout, env=os.environ.copy())
    log = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        raise RuntimeError(f"[skeuo] {script} exit {r.returncode}\n{log[-3000:]}")
    return log


def _effective_spec(spec_path, spec_json, seed, gen12_dir):
    """Return a concrete spec-file path + its assets dir, honoring an inline JSON override
    and a seed override (written to a temp spec so the gen12 scripts stay untouched)."""
    if spec_json and spec_json.strip():
        spec = json.loads(spec_json)
        src = "<inline>"
    else:
        src = spec_path
        spec = json.load(open(spec_path))
    if seed is not None and seed >= 0:
        spec["seed"] = int(seed)
    sid = spec["id"]
    assets = os.path.join(gen12_dir, f"assets-{sid}")
    if spec_json and spec_json.strip() or (seed is not None and seed >= 0):
        # persist the effective spec next to gen12 so genskin can read it
        tmp = os.path.join(tempfile.gettempdir(), f"skeuo_spec_{sid}.json")
        json.dump(spec, open(tmp, "w"), indent=2)
        eff = tmp
    else:
        eff = src
    return eff, assets, sid


# ================================================================= NODES
class SkeuoBlueprint:
    """Theme spec -> technical-drawing blueprint (grey placeholder body + coloured control
    outline guides + sprite-strip band) + guide-key json + the EXACT structural prompt.
    Runs the unmodified genskin.py via prompt_capture.py (fal helpers stubbed), so the
    blueprint AND the verbatim prompt genskin would send are produced with zero API calls.
    The prompt output feeds ComfyUI's native Gemini/Nano-Banana API node directly."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "spec_path": ("STRING", {"default": os.path.join(DEFAULT_GEN12_DIR, "theme_specs", "fa-pod.json")}),
            },
            "optional": {
                "spec_json": ("STRING", {"default": "", "multiline": True}),
                "seed_override": ("INT", {"default": -1, "min": -1, "max": 2**31 - 1}),
                "gen12_dir": ("STRING", {"default": DEFAULT_GEN12_DIR}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "SKEUO_JOB", "STRING")
    RETURN_NAMES = ("blueprint", "keys_json", "job", "prompt")
    FUNCTION = "run"
    CATEGORY = CATEGORY

    def run(self, spec_path, spec_json="", seed_override=-1, gen12_dir=DEFAULT_GEN12_DIR):
        eff, assets, sid = _effective_spec(spec_path, spec_json, seed_override, gen12_dir)
        # run the REAL genskin.py with fal helpers stubbed: writes blueprint.png +
        # results.json and captures the verbatim structural prompt (no network).
        ptmp = os.path.join(tempfile.gettempdir(), f"skeuo_prompt_{sid}.txt")
        driver = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt_capture.py")
        r = subprocess.run([PYBIN, driver, eff, gen12_dir, ptmp], cwd=gen12_dir,
                           capture_output=True, text=True, timeout=300, env=os.environ.copy())
        if r.returncode != 0:
            raise RuntimeError(f"[skeuo] prompt_capture exit {r.returncode}\n"
                               f"{((r.stdout or '') + (r.stderr or ''))[-3000:]}")
        prompt = open(ptmp).read()
        bp = _to_image(os.path.join(assets, "blueprint.png"))
        res = json.load(open(os.path.join(assets, "results.json")))
        keys_json = json.dumps({"keys": res.get("keys"), "keyNames": res.get("keyNames"),
                                "mode": res.get("mode"), "id": sid}, indent=2)
        job = {"spec_path": eff, "assets_dir": assets, "gen12_dir": gen12_dir, "sid": sid}
        return (bp, keys_json, job, prompt)


class SkeuoNanoBananaEdit:
    """Blueprint + structural prompt -> joint (2-panel: painted skin | region mask), via the
    real fal-ai/gemini-3-pro-image-preview/edit (nano-banana pro). Wraps the full `genskin.py`,
    which builds the exact prompt, uploads the blueprint, runs the edit, and splits the result.
    FAL_KEY is read by genskin.py from ~/dev/central/.env — never handled here."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"job": ("SKEUO_JOB",)}}

    RETURN_TYPES = ("IMAGE", "IMAGE", "IMAGE", "SKEUO_JOB")
    RETURN_NAMES = ("joint", "paint", "mask", "job")
    FUNCTION = "run"
    CATEGORY = CATEGORY

    def run(self, job):
        gen12_dir = job["gen12_dir"]
        assets = job["assets_dir"]
        _run("genskin.py", [job["spec_path"]], gen12_dir)
        joint = _to_image(os.path.join(assets, "joint-4k.png"))
        paint = _to_image(os.path.join(assets, "paint.png"))
        mask = _to_image(os.path.join(assets, "mask.png"))
        return (joint, paint, mask, job)


class SkeuoSplitJoint:
    """2-panel joint image -> paint (left) + mask (right), split at width//2 (matches genskin).
    Rewrites paint.png / mask.png in the job dir from the incoming tensor so the graph's split
    is authoritative for the downstream BiRefNet / Extract stages."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"joint": ("IMAGE",), "job": ("SKEUO_JOB",)}}

    RETURN_TYPES = ("IMAGE", "IMAGE", "SKEUO_JOB")
    RETURN_NAMES = ("paint", "mask", "job")
    FUNCTION = "run"
    CATEGORY = CATEGORY

    def run(self, joint, job):
        w = joint.shape[2]
        half = w // 2
        paint = joint[:, :, :half, :]
        mask = joint[:, :, half:, :]
        assets = job["assets_dir"]
        os.makedirs(assets, exist_ok=True)
        _save_image(paint, os.path.join(assets, "paint.png"))
        _save_image(mask, os.path.join(assets, "mask.png"))
        return (paint, mask, job)


class SkeuoBiRefNet:
    """Island split (+ matting). Wraps the real `biref12.py` (connected-component island
    split correlated to the mask strip cells by overlap). biref12 needs regions.json, so an
    extract pass-1 is run first as its dependency (the graph's Extract node is pass-2).

    TWO matte sources:
    * `matte` input CONNECTED (a LOCAL BiRefNet mask, e.g. ComfyUI_BiRefNet_ll ->
      MaskToImage): the matte is composed with paint.png into an RGBA cutout and written to
      assets_biref/global-matte.png BEFORE biref12 runs — biref12 detects the existing matte
      and reuses it ("[global] reused existing matte"), so NO fal call is made. This is the
      local path; only the skeuo-specific island split runs.
    * `matte` input EMPTY: legacy behaviour — biref12 calls fal-ai/birefnet/v2 for the
      matte (needs FAL_KEY in ~/dev/central/.env, read by biref12 itself, never here)."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"job": ("SKEUO_JOB",)},
            "optional": {"matte": ("IMAGE",)},
        }

    RETURN_TYPES = ("IMAGE", "SKEUO_JOB")
    RETURN_NAMES = ("matte", "job")
    FUNCTION = "run"
    CATEGORY = CATEGORY

    def run(self, job, matte=None):
        gen12_dir = job["gen12_dir"]
        assets = job["assets_dir"]
        if matte is not None:
            # write the externally-computed matte where biref12 reuses it (skips fal)
            out = assets + "_biref"
            os.makedirs(out, exist_ok=True)
            paint = Image.open(os.path.join(assets, "paint.png")).convert("RGB")
            t = matte[0]
            arr = t.cpu().numpy() if hasattr(t, "cpu") else np.asarray(t)
            gray = arr.mean(axis=-1) if arr.ndim == 3 else arr
            a8 = (gray * 255.0).clip(0, 255).astype(np.uint8)
            alpha = Image.fromarray(a8, "L").resize(paint.size)
            rgba = paint.copy()
            rgba.putalpha(alpha)
            rgba.save(os.path.join(out, "global-matte.png"))
        # pass-1 extract produces regions.json that biref12 correlates islands against
        if not os.path.exists(os.path.join(assets, "regions.json")):
            _run("extract12.py", [assets], gen12_dir)
        _run("biref12.py", [assets], gen12_dir)
        matte_img = _to_image(os.path.join(assets + "_biref", "global-matte.png"), alpha_as_gray=True)
        return (matte_img, job)


class SkeuoExtractRegions:
    """paint + mask + matte -> regions.json + overlay. Wraps the real `extract12.py` (pass-2,
    authoritative): mask-colour correlation, matte-hole knob seats, coverage-span seek travel,
    silhouette-IoU toggle state-align, and the PASS/FAIL gate."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"job": ("SKEUO_JOB",)}}

    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "SKEUO_JOB")
    RETURN_NAMES = ("overlay", "regions_json", "gate", "job")
    FUNCTION = "run"
    OUTPUT_NODE = True
    CATEGORY = CATEGORY

    def run(self, job):
        gen12_dir = job["gen12_dir"]
        assets = job["assets_dir"]
        _run("extract12.py", [assets], gen12_dir)
        overlay = _to_image(os.path.join(assets, "overlay.png"))
        regions = json.load(open(os.path.join(assets, "regions.json")))
        gate = json.dumps(regions.get("gate", {}), indent=2)
        print(f"[skeuo][gate] {job['sid']}: {gate}")
        return (overlay, json.dumps(regions), gate, job)


class SkeuoBuildPlayer:
    """regions.json + assets -> standalone interactive player.html (seats the cut parts).
    Wraps the real `build_player.py`. Returns the player.html path."""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"job": ("SKEUO_JOB",)}}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("player_path",)
    FUNCTION = "run"
    OUTPUT_NODE = True
    CATEGORY = CATEGORY

    def run(self, job):
        gen12_dir = job["gen12_dir"]
        assets = job["assets_dir"]
        _run("build_player.py", [assets], gen12_dir)
        path = os.path.join(assets, "player.html")
        print(f"[skeuo][player] {path}")
        return (path,)


NODE_CLASS_MAPPINGS = {
    "SkeuoBlueprint": SkeuoBlueprint,
    "SkeuoNanoBananaEdit": SkeuoNanoBananaEdit,
    "SkeuoSplitJoint": SkeuoSplitJoint,
    "SkeuoBiRefNet": SkeuoBiRefNet,
    "SkeuoExtractRegions": SkeuoExtractRegions,
    "SkeuoBuildPlayer": SkeuoBuildPlayer,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "SkeuoBlueprint": "Skeuo Blueprint (gen12)",
    "SkeuoNanoBananaEdit": "Skeuo Nano-Banana Edit (gen12)",
    "SkeuoSplitJoint": "Skeuo Split Joint (gen12)",
    "SkeuoBiRefNet": "Skeuo Island Split — local matte in / fal fallback (gen12)",
    "SkeuoExtractRegions": "Skeuo Extract Regions (gen12)",
    "SkeuoBuildPlayer": "Skeuo Build Player (gen12)",
}
