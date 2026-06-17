# skeuo-ui "idea → skin" pipeline as a ComfyUI workflow

`skeuo-pipeline.comfyui.json` reproduces the four-stage image pipeline from
`src/generate/pipeline.ts` inside ComfyUI:

1. **Blueprint** — `LoadImage` of the wells-only control layout (controls on white).
2. **ENVELOPE pass** — fal `gemini-3-pro-image-preview/edit` grows a flat dark-gray
   body silhouette around the wells (`ENVELOPE_PROMPT`).
3. **PAINT pass** — same endpoint restyles the envelope into the chosen MATERIAL
   (`STYLE_PROMPT` + `MATERIAL[...]`).
4. **COMPOSITE** — paint × region alpha-mask → final RGBA `frame.png`.

Open it in ComfyUI with **Workflow → Open** (or drag the `.json` onto the canvas).

## Custom node pack to install

**[gokayfem/ComfyUI-fal-API](https://github.com/gokayfem/ComfyUI-fal-API)** — the
fal.ai node pack. Install via **ComfyUI Manager → Install via Git URL**, or:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/gokayfem/ComfyUI-fal-API
pip install -r ComfyUI-fal-API/requirements.txt
# restart ComfyUI
```

The two edit passes use the pack's **`Nano Banana Pro (fal)`** node
(`NanoBananaPro_fal`). **Nano Banana Pro IS Google's Gemini 3 Pro Image model =
`fal-ai/gemini-3-pro-image-preview`** — the exact endpoint `pipeline.ts` calls
(`const ENDPOINT = "fal-ai/gemini-3-pro-image-preview/edit"`). Its widgets are
pre-set to `resolution=2K`, `aspect_ratio=2:3`, `output_format=png` to match
`falSubmit()`.

The composite uses **ComfyUI core nodes only** (no extra install):
`LoadImage`, `ImageToMask`, `JoinImageWithAlpha`, `ImageBatch`, `SaveImage`.

## Set the FAL key

Either one (do this before launching ComfyUI):

```bash
export FAL_KEY=your_fal_key
```

…or edit `ComfyUI/custom_nodes/ComfyUI-fal-API/config.ini`:

```ini
[API]
fal_key = your_fal_key
```

Do **not** paste the key into the workflow JSON or commit it.

## What to edit before running

- **Node 2 (ENVELOPE) prompt** contains the literal placeholder `{brief}`.
  `pipeline.ts` substitutes it at runtime with the silhouette brief
  (e.g. `"a fanged anglerfish jaw"`). Replace `{brief}` with your own
  creature/object description.
- **Node 4 (PAINT) prompt** ends with `MATERIAL: ` + the **winamp** preset.
  The full set of MATERIAL strings (biomech / winamp / frog / wmp / halo) is in
  the "MATERIAL presets" Note node — paste a different one after `MATERIAL: ` to
  switch the skin.
- **Three `LoadImage` nodes** need real files: the wells-only blueprint (node 1),
  the region alpha mask (node 5), and — optionally — a reference-style image
  (node 3).

## Honest caveats / approximations

- **No node maps 1:1 to `…/edit` with a separate "primary image + N reference
  images" signature.** `NanoBananaPro_fal` takes a single `images` **batch**
  input, not the numbered `image_urls[0]=layout authority, [1..]=refs` array that
  `falSubmit()` sends. For the basic two-pass flow this is fine (one image in →
  one image out). To ride reference-style images along in the PAINT pass like
  `pipeline.ts` does, **un-mute** the `ImageBatch` (node 11) and the reference
  `LoadImage` (node 3), wire `envelope → ImageBatch.image1`, `ref →
  ImageBatch.image2`, and `ImageBatch → PAINT.images`. fal's edit endpoint treats
  the first image as the layout authority, so keep the envelope first in the batch.
- **Fallback node:** if `Nano Banana Pro (fal)` shows up red/"missing" (older pack
  version predating the gemini-3 / nano-banana-pro wave), update the pack. The
  equivalent fallback is **`Nano Banana Edit (fal)`** (`NanoBananaEdit_fal`), which
  takes the same `prompt` plus discrete `image_1..image_4` slots — that variant
  actually maps the "layout image + refs" idea more directly (image_1 = envelope,
  image_2.. = refs), at the cost of the `resolution`/`aspect_ratio` widgets that
  Nano Banana Pro exposes.
- **Composite differs in mechanism, not result.** `pipeline.ts` multiplies the
  paint by an 8-bit luminance alpha to make an RGBA PNG. Here, `ImageToMask`
  reads the mask PNG into a MASK and `JoinImageWithAlpha` attaches it as the alpha
  channel — same outcome (RGBA where mask=white is opaque, mask=black is
  transparent). The mask must match the paint's WxH (paint is 2K @ 2:3); add an
  `ImageScale` before `ImageToMask` if your mask differs.
- **No BiRefNet.** Like `pipeline.ts`, this uses a *constant* region mask rather
  than a learned background remover. If you'd rather auto-segment, replace nodes
  5–6 with a background-removal node (e.g. RMBG/BiRefNet) feeding its MASK into
  `JoinImageWithAlpha`.
- **Generation is queued/remote.** Each `NanoBananaPro_fal` node makes a real
  billed fal API call; expect a few seconds to a couple minutes per pass.

## Source of truth

Prompts and the MATERIAL table are copied **verbatim** from
`src/generate/pipeline.ts` (`ENVELOPE_PROMPT`, `STYLE_PROMPT`, `MATERIAL`). If the
pipeline's prompts change, re-copy them into the two `NanoBananaPro_fal` prompt
widgets and the "MATERIAL presets" Note.
