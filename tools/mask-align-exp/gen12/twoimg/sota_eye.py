#!/usr/bin/env python3
"""sota_eye — the [[sota-eye-review-rule]] pass for the twoimg experiment. This agent is
Sonnet (sub-SOTA), so the final visual verdict on guide-colour residue/bleed for each of the
8 generations is routed through a SOTA vision model (Gemini via fal openrouter/router/vision,
~$0.01-0.03/call — same proven endpoint+model as gen12/observe12.py) rather than trusted from
this agent's own look.

Sends: paint.png downscaled (full device+strip context) + the vol/seek/shuffle full-res crops
(the historically most bleed-prone sockets per the abshape verdict) + one button crop. Prompt
states each control's guide-key colour NAME (so the model can check for that EXACT hue as
residue) and asks for a structured per-control residue call plus one VERDICT line.

Usage: python3 sota_eye.py   (no args — walks the same 8 gens as score_twoimg.py)
Writes <assets-dir>/vlm.json + folds a summary into scores.json.
"""
import os, re, sys, json, time, base64, io
import requests
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
THEMES = ["fa-pod", "wc-goldshield"]
SEEDS = [121, 134]
ARMS = ["control", "treat"]
MODEL_ID = "google/gemini-2.5-pro"
EYE = f"fal openrouter/router/vision ({MODEL_ID})"


def load_fal_key():
    for line in open(os.path.expanduser("~/dev/central/.env")):
        m = re.match(r"\s*FAL_KEY\s*=\s*(.+)", line)
        if m: return m.group(1).strip().strip('"').strip("'")
    sys.exit("no FAL_KEY")


def b64_resized(path, max_w=1400):
    im = Image.open(path).convert("RGB")
    if im.width > max_w:
        h = int(im.height * max_w / im.width)
        im = im.resize((max_w, h), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def b64_raw(path):
    return "data:image/png;base64," + base64.b64encode(open(path, "rb").read()).decode()


def call_vlm(KEY, prompt, image_data_uris):
    # reasoning:true is MANDATORY for gemini-2.5-pro on this endpoint (verified live
    # 2026-07-10: without it every call returns '{"detail": "Reasoning is mandatory for
    # this endpoint and cannot be disabled."}')
    body = {"prompt": prompt, "model": MODEL_ID, "image_urls": image_data_uris,
            "reasoning": True}
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


def main():
    KEY = load_fal_key()
    n_calls = 0
    for theme in THEMES:
        for seed in SEEDS:
            for arm in ARMS:
                tag = f"{theme}-{arm}-{seed}"
                d = os.path.join(HERE, f"assets-twoimg-{tag}")
                if not os.path.exists(os.path.join(d, "paint.png")):
                    print(f"[{tag}] no paint.png -- skipping"); continue
                res = json.load(open(os.path.join(d, "results.json")))
                keyNames = res.get("keyNames", {})
                roster = "; ".join(f"{k} ({res.get('roles', {}).get(k,'?')}) guide-colour={v}"
                                    for k, v in keyNames.items())
                images = [b64_resized(os.path.join(d, "paint.png"))]
                crop_names = []
                for cn in ["vol", "seek", "shuffle", "playpause", "queue"]:
                    cp = os.path.join(d, f"crop-{cn}.png")
                    if os.path.exists(cp):
                        images.append(b64_raw(cp)); crop_names.append(cn)
                prompt = (
                    f"This is a generated skeuomorphic media-player skin ('{theme}', "
                    f"experiment arm='{arm}'). It was painted from a blueprint where each "
                    f"control's on-canvas POSITION was marked during generation by a distinct "
                    f"guide colour (a design-tool artifact, like masking tape) that must be "
                    f"COMPLETELY ABSENT from the finished paint: {roster}.\n"
                    "First image is the full device+strip paint (downscaled). Remaining images "
                    f"are full-resolution close-up crops of: {', '.join(crop_names)}.\n"
                    "For EACH control listed in the roster, report ONE of: "
                    "NONE (no trace of its guide colour), RING (a thin coloured ring/bezel/edge-"
                    "tint of the guide colour visible around it), FLOODED (the guide colour "
                    "fills a large area of it), or N/A (can't tell from provided images). Also "
                    "separately report, for vol/seek/shuffle specifically, whether their cavity/"
                    "socket/slot is EMPTY (bare recess, no part installed) or FILLED (a part or "
                    "colour fill sits in it — wrong, should be empty pre-assembly).\n"
                    "End with exactly one line: VERDICT: PASS or VERDICT: FAIL — FAIL if ANY "
                    "control shows RING or FLOODED guide-colour residue, or if any of "
                    "vol/seek/shuffle is FILLED when it should be EMPTY."
                )
                out = call_vlm(KEY, prompt, images)
                verdict = "PASS" if re.search(r"VERDICT:\s*PASS", str(out)) else \
                          "FAIL" if re.search(r"VERDICT:\s*FAIL", str(out)) else "UNPARSED"
                rec = {"tag": tag, "theme": theme, "arm": arm, "seed": seed, "eye": EYE,
                       "verdict": verdict, "raw": out, "images_sent": ["paint.png(resized)"] + [f"crop-{c}.png" for c in crop_names],
                       "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
                json.dump(rec, open(os.path.join(d, "vlm.json"), "w"), indent=2)
                n_calls += 1
                print(f"[{tag}] VLM verdict={verdict} ({EYE}) [{n_calls} calls so far]")


if __name__ == "__main__":
    main()
