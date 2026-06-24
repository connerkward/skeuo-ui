# Branch `cutout-coloured-despill` — merge context

**One-liner:** paint each device on a flat **contrasting backdrop** and key it out with a
**color-aware matte (key → color-aware fill → despill)**, replacing the white-key +
fill-all-holes cutout. Fixes the two long-standing cutout bugs at the source.

Base: `main` (branched 2026-06-23, tip `29de2be`). Build green (`npm run build`).

## Why

The old runtime cutout (`cutoutAlpha`, white-key + fill-ALL-holes) had two failures:
1. **Near-white screens/bodies lost** — on a white background a near-white screen is
   indistinguishable from the background, so it gets dropped or the white pocket kept.
2. **Backdrop bleed through thin gaps kept opaque** — leaked white in thin slots stayed.

Painting on a **colored** backdrop makes the cut unambiguous: a screen ≠ the backdrop
color, so fill/cut decisions are decidable. Validated this session on real nano-banana
paints + fal BiRefNet v2 (interactive lookdev: `~/Desktop/cc-skeuo/cutout-lookdev/`).

## The change (8 files, one commit)

**Seam contract — `keyColor: [r,g,b]`** flows: chosen at generation → baked into the paint
backdrop → carried in the response → used by the client cutout. White `[255,255,255]` =
legacy/fallback behavior.

- `src/generate/pipeline.ts`
  - `pickKeyColor(materialText)` → `{key, css, phrase}`. Deterministic (no LLM). Picks a
    bright hue **far from the device's own palette**; **translucent/iridescent → white**.
  - `ENVELOPE_PROMPT` / `STYLE_PROMPT` now use a `{BG}` token filled per-generation; the
    STYLE prompt adds an explicit "backdrop must not tint/reflect/spill onto the device".
  - wells-blueprint background = the key css color; `keyColor` added to `GenerateResult`;
    passed to `deps.cutout(paintPng, key)`.
- `src/generate/blueprint.ts`
  - **`cutoutColorAware(rgba, W, H, key=KEY_WHITE)`** — the new standard. MUTATES rgba in
    place (despilled RGB + alpha). Pipeline: color-key body → largest component →
    color-aware fill (enclosed **non-backdrop** pixels stay opaque = keep dark screens; cut
    leaked backdrop) → 1px erode → despill (subtract the backdrop hue's chroma direction).
    For a **white key it delegates to `cutoutAlpha`** (unchanged legacy path).
  - `cutoutAlpha`, `RGB`, `KEY_WHITE` exported; `wellsOnlySvg(regs, bg="white")`.
- `src/generate/api.ts` `GenerateDone.keyColor?: [number,number,number]`.
- `src/generate/handler.ts` sets `keyColor: r.keyColor` on the response.
- `src/generate/cutoutClient.ts` `cutoutPaintToFrame` / `finishCutout` take `key`, call
  `cutoutColorAware` (no separate alpha loop — it mutates RGB+alpha together).
- `src/generate/CreateWizard.tsx`, `CreatePanel.tsx` pass `data.keyColor` to `finishCutout`.

The cutout runs **only in the browser** (`cutoutClient.ts`) — both the CF Worker and the
dev server defer it (`deps.cutout` is unused in practice; its signature was updated anyway).

## Validated caveats (encoded in `pickKeyColor`)

- **Translucent / iridescent / pearl / jelly / slime / glass → white key, NO despill.** A
  colored-key despill desaturates a body that legitimately carries the backdrop hue (light
  through / shifting sheen). These keep the legacy white path.
- **Never key on a hue in the device's palette** (green bg on a green-LED device ate the
  LEDs). The picker maps device-hue → a contrasting backdrop.
- Bright/high-luminance keys give the sharpest edge; dark keys risk eating black screens.

## What's verified vs NOT

- **Verified:** `npm run build` (tsc + vite) green. `cutoutColorAware` run via esbuild on
  real nano-banana paints (obsidian comb artifact gone, dark screens kept solid, magenta/
  yellow keyed clean, despilled edges). Colored-backdrop painting validated this session.
- **NOT verified:** a **live end-to-end generation** through the wizard (paint on colored
  bg → finalize → cutout in-app). Do this once before relying on it.

## Merge guidance — IMPORTANT

This is a **pure-JS color-key matte** on top of `main`. The pending #1-priority branch
**`spritesheet-pipeline`** reworks the cutout with **BiRefNet** (`functions/api/cutout.ts`)
and per-skin sprites. The two touch the same area. **Decide the integration:**

- **Option A — merge to `main` now.** Clean against current `main` (this branch IS based on
  it). Later, the `spritesheet-pipeline` merge must reconcile its cutout with this one.
- **Option B (recommended) — fold into `spritesheet-pipeline` first**, so the BiRefNet
  device cutout and this color-aware matte reconcile in ONE place. The natural end state:
  **BiRefNet alpha → this same color-aware fill + despill (+ a color-aware CUT step for
  backdrop BiRefNet wrongly keeps) → despill.** The Python reference for the BiRefNet+cut+
  fill+despill variant is in the session scratch `bake_all.py`; the lookdev studio at
  `~/Desktop/cc-skeuo/cutout-lookdev/` shows every stage.

Likely conflict/reconcile points if merging with `spritesheet-pipeline`:
`pipeline.ts` (prompts + result shape), the cutout module (`blueprint.ts` vs
`functions/api/cutout.ts`), and the response type (`api.ts`/`handler.ts` `keyColor`).

## How to test before/after merge

1. `npm run build` — must stay green.
2. Run the dev server, generate a skin via the wizard for a few materials (a green one, a
   white/silver one, a translucent one). Confirm: backdrop is keyed out, dark screens are
   solid (not holes), no colored fringe, translucent one falls back to white cleanly.
3. Spot a tricky one (mirror/iridescent) and eyeball the cut over a contrasting backdrop.
