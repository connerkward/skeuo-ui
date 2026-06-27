---
name: lookdev-auto
description: Tune a visual/animation/render parameter by eye using a VISION or VIDEO model as the judge — render several labeled variants into ONE artifact, ask the model to rate them and suggest better values, render the suggestions, ask it to pick the best, repeat until good. Use whenever "looks/feels right" is the success criterion and there's no cheap numeric metric — animation easing/timing, zoom/camera feel, color grade, layout/spacing, design params, render/encoder settings, prompt params. The model is the eye; you do the rendering and the loop.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Visual eval loop — let a vision/video model tune what only an eye can judge

When the target is "does this LOOK/FEEL right" (not a number you can minimize), a
vision model (image) or video-understanding model (motion/timing) can be the judge in
a tight optimize loop. Worked reference: the `screenstudio-alt` skill (`iteration.py`)
(tuned zoom-animation feel by a video model). **Pick the video judge dynamically — don't
hardcode a model.** When you need it, list the current video-to-text models
(`fal search_models category="video-to-text"` — not `recommend_model`, which returns video
*generators* for a "video" task), see what's available right now, and choose the strongest
reasoning-capable VLM for the job — **biasing slightly toward SOTA** (when close, prefer the
newest-generation / most-capable model; cost is negligible), then run it on the
labeled-variants clip. The best model rotates; decide from the live list at call time.

## The loop

1. **Render N labeled variants into ONE artifact.** Vary the parameter(s) across a
   small spread. **Annotate each variant's params ON the artifact** (burn the label in:
   "A · 2.2Hz · ζ0.5"). Images → a labeled grid/contact sheet. Video/motion → a
   labeled *sequence* (label card or burned-in overlay before/over each clip) so the
   model can compare temporally.
2. **One model call, structured output.** Send the single artifact with an explicit
   rubric (define what "good" means — and what "too much"/"too little" look like).
   Ask for **per-variant ratings + concrete suggested new values as JSON**:
   `{"ratings":{"A":n,...},"best_so_far":"X","suggest":[[p1,p2],...]}`.
3. **Coarse → fine.** Round 1 = wide spread to locate the region. Round 2 = render the
   model's suggestions (+ carry the current best) into one artifact; ask it to **pick
   the single best**. Usually converges in **2 rounds**.
4. **Stop when sufficient** — best rates high and suggestions cluster. Apply the winner.

## Token / quality / step reductions (do these)

- **One artifact per round, not one call per variant.** The biggest saver — a 6-variant
  round is 1 upload + 1 inference, not 6. Montage/grid beats a loop of single calls.
- **Burn params onto the artifact.** The model sees label+result together → no separate
  "variant A used X" context to carry → fewer tokens, fewer mistakes.
- **Structured JSON out + parse.** No re-asking, no free-text wrangling. Prompt "return
  ONLY JSON"; regex the first `{...}`.
- **Short representative sample.** Tune on a 3-5s clip / one frame / one component, not
  the whole asset. Cheaper render, smaller upload, faster inference. Apply the found
  params to the full render once.
- **Cap variants at ~5-6.** More doesn't improve the model's discrimination and multiplies
  render + token cost. Wide-but-sparse round 1, narrow round 2.
- **Calibration anchors.** Include one deliberately-bad and one safe-default variant as
  fixed anchors each round — gives the model a reference scale and exposes when its
  "best" is worse than the safe default (catch a bad recommendation early).
- **Independent rubric, stated up front.** Define "good" concretely in the prompt
  (smooth, subtle settle, not bouncy, not sluggish). Don't ask "which do you like" —
  that lets it echo your framing. A held-out criterion keeps the judge honest
  (see [[verify-outputs-rule]]: the check must be independent of what you tuned).
- **Always leave a free-comment escape hatch — on EVERY video/vision-model query, not
  just tuning loops.** End the prompt with an explicit invite to flag ANYTHING else it
  notices beyond your specific questions: "also, freely comment on anything else that
  seems off, awkward, or could be improved — even if I didn't ask." Your questions only
  encode what you already suspect; the open "what else is wrong?" catches the failure you
  didn't think to ask about (the completeness-critic move). Concrete burn (portfolio-2026
  WARD dither-in reveal): the targeted QA questions all came back clean, but the
  free-comment line is what surfaced one letter ('D') resolving a beat late — a real
  defect the specific questions completely missed.
- **Reuse renders across rounds.** Carry the round-1 winner's clip into round 2 instead
  of re-rendering it.
- **Early-exit.** If round-1 top ≥9/10 and the three suggestions are within a small delta,
  skip round 2.
- **Cheapest judge that can see the failure.** Frames-through an image VLM can judge
  spatial things (layout, color, crop); only reach for a true *video* model when the
  thing being judged is **temporal** (easing, timing, motion smoothness) — those are
  invisible in stills.

## When NOT to use it

- A real numeric metric exists and correlates with quality → optimize that directly;
  don't pay a model per step.
- The judgment is subjective-to-the-user (their taste, brand) → show them the variants
  and let them pick; a model's "best" isn't their best. (This is why the screen-studio
  spring auto-tune was dropped — the model's pick didn't match the owner's eye.)
- One or two variants → just look yourself.

## Caveats (learned)

- The model's pick is an *opinion*, not ground truth — anchor it, and sanity-check the
  winner against the safe default yourself before committing.
- Vision/video models perceive gross differences well, fine ones poorly — keep variant
  spacing perceptible; near-identical variants get noise-rated.
