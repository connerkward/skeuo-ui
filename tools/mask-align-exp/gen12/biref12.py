#!/usr/bin/env python3
"""biref12 — ONE global BiRefNet pass over a gen12 paint, then SPLIT the matte into
connected-component islands: device body + each moving part (knob cap / seek thumb / toggle
OFF+ON), correlated to identity via the regions.json strip cells (centroid match). Role-driven,
argv assets dir. Usage: python3 biref12.py <assets-dir>"""
import os, re, io, time, json, sys
import requests
import numpy as np
from PIL import Image
from scipy import ndimage

# BIREF_LOCAL: run BiRefNet locally (torch/transformers, MPS) instead of the fal endpoint —
# $0/matte, no rate limits, no billing-lock dependency (see .claude/rules/generation-spend-rule.md).
# Flip only BETWEEN batches, never mid-batch (a concurrent agent may be running this file
# right now). ON since 2026-07-10 (user call; verified IoU 0.9973 vs fal, 13-19s/matte MPS).
BIREF_LOCAL = True

HERE = os.path.dirname(os.path.abspath(__file__))
_VENV_PY = os.path.join(HERE, ".venv-biref", "bin", "python3")  # torch+transformers venv (not the global python3)
if BIREF_LOCAL:
    try:
        import torch  # noqa: F401  (present only in .venv-biref)
    except ImportError:
        if os.path.exists(_VENV_PY) and os.environ.get("_BIREF_REEXEC") != "1":
            os.environ["_BIREF_REEXEC"] = "1"
            os.execv(_VENV_PY, [_VENV_PY] + sys.argv)  # re-exec under the venv that has torch
        sys.exit("BIREF_LOCAL=True needs torch+transformers — run "
                  "`python3.13 -m venv .venv-biref && .venv-biref/bin/pip install torch torchvision "
                  "transformers huggingface-hub accelerate scipy pillow requests numpy` in gen12/, "
                  "or install torch in the interpreter running this file.")

_LOCAL_MODEL = None  # cached (model, device) — loaded once per invocation, reused across islands

# BiRefNet_HR: the 2048-trained full (220.7M) checkpoint — matches the 2048x2048 operating
# resolution the fal call below requests, and scored best-equal on the fallout-vault bench
# (IoU vs fal matte: HR@2048 0.9978, general@2048 0.9979, general@1024 0.9973, lite@1024
# 0.9976 — all candidates within noise; HR is the one TRAINED for 2048 inference).
_LOCAL_CKPT, _LOCAL_RES = "ZhengPeng7/BiRefNet_HR", 2048


def _local_matte(png_bytes):
    """BiRefNet via transformers (checkpoint/res: _LOCAL_CKPT/_LOCAL_RES), on MPS when available.
    Same contract as the fal path: PNG bytes in, RGBA PNG bytes out (mask resized back to the
    input's native size)."""
    global _LOCAL_MODEL
    import torch
    from torchvision import transforms
    from transformers import AutoModelForImageSegmentation
    if _LOCAL_MODEL is None:
        dev = "mps" if torch.backends.mps.is_available() else "cpu"
        model = AutoModelForImageSegmentation.from_pretrained(_LOCAL_CKPT, trust_remote_code=True)
        model.to(dev, dtype=torch.float32).eval()  # checkpoint loads as fp16 by default; fp32 avoids a dtype mismatch vs the fp32 input tensor
        _LOCAL_MODEL = (model, dev)
    model, dev = _LOCAL_MODEL
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB"); W0, H0 = im.size
    tfm = transforms.Compose([transforms.Resize((_LOCAL_RES, _LOCAL_RES)), transforms.ToTensor(),
                               transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
    x = tfm(im).unsqueeze(0).to(dev)
    with torch.no_grad():
        pred = model(x)[-1].sigmoid().cpu().squeeze()
    mask = transforms.ToPILImage()(pred).resize((W0, H0), Image.BICUBIC)
    rgba = im.convert("RGBA"); rgba.putalpha(mask)
    buf = io.BytesIO(); rgba.save(buf, "PNG")
    return buf.getvalue()


def fal_key():
    for line in open(os.path.expanduser("~/dev/central/.env")):
        m = re.match(r"\s*FAL_KEY\s*=\s*(.+)", line)
        if m: return m.group(1).strip().strip('"').strip("'")
    sys.exit("no FAL_KEY")


FAL = None if BIREF_LOCAL else fal_key()  # local path needs no fal credential at all
SRC = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
OUT = SRC + "_biref"; os.makedirs(OUT, exist_ok=True)


def upload(b):
    init = requests.post("https://rest.alpha.fal.ai/storage/upload/initiate",
        headers={"Authorization": f"Key {FAL}", "Content-Type": "application/json"},
        json={"file_name": "p.png", "content_type": "image/png"}).json()
    requests.put(init["upload_url"], headers={"Content-Type": "image/png"}, data=b)
    return init["file_url"]


paint = Image.open(os.path.join(SRC, "paint.png")).convert("RGB"); PW, PH = paint.size
_mp = os.path.join(OUT, "global-matte.png")
_paint_p = os.path.join(SRC, "paint.png")
_fresh = os.path.exists(_mp) and os.path.getmtime(_mp) >= os.path.getmtime(_paint_p)
# STALE-MATTE GUARD: after a REGEN the paint is new but the old matte lingers — reusing it cuts
# parts from the PREVIOUS generation (phantom switches "not on the sprite sheet"). Reuse only a
# matte at least as new as the paint.
if _fresh and "--force" not in sys.argv:
    raw = open(_mp, "rb").read(); print("[global] reused existing matte", flush=True)   # re-cut for free
elif BIREF_LOCAL:
    buf = io.BytesIO(); paint.save(buf, "PNG")
    t0 = time.time()
    raw = _local_matte(buf.getvalue())
    open(_mp, "wb").write(raw)
    print(f"[global-local] {time.time() - t0:.1f}s ({_LOCAL_CKPT} @{_LOCAL_RES}, {_LOCAL_MODEL[1]})", flush=True)
else:
    buf = io.BytesIO(); paint.save(buf, "PNG")
    job = requests.post("https://queue.fal.run/fal-ai/birefnet/v2",
        headers={"Authorization": f"Key {FAL}", "Content-Type": "application/json"},
        json={"image_url": upload(buf.getvalue()), "model": "General Use (Heavy)",
              "operating_resolution": "2048x2048", "output_format": "png"}).json()
    t0 = time.time()
    while True:
        s = requests.get(job["status_url"], headers={"Authorization": f"Key {FAL}"}).json().get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR") or time.time() - t0 > 180: sys.exit(f"birefnet {s}")
        time.sleep(2)
    out = requests.get(job["response_url"], headers={"Authorization": f"Key {FAL}"}).json()
    raw = requests.get(out["image"]["url"]).content
    open(_mp, "wb").write(raw)
    print(f"[global] {time.time() - t0:.1f}s", flush=True)

g = Image.open(io.BytesIO(raw)).convert("RGBA").resize((PW, PH))
A = np.asarray(g)[:, :, 3] > 90
lbl, n = ndimage.label(A)
sizes = ndimage.sum(np.ones_like(lbl), lbl, range(1, n + 1))
order = np.argsort(sizes)[::-1]


def save_island(idx, name):
    ys, xs = np.where(lbl == idx)
    crop = g.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    crop.save(os.path.join(OUT, f"{name}.png"))
    return (xs.min() + xs.max()) / 2 / PW, (ys.min() + ys.max()) / 2 / PH, len(xs)


dev = save_island(1 + int(order[0]), "device"); print("device island px:", dev[2])

RES = json.load(open(os.path.join(SRC, "regions.json")))
R = RES["regions"]; ROLES = RES.get("roles", {}); SPR = RES.get("sprites", [])
KNOBS = [k for k in SPR if ROLES.get(k) == "knob"] or [k for k in SPR if k == "vol"]
SLIDER = next((k for k in SPR if ROLES.get(k) == "slider"), "seek" if "seek" in SPR else None)
TOGGLE = next((k for k in SPR if ROLES.get(k) == "toggle"), "tog" if "tog" in SPR else None)

# IDENTITY + LOCATION come from the colour-coded MASK strip cell (each part has its OWN guide
# colour, so its cell bbox is unambiguous); BiRefNet only supplies the clean CUT. Assign each part
# to the island that most OVERLAPS its mask-cell bbox — NOT nearest-centroid (which cross-assigns,
# e.g. a switch island landing closest to the seek cell → mislabelled seek). Overlap is definitive.
parts = {}   # name -> mask strip-cell bbox (x, y, w, h) normalised
for k in KNOBS + ([SLIDER] if SLIDER else []):
    s = (R.get(k) or {}).get("strip") or []
    if s and s[0]: parts[k] = s[0]
if TOGGLE:
    # TOGGLE_TRACK_ENABLED (2026-07-12): a single lever cell (regions.json's toggle strip has
    # ONE entry, not two) -> cut it as "<toggle>_lever". Legacy two-state regions still carry
    # TWO strip cells -> unchanged off/on split. Keyed off cell COUNT (the regions.json shape
    # itself), not RES["toggle_track_enabled"], so this reads any regions.json correctly
    # regardless of which genskin.py flag state produced it.
    ts = (R.get(TOGGLE) or {}).get("strip") or []
    if len(ts) >= 2:
        for i, cell in enumerate(ts[:2]):
            if cell: parts[TOGGLE + ("_off", "_on")[i]] = cell
    elif len(ts) == 1 and ts[0]:
        parts[TOGGLE + "_lever"] = ts[0]

# island bounding boxes (normalised), skipping the device + tiny specks
iboxes = {}
for oi in order[1:]:
    idx = 1 + int(oi)
    if sizes[int(oi)] < 1500: continue
    ys, xs = np.where(lbl == idx)
    iboxes[idx] = (xs.min() / PW, ys.min() / PH, xs.max() / PW, ys.max() / PH)


def _inter(a, b):   # intersection area of two (x0,y0,x1,y1) boxes
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy


used = set()
unmatched = []
for name, cell in parts.items():
    cellbox = (cell[0], cell[1], cell[0] + cell[2], cell[1] + cell[3])
    cell_area = max(1e-9, cell[2] * cell[3])
    best_idx, best_ov = None, 0.0
    for idx, ib in iboxes.items():
        if idx in used: continue
        ov = _inter(cellbox, ib)
        if ov > best_ov: best_ov, best_idx = ov, idx
    if best_idx is not None and best_ov > 0.15 * cell_area:      # island must genuinely cover the cell
        save_island(best_idx, name); used.add(best_idx)
        print(f"{name:10} <- island (overlap {best_ov / cell_area * 100:.0f}% of its mask cell)")
    else:
        unmatched.append((name, cell))
        print(f"{name:10} UNMATCHED (no island overlaps its mask cell)")

# ---- CELL-CROP LOCAL-MATTE RECOVERY for unmatched parts (ported from knobup/recover_caps.py's
# proven fallback, generalized to ANY strip part, 2026-07-12). The GLOBAL BiRefNet matte
# routinely drops a small isolated strip part entirely (fa-pod-toggletrack1: the shuffle lever
# region measured ZERO alpha — the salient-object model didn't consider the small satellite
# pill an object at full-frame scale). A local matte on just the padded mask-cell crop reframes
# the part as THE salient object and recovers it at $0 (same local checkpoint, MPS). Fires only
# for a non-degenerate mask cell (a sliver cell means the MASK itself is broken — nothing
# trustworthy to crop) and only in BIREF_LOCAL mode (the fal path would cost a paid call per
# recovery; those gens still surface via the biref-parts gate).
def _recover_from_cell(name, cell):
    if not BIREF_LOCAL: return False
    if cell[2] < 0.01 or cell[3] < 0.01: return False           # degenerate mask cell — skip
    padx, pady = cell[2] * 0.35, cell[3] * 0.35
    x0 = max(0, int((cell[0] - padx) * PW)); x1 = min(PW, int((cell[0] + cell[2] + padx) * PW))
    y0 = max(0, int((cell[1] - pady) * PH)); y1 = min(PH, int((cell[1] + cell[3] + pady) * PH))
    if x1 - x0 < 8 or y1 - y0 < 8: return False
    crop = paint.crop((x0, y0, x1, y1))
    buf = io.BytesIO(); crop.save(buf, "PNG")
    rgba = Image.open(io.BytesIO(_local_matte(buf.getvalue()))).convert("RGBA")
    a = np.asarray(rgba)[:, :, 3] > 90
    l2, n2 = ndimage.label(a)
    if n2 == 0: return False
    s2 = ndimage.sum(np.ones_like(l2), l2, range(1, n2 + 1))
    big = 1 + int(np.argmax(s2))
    if s2[big - 1] < 1000: return False                          # speck — not a real part
    ys2, xs2 = np.where(l2 == big)
    cut = rgba.crop((int(xs2.min()), int(ys2.min()), int(xs2.max()) + 1, int(ys2.max()) + 1))
    cut.save(os.path.join(OUT, f"{name}.png"))
    print(f"{name:10} <- RECOVERED via cell-crop local matte ({int(s2[big-1])}px island)")
    return True

for name, cell in unmatched:
    if not _recover_from_cell(name, cell):
        print(f"{name:10} recovery skipped/failed (degenerate cell or no island)")
extra = 0
for idx in iboxes:
    if idx not in used:
        extra += 1; save_island(idx, f"extra-{extra}")
print("parts matched:", sorted(used and [n for n in parts] or []) or "none")
