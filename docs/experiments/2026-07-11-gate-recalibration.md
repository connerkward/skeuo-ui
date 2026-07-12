# Gate recalibration vs human review round 1 — baked-thumb, sprite-fit, orientation (+ art/viz swap-relabel)

**Question.** The 2026-07-11 human review round 1 ([review-2026-07-11-round1.json](../../tools/mask-align-exp/gen12/review-2026-07-11-round1.json)) failed **15/15** skins while the deterministic gate passed 7/15 — which recurring human-named defect classes can be caught deterministically (no VLM), and at what honest recall?

**Method.** For each candidate gate: crop-inspect the named defects on the real `paint.png`s (per-skin slider/switch crops at 3-5x), design a material-agnostic, body/floor-relative metric inside `extract12.py`'s existing machinery, sweep it across the full 15-skin roster's LIVE extraction, and pick thresholds that separate the human-named population from the clean population — reporting overlaps instead of forcing them. Re-run: `python3 extract12.py assets-<skin>` (all 15, $0 — pure re-extraction, no generation spend).

## Gate 1 — baked-thumb-in-groove (`baked-thumb:seek`)

Human named 6/15: claymation, diablo-gothic, fallout-pipboy, fallout-vault, n64-cutscene, wc-goldshield ("baked slider thumb/knob"). The travel walk never visits the slot-cell interior by design and the emptiness gate shrinks the slider bbox 18%/side — a baked thumb passed both.

Metric: on the same smoothed column profile (`med`) the travel walk computes, score every column of the final travel span `(med − Dfloor)/(bodyRef − Dfloor)` (0 = channel floor, 1 = raised body level); largest contiguous run with score > 0.40, after margin-trim + closing. Flag when `0.05 ≤ run_frac ≤ 0.28` and `peak ≥ 1.17`.

| skin | run_frac | peak | flagged | human named | verdict |
|---|---|---|---|---|---|
| claymation | 0.147 | 1.27 | YES | yes | hit |
| fallout-vault | 0.080 | 1.29 | YES | yes | hit |
| fallout-pipboy | 0.119 | 1.54 | YES | yes | hit |
| n64-cutscene | 0.000 | 1.38 | no | yes | **miss** — thumb overlaps the groove END CAP, left of the walked span |
| wc-goldshield | 0.000 | 0.75 | no | yes | **miss** — same end-cap pattern |
| diablo-gothic | 0.516 | 2.56 | no | yes | **miss** — baked handle spans half the groove; indistinguishable by run-length from vario's glow |
| steam-porthole | 0.046 | 1.99 | no | no | true negative (0.05 floor exists for exactly this stepped-recess specular) |
| wmp-vario | 0.440 | 1.16 | no | no | true negative (ambient glow band) |
| wmp-quicksilver | 0.286 | 1.34 | no | no | true negative (0.006 above the 0.28 ceiling — thin margin, watch on future rolls) |
| fa-sky / fa-pod / myst / ps1-crunchy / ps1-wild / n64-prerender | ≤0.042 or peak <1.17 | — | no | no | true negatives |

**Recall 3/6, 0 false positives.** All 3 misses independently FAIL via sprite-fit (below), so skin-level recall of the defect class is 6/6. The end-cap pattern (thumb straddling the groove end, outside the walked span) is a structural blind spot of an in-groove scan; scanning beyond the span would score body-level columns ~1.0 and false-positive everywhere.

## Gate 2 — sprite-vs-slot fit (`sprite-fit:<part>`)

Human named 7/15 switch/slot mismatches + 1 slider-thumb size. Metric: BIREF-cut sprite alpha-bbox (the actual composited pixels) vs detected slot; toggle = symmetric area ratio `min/max`, threshold **< 0.78**; slider thumb = cross-dim ratio, wide bounds [0.55, 6.5] (overhang is legitimate design; roster spans 0.57–4.93 with the one named case mid-pack).

| skin | toggle area-ratio | flagged | human named | verdict |
|---|---|---|---|---|
| wc-goldshield | 0.205 | YES | yes | hit |
| claymation | 0.387 | YES | yes | hit |
| wmp-vario | 0.452 | YES | yes | hit |
| steam-porthole | 0.463 | YES | yes | hit |
| fa-pod | 0.728 | YES | yes | hit |
| n64-cutscene | 0.739 | YES | yes | hit |
| fallout-pipboy | ~0.877 | no | yes | **miss** (skin still FAILs via baked-thumb + drift) |
| diablo-gothic | 0.338 | YES | no* | *human called the switch "a little weird" — treated as soft agreement |
| fallout-vault | 0.562 | YES | no* | *human: "shuffle button failed to work" — plausibly the same defect surfacing |
| ps1-wild | 0.184 | YES | no | over-flag on an already-multiply-failed skin |
| fa-sky 0.87 / ps1-crunchy 0.85 / quicksilver ~0.79+ / n64-prerender 0.99 / myst n/a | — | no | no | true negatives |

**Recall 6/7 named, no clean-skin false positives.** The two populations overlap (ps1-wild 0.18 vs goldshield 0.20) — bbox geometry cannot cleanly separate this roster; several "doesn't match slot" complaints are SHAPE/style mismatches a w×h bbox can't see. Honest partial classifier, not perfect.

## Gate 3 — device orientation (`orientation:device`)

Trigger: n64-prerender-character ("what the fuck is this orientation?"). Investigation: that skin's device-silhouette PCA angle is **86.5°** — NOT tilted; the complaint traces to a control-substitution defect (toggle sprite in the `next` button slot) that missing/state-align/emptiness/guide-ring already catch. **This gate does not reproduce that human catch** — the semantic layout check belongs to the VLM lane ([2026-07-11-verification-recalibration.md](./2026-07-11-verification-recalibration.md)).

It does catch a real, different failure found during investigation: **ps1-wild** is painted as a rotated 3/4 side-profile vehicle (43.1° off vertical) vs the roster's healthy ceiling of 11.7° (claymation) — >3x margin. Threshold 30°, gated on silhouette elongation ≥ 1.15.

| skin | off-vertical | flagged |
|---|---|---|
| ps1-wild | 43.1° | YES ("absulute falire" — agrees) |
| claymation | 11.7° | no (worst clean) |
| all others | ≤ 7.1° | no |

## Addition — art/viz SWAP-RELABEL (coordinator scope add, fallout-pipboy seed 951)

Deterministic fallback in extract12 after region-refit: when `album_art`/`visualizer` are both detected and their vertical order is inverted vs the template's declared arrangement, swap their identities (they're interchangeable display glass) — guarded by **mutual-nearest** (each detected window closer to the OTHER's template slot), else left for the drift gate. Logged as `art_viz_swapped` in regions.json.

**Validation on seed 951 ($0 re-extract): the guard correctly DECLINES, and the predicted drift collapse does not hold.** Numbers: detected art centre (0.666, 0.574), viz (0.668, 0.310); template art (0.5, 0.0975), viz (0.5, 0.27). Order IS inverted, but viz's detected window is nearest its OWN slot (0.172 vs 0.271) — mutual-nearest fails. Force-swapping would move album_art 1807.8→~877px but visualizer 413.8→~1191px; mean drift 925.7→~910px, still far over the 650px threshold, because ALL 10 controls drift 500–1250px (whole-layout rearrangement, not a label swap). Seed 951's dominant defect is global layout drift; the drift gate correctly holds it. No correctly-stacked skin triggers the swap (fa-pod, ps1-crunchy, steam-porthole, wc-goldshield, wmp-quicksilver: order-inverted = False; live logs show no swap lines).

## Roster outcome (gate vs human, post-recalibration)

Gate now FAILs **12/15** (was 7/15 passing) vs human 15/15. Remaining disagreements — the three gate-PASSes:

- **ps1-crunchy** — human: "visualizer not working" (player bug, not paint), "slider css too far left" (render-side travel consumption). Closest to a legitimate PASS.
- **fa-sky** — human: button depression silhouette mismatch, phantom play button, slider CSS overshoot. Silhouette/CSS-alignment classes, not covered by any deterministic paint gate yet.
- **myst-arcanum** — human: "all completely wrong" (semantic placement). Needs the VLM lane.

**Verdict (agent, human-named cases as ground truth).** The three defect classes worth deterministic gates are now gated with stated recall; the residual human-complaint classes (button-depression silhouette match, CSS-vs-sprite alignment in the shipped player, semantic layout sanity) are render-side or semantic and belong to the player-DOM measurement + VLM recalibration lanes, not paint-space extraction.

Method/spend: extraction-only, local, $0. Models: none (pure numpy/scipy geometry). Source: `tools/mask-align-exp/gen12/extract12.py` (this commit).
