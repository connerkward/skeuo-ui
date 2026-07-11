#!/usr/bin/env python3
"""sota_eye_jsonspec — SOTA-eye pass (per [[sota-eye-review-rule]]) for the jsonspec
experiment. This agent is Sonnet (sub-SOTA); the final visual verdict on baked
text/rearrangement/quality for each of the 8 generations is routed through a SOTA vision
model (Gemini via fal openrouter/router/vision, reasoning:true — same proven endpoint+model
as twoimg/sota_eye.py) rather than trusted from this agent's own look. Any FAIL/MISPLACED
claim it makes is adjudicated against the deterministic pixel metrics in scores.json before
being treated as ground truth, per verify-outputs-rule.

Sends: paint.png downscaled (full device+strip context) + full-res crops of every control.
Prompt asks for baked-text detection, layout-adherence (did the model follow the guide
positions), and overall quality, plus one VERDICT line.

Usage: python3 sota_eye_jsonspec.py   (no args — walks the same 8 gens as score_jsonspec.py)
Writes <assets-dir>/vlm.json.
"""
import os, re, sys, json, time, base64, io
import requests
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
THEMES = ["wc-goldshield", "fa-pod"]
SEEDS = [121, 134]
ARMS = ["control", "treat"]
MODEL_ID = "google/gemini-2.5-pro"
EYE = f"fal openrouter/router/vision ({MODEL_ID})"
ALL_CTRLS = ["playpause", "prev", "next", "repeat", "queue", "vol", "seek", "shuffle",
             "visualizer", "album_art"]


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


def b64_jpeg_fullres(path, quality=90):
    im = Image.open(path).convert("RGB")
    buf = io.BytesIO(); im.save(buf, format="JPEG", quality=quality)
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


def main():
    KEY = load_fal_key()
    n_calls = 0
    for theme in THEMES:
        for seed in SEEDS:
            for arm in ARMS:
                tag = f"{theme}-{arm}-{seed}"
                d = os.path.join(HERE, f"assets-jsonspec-{tag}")
                if not os.path.exists(os.path.join(d, "paint.png")):
                    print(f"[{tag}] no paint.png -- skipping"); continue
                vlm_path = os.path.join(d, "vlm.json")
                if os.path.exists(vlm_path) and "--force" not in sys.argv:
                    print(f"[{tag}] vlm.json already exists -- skipping (pass --force to redo)")
                    continue
                res = json.load(open(os.path.join(d, "results.json")))
                keyNames = res.get("keyNames", {})
                roster = "; ".join(f"{k} ({res.get('roles', {}).get(k,'?')}) guide-colour={v}"
                                    for k, v in keyNames.items()) if keyNames else "10 controls"
                images = [b64_resized(os.path.join(d, "paint.png"))]
                crop_names = []
                for cn in ALL_CTRLS:
                    cp = os.path.join(d, f"crop-{cn}.png")
                    if os.path.exists(cp):
                        images.append(b64_jpeg_fullres(cp)); crop_names.append(cn)
                arm_desc = ("CONTROL arm: laid out via a prose text prompt describing each "
                            "control's position/size/guide-colour." if arm == "control" else
                            "TREATMENT arm: laid out via a fenced ```json``` machine-readable "
                            "spec block (same information, structured encoding) instead of prose.")
                prompt = (
                    f"This is a generated skeuomorphic media-player skin ('{theme}', experiment "
                    f"arm='{arm}'). {arm_desc} It was painted from a blueprint where each "
                    f"control's on-canvas POSITION was marked during generation by a distinct "
                    f"guide colour (a design-tool artifact, like masking tape) that must be "
                    f"COMPLETELY ABSENT from the finished paint: {roster}.\n"
                    "First image is the full device+strip paint (downscaled). Remaining images "
                    f"are full-resolution close-up crops of each control: {', '.join(crop_names)}.\n"
                    "Report, for the device overall: (1) BAKED TEXT — any letters, numbers, "
                    "words, or ON/OFF-style labels baked into the device or strip (should be "
                    "ZERO); (2) LAYOUT ADHERENCE — does every control sit in a sensible, "
                    "non-overlapping position consistent with a real media player (transport "
                    "buttons in a row, volume knob, seek slider, shuffle switch, album-art + "
                    "visualizer windows), with no control missing, duplicated, or grossly "
                    "misplaced/rearranged; (3) GUIDE-COLOUR RESIDUE — any ring/rim/flood of a "
                    "guide colour visible around any control; (4) OVERALL QUALITY — is this a "
                    "convincing, richly detailed, theme-appropriate skeuomorphic skin, on a "
                    "scale you state as POOR/OK/GOOD/EXCELLENT.\n"
                    "End with exactly one line: \"VERDICT: PASS\" or \"VERDICT: FAIL\" (FAIL if "
                    "baked text is present, OR any control is missing/grossly misplaced, OR "
                    "guide-colour residue floods a control)."
                )
                out = call_vlm(KEY, prompt, images)
                verdict = "PASS" if re.search(r"VERDICT:\s*PASS", str(out)) else \
                          "FAIL" if re.search(r"VERDICT:\s*FAIL", str(out)) else "UNPARSED"
                rec = {"tag": tag, "theme": theme, "arm": arm, "seed": seed, "eye": EYE,
                       "verdict": verdict, "raw": out,
                       "images_sent": ["paint.png(resized)"] + [f"crop-{c}.png" for c in crop_names],
                       "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
                json.dump(rec, open(vlm_path, "w"), indent=2)
                n_calls += 1
                print(f"[{tag}] VLM verdict={verdict} ({EYE}) [{n_calls} calls so far]")


if __name__ == "__main__":
    main()
