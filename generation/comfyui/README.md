# skeuo.fm skin pipeline → ComfyUI (local, free BiRefNet cutting)

`skeuo-pipeline.workflow.json` is a ComfyUI **API-format** workflow that ports the
runtime skin-generation pipeline (`src/generate/pipeline.ts` → `generateSkin`) to
local ComfyUI nodes, centered on the **BiRefNet** background-removal / control-cutting
that the fal pipeline pays for at `fal-ai/birefnet/v2`. Those cut stages now run
**locally and free** via the installed `RembgByBiRefNet` node.

> Why this exists: the project's fal balance is exhausted. The cutting half of the
> pipeline (stages 3–4) maps cleanly onto local ComfyUI and is the expensive part to
> run repeatedly. This workflow does that half for $0. The generative half (stages 1–2)
> can't run locally on this box's installed models — see "Honest gaps" below.

This **supersedes** the older `skeuo-pipeline.comfyui.json` / `workflow_paint.json` /
`workflow_silhouette.json` in this dir, which wired the *paid* fal cloud-API nodes
(`NanoBananaPro_fal`) for the deprecated envelope+paint pipeline. Those are left in
place for reference but are not the local-free path.

## Validation

Validated against the **live running ComfyUI** via the MCP `validate_workflow` tool:

```
{ "valid": true, "errors": [], "warnings": [], "nodeCount": 23,
  "nodeTypes": ["LoadImage","LoadRembgByBiRefNetModel","ImageCrop","RembgByBiRefNet","SaveImage"] }
```

All 5 node types are recognized by the running server. `RembgByBiRefNet` is from the
installed custom pack **`ComfyUI_BiRefNet_ll`** (lldacing); the model
`General.safetensors` (424 MB) is present at
`~/ComfyUI-Installs/Local/ComfyUI/models/BiRefNet/General.safetensors`.

(`validate_workflow` confirms node types, wiring, and required inputs. It does NOT
run the graph — proof the cut is correct still requires running it and looking at the
output PNGs per the repo's verify-outputs rule. This deliverable is the *valid wired
graph*, not a verified render; see "Run it" + "Not yet verified".)

## Pipeline stage → ComfyUI node map

| # | pipeline.ts stage | ComfyUI node(s) | maps how |
|---|---|---|---|
| 1 | **Blueprint** (procedural SVG: device 2:3 + magenta-ringed sockets on top, bare-control strip below, packed to 9:16) — `combinedBlueprint` | `LoadImage` (node `10`) | **Adapted/placeholder.** SVG raster is deterministic geometry, not a diffusion step; ComfyUI has no SVG drawer. The blueprint is produced outside Comfy (resvg) and is implicit in the loaded paint. |
| 2 | **PAINT** restyle blueprint → finished product render — fal `gemini`/`gpt-image` edit | `LoadImage` (node `10`, same input) | **Gap — see below.** No local SD/SDXL/Flux checkpoint is installed, so an img2img/ControlNet restyle isn't possible without downloading weights. Node `10` loads the *already-painted* combined image so the local cutting (3–4) runs on it. |
| 3 | **DEVICE CUTOUT** — BiRefNet the device region → transparent `frame.png` (`removeBackground` → fal-ai/birefnet/v2) | `ImageCrop` (`30`, top 1024×1536) → **`RembgByBiRefNet`** (`31`, model from `20`) → `SaveImage` (`32`, `skeuo/frame`) | **1:1, local + free.** `RembgByBiRefNet` = the same BiRefNet model class the fal node runs, here on local MPS/CPU. |
| 4 | **CONTROL ISOLATION** — BiRefNet the strip → transparent strip → crop each control cell → per-control sprites (`cutFromTransparentStrip`) | `ImageCrop` (`40`, bottom 1024×284) → **`RembgByBiRefNet`** (`41`) → 8× `ImageCrop` (`50/52/…/64`, one per cell) → 8× `SaveImage` (`51/53/…/65`, `skeuo/sprites/<bind>`) | **1:1, local + free.** Strip is BiRefNet'd ONCE (matches the code), then each cell is cropped from the transparent strip by its pixel rect. |

Shared: `LoadRembgByBiRefNetModel` (node `20`, `General.safetensors`, device `AUTO`,
`float32`) loads the BiRefNet model once and feeds both rembg nodes (`31`, `41`).

## Geometry (baked from the real constants)

Computed from `GEN_W=1024`, `GEN_H=1536`, `PAINT_ASPECT=9/16` exactly as
`blueprint.ts` does, so the crops line up with what the painter produced:

```
COMBINED_H = round(1024 / (9/16)) = 1820     # combined paint is 1024 × 1820 (9:16)
DEVICE_H   = min(1536, 1820 - round(1820*0.14)) = 1536   # device 2:3
STRIP_H    = 1820 - 1536 = 284               # control strip
DEVICE_FRAC = 1536/1820 = 0.844

device crop : x=0  y=0     w=1024 h=1536
strip  crop : x=0  y=1536  w=1024 h=284
```

The 8 strip cells (this representative strip exercises every sprite kind:
4 transport buttons + a knob + a slider thumb + a toggle off/on pair) use the SAME
`combinedBlueprint` cell formula (`cellW = GEN_W/n`, `cw = cellW*0.92`,
`y = GEN_H + STRIP_H*0.04`, `h = STRIP_H*0.78`), expressed in **strip-local** pixels
(after the strip crop, so y is relative to the 284-px strip):

| cell | bind        | x   | y  | w   | h   |
|------|-------------|-----|----|-----|-----|
| 1    | prev        | 5   | 11 | 118 | 222 |
| 2    | play        | 133 | 11 | 118 | 222 |
| 3    | next        | 261 | 11 | 118 | 222 |
| 4    | stop        | 389 | 11 | 118 | 222 |
| 5    | vol (knob)  | 517 | 11 | 118 | 222 |
| 6    | seek (slider)| 645| 11 | 118 | 222 |
| 7    | switch-off  | 773 | 11 | 118 | 222 |
| 8    | switch-on   | 901 | 11 | 118 | 222 |

**If your skin's strip has a different control set / count**, recompute the cells:
`cellW = 1024 / n`, then for cell `i`: `x = round(i*cellW + cellW*0.04)`,
`w = round(cellW*0.92)`, `y = 11`, `h = 222`. Update the 8 `ImageCrop` cell nodes
(`50…64`) to match `n` (add/remove cell+SaveImage pairs). The cleaner long-term move is
to emit this workflow programmatically from `layout.cells` rather than hand-editing.

## Run it

1. **Drop your painted combined image** into the ComfyUI input dir as
   `skeuo_paint_combined.png`:
   `~/ComfyUI-Installs/Local/ComfyUI/input/skeuo_paint_combined.png`
   (it must be the 1024×1820 combined paint: device on top, control strip below).
   Until fal credits return, you can hand-paint / use any image-edit tool to produce
   this from the blueprint — the workflow only does the *cutting*.
2. Load `skeuo-pipeline.workflow.json` — API format, so **drag-drop it onto the
   ComfyUI canvas** (`loadApiJson`); the sidebar "open workflow" expects UI-graph
   format and will look empty. Or run it headless with the sibling `run.py`
   (`python3 run.py skeuo-pipeline.workflow.json`).
3. Queue. Outputs land in the ComfyUI output dir:
   `skeuo/frame_*.png` (transparent device) and `skeuo/sprites/<bind>_*.png` (8 sprites).

The first run loads the 424 MB BiRefNet model (a few seconds on MPS). `device:"AUTO"`
uses MPS/GPU; switch node `20` to `CPU` if MPS OOMs.

## Honest gaps — what does NOT run locally, and why

- **Stage 1 (SVG blueprint):** ComfyUI has no node that rasterizes the project's SVG
  control map. It's deterministic geometry (`combinedBlueprint` → resvg), so it stays
  in TS/Python; ComfyUI consumes its PNG. Not a loss — it was never a model step.
- **Stage 2 (PAINT restyle):** **This is the real gap.** `list_models` on the running
  server shows only `sam3.1_multiplex_fp16.safetensors` (a SAM checkpoint) and a
  `pixel_space` VAE — **no SD/SDXL/SD3/Flux checkpoint**, so there's no installed model
  to do a layout-preserving img2img/ControlNet restyle. Options to close it, in order:
  - Restore fal credits and keep the paint on `gemini`/`gpt-image` (best quality, what
    the SOTA writeup chose), then cut locally with this workflow.
  - Install a local checkpoint (e.g. a Flux/SDXL + an img2img or Flux-Kontext / ControlNet
    edit graph) and prepend it before node `10`. The running server *does* expose
    `FluxKontextImageScale` and the partner edit nodes, but those need weights/credits
    not present here, so wiring them now would validate-then-fail at runtime — left out
    deliberately rather than claimed.
  - Hand-produce the paint and drop it in as in "Run it" above (zero-cost stopgap).
- **VLM align (`snapToVLM`, gpt-4o):** optional polish in the runtime that nudges
  control rects to their painted positions. Not ported — it's a hosted-LLM call, not a
  ComfyUI image op, and the SOTA writeup treats the repacked template as the
  load-bearing baseline with the VLM as optional. The local cut uses the deterministic
  cell rects (the clean baseline), which is the recommended default anyway.

## Not yet verified (do this before trusting it)

`validate_workflow` proves the graph is **wired correctly and runnable**; it does not
prove the **cut is good**. To actually verify per the repo's verify-outputs rule:
run the graph on a real painted combined image and open `skeuo/frame_*.png` and the
8 `skeuo/sprites/*` — confirm the device is cleanly keyed and each sprite is the bare
control with no neighbour bleed / no white halo. That run needs a real stage-2 paint as
input, which is the gap above; it has **not** been executed here, so no "works" claim is
made about the rendered output — only that the workflow validates against the live server.
