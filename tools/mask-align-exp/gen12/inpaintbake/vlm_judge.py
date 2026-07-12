#!/usr/bin/env python3
"""vlm_judge — SOTA-eye cross-check (verify-outputs-rule §1b stage 2 / gen12's own
semissive/sota_eval.py pattern, reused: openrouter/router/vision, google/gemini-2.5-pro,
reasoning=true — same endpoint+model the project already proved live 2026-07-11).

Sends BEFORE (defect still present) + AFTER (candidate result) crops for each skin x model
cell and asks Gemini to score: (1) defect fully removed, (2) material/texture continuity at
the seam, (3) no new artifacts introduced. Per verify-outputs-rule, this is a WITNESS, not a
judge — every FAIL/MISPLACED claim gets adjudicated against the deterministic det_scores.json
+ my own full-res look before it drives the routing recommendation.

Usage: python3 vlm_judge.py
"""
import json, os, sys, time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)

MODEL = "google/gemini-2.5-pro"
ENDPOINT = "openrouter/router/vision"
COST_ESTIMATE = 0.02

CROPS_META = json.load(open(os.path.join(HERE, "crops_meta.json")))
MODELS = ["lama", "z-image-turbo", "qwen-inpaint", "flux-pro-fill", "flux-dev-fill", "vertex"]

SYSTEM_PROMPT = (
    "You are an independent visual QA reviewer for an AI-inpainting repair. A slider thumb/"
    "handle was baked into a device control's recessed groove by mistake and had to be erased. "
    "You are shown TWO crops of the SAME region: [0] BEFORE (defect present, the handle you "
    "should no longer see) and [1] AFTER (the candidate repair). Judge the AFTER image only "
    "against the BEFORE for reference. Score three criteria: "
    "(1) removed — is the handle/thumb fully gone from the groove (not just faded)? "
    "(2) seamless — does the repaired area continue the SAME material/texture/lighting as the "
    "surrounding groove, with no visible patch, blur smear, colour mismatch, or hard edge? "
    "(3) no_new_artifacts — did the repair introduce anything wrong (a new blob, warped "
    "geometry, wrong material, text, or unrelated content)? "
    "Return STRICT JSON only, no markdown fences, in exactly this shape: "
    '{"removed": true|false, "seamless": true|false, "no_new_artifacts": true|false, '
    '"notes": "...", "verdict": "PASS"|"FAIL"}'
)


def load_fal_key():
    for line in open("/Users/conner/dev/central/.env"):
        line = line.strip()
        if line.startswith("FAL_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("no FAL_KEY")


def upload(path, fal_key):
    r = requests.post("https://rest.alpha.fal.ai/storage/upload/initiate",
                       headers={"Authorization": f"Key {fal_key}"},
                       json={"file_name": os.path.basename(path), "content_type": "image/png"})
    r.raise_for_status()
    d = r.json()
    with open(path, "rb") as f:
        requests.put(d["upload_url"], data=f.read(),
                     headers={"Content-Type": "image/png"}).raise_for_status()
    return d["file_url"]


def judge_one(skin, model, fal_key, before_url_cache):
    result_path = os.path.join(HERE, "results", f"{skin}__{model}.png")
    if not os.path.exists(result_path):
        return None
    if skin not in before_url_cache:
        before_url_cache[skin] = upload(CROPS_META[skin]["crop_path"], fal_key)
    before_url = before_url_cache[skin]
    after_url = upload(result_path, fal_key)

    body = {
        "image_urls": [before_url, after_url],
        "prompt": f"Skin: {skin}. Material: {CROPS_META[skin]['material']}. Repair model: "
                  f"{model}. Judge image [1] (AFTER) against image [0] (BEFORE) per the "
                  f"system prompt's three criteria.",
        "system_prompt": SYSTEM_PROMPT, "reasoning": True, "temperature": 0.1, "model": MODEL,
    }
    t0 = time.time()
    r = requests.post(f"https://queue.fal.run/{ENDPOINT}",
                       headers={"Authorization": f"Key {fal_key}", "Content-Type": "application/json"},
                       json=body)
    sub = r.json()
    if "status_url" not in sub:
        return {"skin": skin, "model": model, "error": str(sub)}
    while True:
        st = requests.get(sub["status_url"], headers={"Authorization": f"Key {fal_key}"}).json()
        if st.get("status") == "COMPLETED":
            break
        if st.get("status") in ("FAILED", "ERROR") or time.time() - t0 > 150:
            return {"skin": skin, "model": model, "error": str(st)}
        time.sleep(2)
    res = requests.get(sub["response_url"], headers={"Authorization": f"Key {fal_key}"}).json()
    result = res.get("result", res)
    raw = result.get("output", "")
    real_cost = (result.get("usage") or {}).get("cost")
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}") + 1]
    try:
        parsed = json.loads(cleaned)
    except Exception:
        parsed = {"verdict": "UNPARSED", "raw": raw[:1000]}
    parsed.update({"skin": skin, "model": model,
                   "cost_usd": real_cost if real_cost is not None else COST_ESTIMATE,
                   "elapsed_s": round(time.time() - t0, 1)})
    return parsed


def main():
    fal_key = load_fal_key()
    out_path = os.path.join(HERE, "vlm_judgments.json")
    existing = {(r["skin"], r["model"]): r for r in json.load(open(out_path))} \
        if os.path.exists(out_path) else {}
    before_url_cache = {}
    total_cost = sum(r.get("cost_usd", 0) for r in existing.values())
    for skin in CROPS_META:
        for model in MODELS:
            if (skin, model) in existing:
                continue
            r = judge_one(skin, model, fal_key, before_url_cache)
            if r is None:
                continue
            existing[(skin, model)] = r
            cost = r.get("cost_usd", 0) or 0
            total_cost += cost
            print(f"[judge] {skin:16s} {model:15s} verdict={r.get('verdict')} "
                  f"removed={r.get('removed')} seamless={r.get('seamless')} "
                  f"(${cost:.4f}, running total ${total_cost:.3f})")
            json.dump(list(existing.values()), open(out_path, "w"), indent=2)
    print(f"\nVLM judging total: ${total_cost:.3f} -> {out_path}")


if __name__ == "__main__":
    main()
