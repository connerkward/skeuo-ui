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
ARMS = ["control", "treat", "neutral"]
MODEL_ID = "google/gemini-2.5-pro"
EYE = f"fal openrouter/router/vision ({MODEL_ID})"
# every control gets a full-res crop sent (not just the historically bleed-prone 5) — the
# neutral arm's hypothesis under test is DIGIT contamination, which could show up anywhere,
# not only vol/seek/shuffle.
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


def b64_raw(path):
    return "data:image/png;base64," + base64.b64encode(open(path, "rb").read()).decode()


def b64_jpeg_fullres(path, quality=90):
    """Full-resolution JPEG re-encode — used when a gen's raw-PNG crop payload exceeds fal's
    30MB download cap (hit live 2026-07-11 on wc-goldshield-control-121: the call returned
    '{"detail": "Downloaded image content cannot exceed 30MB"}' instead of a verdict, which
    parsed as UNPARSED). Same pixels/resolution, ~10x smaller; q90 keeps ring/digit detail."""
    im = Image.open(path).convert("RGB")
    buf = io.BytesIO(); im.save(buf, format="JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


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
                vlm_path = os.path.join(d, "vlm.json")
                if os.path.exists(vlm_path) and "--force" not in sys.argv:
                    print(f"[{tag}] vlm.json already exists -- skipping (pass --force to redo)")
                    continue
                res = json.load(open(os.path.join(d, "results.json")))
                keyNames = res.get("keyNames", {})
                roster = "; ".join(f"{k} ({res.get('roles', {}).get(k,'?')}) guide-colour={v}"
                                    for k, v in keyNames.items())
                images = [b64_resized(os.path.join(d, "paint.png"))]
                crop_names = []
                for cn in ALL_CTRLS:
                    cp = os.path.join(d, f"crop-{cn}.png")
                    if os.path.exists(cp):
                        images.append(b64_raw(cp)); crop_names.append(cn)
                # fal caps 'downloaded image content' at 30MB and (verified live 2026-07-11:
                # a 24.4MB-decoded / 32.5MB-base64 batch was rejected) the cap counts the
                # ENCODED data-URI length, not decoded bytes — keep encoded total under 24MB
                if sum(len(u) for u in images) > 24 * 1024 * 1024:
                    images = [images[0]] + [b64_jpeg_fullres(os.path.join(d, f"crop-{cn}.png"))
                                             for cn in crop_names]
                    print(f"[{tag}] payload >28MB — crops re-encoded as full-res JPEG q90")
                is_neutral = arm == "neutral"
                digit_clause = (
                    "This gen's reference used a COLOURLESS numbered line-art layout guide (small "
                    "printed numerals 1-10, one beside each control, on thin grey outline shapes) "
                    "instead of coloured guide shapes — the prompt explicitly forbade painting those "
                    "numbers/outlines into the output. " if is_neutral else
                    "This gen's reference used coloured guide shapes only (no numbers were ever shown "
                    "to the model), so any digit-like mark below would be a spontaneous artifact, not "
                    "a copied reference number. "
                )
                prompt = (
                    f"This is a generated skeuomorphic media-player skin ('{theme}', "
                    f"experiment arm='{arm}'). It was painted from a blueprint where each "
                    f"control's on-canvas POSITION was marked during generation by a distinct "
                    f"guide colour (a design-tool artifact, like masking tape) that must be "
                    f"COMPLETELY ABSENT from the finished paint: {roster}.\n"
                    "First image is the full device+strip paint (downscaled). Remaining images "
                    f"are full-resolution close-up crops of EVERY control: {', '.join(crop_names)}.\n"
                    "For EACH control listed in the roster, report ONE of: "
                    "NONE (no trace of its guide colour), RING (a thin coloured ring/bezel/edge-"
                    "tint of the guide colour visible around it), FLOODED (the guide colour "
                    "fills a large area of it), or N/A (can't tell from provided images). Also "
                    "separately report, for vol/seek/shuffle specifically, whether their cavity/"
                    "socket/slot is EMPTY (bare recess, no part installed) or FILLED (a part or "
                    "colour fill sits in it — wrong, should be empty pre-assembly).\n"
                    + digit_clause +
                    "SEPARATELY, for EACH of the same 10 controls, hunt specifically for a baked "
                    "NUMERAL, DIGIT, tick-mark, callout dot, or number-like tag anywhere in or "
                    "beside its crop (engraved, painted, embossed, or worked in as a decorative "
                    "motif) and report ONE of: DIGITS-NONE (no numeral/digit/tag-like mark) or "
                    "DIGITS-FOUND (describe exactly what you see and where, including if it's "
                    "faint/stylized/ambiguous).\n"
                    "End with exactly two lines, each on its own: "
                    "\"VERDICT: PASS\" or \"VERDICT: FAIL\" (FAIL if ANY control shows RING or "
                    "FLOODED guide-colour residue, or if any of vol/seek/shuffle is FILLED when it "
                    "should be EMPTY); and "
                    "\"DIGIT-VERDICT: CLEAN\" or \"DIGIT-VERDICT: CONTAMINATED\" (CONTAMINATED if "
                    "ANY control crop shows DIGITS-FOUND — a baked numeral, digit, tick-mark, "
                    "callout dot, or number-like tag anywhere)."
                )
                out = call_vlm(KEY, prompt, images)
                verdict = "PASS" if re.search(r"VERDICT:\s*PASS", str(out)) else \
                          "FAIL" if re.search(r"VERDICT:\s*FAIL", str(out)) else "UNPARSED"
                digit_verdict = "CLEAN" if re.search(r"DIGIT-VERDICT:\s*CLEAN", str(out)) else \
                                "CONTAMINATED" if re.search(r"DIGIT-VERDICT:\s*CONTAMINATED", str(out)) else "UNPARSED"
                rec = {"tag": tag, "theme": theme, "arm": arm, "seed": seed, "eye": EYE,
                       "verdict": verdict, "digit_verdict": digit_verdict, "raw": out,
                       "images_sent": ["paint.png(resized)"] + [f"crop-{c}.png" for c in crop_names],
                       "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
                json.dump(rec, open(os.path.join(d, "vlm.json"), "w"), indent=2)
                n_calls += 1
                print(f"[{tag}] VLM verdict={verdict} digit-verdict={digit_verdict} ({EYE}) [{n_calls} calls so far]")


if __name__ == "__main__":
    main()
