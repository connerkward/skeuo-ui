# 2026-07-07 — Dual-output button/socket region mask from the paint model

**Question.** Can a paint model output a reliable **region mask** — marking not just baked
buttons but the **knob sockets and sprite-strip cells** — *alongside* the painted skin, in a
single generation, so the runtime can cut each sprite and re-align it into its socket without
any separate detector?

Follow-on to the 2026-06-27 decision that **detection-snapping is rejected** (CV / gpt-4o /
SAM / Gemini all made alignment worse) and the 2026-07-01 decision to author layout as DATA.
This asks a different question: not "detect where the paint put things" (a VLM returning
coordinates — the rejected path) but "have the image model **paint a flat colour blob** over
each control in a companion panel" — a generative fill, which plays to an image model's
strength instead of a VLM's weakness.

## Method

- Model: **nano-banana-pro** (`fal-ai/gemini-3-pro-image-preview/edit`), `num_images: 1`.
- Blueprint = a **two-panel canvas**: LEFT column is the real combined blueprint (device with
  colour-ring control guides + a sprite strip); RIGHT column is pure black (the mask target).
  The model fills both, told to keep the layout identical so the panels overlay.
- **Joint** (the one being evaluated): paint + mask come from ONE generation (the two panels).
- **Separate** (control): take the joint's painted panel, feed it back alone, ask for the mask
  → tests post-hoc segmentation by the same model (the "detection" shape, but as colour-fill).
- Region extraction: nearest-target-colour assignment per pixel + 2–98 percentile bbox
  (robust to bleed), split device-socket vs strip-cell by y.
- Every mask composited 50 % over its paint to verify each blob lands on its control.

Progression of hardness (each a real fal generation):

| Run | Buttons | Result |
| --- | --- | --- |
| clean | round, distinct icons, tidy row | both joint & separate align |
| coloured molded | non-circular facets, painted in guide colours | both align — but colour is a cue (confound) |
| **monochrome molded** | non-circular facets in the **body material**, icon+relief only | **both still align** — the real test |
| **4K + full sprite sheet** | monochrome + knob sockets + seek + toggle, mask marks all | joint marks all 8 targets, aligned |

## Results

- **A paint model CAN output a reliable region mask.** Even on wild-organic bodies with
  **non-circular, monochrome, molded-into-body facets** (a chrome button on a chrome body,
  distinguished only by embossed icon + relief), both the joint and separate masks land on
  every control, and the blob **shapes** track the facet silhouettes (the play lobe's notch
  shows up in the mask).
- **Why it works where detection failed:** the ask is a **generative colour-fill** (paint a
  blob on the control), not numeric bounding boxes (gpt-4o 7/16, SAM 1/10 in the rejected
  era). Reframing the task + a far stronger model flips the outcome.
- **The mask carries full sprite alignment.** In the 4K run the mask marks 4 button facets +
  **2 knob sockets on the device** + **2/4 strip cells**, colour-keyed so each cap cell shares
  its socket's colour (green = volume, cyan = balance, orange = seek, pink = toggle). That is
  everything a runtime needs to cut a sprite from the sheet and seat it into its socket —
  proven by the interactive chain view (sprites cut client-side from the raw paint via the
  mask regions, knobs rotate under a pinned specular).
- **PAINT must be monochrome.** First 4K run painted the sockets/parts in the guide colours
  (unreadable, and a cue that inflated the separate pass). Forcing "buttons molded, sockets =
  neutral dark wells, parts in the body material — NONE of the guide colours in the paint;
  colours appear ONLY in the mask" gives the correct integrated look and a fair test.

### Cost (verified against live fal pricing, 2026-07-07)

| Approach | Images billed | $ (nano-pro) | Notes |
| --- | --- | --- | --- |
| **Joint, one canvas** | 1 | **$0.15** | mask is $0 extra — rides the same generation |
| Separate 2nd pass | 2 | $0.30 | full-res paint, mask re-derived (2×) |
| `num_images: 2` | 2 | $0.30 | bills per image → 2× |

- fal bills **flat per image**, resolution-independent. At the **same** resolution setting the
  joint device is ~half a standalone paint's pixels (it shares the canvas), **but** requesting
  **4K** recovers it for the same $0.15: measured device half **2304×3712 ≈ 8.5 MP vs a
  standalone 2K paint's ~4.3 MP**. So the split costs latency, not dollars or resolution.

## Verdict

- **Adopt the JOINT one-canvas approach at 4K** if a model-generated region mask is wanted:
  one $0.15 generation yields paint + sprite sheet + a mask that marks every button, knob
  socket, and sprite cell, colour-keyed for cut-and-place. It never re-identifies (it's told
  the layout), so it's robust; the separate pass is a proven fallback at 2× cost.
- This does **not** overturn 2026-06-27 (detection-snapping rejected). Placement is still
  authored-by-construction; this is an *optional* model-emitted mask for capturing the painted
  reality (drift-tracking + sprite-socket alignment), reframed as generative fill.
- **Honest bounds:** clean 4-control layouts with crisply-embossed icons; n small; subtle/worn
  icons or denser layouts untested.

## Pipeline changes shipped this session (commit d559145)

Two fixes surfaced while running this:

1. **`pickKeyColor` silver→dark backdrop.** A silver/light material that also mentioned a dark
   keyword matched both regexes and fell to neutral **grey** — low contrast, worse BiRefNet
   matte on a silver body. Now counts light vs dark hits and picks the **contrasting** backdrop
   of the dominant lightness (translucent/iridescent still keep grey).
2. **No enclosed transparent regions.** `cutoutAlpha` fills enclosed interior holes as opaque
   (so wells don't punch through), which also killed genuine see-through gaps. Added a
   `PAINT_PROMPT` clause forcing a single solid silhouette — negative space must open to the
   outer edge; a fully-surrounded hole is forbidden.

## Artifacts

- 4K joint (paint + sprite sheet + socket/cell mask): `assets/2026-07-07-mask-4k-joint.png`
- 4K mask ⊕ paint overlay (all 8 targets aligned): `assets/2026-07-07-mask-4k-overlay.png`
- Monochrome molded facets (the hard test): `assets/2026-07-07-mask-monochrome-molded.png`
- Clean baseline: `assets/2026-07-07-mask-clean-joint.png`
- Interactive chain view + all runs: served from `/private/tmp/skeuo-maskexp/` (interactive.html
  cuts sprites from the raw paint via the mask regions and makes them live).

![4K joint — paint + sprite sheet + region mask](assets/2026-07-07-mask-4k-joint.png)
![Mask overlaid on the paint — all 8 targets land](assets/2026-07-07-mask-4k-overlay.png)
