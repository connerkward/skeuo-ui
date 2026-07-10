#!/usr/bin/env python3
"""B-proof round 2: a 3-TIER prompt-load ramp (light / medium / heavy) to test whether
paint quality degrades LINEARLY with constraint load or falls off a CLIFF at some
threshold — round 1 only had two points (light ~600 chars vs the real gen12 pipeline's
~9-11k chars), which can't distinguish a straight line from a cliff.

Design choice (stated up front, not hidden): ALL THREE tiers here render through the
SAME single flat-canvas, single-panel format that round 1's "froggo-style" condition
used — unlike round 1's "gen12" condition, which was the real two-column blueprint+mask
pipeline artifact. Holding the input/output FORMAT constant across all 3 tiers means
prompt length/constraint-count is the ONLY variable this round, which is what the
linear-vs-cliff question actually needs. The tradeoff: this round's "heavy" tier is NOT
the literal ~9-11k-char shipping prompt (that prompt requires the two-column blueprint+
mask task, which is a different structural ask, not just "more constraints on the same
content" — reusing it here would reintroduce round 1's format confound). Instead, heavy
here is built by literally layering on real clauses lifted from genskin.py's shipping
prompt (empty-cavity rule, blank-screens rule, seek-is-a-slot-only rule, embossed-button-
relief rule + real per-icon roster via genskin.ICON, the full no-text rule, and a closing
reinforcement paragraph) — same *content*, different total length by construction.

Themes: 2 reused from round 1 (steam-porthole, diablo-gothic) at FRESH seeds (not round
1's 84/110), plus 1 theme not yet in bproof (wmp-quicksilver) at its own fresh seed.
3 themes x 3 tiers x 1 seed = 9 generations. Same model/serving path as round 1's
"froggo-style" condition (Vertex AI `gemini-3-pro-image-preview`, global) — fal's
account is still locked ("User is locked: Exhausted balance", reconfirmed live before
this run), Vertex is not, so this is not blocked. ~$0.24/image x 9 = ~$2.16.
"""
import base64, io, json, os, subprocess, sys, time
import requests
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
sys.path.insert(0, GEN12)
import genskin  # ICON / BUTTONS only — no fal calls

PROJ = "muser-2605300220"
VMODEL = "gemini-3-pro-image-preview"
URL = (f"https://aiplatform.googleapis.com/v1/projects/{PROJ}/locations/global/"
       f"publishers/google/models/{VMODEL}:generateContent")

# theme -> fresh round-2 seed (all different from round 1's 84 / 110)
THEMES2 = {"steam-porthole": 284, "diablo-gothic": 310, "wmp-quicksilver": 405}

LIGHT_TMPL = (
    "A skeuomorphic media-player device, top-down orthographic, centered on a flat "
    "uniform pale grey-white backdrop: {theme} It has physical controls: five icon "
    "buttons (play/pause, prev, next, repeat, queue), a round volume knob, a "
    "horizontal seek slot, a small toggle switch, an album-art window and a "
    "visualizer window. No text anywhere."
)

EMPTY_CAVITIES = (
    " THE SINGLE MOST IMPORTANT RULE — EVERY MOVING-PART CAVITY IS EMPTY. The volume knob "
    "socket is a bare round HOLE showing only its dark recessed floor (NO knob, NO cap, NO "
    "dome, NO dial, NO pointer — nothing installed). The seek slider groove is an EMPTY DARK "
    "RECESSED CHANNEL cut into the body (NO thumb, NO grip, NO handle, NO fill — it is NOT a "
    "coloured or filled bar, it is a hollow dark slot). The shuffle switch slot is an EMPTY "
    "DARK rounded well (NO switch, NO lever, NO toggle installed). The device is photographed "
    "BEFORE ASSEMBLY. Do NOT colour the empty wells — neutral DARK recesses only. If ANY of "
    "the three cavities (knob socket, seek slot, shuffle slot) contains ANY part or any fill "
    "colour, the output is WRONG and must be redone."
)
BLANK_SCREENS = (
    " The ALBUM-ART window and the VISUALIZER window are BLANK, DARK, EMPTY recessed glass "
    "SCREENS — flat unlit dark glass panels only, with NOTHING inside them: NO baked "
    "spectrum/equalizer bars, NO album cover or artwork, NO waveform, NO icons, NO text, NO "
    "content whatsoever. They are OFF screens; the app draws their live content later. If "
    "either window contains any baked graphics, it is WRONG."
)
SEEK_SLOT_ONLY = (
    " SEEK IS JUST AN EMPTY SLOT — treat the seek as a plain EMPTY recessed horizontal "
    "SLOT/CHANNEL only, NOT a functioning slider. Absolutely do NOT bake a slider thumb, grip, "
    "knob, handle, bar, fill, track-fill or progress indicator into it — it is a bare dark "
    "empty channel. A seek slot with anything riding in it is WRONG."
)
NO_TEXT_FULL = (
    " ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, NO CAPTIONS and NO LABELS anywhere "
    "on the device — not under controls, not on the body, not a title, nothing; the device is "
    "wordless, identified by icons and shapes only."
)
REINFORCE = (
    " These rules are not optional stylistic suggestions — they are hard pass/fail "
    "requirements: an installed knob, a filled seek bar, a populated screen, or any text "
    "anywhere makes the ENTIRE image WRONG and unusable, regardless of how good the rest of "
    "the device looks. Re-check every cavity and every screen before finishing: knob socket "
    "EMPTY, seek channel EMPTY, shuffle well EMPTY, album-art screen BLANK, visualizer screen "
    "BLANK, zero text anywhere. If you are uncertain whether a cavity looks too empty or too "
    "plain, err on the side of MORE empty, MORE bare, MORE unfinished-looking — a too-full "
    "cavity is a hard failure, a too-empty one is always acceptable and correct."
)


def button_relief():
    roster = "; ".join(f"{c} = {genskin.ICON[c]}" for c in genskin.BUTTONS)
    return (
        " The 5 transport/function BUTTONS are raised, glossy, tactile control facets set into "
        "the body, EACH clearly bearing its icon EMBOSSED/engraved in relief, one icon per "
        "button, each appearing EXACTLY once: " + roster + ". Shape + icon + relief only; no "
        "text labels; no coloured rim or halo around any button."
    )


def build_tiers(theme_text):
    light = LIGHT_TMPL.format(theme=theme_text)
    medium = light + EMPTY_CAVITIES + BLANK_SCREENS + SEEK_SLOT_ONLY
    heavy = medium + button_relief() + NO_TEXT_FULL + REINFORCE
    return {"light": light, "medium": medium, "heavy": heavy}


def main():
    tok = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    canvas = os.path.join(HERE, "input-flat.png")
    if not os.path.exists(canvas):
        Image.new("RGB", (1200, 1500), (235, 235, 238)).save(canvas)
    b64 = base64.b64encode(open(canvas, "rb").read()).decode()

    for sid, seed in THEMES2.items():
        spec = json.load(open(os.path.join(GEN12, "theme_specs", f"{sid}.json")))
        theme_text = spec["theme_prompt"].strip()
        tiers = build_tiers(theme_text)
        for tier, prompt in tiers.items():
            out = os.path.join(HERE, f"r2-{sid}-{tier}.png")
            if os.path.exists(out):
                print(f"[{sid}/{tier}] already have {out}, skipping", flush=True)
                continue
            print(f"[{sid}/{tier}] seed={seed} {len(prompt)} chars", flush=True)
            body = {
                "contents": [{"role": "user", "parts": [
                    {"inline_data": {"mime_type": "image/png", "data": b64}},
                    {"text": prompt},
                ]}],
                "generationConfig": {
                    "responseModalities": ["IMAGE"],
                    "seed": seed,
                    "candidateCount": 1,
                    "imageConfig": {"aspectRatio": "4:5", "imageSize": "4K"},
                },
            }
            t0 = time.time()
            r = requests.post(URL, headers={"Authorization": f"Bearer {tok}",
                                            "Content-Type": "application/json"},
                              json=body, timeout=420)
            if r.status_code != 200:
                print(f"[{sid}/{tier}] HTTP {r.status_code}: {r.text[:400]}", flush=True)
                continue
            resp = r.json()
            img_b64 = None
            for part in resp["candidates"][0]["content"]["parts"]:
                d = part.get("inlineData") or part.get("inline_data") or {}
                if d.get("data"):
                    img_b64 = d["data"]; break
            if not img_b64:
                print(f"[{sid}/{tier}] no image part: {json.dumps(resp)[:400]}", flush=True)
                continue
            png = base64.b64decode(img_b64)
            open(out, "wb").write(png)
            w, h = Image.open(io.BytesIO(png)).size
            meta = {"id": sid, "tier": tier, "model": f"{VMODEL} (Vertex AI, global)",
                    "seed": seed, "resolution": "4K", "aspect_ratio": "4:5", "dims": [w, h],
                    "prompt": prompt, "prompt_chars": len(prompt),
                    "elapsed_s": round(time.time() - t0, 1),
                    "input": "flat 1200x1500 RGB(235,235,238) canvas"}
            json.dump(meta, open(os.path.join(HERE, f"r2-{sid}-{tier}-meta.json"), "w"), indent=1)
            print(f"[{sid}/{tier}] done {w}x{h} in {meta['elapsed_s']}s -> {out}", flush=True)


if __name__ == "__main__":
    main()
