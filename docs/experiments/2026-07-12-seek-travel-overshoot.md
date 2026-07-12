# 2026-07-12 — seek slider: `travel` double-padding overshoots the visual groove

## Question

Recurring, cross-roster human review complaint on the gen12 seek slider: "CSS slider
outside slot" / "css goes outisde the bounds of slider slot (this is consistent" /
"CSS OUTISDE SLOT FOR SLIDER!!!" — reported on claymation, diablo-gothic, fallout-vault
(both sides), n64-cutscene, ps1-crunchy, across round1 (2026-07-11), round2, and round3
(2026-07-12) reviews. A same-day prior fix
([`2026-07-12-extract12-hitbox-and-travel-fixes.md`](./2026-07-12-extract12-hitbox-and-travel-fixes.md))
already hardened the extractor's outward WALK (saturated-walk distrust, direction-
agnostic body reference, progressive local-window widening) and reduced measured
overshoot on some skins (ps1-crunchy 44px→8px, wmp-vario 88px→0). The complaint
persisted into round3 regardless. Was the walk still wrong, or is there a second bug
downstream of it?

## Method

1. Read `regions.json`'s `seek` entry for all 5 flagged skins; compared `travel` against
   `device` (the walked groove rect the extractor itself already computes).
2. Built a static diagnostic overlay (device=yellow, maskDevice=cyan, travel=red) on
   crops of `paint.png` for each flagged skin to sanity-check the numbers against the
   real painted groove.
3. Served the actual shipped `player.html` (not a reimplementation) via
   `~/dev/central/scripts/serve`, drove `window.__seek()` to both travel extremes in
   headless Playwright, and measured `.pthumb` / `.pseek-track` / `.pseek-fill`
   `getBoundingClientRect()` against the device rect converted to the same CSS-px space
   (accounting for the vertical `/DF` crop-fraction the player itself uses).
4. Cropped and visually inspected the rendered screenshots at the groove's rounded
   end-caps (fallout-vault, both ends) against the pre-fix baseline.

## Root cause

`extract12.py`'s seek-groove block computes `device` (`lo..hi`) as the outward-walked
"coverage span" beyond the model's own declared mask cell (`mx0..mx1`) — already an
intentional "err wide" widening, up to 12% of the mask-cell width per side, per
[[placement-invariants-rule]] §1. On top of that, it then computed:

```python
M = int((hi - lo) * 0.02)
tvv = [round(max(0, lo - M) / _W, 5), round(min(_W, hi + M) / _W, 5)]
```

— a SECOND, unconditional +2%-of-span pad, applied uniformly regardless of material or
how much the walk had already widened. `build_player.py` then positioned the thumb's
OUTER edges (`x0=tv[0]`, `x1=tv[1]-tw`) and — for the newly-added seek-track/fill CSS
overlay (`pseek-track`/`pseek-fill`, same-day feature) — the ENTIRE visible bar
(`left=tv[0]`, `width=tv[1]-tv[0]`) to reach exactly `travel`'s bounds, with **no clamp
against `device`** anywhere in the consumer.

Measured on the shipped fallout-vault player (real runtime, not a reimplementation):
at `val=1` the thumb's rendered right edge landed **~11px (2.4% of a 460px-wide
render)** past the true visual channel edge — of which `device` alone (no pad) already
accounted for ~6.5px (1.4%), and the `M` pad added the remaining ~4.5px on top. Two
independent widenings stacked: the prior same-day fix addressed the first (the walk);
nothing had addressed the second (the fixed +2% pad) or added a consumer-side floor —
which is why the complaint survived that fix into round2/round3, and predates the
track/fill overlay (round1 already said "css slider bar too far left. too far right
also," before that overlay existed) — ruling out the overlay as the sole cause.

## Fix

1. **`extract12.py`**: drop the `M` pad. `travel = [lo/_W, hi/_W]` exactly — the walked/
   device span, no further widening. One line, material-agnostic (the removed pad was
   never material-aware to begin with — always a flat +2% of span).
2. **`build_player.py`**: hard-clamp `travel` to `device`'s own extent
   (`tv = [max(travel[0], trackLo), min(travel[1], trackHi)]`) at the single point both
   the thumb and the `pseek-track`/`pseek-fill` overlay read `tv` from. This is a
   defense-in-depth invariant, not just a mirror of fix #1 — it protects any
   already-baked `regions.json` on disk (not yet re-extracted) and any future extractor
   regression, uniformly, for every consumer of `tv` in one place.

## Verification (before → after, real shipped `player.html`, Playwright `getBoundingClientRect`)

`travel` vs `device` overshoot, all 5 flagged skins, read directly from `regions.json`
after re-extraction:

| skin | axis | device span (norm) | travel before | travel after | overshoot before | overshoot after |
|---|---|---|---|---|---|---|
| diablo-gothic | vertical | [0.28637, 0.61638] | [0.2799, 0.62284] | [0.28637, 0.61638] | ~24px / 3712px tall (~0.6%) | **0px** |
| fallout-vault | horizontal | [0.34332, 0.86849] | [0.3329, 0.87891] | [0.34332, 0.86849] | ~11px / 460px wide (2.4%, real-runtime measured) | **0px** |
| n64-cutscene | horizontal | [0.18490, 0.65321] | [0.17578, 0.66233] | [0.18490, 0.65321] | ~4.2px / 460px (0.9%) | **0px** |
| ps1-crunchy | horizontal | [0.12283, 0.56337] | [0.11415, 0.57205] | [0.12283, 0.56337] | ~4px / 460px (0.9%) | **0px** |
| claymation | horizontal | [0.44010, 0.80122] | [0.43316, 0.80816] | [0.44010, 0.80122] | ~3.2px / 460px (0.7%) | **0px** |

Extractor's own `gate.seek_cov` metric (`travel span / device extent`, 1.0 = exact
match) independently confirms this: **1.039–1.04 → 1.0 exactly, all 5 skins.**

Real-runtime re-check (Playwright, actual `player.html`, not a reimplementation):
drove `.pthumb` to both extremes on all 5 skins via `window.__seek()` and compared its
`getBoundingClientRect()` to `device`'s own px bounds in the same phone-viewport space
(dividing by `devFrac` for the vertical case, matching the player's own math). All 5:
thumb edges land on `device`'s bounds within ≤0.15px (float/CSS `aspect-ratio` rounding
noise) at both `val=0` and `val=1` — zero measurable overshoot. Visual re-check on
fallout-vault (the worst pre-fix case, "both sides" flagged): the seek-track/fill bar
that previously punched visibly past the groove's right rounded end-cap onto the raised
latch bracket now terminates cleanly inside the recess at both extremes (screenshots
inspected at 4x crop, both ends).

Diff-validated per [[placement-invariants-rule]]: re-extracting diablo-gothic and
fallout-vault against a saved pre-fix `regions.json` changed only
`regions.seek.travel[0]`, `regions.seek.travel[1]`, and the derived `gate.seek_cov` —
no other field moved (a `toggle_track: null→false` diff in both is unrelated pre-
existing drift from a same-day toggle-track feature landing in `extract12.py` before
this session, orthogonal to the seek fix and outside this task's SEEK-only lane).

## Decision

Shipped both fixes in the shared pipeline (`extract12.py` + `build_player.py`, per
[[fix-generalizable-rule]] — no per-skin edits). Re-extracted + rebuilt all 5 flagged
skins ($0, existing paint, per [[generation-spend-rule]] — this was an extractor/
consumer-side defect, not a paint defect). Toggle/switch subsystem intentionally
untouched (owned by a concurrent agent in this worktree).
