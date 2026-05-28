# Findings: gpt-image-2 vs Flux+ControlNet for skeuomorphic UI restyle

Three rounds of A/B testing across 5 styles (Pip-Boy, Winamp Organic, iPod, Nautical, Cyberpunk). Source: `canonical-zero.png` (empty Winamp UI template, all components at idle state).

## Headline

**Use ControlNet round-3 recipe** (`fal-ai/flux-control-lora-canny` text-to-image, `control_lora_strength=0.85`, semantic prompts naming buttons/sliders/displays explicitly). It beats both gpt-image-2/edit and looser ControlNet configs on layout fidelity *and* aesthetic capture.

## Rounds

### Round 1 — gpt-image-2/edit
- Pipeline: edit canonical-zero with style description.
- **Aesthetic:** 5/5 across styles.
- **Layout fidelity:** mixed. iPod was the worst — gpt-image shrunk the device to ~half canvas, ~30-60px drift on every component. Pip-Boy, Winamp, Nautical, Cyberpunk: ~5-20px drift on individual components.
- Cost: ~$0.10/image.

### Round 2 — ControlNet image-to-image (canonical as both control + color init)
- Pipeline: `fal-ai/flux-control-lora-canny/image-to-image`, `control_lora_strength=0.85`, `strength=0.95`, source image as both `image_url` and `control_lora_image_url`.
- **Aesthetic:** 1-2/5. The canonical's gray-steel color init dominated; every output stayed gray steel.
- **Layout:** pixel-perfect (geometry preserved) but moot when aesthetic failed.
- Cost: ~$0.04/image.

### Round 2.5 — ControlNet text-to-image, strength 0.65
- Pipeline: text-to-image with Canny control only, no `image_url`. Style prompts as in round 1.
- **Aesthetic:** 4-5/5. Big jump — colors came through.
- **Layout:** mixed. Components-as-decoration problem: Flux drew the Canny edges as engraving on a flat brass plate (Pip-Boy, Nautical) rather than as raised buttons. iPod and Cyberpunk worked.

### Round 3 — ControlNet text-to-image, strength 0.85 + semantic prompts ✅
- Pipeline: same as 2.5 but `control_lora_strength=0.85` + explicit semantic vocabulary in prompts.
- Prompt template:
  > Photorealistic 3D rendered media player UI panel, [STYLE]. The interface consists of **RAISED PRESSABLE PHYSICAL BUTTONS** [details]. **RECESSED VERTICAL SLIDER CHANNELS** with [details]. **INSET DARK LCD SCREENS** [details]. Panel material: [STYLE MATERIAL]. The buttons are clearly distinct from the panel — they protrude, catch light differently, have their own bevels.
- **Aesthetic:** 4-5/5 across all styles.
- **Layout:** 4-5/5. Pip-Boy now has distinct transport buttons with icons; iPod has chrome discs at correct positions; sliders align with their hotspot rects; switches are visible.
- Cost: ~$0.04/image.

## Per-style winner

| Style | Round-1 (gpt-image-2) | Round-2.5 (CN-loose) | Round-3 (CN-semantic) |
|---|---|---|---|
| Pip-Boy | aesthetic ✓, ~10px drift | aesthetic ✓ but transport = engraving | **best** |
| Winamp Organic | aesthetic ✓, ~15-20px on switches | aesthetic ✓, layout ~OK | **best** (jelly buttons distinct) |
| iPod | shrunken device ✗ | aesthetic ✓, buttons faint | **best** (chrome discs aligned) |
| Nautical | aesthetic ✓, ~10-20px drift | brass ✓, transport = engraving | **best** (raised brass discs) |
| Cyberpunk | aesthetic ✓, tightest of gpt set | aesthetic ✓, layout OK | **best** |

## Why semantic prompts worked

Flux+Canny on a UI template sees abstract edges. Without explicit guidance, it disambiguates ambiguous regions toward whatever the prompt vibes (style description alone) emphasize. "Brass nautical instrument" without further context → engraved details on a brass plate is the most likely interpretation; transport buttons happen to look like ornamental engraving in a brass setting.

Telling Flux *what the rectangles are* — pressable physical buttons that protrude, recessed slider channels, inset displays — gives it a concrete UI ontology to render against. Round 3 produced recognizable UI components in every style.

## Cost summary

Total spend across all rounds for this project: **~$1.50**.

- Round 1: 5 × $0.10 = $0.50 (gpt-image-2)
- Round 2: 5 × $0.04 = $0.20 (CN i2i)
- Round 2.5: 5 × $0.04 = $0.20 (CN t2i loose)
- Round 3: 5 × $0.04 = $0.20 (CN t2i semantic)
- Frame-only generation: 10 × $0.04 = $0.40 (gpt-image-2 edit, two waves)

Re-running the pipeline on a new style with the round-3 recipe: ~$0.08 ($0.04 styled-idle + $0.04 frame-only).

## Recommendation

For new style additions:
1. **Generate styled-idle with ControlNet round-3 recipe** (Canny from canonical-zero + strength=0.85 + semantic prompts).
2. **Generate frame-only with gpt-image-2/edit** on the styled-idle output, prompted to remove all components while preserving the chrome material.
3. Run `python3 scripts/extract_sprites.py`.

ControlNet wins on the styled-idle pass because button positions matter for sprite extraction. gpt-image-2/edit wins on the frame-only pass because it's better at the "remove these specific things from a photo" instruction than Flux is.
