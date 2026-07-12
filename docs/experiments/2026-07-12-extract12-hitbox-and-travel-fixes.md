# 2026-07-12 — extract12: exclusive blob→key assignment + seek-walk saturation distrust

## Question

Review round `review-2026-07-11-round1.json` (15/15 FAIL) named two extractor defect
classes: (1) button hitboxes landing on the WRONG control entirely (wmp-quicksilver
"prev button… failed to work" — prev's hitbox sat on the seek groove, playpause's on the
volume knob; fallout-vault "prev button, shuffle button, failed to work"; myst-arcanum
"all completley wrong"), and (2) seek slider CSS travel over/undershooting the painted
groove ("css slider bar too far left. too far right also" — wmp-vario; "slider css too
far left" — ps1-crunchy; "slider css too long" — steam-porthole). Paint-side or
extract-side?

## Root causes (all extract-side, in `tools/mask-align-exp/gen12/extract12.py`)

**1. Per-pixel nearest-key argmin mis-assigns whole controls.** `mask.png` is not flat
key-colour fills — genskin's guide render bakes shading on top (measured: quicksilver
playpause key (255,255,0) painted ~(249,224,71), 78px euclidean from its own key). A
shading-drifted blob can land *closer to a different control's key* than its own; the
per-pixel argmin then merges two distinct, non-touching blobs under one index and
`largest_cc_bbox` coin-flips which wins. Quicksilver: playpause+vol both keyed
"playpause" (107,888 vs 102,150 px — the WRONG one won); prev/next/repeat/shuffle/vol
had ZERO pixels under their own keys. Fix: connected-component segmentation of the
device band + greedy EXCLUSIVE blob↔key matching on blob-median colour, with two
bounded tie-breaks: role-size consistency (same-skin buttons are near-identically
sized: 97,591–98,522 px on myst; the disputed blob 98,192) and role-shape consistency
(slider/toggle housings are elongated ≥1.8, buttons ~1.0 — a circular blob can never
be a groove). Strip band keeps the old path (toggle needs two cells under one key).

**2. `snap_to_paint` unbounded X-recentre.** On weathered bodies the "vivid pixel"
test finds decorative trim next to the icon (fallout-vault: rust/gold strip left of
prev/repeat, sel.mean 0.40–0.48) and dragged the box a full button-width off. The raw
mask position was already dead-on (visual crop). Capped to ±20% of button width.

**3. Knob-derived "global drift" blindly overwrote button positions.** The drift
sample comes only from knob circle-fits (quicksilver: vol's −37px offset → −1.61%
canvas-wide), then overwrote every button's already-snapped device with
maskDevice+drift. Buttons excluded now; slider/toggle/regions keep it (each has its
own downstream local refit that self-corrects).

**4. Seek-walk `_body` reference wrong-signed for dark bodies.** The flank-plateau
filter `fl > backdrop+25` assumes the body is BRIGHTER than the backdrop; ps1-crunchy's
chassis (~40–100) on the light canvas (235) never passed, so `_body` fell back to a
whole-row percentile blending groove+body+backdrop — too permissive, walk rode 44px
past the declared cell. Replaced with backdrop-colour-distance (`cdist > 30`), which is
direction-agnostic. Plus: progressive local-window widening (2×/3×/5× fw) before the
whole-row fallback (wmp-vario: the volume knob's glow inside the search window inflated
the whole-row reference to 197 vs the slot's ~85 local material), and a wider
recessed-vs-body margin (0.22→0.35) for bevel-fillet shading bounce (steam-porthole).

**5. Saturated-walk distrust.** A real end-cap walk stops on a rim/body/backdrop
signal. A walk that rides all the way past the ±12% clamp found NO stop signal
(wmp-vario: uniformly low-contrast outer trough → both sides shipped the full 88px/side
clamp overshoot — the exact reviewed defect). A saturated side now falls back to the
model's own declared slot-cell edge; sides stopping within the clamp keep their walked
extent (fallout-vault's legitimate 109px stepped-recess widening preserved).

## Verification (before → after)

- wmp-quicksilver: all 8 buttons/sprites now centre on their correct painted control
  (labelled overlay inspected at full res); previously playpause→vol knob, prev→seek
  groove, repeat→shuffle housing, seek→prev button, shuffle→repeat button. Drift gate
  934.4px FAIL → 544.9px ok. Coordinator's JS-probe lane independently confirmed
  fallout-vault prev/shuffle now pass a real mouse hit-test in the shipped player.
- fallout-vault: gate FAIL → PASS; prev/repeat boxes seated on their engraved buttons
  (line-overlay crop inspected; snap previously dragged them onto the yellow trim).
- myst-arcanum: repeat recovered to correct shape (aspect 1.596, siblings 1.586–1.591;
  was a 0.55-aspect sliver). Its `vol` now honestly gate-FAILs `missing:vol` — the
  source mask.png contains NO distinct vol blob (model omission, un-recoverable
  extract-side; previously masked by a wrong box that "found" something).
- ps1-crunchy seek: left overshoot 44px → 8px (travel 0.09852 → 0.11415).
- wmp-vario seek: 88px/side clamp-saturation overshoot → exact declared cell
  (travel [0.35069, 0.75825] → [0.38845, 0.71962]); full-res crop confirms the span
  brackets the recessed channel.
- Regression controls: claymation travel unchanged (0.43359..0.8138); wc-goldshield
  within 11px of prior; fallout-vault stepped-recess widening intact; n64-prerender
  vertical walk intact. Full 15-skin roster re-extracted clean (no Tracebacks; gate
  deltas all trace to these fixes or pre-existing named defects).

## Decision

Shipped all five fixes in `extract12.py` (shared pipeline, per fix-generalizable-rule —
no per-skin edits). regions.json regenerated for the full roster; players read
regions.json at runtime so no player.html changes. Remaining review-round defects
(baked thumbs, sprite/slot mismatch, ps1-wild orientation) are generation-side and
already surfaced by their own gates.
