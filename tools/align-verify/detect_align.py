#!/usr/bin/env python3
"""Gemini overlay-to-paint ALIGNMENT: move each control's box onto the actual painted control.

The painter drifts controls off the blueprint sockets, so the overlay boxes (button
hit-regions, knob caps, seek/slider, visualizer/screen) don't land on the paint. This
detects the REAL painted box per control with Gemini 2.5 Pro and snaps the template rect
to it — but SAFELY, unlike SAM: the current labelled box is drawn ON the image so Gemini
CORRECTS a known box (no control-swaps), 2-run consensus is averaged, and a correction is
accepted only within sanity bounds (size 0.4–2.5× prior, center moves < 0.32) so it can
never resize a control to garbage. Writes <id>-template.json (--apply) + a .prior backup.

Usage: python3 detect_align.py <id> [--apply]
"""
import json, os, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEN = os.path.join(ROOT, "public", "generated")
OUT = "/tmp/detect-align"; os.makedirs(OUT, exist_ok=True)
MODEL = "google/gemini-2.5-pro"
VISION = "https://queue.fal.run/openrouter/router/vision"
ALIGN = {"button", "toggle", "knob", "slider-h", "slider-v", "slider-arc", "slider-path", "display"}


def _key(name):
    for p in (os.path.join(ROOT, ".dev.vars"), "/Users/conner/dev/central/.env"):
        if os.path.exists(p):
            for line in open(p):
                if line.startswith(name + "="): return line.split("=", 1)[1].strip()
    return os.environ.get(name)


FAL = _key("FAL_KEY")


def _req(url, data=None, headers=None, method=None):
    r = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(r, timeout=180) as resp:
        return json.loads(resp.read().decode() or "{}")


def upload(path):
    init = _req("https://rest.alpha.fal.ai/storage/upload/initiate",
                json.dumps({"file_name": os.path.basename(path), "content_type": "image/png"}).encode(),
                {"Authorization": f"Key {FAL}", "Content-Type": "application/json"})
    urllib.request.urlopen(urllib.request.Request(init["upload_url"], data=open(path, "rb").read(),
                           headers={"Content-Type": "image/png"}, method="PUT"), timeout=180)
    return init["file_url"]


ROLE = {"play": "PLAY button", "pause": "PAUSE button", "stop": "STOP button",
        "prev": "PREVIOUS/REWIND button", "next": "NEXT/FF button", "seek": "horizontal SEEK bar/groove",
        "volume": "VOLUME knob", "balance": "BALANCE knob", "bass": "BASS knob", "treble": "TREBLE knob",
        "shuffle": "SHUFFLE toggle", "visualizer": "VISUALIZER screen", "albumart": "ALBUM-ART screen",
        "cd": "CD/disc", "marquee": "track-title screen", "time": "time readout"}
KINDD = {"button": "push button", "knob": "round rotary knob", "toggle": "toggle switch",
         "slider-h": "horizontal slider groove", "slider-v": "vertical fader", "slider-arc": "arc slider",
         "display": "screen/display panel"}


def label_of(r): return r.get("bind") or r.get("id") or r["kind"]
def desc(r):
    b = r.get("bind")
    return ROLE.get(b) or KINDD.get(r["kind"], "control")


def draw(skin, ctrl):
    from PIL import Image, ImageDraw, ImageFont
    fr = Image.open(os.path.join(GEN, f"{skin}-frame.png")).convert("RGBA")
    bg = Image.new("RGBA", fr.size, (24, 24, 27, 255)); bg.alpha_composite(fr); im = bg.convert("RGB")
    W, H = im.size; d = ImageDraw.Draw(im)
    try: font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", max(15, W // 50))
    except: font = ImageFont.load_default()
    for r in ctrl:
        rc = r["rect"]; x0, y0 = rc["x"] * W, rc["y"] * H; x1, y1 = (rc["x"] + rc["w"]) * W, (rc["y"] + rc["h"]) * H
        d.rectangle([x0, y0, x1, y1], outline=(0, 229, 255), width=max(2, W // 380))
        nm = r["_lab"]
        tb = d.textbbox((0, 0), nm, font=font); ly = max(0, y0 - (tb[3] - tb[1]) - 5)
        d.rectangle([x0, ly, x0 + (tb[2] - tb[0]) + 6, ly + (tb[3] - tb[1]) + 6], fill=(0, 0, 0))
        d.text((x0 + 3, ly + 1), nm, fill=(0, 229, 255), font=font)
    p = os.path.join(OUT, f"{skin}-priors.png"); im.save(p); return p


def detect(url, ctrl):
    lines = "\n".join(f"- {r['_lab']}: the {desc(r)}" for r in ctrl)
    prompt = (
        "This is a music-player's painted hardware. CYAN labelled boxes mark where the app CURRENTLY thinks each "
        "control is — but the boxes are MISALIGNED with the actual painted controls. For EACH label, return the "
        "CORRECTED tight bounding box around the ACTUAL painted control of that type (the real knob, button, "
        "screen, or slider groove on the hardware). Keep the SAME label→control identity; just fix the box to hug "
        "the real painted control.\n\n"
        f"Controls:\n{lines}\n\n"
        "Return ONLY strict JSON mapping each label to [x_min,y_min,x_max,y_max] normalised 0..1 (whole image). "
        'If a control truly is not painted anywhere, use null. Example: {"volume":[0.30,0.60,0.42,0.71]}'
    )
    payload = {"model": MODEL, "reasoning": True, "max_tokens": 4000, "temperature": 0,
               "image_urls": [url], "prompt": prompt}
    sub = _req(VISION, json.dumps(payload).encode(), {"Authorization": f"Key {FAL}", "Content-Type": "application/json"})
    t0 = time.time()
    while True:
        st = _req(sub["status_url"], headers={"Authorization": f"Key {FAL}"})
        if st.get("status") == "COMPLETED": break
        if st.get("status") in ("FAILED", "ERROR") or time.time() - t0 > 160: return {}
        time.sleep(2)
    out = _req(sub["response_url"], headers={"Authorization": f"Key {FAL}"}).get("output", "")
    s, e = out.find("{"), out.rfind("}")
    try: return json.loads(out[s:e + 1]) if s >= 0 else {}
    except Exception: return {}


def sane(rc, box, kind):
    if not isinstance(box, list) or len(box) != 4: return None
    x0, y0, x1, y1 = box
    if not all(isinstance(v, (int, float)) for v in box): return None
    if not (0 <= x0 < x1 <= 1.02 and 0 <= y0 < y1 <= 1.02): return None
    w, h = x1 - x0, y1 - y0
    if w < 0.015 or h < 0.015: return None
    loS, hiS = (0.35, 3.2) if kind == "display" else (0.4, 2.5)   # screens vary more
    if not (loS < w / rc["w"] < hiS and loS < h / rc["h"] < hiS): return None
    pcx, pcy, ncx, ncy = rc["x"] + rc["w"] / 2, rc["y"] + rc["h"] / 2, (x0 + x1) / 2, (y0 + y1) / 2
    if ((ncx - pcx) ** 2 + (ncy - pcy) ** 2) ** 0.5 > 0.32: return None   # didn't wander across device
    return {"x": round(x0, 4), "y": round(y0, 4), "w": round(w, 4), "h": round(h, 4)}


def run(skin, apply=False):
    tpl = json.load(open(os.path.join(GEN, f"{skin}-template.json")))
    ctrl = [r for r in tpl["regions"] if r["kind"] in ALIGN]
    for r in ctrl: r["_lab"] = label_of(r)
    # de-dup labels (eqBand×N)
    seen = {}
    for r in ctrl:
        if ctrl.count(r) or r["_lab"] in seen: r["_lab"] = f"{r['_lab']}_{seen.get(r['_lab'],0)}" if r["_lab"] in seen else r["_lab"]
        seen[label_of(r)] = seen.get(label_of(r), 0) + 1
    url = upload(draw(skin, ctrl))
    runs = [detect(url, ctrl), detect(url, ctrl)]   # 2-run consensus
    moved = []
    for r in tpl["regions"]:
        if r["kind"] not in ALIGN: continue
        lab = r.get("_lab") or label_of(r)
        boxes = [d.get(lab) for d in runs if isinstance(d.get(lab), list)]
        cand = None
        if len(boxes) == 2:
            cand = [sum(b[i] for b in boxes) / 2 for i in range(4)]   # average
        elif len(boxes) == 1:
            cand = boxes[0]
        nb = sane(r["rect"], cand, r["kind"]) if cand else None
        if nb:
            moved.append((lab, r["kind"])); r["rect"] = nb
        r.pop("_lab", None)
    for r in tpl["regions"]: r.pop("_lab", None)
    if apply:
        bp = os.path.join(GEN, f"{skin}-template.prior.json")
        if not os.path.exists(bp):
            import shutil; shutil.copy(os.path.join(GEN, f"{skin}-template.json"), bp)
        json.dump(tpl, open(os.path.join(GEN, f"{skin}-template.json"), "w"))
    print(f"[{skin[-4:]}] aligned {len(moved)}/{len(ctrl)} controls: {[m[0] for m in moved]}")
    return tpl


if __name__ == "__main__":
    if not FAL: raise SystemExit("FAL_KEY not found")
    apply = "--apply" in sys.argv
    for sid in [a for a in sys.argv[1:] if not a.startswith("--")]:
        run(sid, apply)
