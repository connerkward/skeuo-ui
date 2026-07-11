# 2026-07-11 — Drift-clause bisect: is the BOLD-silhouette clause driving template drift?

## Question

The roster template-adherence audit (`tools/mask-align-exp/gen12/twoimg/roster_audit.json`,
2026-07-11) measured 4/6 templated-passing skins with MORE drift than the original 14-skin
batch (`794da20e`) — worst `fallout-pipboy` 143→950px mean. The knobticks re-crop
independently measured every gen's knob displaced ≥1.4 knob-radii. Suspect #1 by intuition:
the "you are FREE and STRONGLY ENCOURAGED to sculpt a BOLD, DISTINCTIVE… ONLY the control
positions stay fixed" housing-freedom clause in `genskin.py`'s templated prompt. But the
design note (`docs/design/2026-07-11-think-about-notes.md` §3) verified via `git log -S`
that this clause's wording is UNCHANGED since the low-drift baseline batch — so the bisect
must isolate the clause from the other things that DID change (random solid/outline
conditioning-arm draw `8d580b74`, mask-cell-overlap cut rewrite `ac28cd74`, display-region
refit `86f69c75`, button-recolor fix `a8bbaad0`), not assume it guilty.

## Method

Self-contained harness `tools/mask-align-exp/gen12/driftbisect/` (pattern: `abshape/`,
`twoimg/`); mainline `genskin.py`/`extract12.py`/`roster_audit.py` untouched —
`genskin_bisect.py` imports genskin.py's canvas/constants/edit_vertex read-only and builds
its own prompt; `score_bisect.py` imports roster_audit.py's `drift_table()` so the metric
is the same CODE, not a reimplementation. Arm A's assembled prompt was verified
**byte-identical** to mainline genskin.py's output (same spec, conditioning=solid) before
any spend.

- **Arm A** — production templated prompt verbatim (bold clause present). Baseline.
- **Arm B** — bold clause REPLACED with a neutral keep-the-housing-close-to-the-placeholder
  instruction (conservative locked silhouette).
- **Arm C** — bold clause KEPT verbatim + appended hard numeric position-lock ("every
  control's CENTRE must land within 2% of the device's width/height of its guide's centre;
  reshape AROUND the guides, never THROUGH them").
- **Conditioning FORCED 'solid'** for every gen in every arm — the mainline
  `pick_blueprint_arm()` random draw (and twoimg) are bypassed so arm-style isn't a
  confound layered on the clause test.
- Matrix: 2 themes (`wc-goldshield` seeds 736/841, `fa-pod` seeds 673/918) × 3 arms = 12
  gens. `gemini-3-pro-image-preview` via Vertex AI (muser-2605300220, global), 4K, 5:4.
- Pipeline per gen: extract12 pass1 → local BiRefNet_HR@2048 matte (MPS, $0) → extract12
  pass2 → gates + `drift_table()` scoring.
- **Metric:** `mean_drift_px` = mean over controls of |authored template centre −
  extract12-detected device centre| on the paint's own ~2300×3712 grid — identical to the
  roster audit's number.
- **Noise floor: 150px** — the audit's own ±82–99px opposite-direction swings on an
  unchanged pipeline mean anything under ~100–150px is indistinguishable from run-to-run
  variance; decision rule requires Δ > +150px vs A on BOTH themes.
- Cost: 12 kept gens × $0.24 + 1 unbilled 429 retry ≈ **$2.88** (matte + scoring $0 local).

## Results

Artifacts (12 paints/blueprints/masks, labeled drift overlays, per-control tables):
`tools/mask-align-exp/gen12/driftbisect/results.html` (+ `bisect_scores.json`).

| arm | pooled mean (n=4) | wc-goldshield (736/841) | fa-pod (673/918) | Δ vs A per theme |
|---|---|---|---|---|
| A production | 485.2px | 392.3 / 483.5 | 570.5 / 494.5 | — |
| B clause removed | 496.1px | 744.3 / 635.8 | 266.8 / 337.6 | wc **−252** (worse), fa-pod **+230** (better) |
| C clause + lock | 629.3px | 550.2 / 630.1 | 603.1 / 733.7 | wc −152, fa-pod −136 (both worse) |

- **Neither B nor C clears the +150px floor on both themes.** B is a clean MIXED result —
  consistent within each theme across both seeds, opposite between themes. C is worse than
  A everywhere (at/below floor).
- **The clause DOES control silhouette boldness** (verified by eye on the real paints: B's
  housings are a plain shield / plain capsule vs A's ornate winged forms) — it just doesn't
  control drift monotonically. wc-goldshield's conservative B gens *rearranged the control
  layout* (5 buttons collapsed to one row) more than the bold A gens did.
- **Baseline validity:** A's means (392–570px) reproduce the live roster audit's values
  (wc 462, fa-pod 503) under FORCED solid conditioning — today's drift level is
  reproducible without the random arm-draw, so the arm-draw alone isn't the driver either.
- Gates: 3/12 gate-PASS (wc-a-841, wc-c-841, fa-pod-b-918) — normal single-roll rate;
  drift metric doesn't require gate-pass. fa-pod-a-673 tripped the gross-leak gate
  (0.87%, guide-hue rings on all five buttons).

## Conclusion (agent)

**The bold-silhouette clause is NOT confirmed as the drift driver; no prompt change ships
from this result.** Per the design note's decision rule, a mixed result (helps one theme,
hurts the other, both beyond the floor in opposite directions) means a theme-specific
confound rather than a clean clause effect — and the strengthened numeric position-lock
(C) bought nothing, consistent with `2026-07-10-bproof-constraint-load.md`'s finding that
piling constraint text on has diminishing/negative returns.

Recommended fall-through (both $0-first):
1. Re-run CURRENT extract12 against the ORIGINAL baseline-batch paints (`794da20e`) —
   separates "the paint drifts more now" from "the detector measures differently now"
   (extraction commits `ac28cd74`/`86f69c75`/`a8bbaad0` are unbisected suspects). Zero new
   generations.
2. If extraction is clean, repeat this bisect on the two actual worst regressors
   (`fallout-pipboy`, `steam-porthole`) — this run used wc-goldshield/fa-pod (per task
   spec), which are the audit's two IMPROVERS; a clause effect confined to the regressing
   themes would be invisible here.

n=2 seeds/theme/arm against a ±150px noise floor: directional evidence, not significance.

## Human verdict

**PENDING** — awaiting human review of `results.html`.
