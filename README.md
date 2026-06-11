# skeuo-ui

AI-generated skeuomorphic music-player skins with **genuinely working hardware** — flip switches whose levers flip, knobs whose caps turn, faders with real caps — driven by a layered generate→detect→composite pipeline and a WebAudio engine.

## The layered architecture

Three independent layers, composited live by React:

```
layer 1 — BODY (AI image)
  canonical skins:  Nano Banana Pro styles a BLANK faceplate (bezel + panel +
                    corner ornament; no screens, no controls) from a template-
                    rendered blueprint                      → gen_faceplate.py
  wild skins:       gpt-image-2 freely designs a Y2K body (chrome horned pod,
                    RobCo insectoid…) with EMPTY screens + EMPTY recessed
                    mounting wells; BiRefNet cuts the silhouette → wild_y2k.py

layer 2 — CONTROL SPRITES with STATES (AI image)    → gen_sprites.py
  per style: the SAME flip switch rendered twice in one image (lever down |
  lever up) and split → toggling swaps real art. A cap-only circular knob
  (center-crop + circle alpha mask) whose art rotates. A 9-sliceable button
  face. A fader cap. gpt-image-1.5 with background:"transparent".

layer 3 — LIVE UI (React)
  recessed screens with live content (canvas spectrum fed by the real
  post-EQ AnalyserNode, marquee, clock, playlist), drag/touch interaction
  (Pointer Events), and a generative WebAudio engine: saw-chord pad → preamp
  → 10 peaking EQ bands → tilt → pan → volume → analyser. Volume/EQ/balance
  changes are audible AND visible in the spectrum.
```

**Alignment is measured, never guessed.** Canonical skins place controls at
template coordinates (the faceplate is blank, so nothing can disagree). Wild
bodies are parsed by `detect_wells.py` — pixel-accurate CV (scipy), two passes:
near-black glass → screens; dark recesses → wells, classified by geometry
(aspect → slider, bbox-fill → knob vs button, row-clustering → transport order).
Each skin dir gets an `_overlay.png` proving every region sits on its feature.
LLM box-grounding was tried and abandoned: boxes landed ~5-10% off, which reads
as broken UI.

## Running

```bash
npm install
npm run dev
```

The dev server binds all interfaces (see `central/rules/dev-server-network-rule.md`):
`http://lappy-heavy.local:5173` on home wifi (iOS-friendly mDNS), tailnet name on
the go. Skins: 6 canonical (Winamp, Fallout Pip-Boy, Baldur's Gate, Aqua,
70s Hi-Fi, Papercraft) + wild Y2K bodies (`Y2K Pod ✦`, `Rust Wasp ✦`).

## Regenerating

```bash
cd generation
python3 render_control.py                 # template → blueprint (CONTROL_OUT/TEMPLATE_JSON env)
FACEPLATE=1 python3 render_control.py     # blueprint without controls/screens
python3 gen_faceplate.py [skins...]       # blank faceplates (Nano Banana Pro)
ASSETS=knob python3 gen_sprites.py        # control sprites; ASSETS filters
python3 wild_y2k.py [pod|wasp|splash]     # wild bodies (gpt-image-2 + cutout)
python3 detect_wells.py public/skins/<id> # CV template from a body
```

Model notes (A/B'd): **Nano Banana Pro** (`fal-ai/gemini-3-pro-image-preview/edit`)
for structure-preserving restyles — gpt-image smears UI edges through its low-res
latent and caps at 1536px. **gpt-image-2** for freeform body design (it does wild
shapes + typography well). **gpt-image-1.5** wherever transparent RGBA output is
needed (sprites). `fal-ai/birefnet/v2` for cutouts.

## Layout

```
src/
  template/winamp-layout.ts   canonical layout (one source of truth, px → normalized)
  player/
    Composite.tsx             template → regions; sprite components w/ CSS fallback
    usePlayer.ts              all state; every control binds to a real action
    useAudio.ts               WebAudio graph (the audible half)
    Visualizer.tsx            canvas spectrum (reads the real analyser)
    skins.ts                  registry: faceplate/sprites/template per skin
  skins/*.css                 per-skin palettes + shared structure (player.css)
generation/                   the AI pipeline scripts (above)
public/skins/<id>/            frame.png, sprites/, template.json (wild), _overlay.png
```
