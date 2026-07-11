#!/usr/bin/env python3
"""semissive/common.py — shared helpers for the 2-stage semantic-emissive prototype.

Experiment scope: docs/design/2026-07-11-semantic-emissive-research.md. NOT wired into the
mainline pipeline — reads assets-<id>/ (paint.png, regions.json, theme_specs/<id>.json) and
writes ONLY under semissive/out/<id>/. Never touches pbr_pass.py, build_player_pbr.py, or
EMISSIVE_ENABLED.
"""
import base64
import hashlib
import json
import os
import re
import subprocess
import time

import numpy as np
import requests
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
OUT_ROOT = os.path.join(HERE, "out")


def load_fal():
    for line in open(os.path.expanduser("~/dev/central/.env")):
        m = re.match(r"\s*FAL_KEY\s*=\s*(.+)", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    raise SystemExit("no FAL_KEY in central/.env")


def skin_paths(sid):
    d = os.path.join(GEN12, f"assets-{sid}")
    return {
        "assets_dir": d,
        "paint": os.path.join(d, "paint.png"),
        "regions": os.path.join(d, "regions.json"),
        "spec": os.path.join(GEN12, "theme_specs", f"{sid}.json"),
        "pbr_dir": os.path.join(GEN12, f"assets-{sid}_pbr"),
        "out_dir": os.path.join(OUT_ROOT, sid),
    }


def load_skin(sid):
    p = skin_paths(sid)
    regs = json.load(open(p["regions"]))
    spec = json.load(open(p["spec"])) if os.path.exists(p["spec"]) else {}
    os.makedirs(p["out_dir"], exist_ok=True)
    return p, regs, spec


def crop_src(paint_path, dev_frac, out_path):
    """Crop paint.png to the top devFrac rows (the device photo, no region-mask strip) —
    same convention as pbr_pass.py's src_im. Returns (PIL.Image, W, H, PW, PH, YS)."""
    im = Image.open(paint_path).convert("RGB")
    PW, PH = im.size
    SRC_H = round(PH * dev_frac)
    YS = PH / SRC_H
    src = im.crop((0, 0, PW, SRC_H))
    src.save(out_path)
    return src, src.width, src.height, PW, PH, YS


def rect_to_src_frac(dev_rect, YS):
    """regions.json 'device' rects are fractions of the FULL paint.png (paint-frac). Convert
    to fractions of the SRC crop (what the judge/SAM actually see) — same formula pbr_pass.py
    uses for its meta.json rects (rect_src())."""
    x, y, w, h = dev_rect
    return [round(x, 4), round(y * YS, 4), round(w, 4), round(h * YS, 4)]


def upload_fal(path, fal_key):
    name = os.path.basename(path)
    ctype = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    init = requests.post(
        "https://rest.alpha.fal.ai/storage/upload/initiate",
        headers={"Authorization": f"Key {fal_key}", "Content-Type": "application/json"},
        json={"file_name": name, "content_type": ctype}).json()
    requests.put(init["upload_url"], headers={"Content-Type": ctype},
                 data=open(path, "rb").read())
    return init["file_url"]


def sha1_file(path):
    return hashlib.sha1(open(path, "rb").read()).hexdigest()[:12]


def hex_to_rgb01(h):
    h = (h or "#ffffff").lstrip("#")
    if len(h) != 6:
        return (1.0, 1.0, 1.0)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb01_to_hue(rgb):
    r, g, b = rgb
    mx, mn = max(r, g, b), min(r, g, b)
    d = max(mx - mn, 1e-6)
    if mx == r:
        h = (60 * ((g - b) / d)) % 360
    elif mx == g:
        h = 60 * ((b - r) / d) + 120
    else:
        h = 60 * ((r - g) / d) + 240
    return h


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, np.float32) - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def hue_window(hue_arr, hc, half):
    dd = np.abs(((hue_arr - hc + 180) % 360) - 180)
    return smoothstep(half, half * 0.55, dd)


def vertex_url(model="gemini-3.1-pro-preview", project=None):
    project = project or os.environ.get("VERTEX_PROJECT", "muser-2605300220")
    return (f"https://aiplatform.googleapis.com/v1/projects/{project}/locations/global/"
            f"publishers/google/models/{model}:generateContent")


def gcloud_token():
    return subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()


def image_part_b64(path):
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    return {"inline_data": {"mime_type": mime, "data": b64}}


def record_cost(out_dir, stage, usd, note=""):
    """Append one line to out/<sid>/spend.jsonl — the per-call cost ledger."""
    p = os.path.join(out_dir, "spend.jsonl")
    with open(p, "a") as f:
        f.write(json.dumps({"stage": stage, "usd": round(usd, 5), "note": note,
                             "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}) + "\n")


def total_spend(out_dir):
    p = os.path.join(out_dir, "spend.jsonl")
    if not os.path.exists(p):
        return 0.0
    return round(sum(json.loads(l)["usd"] for l in open(p) if l.strip()), 5)
