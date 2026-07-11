#!/usr/bin/env python3
"""knobticks — can the paint model be PROVISIONED via prompt to bake a knob tick-mark / start-end
indicator system onto the skin, AND self-report the knob's rotation range as structured JSON text
in the SAME generation call?

Self-contained experiment, scoped entirely to tools/mask-align-exp/gen12/knobticks/. Does NOT
edit ../genskin.py — imports its proven constants/helpers (pick_keys, build_canvas, LAYOUTS,
CONTROLS, ICON, cname, edit_vertex machinery) so the base templated-mode blueprint/prompt
machinery is identical to production; only a NEW tick-arc clause + a JSON-metadata ask are added.

Two arms (the prompt variable under test):
  ticks01     — 0..1 single sweep: MIN mark (~7 o'clock) + MAX mark (~5 o'clock) + minor ticks.
  ticks_ctr   — -1..0..+1 balance sweep: MIN/MAX marks + a distinct CENTER/DETENT mark at 12
                o'clock (conceptually a balance knob).
Angle convention reused from the shipped runtime knob technique (docs/experiments/
2026-07-01-knob-rotation.md: `value -> angle = -135 + value*270`, i.e. 7 o'clock..5 o'clock is the
established -135..+135 physical sweep) — the same convention is asked of the model's JSON report.

imgjson/ coordination: tools/mask-align-exp/gen12/imgjson/ is an EMPTY reserved directory (no
results exist there to reuse — confirmed via git log + directory listing, 2026-07-11). The
sibling research doc docs/design/2026-07-11-semantic-emissive-research.md §4 asserts (analysis,
not a live test) that "nano-banana-2 / gemini-3-pro-image are image models, not JSON-mode LLMs
with an image side-channel in the same call." This experiment's Vertex call sets
responseModalities=["TEXT","IMAGE"] and empirically tests that claim rather than trusting it
(verify-external-claims-rule) — the result (works / doesn't) is recorded either way and feeds
back into that doc's open question.

Usage:
  python3 gen_knobticks.py <theme_spec.json> --arm ticks01|ticks_ctr --seed N [--blueprint-only]
  -> writes knobticks/assets-knobticks-<theme>-<arm>-<seed>/
"""
import os, io, sys, json, time, base64, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # gen12/
import genskin as G  # reuse proven constants/helpers — NOT edited by this experiment
import requests
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
VPROJ = os.environ.get("VERTEX_PROJECT", "muser-2605300220")
VMODEL = "gemini-3-pro-image-preview"
VURL = (f"https://aiplatform.googleapis.com/v1/projects/{VPROJ}/locations/global/"
        f"publishers/google/models/{VMODEL}:generateContent")
MODEL = f"{VMODEL} (Vertex AI, global, responseModalities=[TEXT,IMAGE])"

ARMS = ("ticks01", "ticks_ctr")

# angle convention — matches the shipped runtime CSS-rotation technique (knob-rotation.md,
# 2026-07-01): value 0..1 -> angle -135..+135, 7 o'clock..5 o'clock through 12 o'clock.
START_DEG, END_DEG, CENTER_DEG = -135, 135, 0


def tick_clause(arm):
    """The ONE prompt variable under test. Kept material-agnostic (theme adaptation comes from
    the existing theme_prompt/palette machinery, unchanged) so the clause is identical prose
    across both themes — only the arm (01 vs center) differs, per the experiment brief."""
    common_head = (
        "  • KNOB TICK-ARC PROVISIONING (CRITICAL, NEW) — around the volume knob's EMPTY socket "
        "(engraved/painted/riveted into the STATIC HOUSING immediately surrounding the empty hole "
        "— NEVER on the removable cap, NEVER inside the empty recess itself), add a themed "
        "rotational reference scale rendered in the device's OWN material language (engraved "
        "grooves, riveted studs, painted dashes, cast ridges, glowing dots — whichever suits the "
        "theme, consistent with the rest of the housing): "
    )
    if arm == "ticks01":
        body = (
            "a distinct MIN/START mark (a raised dot, notch, or short raised tick, slightly more "
            "prominent than the others) positioned at the socket's lower-LEFT, roughly the "
            "7-o'clock direction from the hole's centre; a distinct MAX/END mark of the same style "
            "at the socket's lower-RIGHT, roughly the 5-o'clock direction; and 3 small evenly-"
            "spaced MINOR tick marks along the arc between them, sweeping clockwise up over the top "
            "(through 12-o'clock). "
        )
        pointer = (
            "Additionally, on the volume knob CAP in the sprite strip, its pointer notch must be "
            "drawn oriented toward the SAME 7-o'clock START direction (so the cap, dropped onto the "
            "socket, reads at its MINIMUM position by default)."
        )
    else:
        body = (
            "a distinct MIN/START mark at the socket's lower-LEFT, roughly the 7-o'clock direction; "
            "a distinct MAX/END mark of the same style at the socket's lower-RIGHT, roughly the "
            "5-o'clock direction; AND a distinct CENTER/DETENT mark — visually DIFFERENT from the "
            "min/max marks (e.g. a small raised diamond, a deeper notch, or a different colour of "
            "the same material) — at the socket's TOP, exactly 12-o'clock, marking the knob's "
            "resting BALANCE position. Add 1-2 small minor tick marks in each half-arc between the "
            "center mark and each end mark. "
        )
        pointer = (
            "Additionally, on the volume knob CAP in the sprite strip, its pointer notch must be "
            "drawn oriented toward the TOP / 12-o'clock CENTER direction (so the cap, dropped onto "
            "the socket, reads at its CENTERED/BALANCED default position)."
        )
    tail = (
        " The arc must read as a small, legible, PHYSICALLY REAL part of the housing immediately "
        "surrounding the socket — not a printed sticker, not floating elsewhere on the body, not "
        "overlapping any other control, not obscuring the socket's empty recessed floor. "
    )
    return common_head + body + tail + pointer + "\n"


def json_metadata_clause(arm):
    zero = "start" if arm == "ticks01" else "center"
    return (
        "\nSEPARATE TEXT OUTPUT (in addition to the image): after producing the image, ALSO emit a "
        "separate TEXT response part containing ONLY a single JSON object — no markdown code "
        "fences, no prose commentary before or after it — with EXACTLY this shape describing the "
        "volume knob's rotational range as you rendered its tick-arc:\n"
        '{"vol": {"start_deg": <number>, "end_deg": <number>, "zero": "start"|"center"}}\n'
        "Degrees are measured clockwise from straight-up (12-o'clock = 0 degrees), NEGATIVE for "
        "counter-clockwise-of-12: your MIN/START mark at ~7-o'clock is close to -135, your MAX/END "
        f'mark at ~5-o\'clock is close to +135. "zero" is "{zero}" for this design '
        f'({"the knob rests at its MIN/START mark" if zero == "start" else "the knob rests at its marked CENTER/DETENT"}). '
        "Report the ACTUAL degrees of the marks you painted, not necessarily exactly -135/+135."
    )


def build_prompt(spec, arm, KEYS, layout, BG, dark):
    """Templated single-canvas 'solid' conditioning (the abshape-verdict winner, and genskin.py's
    default when the blueprint trial is off) — identical to genskin.py's templated/'solid' branch
    prompt, with ONLY the tick-arc clause inserted and the JSON-metadata ask appended. Every other
    clause (ZERO RESIDUE, EMPTY CAVITIES, EXACT FIT, CAMERA, mask spec, ...) is reused verbatim
    from genskin.py by string-building the SAME way genskin.main() does, not re-authored here."""
    CONTROLS, BUTTONS = G.CONTROLS, G.BUTTONS
    KNOB, SLIDER, TOGGLE = G.KNOB, G.SLIDER, G.TOGGLE
    ICON = G.ICON

    def kn(c): return G.cname(KEYS[c])
    def rgb(c): return ",".join(str(v) for v in KEYS[c])
    NO_LIST = ", ".join(f"NO {kn(c).lower()}" for c in CONTROLS)
    roster_desc = "; ".join(f"{kn(c)} = {ICON[c]}" for c in CONTROLS)
    STRUCT = spec["theme_prompt"].strip()
    mask_lines = "; ".join(f"{kn(c)} region filled {rgb(c)}" for c in CONTROLS)

    preamble = "Two side-by-side columns of identical size, output at 5:4."
    left_layout = (
        "The LEFT column is a BLUEPRINT: a neutral grey placeholder body with COLOURED SOLID "
        "FILLED patches marking each control's EXACT position, size and shape, plus a bottom "
        "SPRITE-STRIP band with 4 loose parts (volume knob cap, seek slider thumb, shuffle switch "
        "first state, shuffle switch second state). Each guide's colour maps to a control: "
        + roster_desc + ". KEEP EVERY CONTROL AT THE EXACT POSITION, SIZE AND SHAPE OF ITS GUIDE — "
        "do NOT move, resize, swap, rearrange, add or drop any control (their layout is locked). "
        "BUT the grey body is ONLY a rough placeholder showing WHERE the controls sit — you are "
        "FREE and STRONGLY ENCOURAGED to sculpt a BOLD, DISTINCTIVE, ASYMMETRIC, theme-appropriate "
        "outer HOUSING around them: an ornate, characterful, sculpted form with a memorable "
        "silhouette (organic curves, wings, pods, fins, greebles, ornament, asymmetry) — NOT a "
        "plain rounded rectangle, NOT a generic slab or pod. Reshape the outer silhouette "
        "DRAMATICALLY to suit the theme; ONLY the control positions stay fixed. The coloured "
        "filled patches are ALIGNMENT MARKINGS (like masking tape) and MUST be completely removed."
    )
    residue_bullet = (
        "  • ZERO RESIDUE (CRITICAL) — the coloured guide patch around EVERY control is a temporary "
        "alignment marking, NOT part of the design. It must VANISH completely. Each finished BUTTON "
        "is ONE solid piece of the device's own material with absolutely NO coloured ring, rim, "
        "bezel, halo, outline or edge-tint around it — if a button has a coloured ring, it is "
        "WRONG. Likewise the album-art and visualizer windows have NO coloured frame (just a dark "
        "recessed glass panel flush in the body), and no socket/groove/slot has any coloured rim. "
        "Paint the body/button material seamlessly OVER where each guide patch was.\n"
    )

    prompt = (
        preamble + " ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO NUMBERS, NO CAPTIONS and NO "
        "LABELS anywhere in EITHER column — not under controls, not on the strip, not a title, "
        "nothing; the device is wordless, identified by icons, shapes and tick marks only. "
        + left_layout + "\n"
        "THEME (design the finished device in THIS style — you own all materials, colours, form, "
        "lighting): " + STRUCT + "\n"
        "Fill BOTH columns keeping the device+strip layout IDENTICAL so they overlay pixel-for-pixel.\n"
        "LEFT column — the FINISHED, richly 3D, tactile, skeuomorphic media player and its loose "
        "parts, in the theme above. CRITICAL for cutout: the BACKDROP around the device and BEHIND "
        f"every strip part is a FLAT, PERFECTLY UNIFORM {'pale grey-white' if dark else 'near-black charcoal'} "
        f"tone (RGB ~{BG[0]},{BG[1]},{BG[2]}) — a separate keyed-out backdrop with NO "
        "gradient/texture/vignette that strongly contrasts the body; the device must never approach "
        "the backdrop tone.\n"
        "  • The finished device uses ONLY its own theme materials/colours — NONE of the guide "
        f"colours. ABSOLUTELY {NO_LIST} anywhere in the LEFT column; the guide colours exist ONLY in "
        "the RIGHT mask.\n"
        + residue_bullet
        + "  • The 5 transport/function BUTTONS (play/pause, previous, next, repeat, queue) are "
        "raised, glossy, tactile control facets set into the body, EACH clearly bearing its icon "
        "EMBOSSED/engraved in relief: " + "; ".join(f"{ICON[c]}" for c in BUTTONS) + ". Shape + icon "
        "+ relief only; no text labels; no coloured rim.\n"
        "  • BUTTON COLOURS COME FROM THE THEME, NEVER FROM THE GUIDES: the guide colour of a "
        "button marks its POSITION ONLY — the finished button's material/fill must NOT inherit, "
        "echo or be tinted toward its guide colour in ANY way. ALL five buttons are made of the "
        "device's OWN theme materials/palette, coloured consistently with each other and the body. "
        "If any button's colour visibly matches its guide colour, the output is WRONG.\n"
        "  • THE SINGLE MOST IMPORTANT RULE — EVERY MOVING-PART CAVITY IS EMPTY. The volume knob "
        "socket is a bare round HOLE showing only its dark recessed floor PLUS the tick-arc "
        "described below engraved into the housing AROUND the hole (NO knob, NO cap, NO dome, NO "
        "dial, NO pointer installed IN the hole). The seek slider groove is an EMPTY DARK RECESSED "
        "CHANNEL cut into the body (NO thumb, NO grip, NO handle, NO fill). The shuffle switch slot "
        "is an EMPTY DARK rounded well (NO switch, NO lever, NO toggle installed). The device is "
        "photographed BEFORE ASSEMBLY: those parts exist ONLY in the bottom sprite strip and have "
        "NOT been installed yet. If ANY of the three cavities contains ANY part or any fill colour, "
        "the output is WRONG and must be redone.\n"
        "  • SEEK IS JUST AN EMPTY SLOT — a plain EMPTY recessed horizontal SLOT/CHANNEL only, NOT "
        "a functioning slider. Absolutely do NOT bake a slider thumb, grip, knob, handle, bar, "
        "fill, track-fill or progress indicator into it; the thumb is a SEPARATE loose part in the "
        "strip.\n"
        "  • The ALBUM-ART window and the VISUALIZER window are BLANK, DARK, EMPTY recessed glass "
        "SCREENS — flat unlit dark glass panels only, with NOTHING inside them: NO baked "
        "spectrum/equalizer bars, NO album cover or artwork, NO waveform, NO icons, NO text. They "
        "are powered-down screens.\n"
        + tick_clause(arm)
        + "  • SPRITE STRIP — EXACTLY FOUR finished parts in ONE horizontal row, left→right: volume "
        "knob cap, seek slider thumb, shuffle switch in its first state, shuffle switch in its "
        "second state — in the device's own materials, outlines removed, on the flat "
        f"{'pale' if dark else 'charcoal'} backdrop.\n"
        "  • THE SEEK STRIP PART IS THE LOOSE THUMB/GRIP ONLY — the small handle piece a finger "
        "slides, shown by itself on the backdrop, like a spare part in a parts tray. It is NOT a "
        "slot, groove, channel, track, rail or recess.\n"
        "  • EXACT FIT — each strip part is the EXACT size & shape of its slot (knob cap = socket "
        "diameter; thumb fits the groove; each shuffle state exactly fills the switch slot).\n"
        "  • SHUFFLE STATES — a CHARACTERFUL two-state mechanism fitting the theme; BOTH states "
        "share the SAME OUTER HOUSING SILHOUETTE and are CLEARLY MIRROR-OPPOSITE. NO text, letters, "
        "numerals, glyphs or labels of ANY kind on either switch part.\n"
        "  • CAMERA — render EVERY strip part in a PERFECTLY FLAT, STRAIGHT-DOWN, TOP-DOWN "
        "ORTHOGRAPHIC view, exactly as it appears seated flat in its socket on the top-down device. "
        "The volume knob cap is a FLAT ROUND DISC / COIN — ONLY its circular TOP FACE (knurled rim, "
        "pointer notch), NO cylindrical side wall or thickness visible. NO 3/4 view, NO tilt, NO "
        "isometric, NO perspective.\n"
        "RIGHT column — a precise REGION MASK on pure BLACK, pixel-aligned to the LEFT. For EACH "
        "control paint ONE SOLID FILLED blob in ITS OWN guide colour, at the EXACT same position, "
        "size and silhouette as that control on the left (the seek-slider blob is a FULL-HEIGHT "
        "horizontal bar matching the groove, NOT a thin line; the shuffle blob is a tall portrait "
        "rounded-rectangle; each knob/button blob a solid disc — the mask blob is JUST the control "
        "silhouette, it does NOT include the tick-arc engraving around the knob): " + mask_lines
        + ". DISPLAY-WINDOW BLOBS — the visualizer and album-art blobs must EXACTLY cover their "
        "painted window's GLASS area on the left: the SAME rectangle at the SAME position with the "
        "SAME rounded corners, edge-to-edge with the glass.\n"
        + "; and each STRIP PART as a solid COMPACT blob of its colour (volume cap=" + kn(KNOB).lower()
        + ", seek thumb=" + kn(SLIDER).lower() + ", BOTH shuffle states=" + kn(TOGGLE).lower()
        + ") exactly matching its part's silhouette & position in the left strip. Every blob is ONE "
        "solid filled silhouette, no outlines, no holes. Everything else is pure black."
        + json_metadata_clause(arm)
    )
    return prompt


def edit_vertex_text_image(bp_path, prompt, seed, aspect="5:4"):
    """generateContent with responseModalities=[TEXT, IMAGE] — the empirical test of whether
    gemini-3-pro-image-preview will emit a structured JSON text part alongside the image in ONE
    call (see module docstring re: imgjson/ + the semantic-emissive research doc's un-tested
    claim that this mode doesn't exist). Returns (image_bytes, text_or_None, raw_json)."""
    tok = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    b64 = base64.b64encode(open(bp_path, "rb").read()).decode()
    # NO-IMAGE FAILURE MODE observed live (2026-07-11, fa-pod ticks01 seed 501): with
    # TEXT+IMAGE modalities the model sometimes returns ONLY 'thought' text parts and never
    # emits the image — it plans the design in text, then stops. Retry the whole request
    # (same seed first, then seed+1000*k to escape a deterministic dead end); each no-image
    # roll is a reliability datapoint, printed for the log.
    for img_attempt in range(3):
        body = {
            "contents": [{"role": "user", "parts": [
                {"inline_data": {"mime_type": "image/png", "data": b64}},
                {"text": prompt},
            ]}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "seed": seed + (1000 * img_attempt if img_attempt else 0),
                "candidateCount": 1,
                "imageConfig": {"aspectRatio": aspect, "imageSize": "4K"},
            },
        }
        for attempt in range(5):
            r = requests.post(VURL, headers={"Authorization": f"Bearer {tok}",
                                              "Content-Type": "application/json"},
                               json=body, timeout=420)
            if r.status_code == 429 and attempt < 4:
                wait = 15 * (attempt + 1)
                print(f"[vertex] 429 rate-limited, retry {attempt+1}/5 in {wait}s", flush=True)
                time.sleep(wait)
                continue
            break
        raw = None
        try:
            raw = r.json()
        except Exception:
            pass
        if r.status_code != 200:
            raise RuntimeError(f"vertex HTTP {r.status_code}: {r.text[:800]}")
        img_bytes, text_out = None, None
        for part in raw["candidates"][0]["content"]["parts"]:
            d = part.get("inlineData") or part.get("inline_data") or {}
            if d.get("data") and img_bytes is None:
                img_bytes = base64.b64decode(d["data"])
            if part.get("text"):
                text_out = (text_out or "") + part["text"]
        if img_bytes is not None:
            if img_attempt:
                print(f"[vertex] image returned on no-image retry {img_attempt} "
                      f"(seed bumped to {seed + 1000 * img_attempt})", flush=True)
            return img_bytes, text_out, raw
        print(f"[vertex] NO-IMAGE response (thought-text only), retry {img_attempt+1}/3", flush=True)
    raise RuntimeError("vertex: no image part after 3 attempts (thought-text-only responses)")


def main():
    spec = json.load(open(sys.argv[1]))
    arm = sys.argv[sys.argv.index("--arm") + 1]
    assert arm in ARMS, f"--arm must be one of {ARMS}"
    seed = int(sys.argv[sys.argv.index("--seed") + 1])
    sid = spec["id"]; mode = spec["mode"]
    assert mode == "templated", "knobticks experiment only makes sense in templated mode"
    palette = {k: tuple(v) for k, v in spec["palette"].items()}
    dark = spec.get("material_is_dark", False)
    BG = (235, 235, 238) if dark else (18, 18, 24)
    tag = f"{sid}-{arm}-{seed}"
    OUT = os.path.join(HERE, f"assets-knobticks-{tag}"); os.makedirs(OUT, exist_ok=True)
    keys = G.pick_keys(palette)
    KEYS = dict(zip(G.CONTROLS, keys))
    layout = G.LAYOUTS[spec.get("layout", "vpod")]()

    edit_img, template = G.build_canvas(BG, layout, KEYS, "solid")
    bp = os.path.join(OUT, "blueprint.png"); edit_img.save(bp)

    res = {"id": sid, "arm": arm, "seed": seed, "model": MODEL, "backdrop": list(BG),
           "palette": {k: list(v) for k, v in palette.items()},
           "keys": {k: list(v) for k, v in KEYS.items()},
           "keyNames": {k: G.cname(v) for k, v in KEYS.items()},
           "buttons": G.BUTTONS, "sprites": [G.KNOB, G.SLIDER, G.TOGGLE], "extras": G.REGIONS,
           "roles": G.ROLES, "devFrac": G.DEVF, "template": template,
           "expected_convention": {"start_deg": START_DEG, "end_deg": END_DEG,
                                    "zero": "start" if arm == "ticks01" else "center"}}
    aa = layout["album_art"]
    res["album_art_rect"] = [aa[0] - aa[3] / G.COL_W / 2, (aa[1] - aa[4] / G.DEV_H / 2) * G.DEVF, aa[3] / G.COL_W, aa[4] / G.DEV_H * G.DEVF]
    vz = layout["visualizer"]
    res["visualizer_rect"] = [vz[0] - vz[3] / G.COL_W / 2, (vz[1] - vz[4] / G.DEV_H / 2) * G.DEVF, vz[3] / G.COL_W, vz[4] / G.DEV_H * G.DEVF]
    knob_fx, knob_fy = layout[G.KNOB][0], layout[G.KNOB][1]
    res["knob_center_frac"] = [knob_fx, knob_fy * G.DEVF]
    res["knob_r_frac"] = G.KNOB_R / G.COL_W
    json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)

    prompt = build_prompt(spec, arm, KEYS, layout, BG, dark)
    res["prompt"] = prompt
    json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)

    if "--blueprint-only" in sys.argv:
        res["prompt_len"] = len(prompt)
        json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)
        print(f"[blueprint-only] {tag} arm={arm} prompt {len(prompt)} chars -> {OUT}")
        return

    t = time.time()
    img_bytes, text_out, raw = edit_vertex_text_image(bp, prompt, seed)
    open(os.path.join(OUT, "joint-4k.png"), "wb").write(img_bytes)
    if text_out:
        open(os.path.join(OUT, "model-text.txt"), "w").write(text_out)
    json.dump(raw, open(os.path.join(OUT, "raw-response-meta.json"), "w"), indent=1) if raw else None
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB"); w, h = im.size; half = w // 2
    im.crop((0, 0, half, h)).save(os.path.join(OUT, "paint.png"))
    im.crop((half, 0, w, h)).save(os.path.join(OUT, "mask.png"))
    res["dims"] = [w, h]
    res["text_part_returned"] = bool(text_out)
    res["model_text_raw"] = text_out
    # try to parse JSON out of the text (model may or may not honor "no fences")
    parsed = None
    if text_out:
        s = text_out.strip()
        if s.startswith("```"):
            s = s.strip("`")
            if s.lower().startswith("json"): s = s[4:]
        try:
            parsed = json.loads(s.strip())
        except Exception:
            import re as _re
            m = _re.search(r"\{.*\}", text_out, _re.S)
            if m:
                try: parsed = json.loads(m.group(0))
                except Exception: parsed = None
    res["model_json_parsed"] = parsed
    json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)
    print(f"[gen] {tag} joint {time.time()-t:.0f}s dims={w}x{h} text_returned={bool(text_out)} "
          f"json_parsed={bool(parsed)}", flush=True)

    import numpy as np
    a = np.asarray(Image.open(os.path.join(OUT, "paint.png")).convert("RGB")).astype(int)
    tot = a.shape[0] * a.shape[1]; sat = (a.max(2) - a.min(2)) > 55; worst = ("none", 0.0)
    for name in G.BUTTONS + [G.KNOB, G.SLIDER, G.TOGGLE]:
        c = KEYS[name]; d2 = ((a - np.array(c)) ** 2).sum(2); frac = int((sat & (d2 < 60 ** 2)).sum()) / tot
        if frac > 0.0003: print(f"  [leak] {name:9} {frac*100:.4f}%")
        if frac > worst[1]: worst = (name, frac)
    print(f"[leak gate] worst-control={worst[0]} {worst[1]*100:.4f}% -> {'FAIL (gross)' if worst[1]>0.0030 else 'ok'}", flush=True)
    res["leak"] = round(worst[1], 6); json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
