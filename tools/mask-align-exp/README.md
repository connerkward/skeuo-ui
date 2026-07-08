# mask-align-exp — joint paint+mask alignment pipeline (2026-07-07)

Working experiment state. Live-iterated copy in `/private/tmp/skeuo-maskexp/`.
Companion record: `docs/experiments/2026-07-07-dual-output-mask.md`.

## What works (verified end-to-end)

One $0.15 nano-banana-pro generation (`fal-ai/gemini-3-pro-image-preview/edit`, 4K, 5:4)
returns a two-panel canvas: **LEFT** = painted device + 5-part sprite strip on flat charcoal
`(22,22,26)`; **RIGHT** = color-keyed region mask on pure black. Split at `w//2`.

Pipeline (`run9.py` → `extract9.py` → `run_biref9.py` → `phone9.html`):

1. **Mask-color correlation** — nearest-color assignment (`sat>55, max>90, dist<95`),
   **largest connected component** per color, sprite-strip cells by **color identity not
   left-to-right order**. Toggle = two pink cells split left/right.
2. **Circle-fit alignment** (extract9) — mini-Hough on gradient magnitude for vol/bal knob
   sockets. Material-agnostic: works on dark-on-dark chrome and MAGMA CORE black bodies.
   Residual vs painted rim center: **<3 px**. Global drift vector from knob fits applied to
   ALL controls (-0.5% X, +0.0% Y on run9 seed 41).
3. **rrect-fit alignment** (extract9) — same gradient scoring along rounded-rect perimeter
   for seek groove and toggle slot. Measured on MAGMA CORE: tog 214×299 px, seek 904×116 px.
4. **Snap-to-paint X ONLY** — model paints mask ~+0.5% right of paint (systematic). Snap
   each region's x-center onto the painted dark well (socket) or saturated icon (button);
   keep mask's y (dark-pixel centroid biased UP by top-light shadow).
5. **Leak gate** (`leak_check()`) — scan paint panel for surviving guide colors (sat>55,
   dist<60 px from any key). FAIL threshold 0.05%. Per-color counts printed.
6. **Relative emptiness gate** — floor = 10th percentile luminance in the socket well.
   FAIL if >10% of interior is >floor+55. Catches baked thumbs/handles on ANY material.
7. **Gate-driven repair** (`erase_baked.py`) — for sockets failing emptiness gate: dilate
   part mask, fill with floor tone + gaussian noise, feathered blend. Cheaper than re-rolling.
8. **BiRefNet global + CC island split** (`run_biref9.py`) — one pass mattes the whole
   paint; largest island = device body; smaller islands identity-matched by centroid to strip
   cells. Alpha holes in device matte = exact painted socket geometry.
9. **Alpha-hole seats** — device BiRefNet matte has enclosed alpha holes at sockets → fit
   inscribed circle → exact painted socket center without any paint-color assumption.
10. **Backdrop-by-material-lightness** — dark body → pale (235,235,238) backdrop; light
    body → charcoal (22,22,26). Parameterized in blueprint canvas AND all prompt clauses.
11. **Screen as mask region** — lime (100,255,0) key, verified min dist 149 from all other
    keys. `extras:["screen"]` in regions.json.

## Adaptive color contract (run10 — wild/stress test)

`run10.py` builds the color key contract FIRST (9 keys from the {0,128,255}³ lattice,
≥120 RGB distance from each other AND from the design palette). Written to `results.json`
before the fal call; `extract10.py` reads colors from there — palette-agnostic. Result on
MAGMA CORE Y2K skin: single-gen fully clean mask on first try (conventional chrome hardware
triggers baked-part prior; vivid unusual designs pass more easily).

## Prompt clauses that matter (run9)

- **ALIGNMENT MARKINGS** framing: "like masking tape on a workpiece — NOT part of the
  product's design and MUST be COMPLETELY removed."
- **ZERO RESIDUE clause**: "Do NOT leave ANY thin coloured rim, ring, halo, edge tint or
  glow around ANY socket, button, slot or part."
- **EXACT FIT clause**: "every strip part's guide outline is drawn at the EXACT SAME SIZE
  AND SHAPE as its slot."
- **PHOTOGRAPHED BEFORE ASSEMBLY** block: device photographed before parts installed →
  all sockets completely empty.
- **Solid blob mask clause**: "NEVER flood a whole strip cell or any rectangle of
  background with colour; NEVER draw outlines or hollow shapes — every blob is ONE solid
  filled silhouette."
- **Congruence contract**: slot geometry defined ONCE (`KNOB_R=76`, `TOG_W/H/R=110/170/38`,
  `GROOVE_W/H=520/70`, `THUMB_W/H/R=150/92/44`) used for BOTH device slot AND strip anchor.
  Old mismatch (110×170 socket vs 120×150 strip anchor) was the toggle-size bug.

## Key numbers

- mask→skin (blob on painted control): **0.5–2% raw, ≈0.05% after gradient-fit + snap**.
- Gradient-fit offset on run9 seed 41: vol -13,+2 px; bal -10,-1 px; global drift -0.50%.
- Joint = 1 image billed; separate mask pass = 2× cost. 4K recovers resolution.
- BiRefNet Heavy 2048: ~$0.005/call.
- Wild Y2K design (run10): passed mask quality on first gen (seed 41).

## Files

- `run9.py` — walkman/phone skin generator with all prompt fixes + congruence contract.
- `extract9.py` — circle-fit + rrect-fit + global drift + slot-extent refinement + gates.
- `erase_baked.py` — gate-driven repair: fills baked parts with floor tone + noise.
- `run_biref9.py` — global BiRefNet pass + CC island split + alpha-hole seats.
- `run10.py` — Y2K MAGMA CORE stress test with adaptive color contract.
- `extract10.py` — same gradient-fit pipeline, reads color keys from results.json.
- `run_biref10.py` — BiRefNet pass for run10 assets.
- `phone9.html` — full contact sheet: blueprint → joint → paint → mask panels → BiRefNet
  global matte + device island → CC sprite islands → finished interactive product.
- `wild10.html` — MAGMA CORE contact sheet with same sections.
- `run8.py` / `extract8.py` / `run_biref.py` / `interactive.html` — earlier iteration
  (snap-to-paint only, no gradient-fit, no gates). Kept as baseline.
- `assets9/` / `assets9_biref/` / `assets10/` / `assets10_biref/` — WebP assets + regions.json.

## Open issues

- run9 sprite cells still wrong-art on seed 41 after repair (pink rings; seek=toggle swap).
  Root cause: model painted toggle where seek should be in the strip. Next: strip cell
  ordering prompt fix or stronger strip-layout enforcement.
- wild10 knob/switch alignment: gradient-fit added to extract10.py (results above) but not
  re-verified interactively after fix.
