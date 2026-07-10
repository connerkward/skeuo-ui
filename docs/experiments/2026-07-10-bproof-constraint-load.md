# B-proof — does gen12's heavy constraint load degrade painted-skin quality? (2026-07-10)

## Question

gen12's shipping paint prompt (`genskin.py`) is ~9,000–11,000 characters of hard pipeline
constraints (empty knob/seek/toggle cavities, zero-residue guide erasure, exact-fit sprite-strip
parts, a pixel-aligned region-mask column, top-down-flat camera rules for loose parts, …), all
necessary for a *runtime-usable* skin (the app seats real controls into those cavities and cuts
sprites from the strip). Does that constraint load cost visible paint quality relative to a
short, unconstrained prompt asking for the same subject — and does the answer generalize past
the 2 themes the pivot decision was originally weighed on? Round 2 adds a second question: does
quality degrade **linearly** with constraint length, or **fall off a cliff** past some threshold
(round 1 only had 2 points on the curve — light and heavy — which can't tell linear from cliff).

This determines whether to adopt the B-pivot: **beautiful-render-first, detect-second**
architecture (paint freely, recover control geometry from the finished art via VLM/SAM/detector,
give up guaranteed-empty-cavity/exact-fit correctness) vs. keep the current constrained,
pipeline-first single-pass generation.

## Method

**Round 1 (2 themes, steam-porthole + diablo-gothic):** one A/B pair per theme — the REAL
shipped gen12 pipeline artifact ("heavy", ~9,016–9,161 chars, two-column blueprint+mask input,
`fal-ai/gemini-3-pro-image-preview/edit` via fal) vs. one new "froggo-style" generation (~600–620
chars, flat pale-grey canvas input, same theme text verbatim, same seed as gen12's final passing
roll). fal's account was exhausted mid-round, so the light-tier rolls went through Vertex AI
directly (`gemini-3-pro-image-preview`, same base model, `global` endpoint) instead of fal's
proxy — confound noted below.

**Round 1 scale-up (4 more themes: fa-pod, fallout-vault, wc-goldshield, claymation):** same
design, same light-prompt template, same per-theme seed as each theme's real gen12 `final_seed`
(from `assets-<id>/orch.json`), all via Vertex (fal still locked — confirmed live with a probe
call, `"User is locked. Reason: Exhausted balance."`). Script: `run_bproof_extra.py`.

**Round 2 (3-tier prompt-load ramp, 3 themes x 3 tiers x 1 seed = 9 renders):** tests linear-vs-
cliff. Design choice: **all 3 tiers use the SAME single flat-canvas, single-panel format**
(unlike round 1's "heavy" condition, which was the real two-column pipeline artifact) — this
holds input/output format constant so prompt length is the only variable, at the cost of the
heavy tier here not being the literal ~9-11k-char shipping prompt (that prompt asks for a
structurally different two-column blueprint+mask task; reusing it would reintroduce round 1's
format confound instead of isolating constraint-length). Tiers, built by literally layering real
clauses lifted from `genskin.py`'s shipping prompt (not paraphrased):
- **light** (~600-640 chars): roster stated once, zero pipeline constraints (same template as
  round 1).
- **medium** (~2,060-2,100 chars): light + the real EMPTY-CAVITY rule (knob/seek/toggle) + the
  real BLANK-SCREENS rule + the real SEEK-IS-A-SLOT-ONLY rule.
- **heavy** (~3,555-3,590 chars): medium + the real embossed-button-relief rule (with the actual
  per-icon roster via `genskin.ICON`) + the real full NO-TEXT rule + a closing reinforcement
  paragraph (pass/fail restated, "err toward more empty/bare").
Themes: steam-porthole and diablo-gothic **at fresh seeds** (284, 310 — different from round 1's
84, 110, to test seed-sensitivity of any effect) + wmp-quicksilver (a theme not yet in bproof) at
seed 405. All via Vertex AI, same endpoint as the round-1 extension. Script:
`run_bproof_round2.py`. New spend: 9 x ~$0.24 ~= $2.16.

Crop pairs (buttons / knob / slider / screen) for the 6-theme round-1 grid are generated
generically from each theme's real `regions.json` control bboxes (`build_assets2.py`) — union
box per control group, padded, mapped onto both the gen12 device crop and the froggo render.
**Caught and fixed during this session:** `regions.json`'s `"device"` fractional boxes are
normalized against the FULL `paint.png` canvas height, not the devFrac-cropped device image's own
height (confirmed by reading `extract12.py`'s `GH, GW = paintg.shape` against `paint.png`, not a
crop) — the first pass silently shifted every crop up by ~1/3 of the image (a "knob" crop landed
on the play/pause button). Fixed in `build_assets2.py`; all 48 crop files regenerated and
re-inspected at full res before use, per verify-outputs-rule.

## Candidates / models

- `fal-ai/gemini-3-pro-image-preview/edit` (round-1 gen12 heavy condition, via fal) — the shipped
  pipeline artifact for steam-porthole and diablo-gothic, pre-existing, no new spend.
- `gemini-3-pro-image-preview` (Vertex AI, `global` endpoint; same base model fal proxies) — every
  new render in this experiment: round-1's 6 light-tier themes + round-2's 9 tiered renders.
  Total new spend this session: 4 x ~$0.24 (round-1 scale-up) + 9 x ~$0.24 (round 2) = ~$3.12.

## Observations

**Round 1 (6 themes, light vs. heavy):** the light-prompt render is visibly richer than the
matched gen12 heavy render on **every** theme inspected at full res and in close-up crops (buttons
/ knob / slider / screen) — real material variation (patina, wear, specular breakup), more
volumetric lighting, higher perceived production value. The gap holds even on surfaces both
conditions were free to render (button facets, body panels) — gen12's paint reads flatter and
more "clean illustration"; the light-prompt paint reads as photographed. Confounds carried over
from round 1's original 2-theme write-up still apply to the other 4: serving path (fal vs.
Vertex — same published model, seed-to-RNG mapping not proven identical across stacks), pixel
budget (gen12's device shares a two-column 4K canvas ~6.4MP vs. froggo's whole-canvas ~17MP), and
layout freedom (froggo is not pipeline-usable — installed knob/thumb/toggle, populated screens).

**Round 2 (linear vs. cliff, pending human review):** [fill in after visual inspection of the
9 renders — does light->medium->heavy read as a smooth gradient of quality loss, or does most of
the drop happen in one jump?]

## Human verdict

**PENDING — lookbook served for evaluation.** See `bproof/index.html`.

Decision this evidence feeds: adopt beautiful-render-first/detect-second (the B-pivot) vs. keep
the constrained single-pass pipeline. Not yet recorded in `docs/DECISIONS.md` — only add that
entry once the human has decided.
