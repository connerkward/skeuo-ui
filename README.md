# skeuo-ui

Prompt-driven skeuomorphic UI: take one canonical Winamp-layout reference, restyle it via diffusion (gpt-image-2 or Flux+ControlNet-Canny), extract per-component sprites, and composite a real React UI over the result. Real buttons, real switches, real sliders — not screenshot overlays.

Five style packs ship: **Pip-Boy 3000**, **Winamp Organic 9x**, **Chrome iPod**, **Nautical Brass**, **Cyberpunk Holo**.

![skeuo-ui screenshot](docs/cover.png)

## Pipeline

```
                      [ canonical-zero.png ]
                      (gpt-image-2/edit: empty UI template,
                       all sliders at 0, all switches off,
                       all buttons unpressed, displays empty)
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
   [ styled-idle ×5 ]                 [ canny edge map ]
   (gpt-image-2/edit: apply style     (PIL+OpenCV: Canny on
    while preserving layout)           canonical-zero)
              │                               │
              │            ┌──────────────────┘
              │            ▼
              │   [ ControlNet styled ×5 ]
              │   (fal-ai/flux-control-lora-canny
              │    text-to-image, strength=0.85,
              │    semantic prompts)
              │            │
              └────────────┤
                           ▼
                  [ frame-only ×5 ]
                  (gpt-image-2/edit on styled-idle:
                   "remove all components, keep
                    only chrome frame + screws
                    + title plates")
                           │
                           ▼
              [ Python extract_sprites.py ]
              per-style outputs:
                • panel-{main,eq,playlist}.png  (chrome bg)
                • tile-{main,eq,playlist}.png   (tileable patch)
                • {component-id}.png            (37 sprites)
                           │
                           ▼
                   [ React app ]
              (absolute positioning at
               normalized hotspot coords)
```

## Running

```bash
npm install
npm run dev    # http://localhost:5173/
```

Public sprite atlases are committed under `public/sprites/{styleId}/` so the app runs offline. To regenerate from new source images:

```bash
python3 scripts/extract_sprites.py
```

## Generating new style packs

1. Drop new source images into `assets/refs/`:
   - `{styleId}-idle.png` — full UI in target style (all components visible, displays empty)
   - `{styleId}-frame.png` — same chrome but with all components removed (clean interior)
2. Add the style to `src/styles/packs.ts`.
3. Add an entry to `STYLES` in `scripts/extract_sprites.py`.
4. Re-run extraction.

### Recommended generation recipe

After three rounds of A/B testing (see `docs/findings.md`):

**Best: Flux + ControlNet-Canny (text-to-image)** — `fal-ai/flux-control-lora-canny`

```json
{
  "control_lora_image_url": "<canny edge map of canonical-zero>",
  "prompt": "Photorealistic 3D rendered media player UI panel, [STYLE]. The interface consists of RAISED PRESSABLE PHYSICAL BUTTONS [details]. RECESSED VERTICAL SLIDER CHANNELS with [details]. INSET DARK LCD SCREENS [details]. Panel material: [STYLE MATERIAL]. The buttons are clearly distinct from the panel — they protrude, catch light differently, have their own bevels.",
  "control_lora_strength": 0.85,
  "guidance_scale": 3.5,
  "num_inference_steps": 35,
  "image_size": {"width": 1536, "height": 1024}
}
```

Key trick: **explicit semantic vocabulary** ("RAISED PRESSABLE PHYSICAL BUTTONS", "RECESSED SLIDER CHANNELS", "INSET LCD SCREENS") tells Flux that the Canny edges represent interactive UI, not decoration. Without this, Flux interprets button-rectangles as engraved details on the panel — pretty but unusable.

**Alternative: gpt-image-2/edit** — slightly worse layout fidelity (esp. on iPod, where it shrinks the device) but easier to prompt. Use when you don't have a Canny pipeline.

## Findings

See `docs/findings.md` for the A/B comparison data: drift overlays, per-style scoring, cost estimates, and why ControlNet round 3 beat both gpt-image-2 and the looser ControlNet configs from earlier rounds.

## Tech

- Vite + React + TypeScript
- Python 3 + Pillow for asset extraction
- fal.ai (`openai/gpt-image-2/edit`, `fal-ai/flux-control-lora-canny`) for generation

## Layout

```
src/
  App.tsx                   # style selector + Frame
  components/
    Frame.tsx               # three panels, no responsive logic
    Components.tsx          # Button / Switch / SliderV / SliderH
  styles/
    packs.ts                # style list + hotspot map + panel y-ranges
    base.css                # styling primitives
  types.ts
public/sprites/{styleId}/   # per-style extracted assets
assets/refs/                # AI source images (canonical, idle, frame)
scripts/
  extract_sprites.py        # crop sprites from refs
  measure_drift.py          # diagnostic overlay for layout drift
docs/findings.md            # gpt-image-2 vs ControlNet comparison
```
