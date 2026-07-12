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

## Follow-up — extraction-commit bisect (2026-07-11, $0): PAINT-DRIVEN, not detector-driven

Ran the recommended fall-through step 1. **The originally-planned test (rerun CURRENT
`extract12.py` against the ORIGINAL `794da20e`-batch paints) turned out to be IMPOSSIBLE**: every
one of the 6 templated-passing skins was rerolled to a new seed before its `paint.png` was ever
git-committed (confirmed via `results.json` seed diffs across every intermediate commit + a full
sweep of Drive/`bproof`/`twoimg`/`entire`-checkpoint history — full recovery-attempt log in
[`tools/mask-align-exp/gen12/driftbisect2/README.md`](../../tools/mask-align-exp/gen12/driftbisect2/README.md)).
The true baseline pixels are gone, not merely hard to find.

Substituted the paint-fixed / extractor-swapped twin instead — same evidentiary power, real
data: hold paint fixed at what's on disk TODAY, run both the `794da20e` `extract12.py` (433
lines) and the current one (origin/main, 903 lines; 10 commits of churn since baseline) against
the identical `paint.png`/`mask.png`/`_biref` sprites, using `drift_table()` imported from
`roster_audit.py` unchanged.

| skin | (a) old paint × old extractor | new paint × OLD extractor | (b) new paint × current extractor | extractor-swap Δ | paint-only Δ |
|---|---:|---:|---:|---:|---:|
| fallout-pipboy | 142.7px | 1016.8px | 950.5px | −66.3px | **+874.1px** |
| steam-porthole | 523.2px | 868.6px | 858.3px | −10.3px | **+345.4px** |
| fa-pod (improver, control) | 602.0px | 496.5px | 502.9px | +6.4px | **−105.5px** |

**Verdict: REAL PAINT DRIFT, not a detector artifact.** Swapping ONLY the extractor version
(holding paint fixed) moves drift by −66/−10/+6px — all inside the 150px noise floor established
by this same bisect's Arm A/B/C runs. Swapping ONLY the paint (holding the OLD extractor fixed)
moves it by +874/+345/−105px — 3.5–6× the noise floor, regressors up, the known improver down,
matching the live roster audit's own classification. The 10-commit, 433→903-line extraction
churn since `794da20e` did not regress measurement accuracy — the old extractor actually MISSED
2 controls entirely (template-fallback) on today's paints where the current one caught all 30.

**Implication:** the drift lives in the GENERATIONS themselves getting further from their
authored template layout over the Jul 8→11 window, not in how extract12 measures them. This
bisect already ruled out the BOLD-silhouette clause specifically as the driver — the remaining
open suspects (Vertex-vs-fal serving, seed range, accumulated unrelated prompt edits) are
unbisected. Separately, a real guardrail gap surfaced: paid Vertex outputs are gitignored until
someone manually commits them, so a re-roll can silently destroy the only copy before it's ever
backed up — freeze-on-first-gate-pass would make future bisects a clean git-history diff instead
of a recovery investigation. Full readout, per-control tables, and the fallback-correction
methodology: [`tools/mask-align-exp/gen12/driftbisect2/README.md`](../../tools/mask-align-exp/gen12/driftbisect2/README.md)
+ `driftbisect2/results.json`.

## Follow-up — serving-path bisect (2026-07-11, $2.16): fal→Vertex switch NOT the driver

Tested remaining suspect (a) directly: same current production prompt (`genskin.py` imported
read-only, its real `main()` driven with only the module's `PAINT_VERTEX` attribute toggled per
job), same 2 themes (`fallout-pipboy` + `steam-porthole` — the true regressors this time, per
this doc's own fall-through step 2), same 2 seeds each (571/671, 623/723; 571/623 are the live
production seeds), generated via BOTH serving paths — Vertex direct ($0.24/img 4K, sequential,
429 retry armed, zero 429s) and fal-wrapped `fal-ai/gemini-3-pro-image-preview/edit`
($0.30/img 4K, the pre-switch path that served the low-drift baseline batch). Scored with the
same imported `drift_table()`, same 150px floor, fallback-excluded means. Same seed → same
deterministic conditioning-arm draw, so serving path is the only variable within each pair.

| theme | seed | vertex px | fal px | Δ (v−f) |
|---|---:|---:|---:|---:|
| fallout-pipboy | 571 | 531.2 | 629.1 | −97.9 (noise) |
| fallout-pipboy | 671 | 428.9 | 93.7 | +335.2 |
| steam-porthole | 623 | 529.5 | 718.1 | −188.6 |
| steam-porthole | 723 | 696.8 | 212.2 | +484.6 |
| **pooled (n=4/path)** | | **546.6** | **413.3** | **+133.3 — inside the floor** |

**Verdict: the serving switch is exonerated.** Per-pair deltas point both directions beyond
the floor (the signature of per-gen variance, not a stack effect), the pooled Δ is inside the
floor, and — decisively — the pre-switch fal path does NOT recover the 143px-class baseline
either (413px pooled vs 143px). Suspects narrow to (b) seed ranges / (c) aggregate prompt
additions. New finding for any next bisect: a same-seed same-path re-roll of the live
production config moved drift by 330–420px (vertex-571: 531 fresh vs 950 live; vertex-623:
530 vs 858 — confounded by the post-07-10 tick clauses whose bullets the live prompts lacked,
but bounding per-gen variance either way), so the 150px floor is optimistic for single-gen
comparisons and further arms need n≥4/cell. n=2 seeds/theme/path: directional, not
significance. Full tables + honesty notes:
[`tools/mask-align-exp/gen12/servingbisect/README.md`](../../tools/mask-align-exp/gen12/servingbisect/README.md)
+ `servingbisect/results.json`.
