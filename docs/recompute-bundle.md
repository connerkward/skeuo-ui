# Recomputable Generation Bundle — format spec

> One file per skin generation. Everything needed to **recompute and inspect** that
> generation travels inside it: the layered raster set as a multi-page TIFF, the
> generation metadata as embedded XMP. Subsumes the scattered `-paint.png`,
> `-frame.png`, `-template.json`, `-layout.json`, `-meta.json`, `-sprite-<bind>.png`
> sidecars in `public/generated/` into ONE artifact.

## Principle

Recompute > re-store. The bundle does not exist to hoard pixels — it exists so any
skin can be **re-derived** from pinned inputs (commit + model + request) and
**inspected** layer-by-layer without re-running anything. An artifact you can't
recompute is a dead end: when the pipeline changes, a loose `paint.png` with no
record of the prompt, template, key colour, or model that made it is unreproducible
and unfixable. Store the inputs and the intermediates that are expensive to
regenerate (the AI paint); derive the rest.

## Container — layered TIFF + XMP

Storage mechanism is the `comfyui-save-image-xmp` layered-TIFF format
(`save_layered_tiff_xmp.py`):

- **One multi-page TIFF.** Page 0 is the final composite/preview — what Finder,
  QuickLook and Preview.app render natively. Each subsequent page is one named layer.
- **Layer names via `PageName` (TIFF tag 285)**, written per page as
  `extratags=[(285, "s", 0, name, True)]`. Photoshop/Affinity open each page as a
  named layer.
- **XMP on page 0 only**, embedded as TIFF tag 700:
  `extratags.append((700, "B", 0, xmp_bytes, True))`.
- **Per-page compression varies** — the IFD carries its own compression tag, so the
  preview can be JPEG q90 while masks/sprites are lossless Deflate and any float map
  is uncompressed. (The current node writes `compression="deflate"`,
  `compressionargs={"level": 9}`, `predictor=2` uniformly; this spec asks the skeuo
  emitter to vary it per the manifest below.)
- `bigtiff=False`; layer-name list is mirrored into the XMP `comfy:layers` field.

## Layer manifest

Pages for a skeuo bundle, derived from the single-pass pipeline (`pipeline.ts` ->
`blueprint.ts` -> `cutoutClient.ts`). Sprite pages exist one-per control, keyed by
**region id** (`bindOf(r) = r.id`; unique within a template — `bind` is not, e.g.
six EQ bands all `bind:"eqBand"`).

| Page | `PageName` | What it is | Source today | Compression |
|---|---|---|---|---|
| 0 | `composite` | Final flattened skin (frame + seated sprites + live UI), the QuickLook face | React composite (no durable file today) | JPEG q90 |
| 1 | `blueprint` | Combined blueprint: device body + magenta/cyan socket rings + bottom strip cells | `combinedBlueprint().svg` rasterized (`blueprintPng`, not persisted) | Deflate |
| 2 | `paint` | Raw combined paint (device + strip), the AI output before any cut | `<id>-paint.png` | Deflate (lossless — recompute-critical) |
| 3 | `frame` | Cut device, transparent (colour-keyed body) | `<id>-frame.png` | Deflate (has alpha) |
| 4 | `alpha` | Device cutout alpha plane (`cutoutColorAware` output) | derived, not persisted | Deflate (1-channel) |
| 5…N | `sprite/<id>` | One bare control sprite per cut control | `<id>-sprite-<bind>.png` / `sprites/<bind>.png` | Deflate (alpha) |
| +1 | `align-debug` *(optional)* | Blueprint rings overlaid on the paint, for drift inspection | derived | JPEG q90 |

Real sprite page names for the common transport set: `sprite/prev`, `sprite/play`,
`sprite/play__pause` (the paired pause face), `sprite/next`, `sprite/stop`,
`sprite/volume`, `sprite/balance`, `sprite/seek`, plus `sprite/switch-off` /
`sprite/switch-on` when a toggle exists. Displays (`visualizer`, `marquee`, `time`,
`playlist`) are device-only — painted in place, never cut to a sprite page.

## XMP metadata schema

> **Wire-name caveat.** The reference repo's README documents the fields as `cfl:*`,
> but the **actual node code** (`save_image_xmp.py::_build_xmp`) emits prefix
> `comfy:` under namespace `urn:comfy:xmp:v1`, and the arbitrary-JSON field is
> `comfy:json` (the README's "`cfl:extra`"). This spec uses the **real wire names**
> and notes the README labels. (Reconcile the upstream README to match the code.)

The node's real XMP block (namespace `urn:comfy:xmp:v1`, prefix `comfy:`) carries:

| Wire field (code) | README label | skeuo content |
|---|---|---|
| `comfy:workflow` | `cfl:workflow` | request body + pipeline identity (skeuo commit, pipeline name) |
| `comfy:prompt` | `cfl:prompt` | the filled `PAINT_PROMPT` actually sent to the paint model |
| `comfy:models` | `cfl:models` | image model id `+ hash` (JSON array, mirroring `_collect_model_hashes`) |
| `comfy:json` | `cfl:extra` | the typed skeuo generation object (below) |
| `comfy:layers` | `cfl:layers` | comma-joined `PageName`s |
| `dc:creator` | `cfl:author` | author (e.g. `skeuo.fm`) |
| `xmp:CreateDate`, `xmp:CreatorTool` | — | ISO timestamp, `"skeuo.fm"` |

### `comfy:json` — the typed skeuo object

Stringified JSON; field names are the **real ones** from `api.ts` / `pipeline.ts` /
`director.ts` / `blueprint.ts`:

```json
{
  "bundle_version": 1,
  "skeuo_commit": "b3e4345",
  "pipeline": "single-pass-combined-blueprint",

  "request": {
    "prompt": "a fanged anglerfish jaw",
    "style": "biomech",
    "variant": "simple",
    "model": "fal-ai/gemini-3.1-flash-image-preview/edit",
    "refImage": null,
    "envelope": false,
    "regions": null
  },

  "director": {
    "materialPrompt": "wet chitinous biomech shell, sickly green-amber bioluminescence…",
    "font": "Nosifer",
    "name": "Angler Maw",
    "blurb": "Fanged jaw grown around the dial",
    "style": "biomech"
  },

  "keyColor": { "rgb": [0, 192, 208], "css": "rgb(0,192,208)", "phrase": "pure flat bright cyan (#00C0D0)" },

  "template": {
    "id": "angler-maw-simple-nano-banana-2-8hfm",
    "name": "wild-sculpt",
    "canvas": { "w": 1024, "h": 1536 },
    "regions": [ { "id": "play", "kind": "button", "bind": "play", "rect": {…}, "shape": "ellipse" } ]
  },

  "layout": {
    "devFrac": 0.755,
    "controls": [ { "bind": "play", "kind": "button", "rect": [0.41, 0.62, 0.13, 0.087] } ],
    "cells":    [ { "bind": "play", "kind": "button", "cellRect": [0.30, 0.78, 0.18, 0.13] } ]
  },

  "paint": {
    "model": "fal-ai/gemini-3.1-flash-image-preview/edit",
    "aspectRequested": "9:16",
    "resolution": "2K",
    "seed": null,
    "bankGate": { "enabled": true, "maxTries": 4, "model": "google/gemini-2.5-pro", "triesUsed": 2 }
  },

  "timingMs": { "envelope": 0, "paint": 41200, "total": 47880 },
  "createdAt": "2026-06-30T23:00:00+00:00"
}
```

`request`, `director`, `keyColor`, `template`, `layout`, `timingMs` are the literal
shapes of `GenerateRequest`, `Material`, `KeyChoice`, `Template`, `BlueprintLayout`
and `GenerateResult.timingMs`. `comfy:models` example:
`[{"name":"fal-ai/gemini-3.1-flash-image-preview/edit","sha256":""}]` — hosted, no
local weights, so the hash is empty (see Open questions).

## The recompute contract

To re-run a generation deterministically you must pin, and the bundle stores:

1. **`skeuo_commit`** — the pipeline version. `blueprint.ts`/`layouts.ts`/`pipeline.ts`
   geometry is the load-bearing truth; a different commit produces a different
   blueprint from the same request.
2. **The exact `model` id** — one of the three `MODELS` endpoints. Different endpoint
   => different paint.
3. **The full `request` body** — prompt, style, variant, regions, refImage.
4. **`materialPrompt`** and the **filled `PAINT_PROMPT`** — because the Director is
   itself nondeterministic (below), storing its output is what makes the paint step
   reproducible at all.

### Where determinism breaks today (be honest)

"Recompute" means **re-run the pinned pipeline**, NOT bit-identical pixels — unless
seed *and* model are fixed. The nondeterministic surfaces, all real:

- **The image model has no surfaced seed.** `falSubmit` sends `resolution` +
  `aspect_ratio` (gemini) or `image_size` + `quality` (gpt-image-2) — **no `seed`**.
  The gemini fal edit endpoints *do* accept an optional `seed`; surfacing it on
  `GenerateInput`, passing it in `falSubmit`, and storing it in `paint.seed` is
  **required for true reproducibility**. Until then the paint differs every run.
- **The bank-gate reroll** (`MAX_BANK_TRIES = 4`, gated by a Gemini 2.5 Pro vision
  consensus that is itself temperature-0 but fail-open) picks a different paint per
  run; only `triesUsed` is recorded, not which roll shipped.
- **The Director** (`deriveMaterial`) uses `Math.random` for the font-genre bucket
  and exemplar shuffle; `maybeCdScreen` flips a screen on `Math.random`;
  `layoutRandom` is fully `Math.random`. Storing the *outputs* (materialPrompt, font,
  final regions) sidesteps this — re-feed them instead of re-rolling.

So: a faithful recompute re-feeds `director` + `template` + `layout` + `paint.seed`
(once surfaced) and re-runs only the paint; a from-scratch recompute from `request`
alone will diverge.

## Versioning

`comfy:json` carries three identity fields, checked on read:

- **`bundle_version`** — this format's version (start at `1`); bump on any layer-set
  or field-shape change.
- **`skeuo_commit`** — the skeuo git SHA that produced it.
- **`pipeline`** — the pipeline identifier (`"single-pass-combined-blueprint"`),
  distinct from the legacy two-pass `generation/` lineage.

## Integration point

Emit the bundle **client-side, after the browser cutout completes** —
`finishCutoutFull` in `cutoutClient.ts`, once `frame` + every `sprites/<bind>.png`
exist. That is the **only** place the complete layer set is assembled: the
cut device frame and the per-control sprites exist **only in the browser** (the CF
Pages Function skips the cutout to avoid the CPU-1102 ceiling and returns the raw
combined paint + `layout`).

Tradeoff: the server *could* emit a **partial** bundle right after `generateSkin`
(blueprint + paint + template + layout + XMP — everything except frame/sprites/
composite), which is enough for recompute but not for full inspection. Recommended:
server writes the partial bundle as the durable record; the browser, after finalize,
**rewrites it with the cut layers appended** (page 0 composite, frame, alpha, sprite
pages). One file, completed in two phases — mirroring how `frame.png` +
`sprites/<bind>.png` are uploaded back via `/api/finalize/<id>` today. *Propose only;
do not implement here.*

## Open questions

- **Seed surfacing.** Surface + store the gemini fal `seed` so paint is reproducible;
  decide a default-seed policy (fixed vs. random-but-recorded).
- **Model hashing for hosted models.** fal/gemini weights aren't local, so
  `comfy:models` SHA256 is empty. Pin the endpoint id + any returned request/response
  id instead? Snapshot the model label + cost from `MODELS`?
- **Float layers.** Is the alpha plane / any future depth or drift map worth an
  uncompressed float page, or is 8-bit Deflate enough?
- **Where bundles live.** R2 (`skins/<id>/bundle.tiff`, replacing the sidecar fan-out)
  vs. local `public/generated/`. One bundle per generation, or per published skin only?
- **Composite page 0.** No durable flattened composite exists today (the skin is
  composited live in React). Bake one at finalize, or fall back to `frame.png` as the
  QuickLook face?
