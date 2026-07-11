#!/usr/bin/env python3
"""semissive/sota_eval.py — independent SOTA-eye cross-check.

Per verify-rule (the VLM-as-witness, adjudicated-not-trusted discipline): sends the semantic
path's own composited preview (src + emissive.png, i.e. "what would glow") to Gemini via fal
(openrouter/router/vision, reasoning=true) — a DIFFERENT call path than judge.py's Vertex
gemini-3.1-pro-preview call (fal-hosted OpenRouter vs direct Vertex; still the Gemini family,
so this is a witness for whole-region semantic sanity, not a fully independent second judge —
noted plainly in the experiment record, not oversold).

Asks: does everything that glows make semantic sense, does anything obviously glow-worthy
stand out as MISSING. Structured JSON requested in the prompt text (this endpoint has no
responseSchema param — logged as a structured-IO finding: schema enforcement is Vertex-only
here, openrouter/router/vision only takes prompt/system_prompt/reasoning/model/temperature/
max_tokens, no response-format field, confirmed via get_model_schema 2026-07-11).

Usage: python3 sota_eval.py <skin-id> [<skin-id> ...]
"""
import json
import os
import sys
import time

import requests

from common import load_fal, load_skin, record_cost, upload_fal

# "google/gemini-3-pro-preview" is NOT a valid OpenRouter slug as of 2026-07-11 (verified
# live: "No endpoints found for google/gemini-3-pro-preview") — OpenRouter's Gemini-3 listing
# lags fal's own catalog. google/gemini-2.5-pro confirmed live via openrouter/router/vision.
MODEL = "google/gemini-2.5-pro"
FALLBACK_MODEL = "google/gemini-2.0-flash-001"
ENDPOINT = "openrouter/router/vision"
COST_ESTIMATE_USD = 0.03

SYSTEM_PROMPT = (
    "You are an independent visual QA reviewer for a skeuomorphic device skin's emissive "
    "(self-illumination) lighting. You did NOT decide what glows — a separate model already "
    "did, and its result is composited into the image you're shown. Your job: sanity-check "
    "the RESULT, not re-derive it from scratch. Judge (1) does everything that currently "
    "glows make semantic sense for this material/theme (or does anything look like it's "
    "glowing for no reason), and (2) does anything glow-worthy in the image stand out as "
    "conspicuously MISSING (something that clearly should self-illuminate but doesn't). "
    "Ignore the thin colored ring outlines around some controls — those are UI legibility "
    "guides, not glow, and are expected to be unlit. Return STRICT JSON only, no markdown "
    "fences, no commentary outside the JSON, in exactly this shape:\n"
    '{"sensible": true|false, "per_region": [{"label":"...", "verdict":"sensible|questionable|nonsensical", "note":"..."}], '
    '"missing": ["..."], "overall_note": "...", "verdict": "PASS"|"FAIL"}'
)


def eval_one(sid, model=MODEL):
    p, regs, spec = load_skin(sid)
    judge_path = os.path.join(p["out_dir"], "judge.json")
    refine_path = os.path.join(p["out_dir"], "refine.json")
    preview_path = os.path.join(p["out_dir"], "preview.png")
    src_path = os.path.join(p["out_dir"], "src.png")
    if not os.path.exists(preview_path):
        raise SystemExit(f"no preview.png for {sid} — run refine.py first")
    judge = json.load(open(judge_path))
    refine = json.load(open(refine_path))

    fal_key = load_fal()
    src_url = upload_fal(src_path, fal_key)
    preview_url = upload_fal(preview_path, fal_key)

    region_summary = ", ".join(
        f"{r['label']!r} ({r.get('note','')})" if False else
        f"{r['label']!r} kept={r.get('kept')} color={r.get('color_hex')} pulse={r.get('pulse')}"
        for r in refine["regions"])

    user_prompt = (
        f"Skin id: {sid}. Theme: {spec.get('theme_prompt','')[:200]}\n"
        f"Attached images: [0] the plain device paint (no glow), [1] the SAME device with the "
        f"semantic-emissive result composited on top (this is what's being reviewed).\n"
        f"Regions the pipeline decided should glow: {region_summary or '(none — pipeline found nothing to glow)'}\n\n"
        "Judge image [1] against image [0]. Return the JSON per the schema in the system prompt."
    )

    body = {"image_urls": [src_url, preview_url], "prompt": user_prompt,
            "system_prompt": SYSTEM_PROMPT, "reasoning": True, "temperature": 0.2,
            "model": model}
    t0 = time.time()
    r = requests.post("https://queue.fal.run/openrouter/router/vision",
                       headers={"Authorization": f"Key {fal_key}", "Content-Type": "application/json"},
                       json=body)
    sub = r.json()
    if "status_url" not in sub:
        raise RuntimeError(f"submit failed: {sub}")
    t1 = time.time()
    while True:
        st = requests.get(sub["status_url"], headers={"Authorization": f"Key {fal_key}"}).json()
        if st.get("status") == "COMPLETED":
            break
        if st.get("status") in ("FAILED", "ERROR") or time.time() - t1 > 150:
            raise RuntimeError(f"sota_eval failed: {st}")
        time.sleep(2)
    res = requests.get(sub["response_url"], headers={"Authorization": f"Key {fal_key}"}).json()
    result = res.get("result", res)
    raw = result.get("output", "")
    real_cost = ((result.get("usage") or {}).get("cost"))
    elapsed = round(time.time() - t0, 1)

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}") + 1]
    parse_error = None
    try:
        parsed = json.loads(cleaned)
    except Exception as e:
        parsed = {}
        parse_error = str(e)

    record = {
        "skin": sid, "model": f"fal:{ENDPOINT}:{model}", "reasoning": True,
        "structured_io": {"responseSchema_available": False,
                           "note": "openrouter/router/vision has no response-format param — "
                                   "JSON requested via prompt only, parsed leniently",
                           "parse_error": parse_error},
        "cost_usd": real_cost if real_cost is not None else COST_ESTIMATE_USD,
        "cost_is_estimate": real_cost is None, "elapsed_s": elapsed,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        **parsed,
    }
    if parse_error:
        record["raw"] = raw[:4000]
    json.dump(record, open(os.path.join(p["out_dir"], "sota-eval.json"), "w"), indent=2)
    record_cost(p["out_dir"], "sota_eval", real_cost if real_cost is not None else COST_ESTIMATE_USD,
                f"{model} {elapsed}s")
    v = record.get("verdict", "UNPARSED" if parse_error else "?")
    print(f"[sota_eval] {sid}: verdict={v} sensible={record.get('sensible')} "
          f"missing={record.get('missing')} ({model}, {elapsed}s"
          f"{', PARSE_ERROR' if parse_error else ''}) -> "
          f"{os.path.join(p['out_dir'], 'sota-eval.json')}")
    return record


if __name__ == "__main__":
    ids = sys.argv[1:]
    if not ids:
        raise SystemExit("usage: sota_eval.py <skin-id> [<skin-id> ...]")
    for sid in ids:
        try:
            eval_one(sid, MODEL)
        except RuntimeError as e:
            print(f"[sota_eval] {sid}: {MODEL} failed ({e}), retrying with {FALLBACK_MODEL}")
            eval_one(sid, FALLBACK_MODEL)
