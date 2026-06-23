# Skin Generation & Alignment — State of the Art

**Last updated: 2026-06-23.** This is the canonical, current-best design for how a
generated skin is produced and how its controls are aligned. **Read this before
touching generation or alignment.** Several approaches were tried and rejected —
they're listed at the bottom *specifically so they are not re-attempted*. (Hours were
lost on 2026-06-23 reworking alignment that the VLM approach below already solved.)

Code lives on branch **`spritesheet-pipeline`** (tip `d88a4cc`); merging it to main is
the **#1 TODO**.

---

## The pipeline (this is the SOTA — build on this, don't replace it)

1. **Generation — ONE paint pass.** `combinedBlueprint()` (`src/generate/blueprint.ts`)
   builds a single blueprint: the device **body** (grown around fixed sockets) on top +
   a **strip of labeled control-part cells** on the bottom. ONE fal image-edit call
   (`PAINT_PROMPT`, `src/generate/pipeline.ts`) paints the whole thing → the device **and
   every button/knob/slider part in one image**. No separate envelope pass, no separate
   button generation. **One generative pass total.**

2. **Device cutout — BiRefNet.** `functions/api/cutout.ts` → `removeBackground()`
   (`fal-ai/birefnet/v2`), server-side (FAL_KEY never reaches the browser). Crops the
   device region, returns a transparent PNG. (Masking, not generation, ~$0.001.)

3. **Sprite cutting.** `src/generate/cutoutClient.ts` cuts each control part out of its
   strip cell (detect content bbox → centered square/band → circle/rrect clip) → per-skin
   sprite PNGs uploaded to `skins/<id>/sprites/<bind>.png`. Local canvas, no model calls.

4. **Alignment — VLM (gpt-4o vision). ← THE chosen approach.** Send the **device image**
   + the **template's control checklist** to **gpt-4o** and get back STRICT JSON of each
   control's box `{kind, x, y, w, h}` (normalized), then **snap each cut sprite onto its
   box**. This is already implemented offline in `generation/freeform.py` → `extract()`
   (the `EXTRACT_SYS` prompt + `gpt-4o` `chat/completions` with an `image_url`). Why it's
   right: **semantic** — it reads the painted ►/◄◄/VOL icons + labels, so identity is
   correct *by construction* (no nearest-neighbour mis-assignment); **one cheap call**;
   returns **center AND size**. **STATUS: proven offline, NOT yet ported to runtime.**
   To do: a server `/api/extract` (mirror `/api/cutout`, key server-side) that runs the
   `freeform.py extract()` call against the device + checklist, replacing the interim
   `cutoutClient.snapToSockets` heuristic.

5. **Render — per-skin sprites (Decision A).** `src/player/Composite.tsx` renders each
   generated skin's OWN cut sprites at the aligned coords (NOT the donor style's bundled
   sprites). `canvas` = the device frame's real dimensions (so the frame renders 1:1; no
   stretch). Per-skin sprite URLs via `src/player/skins.ts`.

---

## Locked decisions

- **A — generated skins render their own per-skin cut sprites** (the spritesheet
  approach), NOT main's donor-sprite path. Conner, 2026-06-23: "A is very important to me."
- **Alignment = gpt-4o VLM** (step 4) — NOT the dark-well heuristic, NOT SAM.
- **One generative pass** produces device + buttons together; everything after is masking
  + local compute + the single VLM align call.

---

## Rejected approaches — DO NOT re-attempt

- **Dark-well heuristic** (`cutoutClient.snapToSockets`: detect dark wells → global
  shortest-edge match → snap). Clean on good gens (`j4v9`/`xqeg`) but **flaky per
  generation** (depends on wells detecting cleanly; mis-sizes when a row member is missed).
  Interim only — to be replaced by the VLM (step 4).
- **SAM box-prompt (`generation/sam_snap.py`)** ported to runtime 2026-06-23 → **WORSE**.
  SAM merges/misses controls on AI-painted devices, and its mask order ≠ prompt order.
  Reverted (commits dropped from `spritesheet-pipeline`).
- **Zero-shot open-vocab segmentation** (SAM3 / Florence-2 / GroundingDINO). The ComfyUI
  seg bake-off concluded it **fails on stylized UI art** → per-slot needs prior-guided
  prompts. (Branch `comfyui-segtune` deleted; tip was `044310b` if the harness is ever
  wanted.)
- **Two-pass envelope + paint.** Collapsed into the single paint pass (step 1) for cost +
  coherence.

---

## Why this doc exists

2026-06-23: an agent reworked alignment for hours — reinventing the dark-well heuristic,
then swapping it for a worse SAM port — when `freeform.py`'s gpt-4o approach had already
solved it. Root cause: not searching the whole repo (`generation/`) + the docs before
building. The durable guard is `central/rules/discover-before-building-rule.md`. This doc
is the project-local half: **the alignment problem is solved (gpt-4o vision); the only
open work is porting `freeform.py extract()` into the runtime.**
