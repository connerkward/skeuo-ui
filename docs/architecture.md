# Architecture — alignment by construction

> Deep-dive companion to the [README](../README.md). This is the "how it actually
> works" doc: the three composited layers and why the controls never drift out of
> the painted cavities.

skeuo-ui composites **three independent layers** live in React. The whole design
exists to make one guarantee: **the live controls and the painted device can never
disagree** — not because alignment is detected and repaired, but because it is true
*by construction*.

```
layer 1 — BODY (AI image)        → generation/wild_sculpt.py
layer 2 — CONTROL SPRITES        → generation/gen_sprites.py, gen_buttons.py
layer 3 — LIVE UI (React)        → src/player/*
```

## Layer 1 — the body (and why alignment is free)

Creativity and geometry are split at the right joint, so alignment is never
detected or repaired — it is true by construction:

1. **gpt-image-2 designs only a flat SILHOUETTE** (an easy, reliable ask; this is
   where the wild shape comes from). The prompt invites tall/narrow, squat/wide,
   asymmetric, angular or organic — not a generic blob.
2. **WE draw the interior deterministically INSIDE that exact mask** — screens and
   wells fitted band-by-band to the widest interior span — so every coordinate is
   known and everything fits the shape.
3. **Nano Banana paints the material** over the blueprint (layout-preserving).
   Reference-style images (`assets/refs/`) can ride along as extra `image_urls` to
   steer palette/material while the blueprint stays layout authority.
4. **The SAME mask becomes the alpha** — no BiRefNet, no holes, no guessing.
5. **The template is emitted from the drawn coordinates.**

Layout-FIRST variants (`radial` / `capsule` / `minimal`) invert steps 1↔2: the
arc-native template is drawn FIRST and the image model grows the creature AROUND
the wells (a `covers()` gate rejects bodies that don't fully contain the layout).

**Why it matters.** The old pipeline cut wild bodies with BiRefNet and parsed them
back with CV (`detect_wells.py`) — boxes landed ~5–10% off and read as broken UI.
`wild_sculpt.py` removes that whole class of bug: because WE draw the wells into the
mask and emit the template from those exact coordinates, the live controls and the
painted cavities cannot disagree. Sprites are mounted oversized (knob caps 116%,
molded faces 118% of their box) so the art seats INTO the painted rim instead of
floating in the cavity.

## Layer 2 — control sprites with states

Per style, baked as transparent RGBA:

- The **same flip switch rendered twice in one image** (lever down | lever up) and
  split → toggling swaps real art.
- A **cap-only circular knob** whose art rotates.
- A **fader cap**.
- **MOLDED transport faces** (`gen_buttons.py`): one sheet of five round buttons in
  the skin's own material, split by the column-alpha PROFILE (the valley between
  buttons) so a play button READS as a play button — robust even when organic
  styles bridge neighbours. `gpt-image-1.5`, transparent.

## Layer 3 — the live UI (the audible + visible half)

Recessed screens with live content: a canvas spectrum fed by the **real post-EQ
`AnalyserNode`**, marquee, clock, playlist; a RADIAL spectrum + center clock for
round dial screens; a circular SEEK ring (slider-arc); drag/touch interaction
(Pointer Events); and a generative WebAudio engine:

```
saw-chord pad → preamp → 10 peaking EQ bands → tilt → pan → volume → analyser
```

Volume / EQ / balance changes are **audible AND visible** in the spectrum.

## Layout grammars

One silhouette, many control arrangements — all fitted inside the mask, all gated so
screens stay readable:

| grammar  | shape it suits   | arrangement |
|----------|------------------|-------------|
| classic  | portrait         | stacked rectangles: visualizer · marquee · knobs+EQ · seek · playlist |
| hero     | portrait/tall    | one big center PLAY, small prev/stop/pause/next satellites |
| flank    | portrait         | knobs beside the visualizer like eyes; transport on a downward arc |
| orbit    | round torso      | round dial ringed by buttons (30–150°), knobs as eyes, seek ring on top |
| radial   | any (layout-1st) | orbit, drawn first; body grown around it |
| capsule  | squat/WIDE       | dial pod left, buttons fully ringing it, pill marquee sweeping right |
| minimal  | any (layout-1st) | sparse "now-playing puck": dial · seek · big PLAY+prev/next · one knob |

Transport buttons follow a size hierarchy (`BSIZE` — PLAY 1.5×, stop 0.82×) so a row
never reads as a uniform little grid; the button center stays on its ring, so varying
the diameter keeps it aligned.

## Source layout

```
src/
  template/winamp-layout.ts   canonical layout (one source of truth, px → normalized)
  player/
    Composite.tsx             template → regions; sprite components w/ CSS fallback
    usePlayer.ts              all state; every control binds to a real action
    useAudio.ts               WebAudio graph (the audible half)
    Visualizer.tsx            canvas spectrum (linear + radial dial mode)
    skins.ts                  registry: frame/sprites/template/molded per skin
  skins/*.css                 per-skin palettes + shared structure (player.css)
  skins/all.ts                barrel: every skin's CSS (shared by site + widget)
  platform.ts                 web-vs-Tauri branch (isWidget, redirectUri, openExternal)
  widget/WidgetApp.tsx        desktop widget: one transparent skin + tray-driven skin
  desktop/deeplink.ts         skeuo:// routing (skin handoff + OAuth callback) + drag
  desktop/DesktopHandoff.tsx  website "Open in desktop player" / "Download for Mac"
  spotify/                    PKCE auth + Web API + Playback SDK + useSpotify drive
src-tauri/                    Tauri shell: tauri.conf.json, src/lib.rs (tray+deeplink)
generation/
  wild_sculpt.py              silhouette → deterministic layout → paint → alpha
  gen_buttons.py              molded 5-button transport sheets (profile split)
  gen_sprites.py              knob/switch/fader sprites; generate.py = fal client
public/skins/<id>/            frame.png, sprites/, template.json
```
