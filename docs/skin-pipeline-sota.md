# Skin generation pipeline — SOTA (implemented)

The single-pass skin+button pipeline that actually works, plus the hard-won invariants
that killed a multi-day goose chase. Read the **Invariants** before touching any stage —
each one is anchored to a concrete failure.

## The pipeline (one prompt → a working skin)

```
prompt
  → Director (gpt-4o)
       deriveMaterial()  → {style, materialPrompt}            director.ts
       deriveLayout()    → control SET + rough rects (varied per theme, DENSITY-CAPPED)
  → repackTemplate(regions)                                    layouts.ts
       canonical per-kind sizes + move-based de-overlap (NO slivers)
  → combinedBlueprint(regs)                                    blueprint.ts
       device (2:3, magenta-ringed sockets) + bottom control STRIP, packed to 9:16
  → ONE paint pass (fal gemini edit), aspect_ratio = 9:16      pipeline.ts falSubmit
  → BiRefNet device cutout (top devFrac)            → frame.png  cutoutClient finishCutoutFull
  → cut each control sprite from its strip cell      → sprites/  cutoutClient cutSprite
  → render controls at the TEMPLATE coords (trust the blueprint) → app
```

**VLM placement (load-bearing):** gpt-4o finds each control by its icon/shape, snaps the
region to the detected box if it passes `plausibleBox` (sanity gate: aspect ratio + size
per kind). If VLM can't locate it, falls back to the clean repacked template position.
Fallback = clean blueprint; VLM = image-aware polish when it works. Proven reliable across
6 diverse skins.

Proven end-to-end on 6 diverse Y2K skins with varied interactables: EQ faders (slider-v),
slider-arc dial, XY pad, segmented selector, power toggle, knobs. All controls snapped
via VLM, rendered clean, no overlaps.

## Invariants (each = a real burn; do NOT regress)

1. **Blueprint aspect MUST equal the requested paint aspect.** An image-EDIT model reshapes
   its output to the `aspect_ratio` you ask for, NOT to the input's shape. The combined
   blueprint was 0.513 (tall) while we requested 2:3 (0.667) → the model squished it →
   every normalized strip cell + device socket landed in the wrong row → **sprites cut "way
   off."** Fix: `combinedBlueprint` REPACKS to exactly 9:16 (`PAINT_ASPECT`, `COMBINED_H`),
   `falSubmit` requests 9:16, and there's a pre-paint check (`bpAspect ≈ 9/16`, throws) plus
   a post-paint `pngDims` check that warns if the model didn't honor it.

2. **Repack the template before painting.** The Director's raw rects are often slivers or
   oversized. `repackTemplate` gives every interactable a canonical per-kind size (keeping
   its center) then de-overlaps by MOVING. The old de-overlap *shrank* overlaps to `h=0.03`
   slivers — never do that; the shrink floor is now 0.07 and it's a last resort after moving.

3. **Hard density cap in CODE, not just the prompt.** `deriveLayout` caps interactables at 9
   (EQ bands ≤5), transport/seek prioritized. gpt-4o ignores "keep it minimal" in the prompt.

4. **The paint prompt must forbid fake interactables.** Without an explicit ban the model
   paints phantom buttons/switches/jacks on the body. `PAINT_PROMPT` forbids any
   interactive-looking element outside the defined sockets + strip cells.

5. **VLM placement: trust the gate, not the signal smoothing.** gpt-4o locates controls
   reliably by icon/shape; the plausibleBox sanity gate (aspect ratio + size per kind) is
   all that's needed. Don't try to refine/re-center the VLM box pixel-perfectly — that's
   where the goose chase lived (broken socket detection, threshold tuning, margin hacks).
   VLM box + plausibleBox gate + fallback to blueprint = robust. No heuristics.

6. **Verify in the REAL app render — never a python/proxy reimplementation.** A `/tmp` python
   re-do of the cut/composite looked great for ~10 rounds while the shipped render was broken.
   Drive the actual client (`finishCutoutFull` in the browser via Playwright) and look at the
   app render. See the repo-root `CLAUDE.md` verify-outputs rule.

## Key code

- `src/generate/director.ts` — `deriveMaterial`, `deriveLayout` (density cap), `extractSlots` (VLM, opt-in)
- `src/generate/layouts.ts` — `repackTemplate` (canonical sizes), `resolveOverlaps` (move-based, sliver floor 0.07)
- `src/generate/blueprint.ts` — `PAINT_ASPECT`/`COMBINED_H`/`DEVICE_FRAC` (9:16 repack), `combinedBlueprint`
- `src/generate/pipeline.ts` — `falSubmit` (9:16 request), pre/post-paint aspect checks, `PAINT_PROMPT` (no fake interactables), `pngDims`
- `src/generate/cutoutClient.ts` — `finishCutoutFull` (path A: trust template), `cutSprite` (tight content-detect crop), `snapToVLM` (opt-in path B)
