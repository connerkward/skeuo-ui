#!/usr/bin/env python3
"""director_gate.py — let the DIRECTOR decide, PER SKIN, whether an OPTIONAL pipeline stage is
worth running for THIS theme, instead of every optional stage being an unconditional global
on/off (see TODO.md "Let the DIRECTOR decide whether optional pipeline stages are worth
running per skin", 2026-07-11). Companion to director_review.py, which judges a FINISHED
render's aesthetics; this script judges, from the theme spec ALONE (no render, no images —
cheap and fast by design), whether a candidate optional stage even fits this skin's brief.

NOT a replacement for director_review.py's aesthetic sign-off, and NOT itself gated by this
script (that would be circular — you cannot use the director-review verdict to decide whether
to run the director review). This is the upstream, spec-only gate that orchestrate12.py calls
BEFORE it decides whether to invoke an optional stage at all; director_review.py remains one
of the stages this script can be asked to gate.

Candidate stages are NOT hardcoded to a fixed pair — the caller (orchestrate12.py) passes
whichever subset of STAGE_CATALOG is relevant for this skin's live state (e.g. only ask about
"erase" when extract12.py's gate already flagged a baked-thumb defect for this skin; asking
the director to judge repairing a non-existent defect is nonsensical). Emissive/PBR are
PARKED for skeuo v2 (TODO.md) and are deliberately NOT in STAGE_CATALOG.

Output shape, written to <assets-dir>/director-gate.json:
    {"skin": ..., "model": ..., "cost_estimate_usd": ..., "elapsed_s": ...,
     "decisions": {"<stage>": {"run": bool, "why": "<one-line rationale>"}, ...}}

`orchestrate12.py` also folds `decisions` into `orch.json`'s own `director_decisions` key so a
skipped stage is auditable after the fact (per the TODO's spec) without re-running anything.

Cost: spec-text-only, NO image parts attached (unlike director_review.py's ~$0.02-0.05/skin
full-render judgment) — the TODO's own cost logic puts this in the ~$0.005-0.015/call range,
i.e. well under a third of the stage it might skip, so gating only pays for itself once a real
fraction of skins would say "no" (see TODO's breakeven note). It reuses director_review.py's
Vertex auth/model/schema pattern (gemini-3.1-pro-preview, gcloud-token auth, thinkingLevel
"low", responseSchema-enforced JSON) rather than inventing a second call convention — this
file does NOT import director_review.py (that's a top-level script, not a module, same
reasoning director_review.py itself gives for not importing observe12.py's crop()).

Usage: python3 director_gate.py <assets-dir> --stages erase,director_review [--context '{...}']
  --stages   comma-separated subset of STAGE_CATALOG keys to ask about (required, non-empty).
  --context  optional JSON object of extra per-stage facts to hand the director (e.g. the
             live gate reasons that made "erase" a candidate at all) — merged into the prompt
             verbatim, not schema-validated (keep it small: a few short fields, not a dump).
"""
import os, re, sys, json, time, argparse, subprocess

# --- stage catalog: what the director is allowed to be asked about --------------------------
# Deliberately NOT emissive/PBR (PARKED for skeuo v2, TODO.md "PARKED" section) and NOT any
# core stage (gen/extract/biref/build always run, per fix-generalizable-rule's stage taxonomy
# — those aren't "optional," they're the pipeline). Add a new optional stage here + give
# orchestrate12.py a matching candidate/honor block; nothing else in this file changes.
STAGE_CATALOG = {
    "erase": (
        "erase12.py's auto-repair pass: a detected baked-in defect (most commonly a static "
        "painted slider thumb sitting inside what must be an empty groove/socket) gets erased "
        "via classical inpaint, escalating to a generative model-edit only if the classical "
        "pass still reads bright. Only ever asked about when extract12.py's gate has ALREADY "
        "flagged a concrete baked-thumb defect for this skin (see the gate_reasons context "
        "below) — the question is not 'does this skin need repair scanning' but 'is an "
        "automated AI repair the right move for THIS theme', given the flagged region and "
        "this skin's material. Say NO if the flagged region plausibly reads as an intentional "
        "part of this theme's own material/texture (e.g. an organic, hand-worked, or "
        "deliberately irregular surface where a crisp inpaint could look more wrong than the "
        "defect itself), or if an AI edit risks visibly clashing with the surrounding paint's "
        "distinctive style. Say YES for a clean geometric material (metal, glass, plastic, "
        "stone) where erasing a static thumb back to bare groove is unambiguously an "
        "improvement."
    ),
    "director_review": (
        "director_review.py's full aesthetic/thematic FINAL SIGN-OFF pass: renders the real "
        "shipped player, captures per-control crops, and judges cohesion / material fidelity / "
        "control legibility / seating against this skin's OWN brief. Costs roughly "
        "$0.02-0.05 and ~11s of render+API time per run. Nearly every real roster skin "
        "should say YES — final sign-off is cheap relative to the paint spend it's judging. "
        "Say NO only for a skin that is plainly a throwaway/diagnostic test render never "
        "meant to ship (e.g. an internal geometry-only probe with no real theme brief), not "
        "merely because the theme is simple or the render might score low."
    ),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("assets_dir")
    ap.add_argument("--stages", required=True, help="comma-separated STAGE_CATALOG keys")
    ap.add_argument("--context", default="{}", help="JSON object of extra per-stage facts")
    args = ap.parse_args()

    out = os.path.abspath(args.assets_dir)
    sid = re.sub(r"^assets-", "", os.path.basename(out))
    sid = re.sub(r"_(biref|pbr)$", "", sid)

    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    unknown = [s for s in stages if s not in STAGE_CATALOG]
    if unknown:
        raise SystemExit(f"director_gate: unknown stage(s) {unknown}; known: {list(STAGE_CATALOG)}")
    if not stages:
        raise SystemExit("director_gate: --stages must name at least one candidate stage")
    try:
        extra_context = json.loads(args.context)
    except Exception:
        extra_context = {}

    here = os.path.dirname(os.path.abspath(__file__))
    spec_path = os.path.join(here, "theme_specs", f"{sid}.json")
    spec = json.load(open(spec_path)) if os.path.exists(spec_path) else {}

    palette_txt = ", ".join(f"{k}=rgb{tuple(v)}" for k, v in spec.get("palette", {}).items())
    lighting = spec.get("lighting", {})
    stage_block = "\n".join(
        f"- \"{key}\": {desc}" + (f" Extra context for this stage: {json.dumps(extra_context[key])}"
                                    if key in extra_context else "")
        for key, desc in STAGE_CATALOG.items() if key in stages
    )

    SYSTEM_PROMPT = (
        "You are the DIRECTOR making a fast, cheap PRE-FLIGHT call on a skeuomorphic "
        "music-player skin's generation pipeline: for EACH candidate optional stage listed, "
        "decide whether it is worth running for THIS skin, given ONLY its theme brief (no "
        "render is available yet or being judged here — that is a separate, later pass). "
        "This is a permission call, not a sign-off: default to YES unless the brief gives a "
        "concrete, stated reason to skip. Never invent defects or details not implied by the "
        "brief or the provided context. Keep each rationale to one short sentence."
    )
    user_prompt = (
        f"Skin id: {sid}\n"
        f"Theme brief (theme_prompt): {spec.get('theme_prompt', '(none)')}\n"
        f"Palette: {palette_txt or '(none)'}\n"
        f"Lighting/emissive hint: {lighting.get('emissive_hint', '(none)')}\n\n"
        f"Candidate stages to decide on:\n{stage_block}\n\n"
        "Return one decision entry per candidate stage listed above, using its exact key."
    )

    RESPONSE_SCHEMA = {
        "type": "OBJECT",
        "properties": {
            "decisions": {
                "type": "ARRAY",
                "description": "one entry per candidate stage",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "stage": {"type": "STRING", "description": "exact stage key from the prompt"},
                        "run": {"type": "BOOLEAN"},
                        "why": {"type": "STRING", "description": "one short sentence"},
                    },
                    "required": ["stage", "run", "why"],
                },
            },
        },
        "required": ["decisions"],
    }

    VERTEX_PROJECT = os.environ.get("VERTEX_PROJECT", "muser-2605300220")
    VERTEX_LOCATION = "global"
    VERTEX_MODEL = "gemini-3.1-pro-preview"
    VERTEX_URL = (f"https://aiplatform.googleapis.com/v1/projects/{VERTEX_PROJECT}/locations/"
                  f"{VERTEX_LOCATION}/publishers/google/models/{VERTEX_MODEL}:generateContent")

    def gate_chat():
        import requests
        tok = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
        body = {
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "systemInstruction": {"role": "system", "parts": [{"text": SYSTEM_PROMPT}]},
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": RESPONSE_SCHEMA,
                # text-only, short decision call — force low thinking so the budget goes to
                # the JSON, not internal thought tokens (same reasoning as director_review.py).
                "thinkingConfig": {"thinkingLevel": "low"},
                "maxOutputTokens": 1200,
            },
        }
        r = requests.post(VERTEX_URL, headers={"Authorization": f"Bearer {tok}",
                                                "Content-Type": "application/json"},
                           json=body, timeout=120)
        if r.status_code != 200:
            raise RuntimeError(f"vertex HTTP {r.status_code}: {r.text[:500]}")
        data = r.json()
        cand = (data.get("candidates") or [{}])[0]
        text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
        return text or "{}", cand.get("finishReason")

    t0 = time.time()
    parse_error = None
    decisions = {}
    raw_text = ""
    finish_reason = None
    try:
        raw_text, finish_reason = gate_chat()
        parsed = json.loads(raw_text) if raw_text else {}
        items = parsed.get("decisions", [])
        if not isinstance(items, list):
            raise ValueError(f"decisions not a list: {type(items)}")
        decisions = {item["stage"]: {"run": bool(item["run"]), "why": item.get("why", "")}
                     for item in items if item.get("stage") in stages}
        missing = [s for s in stages if s not in decisions]
        if missing:
            raise ValueError(f"model omitted decisions for {missing}")
    except Exception as e:
        parse_error = f"{e}"
    elapsed = round(time.time() - t0, 1)

    # FAIL OPEN, never fail closed: a broken/unparseable gate call must not silently withhold
    # a stage the global flag already permits — that would be worse than no gating at all
    # (human-labeled-data-rule / verify-outputs-rule spirit: a script bug should never look
    # like a considered decision). Any stage the model didn't return a clean verdict for
    # defaults to run=True with the failure recorded in its own "why".
    for s in stages:
        if s not in decisions:
            decisions[s] = {"run": True,
                             "why": f"director_gate call failed/unparseable ({parse_error}); "
                                    "defaulting to run=True (fail-open)"}

    record = {
        "skin": sid,
        "model": f"vertex:{VERTEX_MODEL}",
        "vertex_project": VERTEX_PROJECT,
        "structured_io": {"responseMimeType": "application/json", "responseSchema_used": True,
                           "finish_reason": finish_reason},
        "cost_estimate_usd": "0.005-0.015",
        "elapsed_s": elapsed,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "stages_asked": stages,
        "decisions": decisions,
    }
    if parse_error:
        record["parse_error"] = parse_error
        record["raw"] = raw_text[:2000]

    json.dump(record, open(os.path.join(out, "director-gate.json"), "w"), indent=2)
    summary = ", ".join(f"{k}={'RUN' if v['run'] else 'SKIP'}" for k, v in decisions.items())
    print(f"[director_gate] {sid}: {summary} ({VERTEX_MODEL}, {elapsed}s) "
          f"-> {os.path.join(out, 'director-gate.json')}")


if __name__ == "__main__":
    main()
