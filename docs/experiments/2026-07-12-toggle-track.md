# 2026-07-12 — shuffle TWO-STATE SPRITE-SWAP → TWO-DETENT TRACK SLIDER

## Question

The shuffle toggle's two-state sprite-swap architecture (paint a mirror-opposite OFF/ON
pair, extract each into its own strip cell, silhouette-register ON onto OFF, click swaps
the sprite) was the single most-named defect class in `review-2026-07-11-round1.json`:
switch/slot size or shape mismatch appeared on 8+/14 reviewed skins (fa-pod "switch isnt
scaled to slot, too small"; steam-porthole "slot and switch dont match"; n64-cutscene
"siwtch doesnt match slot"; wc-goldshield "fun switch but doesnt match slot"; wmp-vario
"siwtch doesnt match slot"; claymation "switch doesnt fit slot"; fa-sky/fallout-pipboy/
fallout-vault also named switch problems). The COVER-fit render patch
(`docs/experiments/2026-07-11-toggle-cover-fit.md`) helped the RENDER side but the root
cause — asking the model to paint two matched, mirror-symmetric, same-silhouette states —
stayed unaddressed.

**User's hypothesis (approved, refined into this experiment):** replace the two-state
mirror-pair with a **two-detent SLIDER** — architecturally identical to the already-robust
seek groove (an empty recessed track + a single loose thumb/lever, coverage-span extracted,
detent positions instead of continuous travel). Does killing the mirror-pair constraint
(the thing the model was visibly failing at) fix the switch/slot mismatch, the same way the
seek groove's "empty channel + separate thumb" contract has been reliable?

## Method

**Pipeline change** (`tools/mask-align-exp/gen12/`, flag `TOGGLE_TRACK_ENABLED` in
`genskin.py`, default `True`; full rollback path kept intact behind `False`):

- `genskin.py` — the shuffle slot becomes a painted EMPTY TRACK/HOUSING (any physical
  two-position mechanism whose moving part travels a short track — lever slot, sliding bolt
  channel, valve track — painted empty; the moving part appears ONLY in the strip, as ONE
  loose cell instead of two mirror-paired states). All mirror/same-silhouette-state language
  deleted. Strip drops from 4 cells to 3 (vol cap, seek thumb, shuffle lever).
- `extract12.py` — detects the shuffle TRACK using the same coverage-span walk algorithm
  already proven on the seek groove (parametrized for a short track, vertical or
  horizontal), emitting `regions.json`'s `shuffle: {device, track, detents:[p0,p1],
  vertical}` in place of the old `stateAlign` two-state registration.
- `biref12.py` — cuts ONE lever cell (`shuffle_lever.png`) instead of two
  (`shuffle_off.png`/`shuffle_on.png`), keyed off the strip-cell COUNT in `regions.json` so
  it reads either contract correctly regardless of which genskin.py flag state produced it.
- `build_player.py` — renders the lever sprite riding the track; click/Enter/Space slides it
  to the other detent with a CSS ease (~200ms, snap cubic-bezier); the active (ON) detent
  gets a subtle drop-shadow glow from the director's `css.glow` (falling back to
  `css.accent`), same engraved register as the knob ticks. **CSS-lever fallback**: when the
  biref cut is missing or has a degenerate aspect ratio (a mis-cut sliver), a themed CSS
  lever (director `css.fill`) renders instead of silently dropping the control —
  deterministic floor regardless of cut quality.

**Validation gens** (per coordinator directive, expanded from the original 3-gen plan to
the full protocol): 4-6 gens across 2 themes (2 templated + 1 re-gen of a switch-complaint
theme from the round1 list), sequential Vertex calls (429-retry), ~$1.5 budget. Compares
against the review round's own baseline numbers (8+/14 switch-mismatch complaints, and the
old sprite-fit:shuffle gate's measured pass rate) rather than a fresh same-seed control arm
— the architecture change is a full prompt/contract rewrite, not a clause tweak, so a
same-seed A/B isn't meaningful (the two arms produce structurally different strip contents).

**Metrics measured per gen:**
1. **Bake rate** — did the model paint a lever INTO the track (the analogous defect to the
   seek groove's baked-thumb problem), vs the historical baked-thumb/state rates.
2. **Lever-to-track fit** — the sprite-fit metric (does the extracted lever visually seat
   within/along its track), vs the review round's measured switch/slot mismatch rate.
3. **Track-detection success rate** — did `extract12.py`'s track walk find a sane
   `track`/`detents` span (not a collapse-to-fit-bbox fallback).

## Results

5 gens (Vertex `gemini-3-pro-image-preview` 4K, sequential, 429-retry, ~$1.20 paint +
~$0.15 erase12 model edits + $0 local BiRefNet ≈ **$1.35 total**). Every claim below is
from direct full-res crop inspection of the real paint + driving the real served player
(Playwright, headless), not metrics alone.

| gen | mode | seed | track detected | lever cut | baked lever? | gate reasons (final) | player driven |
|---|---|---|---|---|---|---|---|
| fa-pod-tt1 | templated | 673 | ✓ vertical, detents [.613,.710] | global matte MISSED it → **recovered** via new cell-crop local matte | **YES** (bottom of track) → erase12 `--control shuffle` model+floor_darken, re-detect clean, emptiness ok after | biref-parts (seek mask cell degenerate — mask defect), guide-ring ×5 (bad roll) | ✓ slides 79.6→92.6%, mid-anim captured, glow `#228aff` follows state |
| fa-pod-tt2 | templated | 1451 | ✓ vertical, [.652,.725] | ✓ direct island match (93% cell overlap) | no (empty=ok) | guide-ring:repeat only | ✓ click + **Enter key** toggle + glow |
| fa-pod-tt3 | templated | 2287 | ✓ vertical, [.499,.594] | cut exists but is a track-housing-shaped pill (model conflated lever with housing) | **YES** (bar mid-track, emptiness FAIL) | emptiness + silhouette-mismatch:prev,queue (**new silcheck gate firing live in orchestrate**) | ✓ slides 59.8→72.4% + glow |
| clay-tt1 | templateless | 662 | ✓ vertical, [.637,.703] | ✓ characterful clay handle — but painted HORIZONTAL for a vertical track | **no — track painted perfectly empty** | guide-ring:next + sprite-fit:shuffle (lever cross-ratio 6.6 > 6.5 — correctly flagged) | ✓ slides + director cream glow (lever renders small, flagged for re-roll) |
| clay-tt2 | templateless | 1901 | ✓ **horizontal**, [.629,.768] | ✓ cut | **YES** (clay lever at right end) → erase12 model edit, re-detect clean | **GATE PASS, reasons=none** (post-erase — the batch's first full pass) | ✓ horizontal slide 53.3→68.0% + glow |

**Metric 1 — bake rate: 3/5 levers baked into the track.** Same defect class and similar
rate to the baked-seek-thumb problem (6/15 in review round1) — the empty-cavity clause does
not reliably beat the model's slider prior for tracks either. erase12 backstops it: run on
2 of the 3 (fa-pod-tt1, clay-tt2), both erased clean (verify crops in each assets dir's
`erase-verify/`), emptiness gate re-passes after. This mirrors exactly the bproof lesson
that led to erase12 for seek: detect+erase post-hoc, don't out-word the model.

**Metric 2 — lever/track fit: the mirror-pair defect class is GONE by construction.** No
state pair exists to mis-scale or mis-mirror. The residual fit failure is one-dimensional
(lever cross-dim vs track cross-dim, clay-tt1's 6.6 ratio) and the new lever-cross
sprite-fit gate catches it. Compare: the review round's 8+/14 switch/slot mismatch class
required silhouette-IoU state registration plus COVER-fit patches and still failed reviews.

**Metric 3 — track detection: 5/5**, spanning vertical AND horizontal tracks, templated AND
templateless modes, on the first attempt each (no collapse-guard or clamp-saturation
fallbacks fired).

**Collateral finds (shipped):**
- BiRefNet's GLOBAL matte drops small isolated strip parts entirely (fa-pod-tt1's lever
  region: zero alpha). Ported knobup/recover_caps.py's cell-crop local-matte fallback into
  `biref12.py` as a general unmatched-part recovery — fixed the lever on tt1 AND a missed
  vol cap on tt2, $0 (local MPS).
- genskin.py now passes the director `css` block through results.json (build_player's
  `RES.get("css")` previously only resolved via a `theme_specs/<SID>.json` file, which
  suffixed experiment/re-roll ids don't have) — the glow verification exposed this.
- CSS-lever fallback verified live on a synthetic missing-cut fixture (themed CSS lever
  renders, slides, glows — deterministic floor).
- Legacy regression: wc-goldshield re-extracted with zero region diffs and an identical
  gate; its legacy two-state player still swaps sprites (driven live).

## Decision

**TOGGLE_TRACK_ENABLED stays ON (the new default architecture).** The two failure modes it
was designed to kill (mirror-pair silhouette mismatch, state-pair registration) did not
appear in any of the 5 gens because they cannot exist under this contract. The dominant
residual defect (baked lever, 3/5) is the SAME class as the known baked-seek-thumb problem
and shares its proven mitigation (erase12) — a candidate for wiring into orchestrate12 as an
automatic post-gen repair pass, tracked in TODO.md. The lever/housing conflation (tt3) and
axis mismatch (clay-tt1) are prompt-tuning follow-ups; both are gated deterministically in
the meantime.
