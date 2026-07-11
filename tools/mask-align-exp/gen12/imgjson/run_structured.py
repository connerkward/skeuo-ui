#!/usr/bin/env python3
"""Structured-I/O viability tests (scope expansion) — the pipeline currently uses NO
structured mechanisms anywhere (prose prompts in, freeform/mime-typed text parsed out).
Tests, all against the same Vertex project/auth as run_tests.py:

OUTPUT side
  s1_director_schema   TEXT model + responseSchema on the director Material shape
                       (name/blurb/style-enum/materialPrompt/font — mirrors
                       src/generate/director.ts deriveMaterial, which today uses
                       responseMimeType only). 3 prompts, schema arm vs prose arm.
  s2_bbox_schema       TEXT model + responseSchema on the control-bbox array shape,
                       same paint + roster as run_tests.py test C (the prose arm) —
                       scored with the same IoU machinery.
  s3_image_schema      IMAGE model + responseMimeType/responseSchema alongside
                       TEXT+IMAGE modalities — accept-or-reject probe, error verbatim.

INPUT side
  s4_json_prompt       Extraction ask with the roster/spec delivered as a fenced JSON
                       block instead of prose (TEXT model, no schema, mime json — so
                       the ONLY variable vs test C is prompt shape). Scored identically.
                       (Paint-GENERATION-side structured prompts are NOT tested — that
                       needs image gens; out of the ≤$1 budget.)

Field names: Vertex generateContent generationConfig.responseMimeType +
generationConfig.responseSchema (OpenAPI-subset schema). director.ts already proves
camelCase generationConfig fields on this exact REST endpoint; responseSchema
acceptance is itself part of what s1/s3 verify empirically (Google's docs pages
for the REST field were nav-shells when fetched 2026-07-11; the empirical accept/
reject below is the authoritative record).

Usage: python3 run_structured.py   → writes out/s*_raw.json + out/structured_results.json
"""
import os, json, time
import requests
import run_tests as T

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

DONOR_STYLES = ["biomech", "winamp", "frog", "wmp", "halo"]

# ---------------------------------------------------------------- director shapes
DIRECTOR_SYSTEM_PROSE = (
    "You art-direct skeuomorphic MP3-player skins. Given a silhouette idea, reply with JSON "
    '{"name": <title>, "blurb": <description>, "style": <one of ' + "|".join(DONOR_STYLES) + ">, "
    '"materialPrompt": <1-2 sentence rich custom material/finish description derived from the idea: '
    "surface, color, sheen, hardware accents>, \"font\": <a Google Fonts family name>}. "
    "name is a CONCISE, punchy skin TITLE — 1 to 3 words. blurb is ONE short line, at most ~8 words. "
    "style MUST be exactly one of the listed values. font is a real Google Fonts family, punchy display face."
)

DIRECTOR_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "name": {"type": "STRING", "description": "concise punchy skin title, 1-3 words"},
        "blurb": {"type": "STRING", "description": "one short descriptive line, <=8 words"},
        "style": {"type": "STRING", "enum": DONOR_STYLES},
        "materialPrompt": {"type": "STRING",
                           "description": "1-2 sentence rich material/finish description: surface, color, sheen, hardware accents"},
        "font": {"type": "STRING", "description": "a real Google Fonts family name, punchy display face"},
    },
    "required": ["name", "blurb", "style", "materialPrompt", "font"],
}

DIRECTOR_PROMPTS = [
    "a rusted deep-sea diving helmet grown over with barnacles",
    "a 1950s pastel diner jukebox with chrome fins",
    "an obsidian volcanic altar with glowing magma veins",
]

# ---------------------------------------------------------------- bbox shapes
BBOX_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING", "enum": T.ROSTER},
            "x": {"type": "NUMBER"}, "y": {"type": "NUMBER"},
            "w": {"type": "NUMBER"}, "h": {"type": "NUMBER"},
        },
        "required": ["name", "x", "y", "w", "h"],
    },
}

# s4: identical TASK to T.PROMPT but the spec arrives as a fenced JSON block
JSON_PROMPT = (
    "This image is a top-down skeuomorphic media-player skin. Task spec:\n\n"
    "```json\n" + json.dumps({
        "task": "locate_controls",
        "controls": [{"name": n, "role": T.ROLES[n]} for n in T.ROSTER],
        "each_present_exactly_once": True,
        "output": {
            "format": "STRICT JSON array only — no markdown fence, no prose",
            "item_shape": {"name": "<control name>", "x": "<float>", "y": "<float>",
                           "w": "<float>", "h": "<float>"},
            "coords": "x,y = TOP-LEFT of a tight bbox around the control's visible housing; "
                      "w,h its size; all normalized 0..1 against this image's own width/height "
                      "(x+w<=1, y+h<=1)",
            "include_only_listed_controls": True,
            "omit_none": True,
        },
    }, indent=2) + "\n```"
)


def call_text(parts, gen_config, tag):
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": gen_config}
    return T._post_with_retry(T.endpoint(T.TEXT_MODEL), body, tag)


def call_image(parts, gen_config, tag):
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": gen_config}
    return T._post_with_retry(T.endpoint(T.IMAGE_MODEL), body, tag)


def img_part(path):
    import base64
    return {"inline_data": {"mime_type": "image/png",
                            "data": base64.b64encode(open(path, "rb").read()).decode()}}


def texts_of(resp):
    t, i, fin = T.extract_parts(resp)
    return "".join(t), i, fin


def validate_director(obj):
    """Field completeness for the director Material shape."""
    if not isinstance(obj, dict):
        return {"complete": False, "reason": "not an object"}
    missing = [k for k in ("name", "blurb", "style", "materialPrompt", "font") if not obj.get(k)]
    bad_style = obj.get("style") not in DONOR_STYLES
    return {"complete": not missing and not bad_style,
            "missing": missing, "style_valid": not bad_style}


def main():
    results = {}
    paint = os.path.join(T.ASSET, "paint.png")

    # ---- s1: director, schema arm vs prose arm, 3 prompts each ----------------
    for arm, cfg in [("prose", {"responseMimeType": "application/json",
                                "thinkingConfig": {"thinkingLevel": "low"}}),
                     ("schema", {"responseMimeType": "application/json",
                                 "responseSchema": DIRECTOR_SCHEMA,
                                 "thinkingConfig": {"thinkingLevel": "low"}})]:
        rows = []
        for i, p in enumerate(DIRECTOR_PROMPTS):
            tag = f"s1_{arm}_{i}"
            print(f"[{tag}] calling...", flush=True)
            try:
                resp = call_text([{"text": DIRECTOR_SYSTEM_PROSE + "\n\nIdea: " + p}], cfg, tag)
                json.dump(resp, open(os.path.join(OUT, f"{tag}_raw.json"), "w"), indent=2)
                txt, _, fin = texts_of(resp)
                obj, err = T.try_parse_json(txt)
                rows.append({"prompt": p, "finishReason": fin, "parse_ok": obj is not None,
                             "parse_error": err, "validation": validate_director(obj),
                             "obj": obj})
            except RuntimeError as e:
                rows.append({"prompt": p, "http_error": str(e)[:400]})
            time.sleep(4)
        results[f"s1_director_{arm}"] = rows

    # ---- s2: bbox extraction with responseSchema ------------------------------
    print("[s2_bbox_schema] calling...", flush=True)
    try:
        resp = call_text([img_part(paint), {"text": T.PROMPT}],
                         {"responseMimeType": "application/json",
                          "responseSchema": BBOX_SCHEMA,
                          "thinkingConfig": {"thinkingLevel": "low"}}, "s2")
        json.dump(resp, open(os.path.join(OUT, "s2_bbox_schema_raw.json"), "w"), indent=2)
        txt, _, fin = texts_of(resp)
        obj, err = T.try_parse_json(txt)
        results["s2_bbox_schema"] = {"finishReason": fin, "parse_ok": obj is not None,
                                     "parse_error": err, "n_items": len(obj) if isinstance(obj, list) else 0}
    except RuntimeError as e:
        results["s2_bbox_schema"] = {"http_error": str(e)[:400]}
    time.sleep(10)

    # ---- s3: IMAGE model + structured-output config, accept/reject probes -----
    s3 = {}
    for variant, cfg in [
        ("mime_only", {"responseModalities": ["TEXT", "IMAGE"], "seed": 71,
                       "responseMimeType": "application/json"}),
        ("mime_plus_schema", {"responseModalities": ["TEXT", "IMAGE"], "seed": 71,
                              "responseMimeType": "application/json",
                              "responseSchema": BBOX_SCHEMA}),
    ]:
        print(f"[s3_{variant}] calling...", flush=True)
        try:
            resp = call_image([img_part(paint), {"text": T.PROMPT}], cfg, f"s3_{variant}")
            json.dump(resp, open(os.path.join(OUT, f"s3_{variant}_raw.json"), "w"), indent=2)
            txt, imgs, fin = texts_of(resp)
            obj, err = T.try_parse_json(txt)
            s3[variant] = {"accepted": True, "finishReason": fin,
                           "n_image_parts": len(imgs), "parse_ok": obj is not None,
                           "parse_error": err, "n_items": len(obj) if isinstance(obj, list) else 0}
        except RuntimeError as e:
            s3[variant] = {"accepted": False, "error_verbatim": str(e)[:600]}
        time.sleep(10)
    results["s3_image_schema"] = s3

    # ---- s4: structured (fenced-JSON) prompt, text model, no schema -----------
    print("[s4_json_prompt] calling...", flush=True)
    try:
        resp = call_text([img_part(paint), {"text": JSON_PROMPT}],
                         {"responseMimeType": "application/json",
                          "thinkingConfig": {"thinkingLevel": "low"}}, "s4")
        json.dump(resp, open(os.path.join(OUT, "s4_json_prompt_raw.json"), "w"), indent=2)
        txt, _, fin = texts_of(resp)
        obj, err = T.try_parse_json(txt)
        results["s4_json_prompt"] = {"finishReason": fin, "parse_ok": obj is not None,
                                     "parse_error": err, "n_items": len(obj) if isinstance(obj, list) else 0}
    except RuntimeError as e:
        results["s4_json_prompt"] = {"http_error": str(e)[:400]}

    json.dump(results, open(os.path.join(OUT, "structured_results.json"), "w"), indent=2)
    print("\nwrote", os.path.join(OUT, "structured_results.json"))


if __name__ == "__main__":
    main()
