# Generation — regenerating bodies, sprites, and templates

> **Pipeline note (2026-06-25):** the SHIPPING web/app pipeline (`src/generate/`) is now a
> SINGLE-PASS combined-blueprint paint (device sockets + sprite strip in one image, no
> separate envelope pass) with a colour-key device cutout. The two-pass `generation/`
> Python tools below are the research lineage. Current feature × platform truth lives in
> [feature-parity.md](feature-parity.md).

> Deep-dive companion to the [README](../README.md). The machine-facing reference
> for running the generate pipeline yourself. For *why* it's built this way, see
> [architecture.md](architecture.md).

## Prerequisites

```bash
cd generation
# a fal key (and OpenAI key for silhouette/sprite passes) in the environment;
# never commit keys — they live in your shell env / .env (gitignored).
```

## Wild bodies

```bash
# wild body: <id> <style> "<silhouette brief>" [sil_path|-] [variant] [ref1,ref2,…]
python3 wild_sculpt.py maw    biomech "a fanged anglerfish jaw"   - radial
python3 wild_sculpt.py pebble frog    "a round amphibian egg-pod" - minimal
python3 wild_sculpt.py slab   winamp  "a wide low armored hull"   - capsule assets/refs/winamp-frame.png
```

- `variant` ∈ `classic · hero · flank · orbit · radial · capsule · minimal`
  (see the grammar table in [architecture.md](architecture.md#layout-grammars)).
- The 6th arg is a comma-separated list of **reference-style image paths** that
  steer the paint pass (palette / material) without touching the blueprint's
  layout.

## Sprites & molded transport faces

```bash
python3 gen_buttons.py [styles…]     # molded transport faces (5-button sheet → split)
ASSETS=knob python3 gen_sprites.py   # knob/switch/fader/button sprites; ASSETS filters
```

## Model notes (A/B'd)

| Model | Used for | Why |
|---|---|---|
| **Nano Banana Pro** (`fal-ai/gemini-3-pro-image-preview/edit`) | structure-preserving restyles | gpt-image smears UI edges through its low-res latent and caps at 1536px |
| **gpt-image-2** | freeform silhouette design | best at wild shapes + typography |
| **gpt-image-1.5** | anything needing transparent RGBA | sprites, molded buttons |

## Output layout

Each generated skin lands in `public/skins/<id>/`:

```
public/skins/<id>/
  frame.png        the painted body (alpha = the silhouette mask)
  sprites/         knob / switch / fader / molded-button art, with states
  template.json    control coordinates, emitted from the drawn layout
```

The skin is then registered in `src/player/skins.ts` (frame / sprites / template /
molded per skin) and its palette CSS added under `src/skins/`.
