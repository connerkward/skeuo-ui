# mask-align-exp — joint paint+mask alignment pipeline (2026-07-07)

Working experiment state, committed for the studio to port. Live-iterated copy lives in
`/private/tmp/skeuo-maskexp/` (this snapshot converts the big PNGs to full-res WebP).
Companion record: `docs/experiments/2026-07-07-dual-output-mask.md`.

## What works (verified end-to-end in `interactive.html`)

One $0.15 nano-banana-pro generation (`fal-ai/gemini-3-pro-image-preview/edit`, 4K, 5:4)
returns a two-panel canvas: **LEFT** = painted device + 5-part sprite strip on flat charcoal
`(22,22,26)`; **RIGHT** = color-keyed region mask on pure black. Split at `w//2` (verified:
the model draws the divider exactly there).

Pipeline (`run8.py` → `extract8.py` → `run_biref.py` → `interactive.html`):

1. **Mask-color correlation** (`extract8.py`) — nearest-color assignment (`sat>55, max>90,
   dist<95`), **largest connected component** per color (kills stray-pixel bbox inflation),
   sprite-strip cells by **color identity, never left-to-right order** (order-based
   assignment put a toggle where seek belonged), toggle = two pink cells split left/right.
2. **Snap-to-paint, X ONLY** — the model paints the mask panel ~**+0.5% right** of the paint
   (systematic across generations; direction consistent, magnitude 0.2–0.7%). Snap each
   region's x-center onto the painted feature (dark well for sockets, saturated icon for
   buttons); **keep the mask's y** — the dark-pixel centroid is biased UP (recess shadow hugs
   the top inner rim under top-light) and was seating knobs too high. Residual after snap:
   **≈0.05%**. `regions.json` carries both `maskDevice` (raw blob bbox) and `device` (snapped).
3. **BiRefNet matting** (`run_biref.py`, `fal-ai/birefnet/v2` Heavy 2048) — **global pass**
   (1 call, ~$0.005) mattes the device body + all parts at once; **per-part crops** (~$0.013
   total) give cleaner small-part edges. Verdict: global for the device, per-part for sprites.
   Client tight-crops the per-part PNGs (BiRefNet returns transparent padding that lies about
   part geometry).
4. **Placement** (`interactive.html`) — knobs: circle-clipped cut seated at snapped center,
   cap rotates under a **pinned** specular (normal-blend hotspot+counter-shade; screen-blend
   white is invisible on chrome), drop shadow on the **non-rotating** container. Seek: thumb
   travel flush to slot ends; `tw = th*(t.w/t.h)*PH/PW` (x/y normalizers differ — omitting
   the PH/PW factor renders 1.6× too narrow). Buttons: baked; press-darkening = the button's
   own mask silhouette cropped around `maskDevice`, positioned translated by the snap delta,
   `mask-size:100%` (1:1 pixel mapping — `contain` rescaling was the oversize bug).

## Key numbers

- mask→skin (does the blob sit on the painted control): **0.5–2% raw, ≈0.05% after snap**.
- template→mask (model rearranges the authored layout): **~26–30% — expected, not error**;
  place from the mask, never the template.
- Joint = 1 image billed; separate mask pass or `num_images:2` = 2× cost. 4K recovers the
  shared-canvas resolution loss for the same $0.15.

## Prompt clauses that matter (see `run8.py` PROMPT)

- Flat uniform charcoal backdrop, strongly contrasting the (monochrome) body — none of the
  guide colors anywhere in the paint.
- Seek track = COMPLETELY EMPTY groove (the model loves to bake a thumb in).
- Strip = EXACTLY FIVE parts, ONE row, **straight-down top-down orthographic** (it defaults
  to 3/4 product shots that can never seat on a flat device), toggle in OFF and ON states.

## Files

- `run8.py` / `extract8.py` / `run_biref.py` / `maskskin.py` / `gen_explain.py` — pipeline.
- `interactive.html` — full-chain live proof (template → paint → mask → cut & placed, all
  controls interactive). `explain.html` — the correlation bug post-mortem. `biref-compare.html`
  — global vs per-part matting. `global-matte-view.html` — raw matte on checkerboard.
- `assets8/` — generation + `regions.json` (WebP full-res). `assets_biref/` — matte cuts.
