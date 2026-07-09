# PBR / delighting / emissive experiments — gen12 skins (2026-07-09)

## Question
Can generated skeuo skins become dynamically lightable (PBR maps, emissive self-illumination),
and what's the best albedo/delight path?

## Method
pbrtest/ (round 1) + pbrtest2/ (round 2), tools/mask-align-exp/gen12/. Models: fal-ai/patina
(image→basecolor/normal/roughness/metal/height, ~$0.03/2MP — the ONLY PBR-decomposition model on
fal; no delighting/intrinsic/emissive model exists there), gemini-3-pro-image-preview (Vertex)
for flat-prompt albedo gens, local Marigold normals (MPS, $0), classical HSV emissive extraction,
hand-rolled WebGL relighting (fresnel glass, blurred-emissive gather + cluster point-lights).

## Results + HUMAN VERDICTS (Conner, 2026-07-09)
- **Original gemini paint (non-delit) is fine for skeuo — move forward with it.** A distinct
  "delight" pass is deferred ("save for later").
- **Flat-prompt gemini gen = the LEAST-lit albedo** of everything tried (best delight-like
  result) — but it can drift cartoon/cel on glossy materials (must prompt photoreal-unlit; still
  fails on glossy dark plastic ~1-in-2).
- **PATINA basecolor ≈ "evenly lit", not truly delit** — it does hand back a de-facto delight
  layer for free in the same single pass as normal/rough/metal/height (one call, one price), and
  works better on matte/rough materials (diablo stone) than glossy (vario plastic).
- **PATINA normals are really good** (user verdict) — good enough to drop the separate local
  Marigold pass when a patina call is already being made; Marigold stays the $0 local fallback.
- **Glass handling looks great** (user verdict): feathered glass mask + in-shader de-bake +
  fresnel + moving procedural env reflections beats frozen baked reflections.
- **Emissive v1 verdict: bad on diablo** — extraction caught orange specular *splatter* on
  surrounding surfaces instead of making the rune GLYPHS glow ("runes aren't lighting up… weird
  splatter"). Needs a rethink: glyph-shaped emissive (chroma + local-contrast + shape), not broad
  hue windows. Rework in flight (pbrtest3).

## Measured
diablo self-glow 7.2× on/off, neighbour bezels 2.1× (directional); vario 10×/2.5×. fal spend
round 2 ≈ $0.22; local stages $0.

## Artifacts
pbrtest/, pbrtest2/ (pages, maps, extraction scripts, shots) — committed f47c88cc etc.

## Round 3 (pbrtest3) — RESULTS (human verdict: "great")
- **Glyph emissive solved**: chroma×luminance gated by two-scale morphological TOP-HAT (only thin
  locally-bright features survive) + erode + area cap → the emissive mask is literally the rune
  strokes / crack shapes; tight 2-level glow gather + 6 cluster point-lights, fast falloff.
  v2-vs-v3 close-ups verified: crisp glowing glyphs, localized spill (no splatter).
- **Patina single-pass CONFIRMED**: one call returns all 5 maps (basecolor/normal/roughness/
  metalness/height) at $0.01/MP — Marigold dropped from the pipeline (kept as $0 fallback).
- **No emissive model exists** on fal or HF (intrinsic models bury emission in residual+specular);
  classical extraction is the right tool.
- **Fully interactive one-shader player**: draggable knob with rotating bump normals, silhouette-
  press buttons re-shaded by live light, VISUALIZER AS EMISSIVE SOURCE (bars light bezel 6.5×),
  shuffle, seek with in-shader groove resample. $0 new spend. Page: gen12/pbrtest3/.
