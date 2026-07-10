# Generation spend — don't pay for what a re-run of code can fix

Project rule for the skin-generation pipeline (gen12 and successors). The paint call is the
expensive artifact (~$0.15/roll); extraction/cutting/scoring are $0 re-runnable code. Spend
discipline follows from that asymmetry. (Adopted 2026-07-10 after a regen burned ~32 paint
rolls where 5 of 8 failing skins were failed by a GATE BUG, not bad paint.)

## 1. Only re-roll on defects the model can actually affect

A regeneration (new seed → new paint call) is justified ONLY when the failure is in the
PAINT: residue/guide-colour leak, non-empty sockets, missing/duplicate controls, baked-in
parts, model rearranged the layout, unusable material rendering. These change with a re-roll.

If the failure is EXTRACTOR-SIDE — a travel walk overshooting, a region misfit, a state-align
mismatch, a gate bug, a mask-cell mismatch that better code would handle — do NOT re-roll.
Fix the code and **re-extract the same paint for $0**. The orchestrator's gate loop must
classify failure reasons into `paint-defect` vs `extract-defect` and only burn a seed on the
former. A roll triggered by an extractor bug wastes $0.15 to fix nothing.

## 2. BiRefNet runs LOCALLY

BiRefNet weights are open and run on this machine (MPS; the local ComfyUI install already
carries the pack). The matte step must use local inference — $0/matte, no rate limits, no
billing-lock dependency (fal 403'd the whole pipeline on 2026-07-10). The fal
`fal-ai/birefnet/v2` endpoint is the FALLBACK, not the default, and only for a machine
without the local weights. Same model either way — zero quality delta.

## 3. Google-model generations go DIRECT via Vertex, not fal-wrapped

Paint calls that hit a Google image model (gemini-image edit et al.) route through the
user's Vertex/Google API credentials directly — fal's wrapper adds margin on every roll and
couples paint availability to fal's billing state. fal remains correct for models fal
uniquely hosts (patina, Seedance, …).

## Mechanics

- New endpoint/backend switches land **feature-flagged, default matching current behaviour**
  (per the feature-flag rule) and flip only between batches — never mid-batch under
  concurrent agents.
- Keep idempotency guards on every paid step (patina sha-skip, matte freshness) and extend
  them to any new paid call (seed+spec hash on paint).

Related: [[fix-generalizable-rule]] (fix the pipeline, not the run), central
`prefer-local-inference-rule` (this is its per-pipeline application),
[[verify-outputs-rule]].
