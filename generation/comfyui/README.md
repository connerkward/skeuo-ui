# ComfyUI port of the wild_sculpt pipeline

A ComfyUI rebuild of the skeuo-ui body pipeline (`generation/wild_sculpt.py`)
using ComfyUI's **cloud API nodes** — the *same* models the fal pipeline uses,
so the look matches:

| skeuo step (wild_sculpt.py)            | fal model                              | ComfyUI API node                  |
|----------------------------------------|----------------------------------------|-----------------------------------|
| 1. silhouette                          | `openai/gpt-image-2`                   | `OpenAIGPTImage1` (model gpt-image-2) |
| 2. deterministic interior draw         | *pure Python (PIL) — not a node*       | fed in via `LoadImage` (the blueprint) |
| 3. layout-preserving material paint    | `fal-ai/gemini-3-pro-image-preview/edit` (Nano Banana Pro) | `GeminiNanoBanana2` (Nano Banana 2 / Gemini Flash Image) |

Step 2 (fit wells/screens into the mask, emit the template) stays in Python —
it's deterministic geometry, not a diffusion step. ComfyUI handles the two
generative ends; the blueprint PNG bridges them. A future build-out can wrap the
draw logic as a custom ComfyUI node for a single end-to-end graph.

## Files

- `workflow_silhouette.json` — stage 1: gpt-image-2 designs a flat silhouette.
  Verbatim `SIL_PROMPT`. `quality=low` (cheap); bump to `medium`/`high` for real bodies.
- `workflow_paint.json` — stage 3: Nano Banana paints a **real blueprint**
  (`_sculpt-fallout.png`) + a reference frame, preserving every well/screen.
  Verbatim `STYLE_PROMPT` + `MATERIAL['fallout']`. Output is directly
  comparable to `generation/_sculpt-fallout-out.png` (the fal baseline).
- `workflow_alpha.json` — stage 4: "the SAME mask becomes the alpha". **Pure
  native nodes, NO API/credits** — thresholds the blueprint's white background to
  a mask and joins it as alpha → an RGBA cutout (body+wells opaque, background
  transparent). Runs offline; verified working (`~/Desktop/cc-skeuo/`).
- `run.py` — headless runner: POST `/prompt`, poll `/history`, save outputs to
  `~/Desktop/cc-skeuo/`. Reads `COMFY_API_KEY` and passes it as
  `extra_data.api_key_comfy_org` (only needed for the cloud stages 1 & 3).

## Auth (one-time)

The API nodes bill **comfy.org credits** and need a Comfy API key (separate from
your fal/OpenAI keys — they route through comfy.org's proxy):

1. Create an account + add credits at <https://platform.comfy.org>.
2. Create a key at <https://platform.comfy.org/profile/api-keys>.
3. Put it in `~/dev/central/.env` (gitignored) as `COMFY_API_KEY=...` —
   **never** paste it into a terminal/chat.

(GUI alternative: Comfy Desktop → Settings → User → Sign in.)

## Run

```bash
cd generation/comfyui
python3 run.py workflow_silhouette.json     # stage 1 (cheap)
python3 run.py workflow_paint.json          # stage 3 (paints a blueprint)
```

Inputs for the paint workflow live in `~/ComfyUI-Shared/input/`
(`skeuo_blueprint_fallout.png`, `skeuo_ref_pipboy.png`). Comfy Desktop serves on
`http://127.0.0.1:8188` (override with `COMFY_SERVER`).

## Opening in the Desktop app

The `workflow_*.json` here are **API format** (for `run.py` / `/prompt`). To open
in the ComfyUI Desktop GUI, convert to UI-graph format first:

```bash
python3 to_ui.py workflow_paint.json ~/ComfyUI-Installs/Local/ComfyUI/user/default/workflows/skeuo_paint.json
```

Then in the app: **Workflows sidebar → skeuo_paint** (already done for paint/alpha/
silhouette). API-format files only load via **drag-drop onto the canvas**
(`loadApiJson`), not the sidebar — that's why a sidebar-opened API file looks empty.
Verified: the converted graphs load in the live frontend with correct widget values.
