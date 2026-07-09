# Control-placement invariants (skeuo-ui) — no per-run one-off fixes

Project-local rule for the skin-generation / mask-align pipeline (`tools/mask-align-exp/`,
`src/generate/maskAlign.ts`, the phone9/wild10 players). It exists because two placement
fixes were caught as **one-off patches that didn't generalize** (2026-07-08): a hand-authored
slider-travel span, and a knob-cap offset "fixed" on one run while a CSS collision silently
mis-placed every cap. The through-line: **a placement value must be COMPUTED from the image by
a material-agnostic rule and VERIFIED in the real DOM — never hand-tuned for the run in front
of you, and never trusted from paint-space math alone.**

## 1. Placement values are COMPUTED and material-agnostic, not hand-authored

Any geometric placement datum written into `regions.json` (or emitted by the extractors /
`maskAlign.ts`) — socket seats, drift, slot extents, **slider `travel`** — must be **derived by
the extractor from the paint**, with one code path that works across materials (dark-on-dark
chrome, bright metallic, vivid/lava bodies, light and dark backdrops). A number typed in by
hand to make ONE run look right is the anti-pattern: it silently breaks on the next skin.

- **Never key on an absolute luminance/colour constant** (`mx < 70`, "dark = recess"). The paint
  backdrop is chosen per material brief, and a dark slot is indistinguishable from a dark body or
  dark background by an absolute threshold. Key on **relative** signals: distance from the KNOWN
  backdrop, a percentile floor of the local window, a gradient/rim edge, a bright-rim SPLIT of a
  dark run. (This is why the shipping `maskAlign.ts` seek-groove widening — absolute `mx < 70` —
  will mis-fire on a dark-background/lava skin; the robust adaptive version lives in
  `extract9.py`/`extract10.py`'s `travel` block and should be ported when the pipeline consumes
  seek travel.)
- **Slider travel is a COVERAGE span, not a fit bbox.** The thumb's extremes must visually COVER
  the slot ends: `travel` = the slot's full visual x-extent (dark recess core PLUS its bright
  bezel rim / rounded end-caps), computed by the dark-core + per-side rim-walk-or-margin
  algorithm in the extractors. NEVER the rrect/slot fit bbox (locks onto the raised outer plate
  on a dark groove, onto the inner recess on a rimmed groove — wrong in both directions), and
  NEVER the recess interior alone (thumb stops flush inside the rim → exposed slot crescent, the
  exact reported bug). Err slightly WIDE (coverage-safe), never onto the body. Consumers clamp
  `x0 = travel[0]`, `x1 = travel[1] − thumbW`.
- **Validate a recompute by diffing:** rerun the extractor and diff `regions.json` — ONLY the
  intended field may change (everything else is deterministic from the same inputs). A computed
  span must reproduce the hand-measured target within a few px before you trust it.
- **A socket CENTRE is the matte alpha-hole CENTROID** — geometric, no luminance bias. Do NOT
  use the dark-well luminance centroid (top-light shadow drags it up ~50px) and do NOT trust a
  gradient circle-fit's centre alone (an asymmetric specular arc pulls it toward the bright
  side ~10px — the bal-knob burn). Fit the RADIUS by gradient, snap the CENTRE to the hole
  centroid; it's a no-op when they already agree (vol, magma) and recentres the asymmetric case.
- **A multi-state widget (toggle off/on, any sprite that swaps) must align its STATES by their
  content, not their cut frame.** Independently-cut sprites (BiRefNet islands) trim each state
  slightly differently, so centring the raw cut makes the housing appear to jump between states.
  Place each state by its content (bright-face) centroid so the fixed housing coincides and only
  the moving part (rocker/lever) changes — verify by measuring the rendered box across states.

## 2. Verify placement in the REAL DOM by centre-vs-centre, not paint-space math alone

A blob-centroid or paint-space check passes while the shipped widget is visibly mis-placed,
because the bug can live entirely in **CSS/DOM layout** (a leaked margin, a transform, a
stacking offset) that paint-space never sees. So:

- **Measure the rendered element against its target in the browser:** `getBoundingClientRect`
  centre of the cap/thumb vs the socket/slot centre. That is the check that catches an 8-px cap
  offset a centroid check and a VLM both miss.
- **Close-up crop + drive the real interaction** (drag the thumb to BOTH extremes, view the
  full-res crop) — per the central `verify-rule` §1b two-stage discipline. The VLM cross-check is
  a witness for whole-part errors, never the judge of ±px geometry; adjudicate any VLM claim
  against a deterministic pixel/`getBoundingClientRect` measurement.

## 3. No generic class names inside a positioned widget — namespace them

The knob-cap bug was a page-level `.cap{...;margin-top:8px}` caption rule also matching the
knob's inner `<div class="cap">`. **Inside any positioned widget (`.pknob`, `.pthumb`, `.ptog`,
…), every child class must be namespaced** (`.pknob .cap`, not a bare `.cap`) so a page-level
rule can't reach in and shift it. When you fix such a collision, grep for the generic selector
and confirm no other positioned widget inherits it.

## 4. When you find a placement bug on ONE page/run, sweep ALL siblings

A placement fix is not done until you've checked every sibling that shares the mechanism:
**all runs** (phone9 AND wild10 AND interactive.html), **the generating extractor(s)** (so the
fix is in the computed source, not just the rendered output), and **any in-flight TS port**
(`maskAlign.ts`). "Fixed on run9" while run10 or the extractor still emits the bad value is the
one-off trap this rule exists to kill.

Related (central): `verify-outputs-rule` (look at the real artifact, independent check),
`verify-external-claims-rule` (absence-from-a-proxy), `ai-image-coords-rule` (aspect + noisy
signals), `discover-before-building-rule`. This rule is the placement-specific, project-local
sharpening of all four.
