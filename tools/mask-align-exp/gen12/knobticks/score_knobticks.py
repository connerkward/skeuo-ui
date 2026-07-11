#!/usr/bin/env python3
"""score_knobticks — harsh per-gen scoring for the knob-tick-provisioning experiment.

For each assets-knobticks-<theme>-<arm>-<seed>/ dir:
  1. deterministic knob-socket crop (from the KNOWN template socket centre/radius, not a
     guess) + a radial tick-mark angle detector (best-effort pixel measurement — flagged as
     such, not treated as ground truth per verify-outputs-rule).
  2. a SOTA vision-model cross-check (Gemini via fal openrouter/router/vision, reasoning:true
     — same proven endpoint as twoimg/sota_eye.py and gen12/observe12.py) on the full paint +
     the knob-socket crop + the loose-cap strip crop: ticks present/at-socket/legible/theme-
     coherent, an independent visual start/end-angle estimate, and a damage check (sockets
     still empty elsewhere, no stray text/digits).
  3. parses the model's OWN self-reported JSON (written by gen_knobticks.py into results.json
     as model_json_parsed) and checks it against BOTH the deterministic measurement and the
     VLM's independent estimate (+-15 degrees agreement per the experiment brief).

Writes <dir>/vlm.json, <dir>/crop-knob.png, <dir>/crop-knob-labeled.png (studio-annotated,
review only), <dir>/crop-cap-strip.png, and knobticks/scores.json (the aggregate).

Usage: python3 score_knobticks.py [--force]
"""
import os, re, sys, io, json, time, math, base64
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import genskin as G
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_ID = "google/gemini-2.5-pro"
EYE = f"fal openrouter/router/vision ({MODEL_ID}, reasoning=true)"
FORCE = "--force" in sys.argv


def load_fal_key():
    for line in open(os.path.expanduser("~/dev/central/.env")):
        m = re.match(r"\s*FAL_KEY\s*=\s*(.+)", line)
        if m: return m.group(1).strip().strip('"').strip("'")
    sys.exit("no FAL_KEY")


def b64_raw(path):
    return "data:image/png;base64," + base64.b64encode(open(path, "rb").read()).decode()


def b64_resized(path, max_w=1400):
    im = Image.open(path).convert("RGB")
    if im.width > max_w:
        h = int(im.height * max_w / im.width)
        im = im.resize((max_w, h), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def call_vlm(KEY, prompt, image_data_uris):
    body = {"prompt": prompt, "model": MODEL_ID, "image_urls": image_data_uris, "reasoning": True}
    q = requests.post("https://queue.fal.run/openrouter/router/vision",
                       headers={"Authorization": f"Key {KEY}", "Content-Type": "application/json"},
                       json=body).json()
    t0 = time.time()
    while True:
        s = requests.get(q["status_url"], headers={"Authorization": f"Key {KEY}"}).json().get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR") or time.time() - t0 > 180: raise RuntimeError(f"vlm {s}")
        time.sleep(3)
    r = requests.get(q["response_url"], headers={"Authorization": f"Key {KEY}"}).json()
    return r.get("output") or r.get("text") or json.dumps(r)[:2000]


def knob_crop_box(res, w, h, rfactor=1.9):
    fx, fy = res["knob_center_frac"]; kr = res["knob_r_frac"]
    cx, cy = fx * w, fy * h
    crad = kr * w * rfactor
    return (int(cx - crad), int(cy - crad), int(cx + crad), int(cy + crad)), (cx, cy, kr * w)


def cap_strip_crop_box(w, h):
    """cell 0 of the strip band = the volume knob cap (build_canvas: cx = COL_W*(0.13+0.20*i),
    sy = DEV_H + (H-DEV_H)//2, i=0). paint.png is COL_W-wide (half the joint canvas), full H
    tall, at whatever supersample scale the model actually returned -> derive scale from w/H."""
    scale = w / G.COL_W
    cx = G.COL_W * 0.13 * scale
    sy = (G.DEV_H + (G.H - G.DEV_H) // 2) * scale
    r = G.KNOB_R * scale * 1.9
    return (int(cx - r), int(sy - r), int(cx + r), int(sy + r))


def angle_from_12(dx, dy):
    """degrees CLOCKWISE from 12 o'clock (straight up), matching gen_knobticks.py's convention
    (== the shipped runtime knob technique, knob-rotation.md 2026-07-01): 3oclock=+90,
    6oclock=180, 9oclock=-90/270, 7oclock=-135ish, 5oclock=+135ish."""
    a = math.degrees(math.atan2(dy, dx)) + 90
    if a > 180: a -= 360
    if a <= -180: a += 360
    return a


def detect_ticks(crop_img, cx_local, cy_local, socket_r_local):
    """Best-effort deterministic tick-mark angle detector: sample a grayscale radial profile at
    several candidate ring radii around the socket, pick the radius with the strongest angular
    variance (the tick ring), then find angular gradient peaks on that ring. NOT ground truth —
    tick engravings are low-contrast relief, this is a coarse pixel signal to CROSS-CHECK the
    VLM/self-reported JSON against, per verify-outputs-rule (independent, not circular)."""
    g = np.asarray(crop_img.convert("L")).astype(float)
    H, W = g.shape
    best = None
    for rf in (1.00, 1.08, 1.15, 1.22, 1.30, 1.38, 1.45):
        r = socket_r_local * rf
        if r >= min(cx_local, cy_local, W - cx_local, H - cy_local) - 2:
            continue
        n = 720
        thetas = np.linspace(0, 2 * math.pi, n, endpoint=False)
        xs = (cx_local + r * np.cos(thetas)).astype(int)
        ys = (cy_local + r * np.sin(thetas)).astype(int)
        valid = (xs >= 0) & (xs < W) & (ys >= 0) & (ys < H)
        if valid.sum() < n * 0.9: continue
        prof = g[ys[valid], xs[valid]]
        var = float(np.var(prof))
        if best is None or var > best[0]:
            best = (var, rf, r, thetas[valid], prof)
    if best is None:
        return {"ring_radius_factor": None, "n_peaks": 0, "peak_degs": [], "span_deg": None}
    var, rf, r, thetas, prof = best
    prof_s = np.convolve(prof, np.ones(5) / 5, mode="same")
    grad = np.abs(np.gradient(prof_s))
    thresh = grad.mean() + 1.3 * grad.std()
    peak_idx = np.where(grad > thresh)[0]
    # cluster adjacent indices (wrap-aware-ish, good enough at this density)
    clusters = []
    for i in sorted(peak_idx):
        if clusters and i - clusters[-1][-1] <= 6:
            clusters[-1].append(i)
        else:
            clusters.append([i])
    peak_degs = []
    for c in clusters:
        idx = c[len(c) // 2]
        peak_degs.append(round(angle_from_12(math.cos(thetas[idx]) * r, math.sin(thetas[idx]) * r), 1))
    peak_degs.sort()
    span = None
    if len(peak_degs) >= 2:
        span = [peak_degs[0], peak_degs[-1]]
    return {"ring_radius_factor": rf, "n_peaks": len(peak_degs), "peak_degs": peak_degs, "span_deg": span}


def label_crop(crop_img, lines):
    """Studio-annotation overlay for HUMAN review only (label-overlays-rule) — NEVER what's sent
    to the VLM (that gets the raw crop_img)."""
    im = crop_img.convert("RGB").copy()
    d = ImageDraw.Draw(im)
    pad = 10
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 26)
    except Exception:
        font = ImageFont.load_default()
    y = pad
    for line in lines:
        bbox = d.textbbox((0, 0), line, font=font)
        d.rectangle([pad - 4, y - 2, pad + (bbox[2] - bbox[0]) + 4, y + (bbox[3] - bbox[1]) + 6], fill=(0, 0, 0, 180))
        d.text((pad, y), line, fill=(255, 220, 60), font=font)
        y += (bbox[3] - bbox[1]) + 12
    return im


def score_one(KEY, d):
    tag = os.path.basename(d).replace("assets-knobticks-", "")
    paint_p = os.path.join(d, "paint.png")
    if not os.path.exists(paint_p):
        print(f"[{tag}] no paint.png -- skipping"); return None
    vlm_path = os.path.join(d, "vlm.json")
    res = json.load(open(os.path.join(d, "results.json")))
    im = Image.open(paint_p).convert("RGB"); w, h = im.size

    box, (cx, cy, socket_r) = knob_crop_box(res, w, h)
    knob_crop = im.crop(box)
    knob_crop.save(os.path.join(d, "crop-knob.png"))
    cap_box = cap_strip_crop_box(w, h)
    cap_crop = im.crop(cap_box)
    cap_crop.save(os.path.join(d, "crop-cap-strip.png"))

    cx_local, cy_local = cx - box[0], cy - box[1]
    det = detect_ticks(knob_crop, cx_local, cy_local, socket_r)

    labeled = label_crop(knob_crop, [
        f"{tag}", f"arm={res['arm']}", f"deterministic ring={det['ring_radius_factor']}",
        f"peaks={det['n_peaks']} span={det['span_deg']}", "STUDIO OVERLAY - not sent to model"])
    labeled.save(os.path.join(d, "crop-knob-labeled.png"))

    if os.path.exists(vlm_path) and not FORCE:
        print(f"[{tag}] vlm.json exists -- skipping VLM call (pass --force to redo)")
        rec = json.load(open(vlm_path))
        rec["deterministic"] = det
        json.dump(rec, open(vlm_path, "w"), indent=2)
        return rec

    expected = res.get("expected_convention", {})
    prompt = (
        f"This is a crop of a generated skeuomorphic media-player's VOLUME KNOB SOCKET "
        f"(theme='{res['id']}', experiment arm='{res['arm']}'). The prompt asked the model to "
        "engrave/paint a themed TICK-ARC reference scale directly into the housing around this "
        "empty socket: a MIN/START mark near 7 o'clock, a MAX/END mark near 5 o'clock, "
        + ("plus 3 minor ticks between them sweeping over the top. " if res["arm"] == "ticks01" else
           "a CENTER/DETENT mark distinct from the other two at 12 o'clock (a balance-knob scale), "
           "plus 1-2 minor ticks in each half-arc. ") +
        "Second image is the corresponding loose VOLUME KNOB CAP from the sprite strip (its "
        "pointer notch should point toward the START direction"
        + (" (7 o'clock)" if res["arm"] == "ticks01" else " (12 o'clock / center)") + ").\n"
        "Answer harshly and specifically:\n"
        "1. TICKS-PRESENT: yes/no — is there a visible tick/mark system at all?\n"
        "2. AT-SOCKET: yes/no — are the marks ON the housing immediately around the socket hole "
        "(not floating elsewhere, not on a different control)?\n"
        "3. LEGIBLE: yes/no — can you actually make out individual discrete tick marks (not just "
        "generic decorative engraving/knurling)?\n"
        "4. START-END-DISTINCT: yes/no — are there two marks visually distinguishable from each "
        "other AND from any minor ticks (e.g. bigger, different shape, different material) "
        "consistent with a MIN and a MAX endpoint" + (", plus a third visually-distinct CENTER "
        "mark" if res["arm"] == "ticks_ctr" else "") + " -- or does it just look like a uniform "
        "ring of identical ticks all the way around with no distinguishable start/end (that "
        "counts as NO)?\n"
        "5. ANGLE-ESTIMATE: your OWN best-guess reading of the START mark's clock position and "
        "the END mark's clock position (e.g. 'START looks like 7 o'clock, END looks like 5 "
        "o'clock') — describe what you actually see, don't assume the intended design.\n"
        "6. THEME-COHERENT: yes/no — does the tick system look like a physically real, "
        "theme-appropriate machined/engraved/painted part of the housing, or does it look like a "
        "flat sticker/decal/UI overlay pasted on top?\n"
        "7. POINTER-NOTCH-ALIGNED: yes/no — does the cap's pointer notch (second image) point "
        "toward the expected start direction described above?\n"
        "8. DAMAGE-CHECK: does anything else look wrong nearby — stray text/digits/numerals "
        "baked in, a coloured guide-residue ring, or the socket recess itself not empty (looks "
        "like a knob is actually installed)? Report NONE or describe exactly what's wrong.\n"
        "End with exactly one line: \"VERDICT: RELIABLE\" (ticks present, at socket, legible, "
        "start/end distinct, theme-coherent, no damage) or \"VERDICT: UNRELIABLE\" (any of those "
        "fail)."
    )
    images = [b64_resized(paint_p), b64_raw(os.path.join(d, "crop-knob.png")), b64_raw(os.path.join(d, "crop-cap-strip.png"))]
    out = call_vlm(KEY, prompt, images)
    verdict = "RELIABLE" if re.search(r"VERDICT:\s*RELIABLE", str(out)) else \
              "UNRELIABLE" if re.search(r"VERDICT:\s*UNRELIABLE", str(out)) else "UNPARSED"
    # pull a rough numeric angle guess out of the VLM prose, if any o'clock mentions parse
    # (literal clock-numeral degrees, 30deg/hour, wrapped to [-180,180] — an approximation:
    # the -135/+135 "7/5 o'clock" convention used in the prompt is itself a loose colloquial
    # label, not the exact clock-numeral angle, so this is only a coarse sanity aid)
    clockmap = {h_: ((h_ % 12) * 30) if ((h_ % 12) * 30) <= 180 else ((h_ % 12) * 30) - 360 for h_ in range(1, 13)}
    vlm_hours = [int(x) for x in re.findall(r"(\d{1,2})\s*o\W?clock", str(out))]
    vlm_angles = [clockmap[hh] for hh in vlm_hours if hh in clockmap]

    model_json = res.get("model_json_parsed")
    agree_json_vs_det = None
    if model_json and det.get("span_deg"):
        try:
            s, e = model_json["vol"]["start_deg"], model_json["vol"]["end_deg"]
            ds, de = det["span_deg"]
            agree_json_vs_det = (abs(s - ds) <= 15 or abs(s - de) <= 15) and (abs(e - ds) <= 15 or abs(e - de) <= 15)
        except Exception:
            agree_json_vs_det = None

    rec = {"tag": tag, "theme": res["id"], "arm": res["arm"], "seed": res["seed"], "eye": EYE,
           "verdict": verdict, "raw": out, "deterministic": det,
           "model_json_parsed": model_json, "expected_convention": expected,
           "vlm_clock_mentions": vlm_hours, "vlm_angle_guess_deg": vlm_angles,
           "agree_json_vs_deterministic_15deg": agree_json_vs_det,
           "text_part_returned": res.get("text_part_returned"),
           "images_sent": ["paint.png(resized)", "crop-knob.png", "crop-cap-strip.png"],
           "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    json.dump(rec, open(vlm_path, "w"), indent=2)
    print(f"[{tag}] VLM verdict={verdict} det_peaks={det['n_peaks']} det_span={det['span_deg']} "
          f"json={model_json} json_vs_det_agree={agree_json_vs_det}")
    return rec


def main():
    KEY = load_fal_key()
    dirs = sorted(d for d in os.listdir(HERE) if d.startswith("assets-knobticks-"))
    recs = []
    for dn in dirs:
        d = os.path.join(HERE, dn)
        r = score_one(KEY, d)
        if r: recs.append(r)
    json.dump(recs, open(os.path.join(HERE, "scores.json"), "w"), indent=2)
    n = len(recs)
    rel = sum(1 for r in recs if r["verdict"] == "RELIABLE")
    print(f"\n[summary] {rel}/{n} RELIABLE overall")
    for arm in ("ticks01", "ticks_ctr"):
        sub = [r for r in recs if r["arm"] == arm]
        rel_a = sum(1 for r in sub if r["verdict"] == "RELIABLE")
        print(f"  arm={arm}: {rel_a}/{len(sub)} RELIABLE")
    json_ok = sum(1 for r in recs if r.get("text_part_returned"))
    json_parsed = sum(1 for r in recs if r.get("model_json_parsed"))
    agree = sum(1 for r in recs if r.get("agree_json_vs_deterministic_15deg"))
    print(f"  text-part returned: {json_ok}/{n}; JSON parsed: {json_parsed}/{n}; "
          f"json-vs-deterministic agreement: {agree}/{max(1, json_parsed)}")


if __name__ == "__main__":
    main()
