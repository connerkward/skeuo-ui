# skeuo-ui

Prompt-driven skeuomorphic UI. **One layout template → many AI-styled skins**, composited into a real, working React media player where the chrome is generated art and the live content (clock, spectrum, marquee, playlist) is dynamic.

Three skins ship: **Winamp Classic**, **Fallout Pip-Boy**, **Warcraft III**.

![skeuo-ui](docs/cover.png)

## The idea

The hard part of "AI-skinned UI" is **consistency** — making generated art line up with real, interactive widgets, and keeping the right things baked vs. the right things live. This repo solves that with a single source of truth:

```
                    src/template/  (ONE template: every region's
                     rect + kind + content-type + layer)
                              │
            ┌─────────────────┴──────────────────┐
            ▼                                     ▼
  generation/render_control.py            src/player/Composite.tsx
  renders a neutral skeuomorphic          reads the SAME template and
  BLUEPRINT (control.png) showing         lays widgets at identical coords
  exactly where each control sits                 │
            │                              • frame.png   → styled background
            ▼                              • sprite regions → interactive
  generation/generate.py                     overlays (press feedback)
  fal gpt-image-1.5/edit restyles         • dynamic regions → live React
  the blueprint per skin, in place,         (clock, spectrum, marquee,
  keeping screens empty + channels           playlist) over blank screens
  knob-free  →  public/skins/<id>/frame.png
```

Because the blueprint handed to the model and the runtime compositor both read the **same normalized coordinates**, generated art and live widgets align *by construction* — no per-skin hand-tuning. Toggle the **Wireframe** checkbox in the app to see the template the model is styling from (color-coded by kind; dashed = dynamic, solid = baked sprite).

### Sprite vs. dynamic — the split that makes it work

Every region in the template declares `content: "sprite" | "dynamic"`:

- **sprite** — baked into `frame.png` (buttons, slider channels, bezel, screen wells). React renders only a transparent hit-target with press feedback.
- **dynamic** — the art leaves this area as empty dark glass; React renders live content into it (elapsed time, spectrum analyzer, scrolling marquee, EQ curve, playlist). Never baked.

## Running

```bash
npm install
npm run dev    # http://localhost:5173/
```

Generated `frame.png` layers are committed under `public/skins/<id>/`, so the app runs offline. The player is fully interactive: transport, shuffle/repeat, EQ sliders, volume/balance, click/double-click playlist rows.

## Regenerating / adding a skin

```bash
python3 generation/render_control.py     # blueprint from the template
python3 generation/generate.py           # styles all skins in parallel via fal
```

`generate.py` reads `FAL_KEY` from `~/dev/central/.env`, uploads the blueprint once, submits one `fal-ai/gpt-image-1.5/edit` job per skin in parallel, and downloads each result to `public/skins/<id>/frame.png` (~60s/skin, ~$0.19 each at `quality: high`).

To add a skin: add a prompt to `SKINS` in `generation/generate.py` and an entry to `skinList` in `src/player/skins.ts`. To change the *layout* (move/resize widgets), edit `src/template/winamp-layout.ts` — every skin updates from the one template.

### Why gpt-image-1.5/edit

It is the one fal model that takes a structural reference image *and* preserves layout at `input_fidelity: high`, so the styled output keeps every control on its blueprint box. The prompt restyles in place, keeps screens **empty** (so live content shows), and leaves slider channels **knob-free** (the knob is a live React element).

## Layout

```
src/
  App.tsx                     # skin selector + wireframe toggle + Composite
  template/
    schema.ts                 # Template / Region types (rect, kind, content, layer)
    winamp-layout.ts          # the canonical layout, authored once in px → normalized
  player/
    Composite.tsx             # reads template, positions sprites + live widgets
    usePlayer.ts              # all live player state (the dynamic half)
    Visualizer.tsx            # canvas spectrum analyzer (colors from skin CSS vars)
    data.ts                   # per-skin playlist content + EQ bands
    skins.ts                  # skin registry (which layers exist, baked flag)
  skins/
    player.css                # shared structure (positioning, sliders, wireframe)
    winamp.css / fallout.css / warcraft.css   # per-skin CSS (vars + effects)
generation/
  render_control.py           # template → neutral blueprint (control.png)
  generate.py                 # blueprint → styled frame.png per skin via fal
  template.json               # exported template (single source of truth for tooling)
public/skins/{id}/frame.png   # generated styled layers
```

Every skin also has a pure-CSS fallback (used when no `frame.png` is present), so the UI is always aligned and presentable even before generation.

## Tech

- Vite + React + TypeScript
- Python 3 + Pillow (blueprint render)
- fal.ai `fal-ai/gpt-image-1.5/edit` (layout-preserving restyle)
