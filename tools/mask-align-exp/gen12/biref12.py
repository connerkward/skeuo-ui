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


def fal_key():
    for line in open(os.path.expanduser("~/dev/central/.env")):
        m = re.match(r"\s*FAL_KEY\s*=\s*(.+)", line)
        if m: return m.group(1).strip().strip('"').strip("'")
    sys.exit("no FAL_KEY")


FAL = fal_key()
SRC = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
OUT = SRC + "_biref"; os.makedirs(OUT, exist_ok=True)


def upload(b):
    init = requests.post("https://rest.alpha.fal.ai/storage/upload/initiate",
        headers={"Authorization": f"Key {FAL}", "Content-Type": "application/json"},
        json={"file_name": "p.png", "content_type": "image/png"}).json()
    requests.put(init["upload_url"], headers={"Content-Type": "image/png"}, data=b)
    return init["file_url"]


paint = Image.open(os.path.join(SRC, "paint.png")).convert("RGB"); PW, PH = paint.size
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
open(os.path.join(OUT, "global-matte.png"), "wb").write(raw)
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

targets = {}
for k in KNOBS + ([SLIDER] if SLIDER else []):
    s = (R.get(k) or {}).get("strip") or []
    if s and s[0]:
        b = s[0]; targets[k] = (b[0] + b[2] / 2, b[1] + b[3] / 2)
if TOGGLE:
    ts = (R.get(TOGGLE) or {}).get("strip") or []
    for i, cell in enumerate(ts[:2]):
        if cell: targets[TOGGLE + ("_off", "_on")[i]] = (cell[0] + cell[2] / 2, cell[1] + cell[3] / 2)

extra = 0
for oi in order[1:]:
    idx = 1 + int(oi)
    if sizes[int(oi)] < 1500: continue
    ys, xs = np.where(lbl == idx)
    cx = (xs.min() + xs.max()) / 2 / PW; cy = (ys.min() + ys.max()) / 2 / PH
    best = None; bd = 1e9
    for k, (tx, ty) in targets.items():
        dd = ((cx - tx) ** 2 + (cy - ty) ** 2) ** .5
        if dd < bd: bd = dd; best = k
    if best and bd < 0.05:
        save_island(idx, best); print(f"{best:10} island  (match {bd * 100:.1f}%)")
        del targets[best]
    else:
        extra += 1; save_island(idx, f"extra-{extra}"); print(f"extra-{extra} island (nearest {best} at {bd * 100:.1f}%)")
print("unmatched targets:", list(targets) or "none")
