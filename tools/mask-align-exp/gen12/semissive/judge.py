#!/usr/bin/env python3
"""semissive/judge.py — Stage 1: SEMANTIC JUDGE.

gemini-3.1-pro-preview via Vertex (gcloud-token auth, same pattern as genskin.py's
edit_vertex()/director_review.py's director_chat(); thinkingConfig thinkingLevel "low" —
gemini-3.1-pro-preview defaults to "high" and burns the whole token budget on internal
thought tokens before emitting JSON, confirmed by director_review.py/director.ts).

INPUT: the cropped device-photo image (paint.png's top devFrac rows — no region-mask strip)
+ a STRUCTURED JSON spec block embedded in the prompt text: skin id, the theme's authored
lighting hint (theme_specs/<id>.json), and every control's rect (regions.json), converted to
the SAME src-crop-fraction space as the attached image. Machine-shaped, not prose — the judge
is handed the same facts the classical pass had (lighting.emissive_hint) as a prior it may
agree with, extend, or override from the actual pixels.

OUTPUT: enforced via generationConfig.responseMimeType=application/json +
generationConfig.responseSchema (OpenAPI-3.0 subset, uppercase Type enum — verified live
against Vertex/Gemini docs 2026-07-11, not memory):
  {"emissive_regions": [{"label","why","box":{x,y,w,h in 0..1 of the attached image},
                          "color_hex","intensity_0_1","pulse": ember|phosphor|breathe|none}]}
0-4 regions. An EMPTY list is a valid, correct answer (fa-pod's "almost nothing glows" case).

Never emits precise geometry — box is a ROUGH seed for stage 2's SAM box prompt, per
ai-image-coords-rule ("don't make a noisy VLM load-bearing for precise geometry").

Usage: python3 judge.py <skin-id> [<skin-id> ...]
Writes semissive/out/<skin-id>/judge.json (+ src.png, the cropped device photo).
"""
import json
import os
import sys
import time

import requests

from common import (crop_src, gcloud_token, image_part_b64, load_skin, rect_to_src_frac,
                     record_cost, skin_paths, vertex_url)

VERTEX_PROJECT = os.environ.get("VERTEX_PROJECT", "muser-2605300220")
VERTEX_MODEL = "gemini-3.1-pro-preview"
URL = vertex_url(VERTEX_MODEL, VERTEX_PROJECT)

# Cost estimate only (Vertex bills per input/output token, not a flat rate) — same order of
# magnitude as director_review.py's identically-shaped call (one image + short JSON reply).
COST_ESTIMATE_USD = 0.03

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "emissive_regions": {
            "type": "ARRAY",
            "description": "0-4 regions of the image that should visually SELF-ILLUMINATE. "
                            "Empty list if nothing should glow.",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "label": {"type": "STRING", "description": "short noun phrase naming the glowing thing, e.g. 'rune glyphs', 'CRT screen'"},
                    "why": {"type": "STRING", "description": "one sentence: why this emits its own light vs merely reflects it"},
                    "box": {
                        "type": "OBJECT",
                        "properties": {
                            "x": {"type": "NUMBER"}, "y": {"type": "NUMBER"},
                            "w": {"type": "NUMBER"}, "h": {"type": "NUMBER"},
                        },
                        "required": ["x", "y", "w", "h"],
                        "description": "ROUGH bounding box, fractions 0-1 of the attached image, x/y = top-left",
                    },
                    "color_hex": {"type": "STRING", "description": "#rrggbb of the emitted light color"},
                    "intensity_0_1": {"type": "NUMBER", "description": "0=barely glowing, 1=maximally bright self-illumination"},
                    "pulse": {"type": "STRING", "enum": ["ember", "phosphor", "breathe", "none"]},
                },
                "required": ["label", "why", "box", "color_hex", "intensity_0_1", "pulse"],
            },
        },
    },
    "required": ["emissive_regions"],
}

SYSTEM_PROMPT = (
    "You are a SEMANTIC MATERIAL JUDGE for a skeuomorphic device skin render. Your ONLY job: "
    "decide WHAT in this image should visually SELF-ILLUMINATE (emit its own light) as opposed "
    "to what merely REFLECTS ambient light. Self-illumination examples: glowing carved runes, "
    "a lit phosphor/CRT/LCD screen showing content, ember/lava cracks, indicator lamps, a "
    "torch flame. NOT self-illumination: polished-metal specular highlights, rust, shadow, a "
    "matte painted surface, or the THIN COLORED RING OUTLINES drawn around some controls "
    "(those are UI legibility guides baked into the render, not light sources — never select a "
    "whole control housing/button/knob as emissive just because it has a colored ring or a "
    "bright paint color). This is a SEMANTIC judgment about image content, not a brightness "
    "threshold: something can be bright without emitting light (a chrome highlight), and can "
    "emit light while it reads dim in a flat photo (a dim ember). Use the supplied lighting "
    "hint as a PRIOR you may agree with, narrow, extend, or override — trust the actual pixels "
    "over the hint if they disagree. If the SAME motif (e.g. runes) appears in several "
    "spatially SEPARATE clusters, return ONE region PER distinct cluster with its OWN TIGHT "
    "box around just that cluster — do NOT merge distant, disconnected occurrences into a "
    "single box that spans unrelated non-glowing area between them (a box should be a tight "
    "fit around where the glow actually is, not a bound around 'the whole device'). Return 0 "
    "to 4 regions total, picking the most salient clusters if there are more than 4. If truly "
    "nothing in this image "
    "should self-illuminate, return an EMPTY LIST — that is a valid, CORRECT answer; do not "
    "invent a region to avoid returning nothing. Box coordinates are ROUGH seeds for a "
    "downstream segmentation model, not final geometry — approximate is fine."
)


def build_user_prompt(sid, regs, spec, src_w, src_h, YS):
    lighting = spec.get("lighting", {})
    controls = []
    for key, reg in regs.get("regions", {}).items():
        if not reg.get("device"):
            continue
        controls.append({
            "name": key,
            "role": regs.get("roles", {}).get(key, "?"),
            "rect_norm": rect_to_src_frac(reg["device"], YS),
        })
    spec_block = {
        "skin_id": sid,
        "theme_prompt": spec.get("theme_prompt", ""),
        "lighting_hint": {
            "emissive_hint": lighting.get("emissive_hint", ""),
            "emissive_color": lighting.get("emissive_color", "auto"),
            "pulse": lighting.get("pulse", "breathe"),
            "intensity": lighting.get("intensity", 0.8),
        },
        "image_size_px": [src_w, src_h],
        "controls": controls,
    }
    return (
        "Structured input spec (machine-shaped, not prose) — 'rect_norm' fields are "
        "[x,y,w,h] fractions of the ATTACHED image (the device photo, top-down, no region-"
        "mask strip):\n" + json.dumps(spec_block, indent=1) +
        "\n\nJudge the attached image. Return emissive_regions per the schema."
    )


def judge_one(sid):
    p, regs, spec = load_skin(sid)
    src_path = os.path.join(p["out_dir"], "src.png")
    _, W, H, PW, PH, YS = crop_src(p["paint"], regs["devFrac"], src_path)

    body = {
        "contents": [{"role": "user", "parts": [
            image_part_b64(src_path),
            {"text": build_user_prompt(sid, regs, spec, W, H, YS)},
        ]}],
        "systemInstruction": {"role": "system", "parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "thinkingConfig": {"thinkingLevel": "low"},
            "maxOutputTokens": 2000,
        },
    }
    tok = gcloud_token()
    t0 = time.time()
    r = requests.post(URL, headers={"Authorization": f"Bearer {tok}",
                                     "Content-Type": "application/json"},
                       json=body, timeout=120)
    elapsed = round(time.time() - t0, 1)
    if r.status_code != 200:
        raise RuntimeError(f"vertex HTTP {r.status_code}: {r.text[:800]}")
    data = r.json()
    cand = (data.get("candidates") or [{}])[0]
    finish_reason = cand.get("finishReason")
    raw_text = "".join(pt.get("text", "") for pt in cand.get("content", {}).get("parts", []))

    parse_error = None
    regions = []
    try:
        parsed = json.loads(raw_text) if raw_text else {}
        regions = parsed.get("emissive_regions", [])
        if not isinstance(regions, list):
            raise ValueError("emissive_regions not a list")
    except Exception as e:
        parse_error = str(e)

    record = {
        "skin": sid,
        "model": f"vertex:{VERTEX_MODEL}",
        "vertex_project": VERTEX_PROJECT,
        "structured_io": {"responseMimeType": "application/json", "responseSchema_used": True,
                           "finish_reason": finish_reason, "parse_error": parse_error},
        "cost_estimate_usd": COST_ESTIMATE_USD,
        "elapsed_s": elapsed,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "src_size": [W, H],
        "emissive_regions": regions,
    }
    if parse_error:
        record["raw"] = raw_text[:4000]
    json.dump(record, open(os.path.join(p["out_dir"], "judge.json"), "w"), indent=2)
    record_cost(p["out_dir"], "judge", COST_ESTIMATE_USD,
                f"{VERTEX_MODEL} {elapsed}s finish={finish_reason}")
    n = len(regions)
    print(f"[judge] {sid}: {n} region(s) ({VERTEX_MODEL}, {elapsed}s, finish={finish_reason}"
          f"{', PARSE_ERROR' if parse_error else ''}) -> "
          f"{os.path.join(p['out_dir'], 'judge.json')}")
    for reg in regions:
        print(f"    - {reg.get('label','?')!r} why={reg.get('why','')[:60]!r} "
              f"color={reg.get('color_hex')} intensity={reg.get('intensity_0_1')} "
              f"pulse={reg.get('pulse')}")
    return record


if __name__ == "__main__":
    ids = sys.argv[1:]
    if not ids:
        raise SystemExit("usage: judge.py <skin-id> [<skin-id> ...]")
    for sid in ids:
        judge_one(sid)
