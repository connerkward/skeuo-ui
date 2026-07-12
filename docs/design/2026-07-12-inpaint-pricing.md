# Inpaint-repair pricing — Vertex vs fal vs local LaMa (2026-07-12)

> **Post-bakeoff correction, fixed same day:** the bake-off
> (`docs/experiments/2026-07-12-inpaint-bakeoff.md`) found that §1's $0.136/repair estimate
> below was never actually being paid — `genskin.py:edit_vertex()` hardcoded
> `imageConfig.imageSize: "4K"` on every call, so every real `erase12.py` crop repair landed
> in the 4K tier ($0.241/repair) regardless of the crop's small (~280-400px) actual size.
> Fixed in `genskin.py:edit_vertex()` (now takes an `image_size` param, default `"4K"` so
> full-canvas callers are unaffected) + `erase12.py:erase_model()` (now picks `"2K"` for any
> crop ≤2048px, `"4K"` only above that). Live-confirmed same day: a real repair call's
> `usageMetadata.candidatesTokenCount` came back **1120** (the 1K/2K tier), not 2000 (4K) —
> so §1's original $0.136/repair figure is now what's actually billed, not $0.241.

## Question

The crop-repair step (erase baked defects — a stray handle, socket residue, a kept guide
ring — from an already-painted 4K skin) currently runs through Vertex `gemini-3-pro-image`
edit on a square crop (~800-1400px around the defect), instructed e.g. *"remove the handle,
continue the channel's carved material seamlessly,"* composited back. Is that the right
model for this job, at today's volume and at seed-mining volume?

All prices below are **live-pulled** (fal MCP `get_pricing`/`get_model_schema`, Google's own
pricing pages) on 2026-07-12, not quoted from memory — see Sources.

## 1. Current path — Vertex `gemini-3-pro-image`, priced exactly

Vertex/Gemini image pricing is **token-based, not per-image**, confirmed identically on two
independent Google sources:

- Input image: **560 tokens** @ $2.00/1M tokens → **$0.00112/input image**
- Output image, **1K–2K tier (1024×1024 to 2048×2048px)**: **1120 tokens** @ $120/1M tokens →
  **$0.134/output image**
- Output image, 4K tier: 2000 tokens → $0.24/output image
- Text prompt tokens (the repair instruction, ~50-150 tokens): negligible, ~$0.0002-0.0003

A ~1024² crop lands squarely in the 1K–2K tier (that tier is flat from 1024 up to 2048px, so
an 800-1400px crop costs the same as a full 2048px one). **Total per repair ≈ $0.00112
(input) + $0.134 (output) + ~$0.0003 (instruction text) ≈ $0.136/repair.**

**This is higher than the $0.05-0.10 range assumed going in.** The 1K/2K tier is a flat
$0.134 regardless of exact resolution inside that bucket — there's no way to land in a
cheaper bucket at 1MP; only dropping under 1024px on either side (not offered as a discrete
tier) or accepting 4K-tier pricing changes it. Flagged per `verify-external-claims-rule` —
don't carry the $0.05-0.10 figure forward.

Sources: [Vertex AI Generative AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing),
[Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) (both show the same
$120/1M output-image-token rate and the 1120-token/1K-2K, 2000-token/4K table).

## 2. fal-hosted inpaint/eraser inventory (live, fal MCP)

Searched `search_models` for "inpaint", "eraser object removal", "fill mask", "edit mask
image", "kontext", plus targeted lookups for ideogram/recraft/sdxl. Every price below is a
direct `get_pricing` call; mask/prompt support confirmed via `get_model_schema` (not
inferred from the description).

| Model | Endpoint | Price | Unit | Mask input | Text prompt | Notes |
|---|---|---|---|---|---|---|
| Z-Image Turbo Inpaint | `fal-ai/z-image/turbo/inpaint` | **$0.01** | /MP | ✅ required | ✅ required | Cheapest mask+prompt option. 6B fast model (Tongyi-MAI), 8-step default. |
| Qwen Image Edit Inpaint | `fal-ai/qwen-image-edit/inpaint` | **$0.03** | /MP | ✅ required | ✅ required | `strength` param (default 0.93) controls how much of the masked region is re-noised — tunable toward conservative local repair. |
| Ideogram V3 Edit | `fal-ai/ideogram/v3/edit` | **$0.03** | /image (flat) | ✅ required | ✅ required | Flat per-image, not per-MP — cheaper than MP-priced models above ~1MP. |
| Bria GenFill v2 | `bria/genfill/v2` | **$0.04** | /MP | ✅ required | ✅ (`instruction`) | "Optimized to work seamlessly with blob-shaped masks" — good fit for our roughly-blob defect masks. Licensed-data-only training (commercial-safe). |
| Bria Eraser | `fal-ai/bria/eraser` | **$0.04** | /generation | ✅ required | ❌ none | Pure object-removal — no instruction field, so "continue the channel's carved material" can't be steered; relies entirely on the model's own scene reconstruction. |
| Finegrain Eraser | `fal-ai/finegrain-eraser/mask` | **$0.045** | /image (flat) | ✅ required | ❌ none | Removes object + shadows/reflections, "seamlessly reconstructing the scene" — no prompt either; `mode: express/standard/premium` trades quality for cost (price shown is the flat listed rate; premium likely higher, unconfirmed). |
| FLUX.1 Kontext-LoRA Inpaint | `fal-ai/flux-kontext-lora/inpaint` | **$0.035** | /MP | ✅ required | ✅ required | |
| FLUX.1 Dev Fill w/ LoRA | `fal-ai/flux-lora-fill` | **$0.035** | /MP | ✅ (implied by Fill family) | ✅ required | |
| FLUX.1 Pro Fill | `fal-ai/flux-pro/v1/fill` | **$0.05** | /MP | ✅ required | ✅ required | Highest-quality FLUX mask-fill; `enhance_prompt` option. |
| FLUX.1 General Inpainting | `fal-ai/flux-general/inpainting` | **$0.075** | /MP | ✅ required | ✅ required | FLUX dev + ControlNet/LoRA/IP-Adapter stack — most flexible, priciest of the FLUX family. |
| SDXL Fast Inpainting | `fal-ai/fast-sdxl/inpainting` | $0.00125 | /compute-second | ✅ required | ✅ (SD-family) | Priced by compute time, not flat/MP — roughly $0.003-0.006/image at typical 2-5s SDXL inference, but not a fixed number; oldest/weakest model of the set. |
| FLUX.1 Kontext [pro] | `fal-ai/flux-pro/kontext` | $0.04 | /image (flat) | ❌ **no `mask_url` param** | ✅ required | Full-frame prompt edit only (same class as nano-banana) — listed for comparison, **not mask-conditioned**, so it can't be scoped to just the defect region; the whole crop gets reinterpreted. |

Full raw pricing/schema dumps came from `mcp__fal-ai__get_pricing` and
`mcp__fal-ai__get_model_schema` calls against each endpoint above, 2026-07-12.

## 3. Local floor — LaMa (MPS, $0 marginal)

**LaMa** (advimman, WACV 2022) — Fourier-convolution large-mask inpainting, open weights,
runs on Apple-Silicon MPS via PyTorch. **$0/repair**, no API, no rate limit, per
`prefer-local-inference-rule`.

- Original repo: [github.com/advimman/lama](https://github.com/advimman/lama)
- Easiest local wrapper (HF Hub weight pull, few lines of code, CPU/GPU incl. MPS):
  [github.com/okaris/simple-lama](https://github.com/okaris/simple-lama)
- Open weights on HF: [huggingface.co/opencv/inpainting_lama](https://huggingface.co/opencv/inpainting_lama)
  (ONNX), [huggingface.co/michaelgold/big-lama](https://huggingface.co/michaelgold/big-lama)
  (safetensors)

**Critical limitation:** LaMa is **not prompt-conditioned** — it has no text input at all. It
can't be told "continue the channel's carved material" as an instruction; it purely
extrapolates the masked region from surrounding pixel statistics (texture synthesis /
structural continuation). This is a feature for style-match (see §4) but means it only works
when the mask is small relative to visible undamaged context around it, and fails on defects
requiring semantic/geometric reconstruction (e.g. redrawing a socket's rim curvature that
isn't visible anywhere in the unmasked crop).

## 4. Comparison table — condensed

| Model | $/repair @ ~1MP crop | Mask-conditioned | Prompt/instruction | Style-match risk vs. nano-banana paint |
|---|---|---|---|---|
| **LaMa (local)** | **$0** | ✅ | ❌ (none — pure texture extrapolation) | **Lowest** — not a foreign "painter," literally repeats local pixel statistics. Best on flat/repetitive material; unreliable on complex geometric edges (bezels, multi-highlight chrome) not visible in the unmasked crop. |
| Z-Image Turbo Inpaint | $0.01 | ✅ | ✅ | High — 6B fast diffusion model, different rendering pipeline than Gemini's painterly style; visible seam likely on ornate/textured material, probably fine on flat/simple. |
| Qwen Image Edit Inpaint | $0.03 | ✅ | ✅ | Medium-high — same reasoning; `strength` param gives some control over how much gets regenerated (lower strength = more conservative, closer to source texture). |
| Ideogram V3 Edit | $0.03 (flat) | ✅ | ✅ | Medium-high — Ideogram's house style (crisp typography/graphic-design bias) is a different aesthetic register than a painterly skeuomorphic render. |
| Bria GenFill v2 | $0.04 | ✅ | ✅ (`instruction`) | Medium — blob-mask-optimized, licensed-data trained; still a foreign diffusion model, foreign style priors. |
| Bria Eraser | $0.04 | ✅ | ❌ | Medium — no instruction means no control over HOW the channel gets rebuilt, just that the object is gone; risk it fills with a plausible-but-wrong material instead of matching the specific carved groove. |
| FLUX Kontext-LoRA / Dev Fill | $0.035 | ✅ | ✅ | Medium — FLUX's rendering has a distinct "clean CG" look vs Gemini's painterly output; more visible on ornate chrome/knurling. |
| FLUX Pro Fill | $0.05 | ✅ | ✅ | Medium — best FLUX-family quality, same style-family risk as above. |
| **Vertex `gemini-3-pro-image` (current)** | **$0.136** | via crop+recomposite (no native mask param — the "mask" is implicit in what's cropped) | ✅ | **Lowest of the AI models** — literally the same model/checkpoint that painted the skin, continuing its own work. Style-match risk is structural, not model-family. |
| FLUX Kontext [pro] (no mask) | $0.04 (flat) | ❌ | ✅ | High — reinterprets the WHOLE crop, not just the defect region; highest risk of drifting unrelated detail even if style matched. |

Qualitative reasoning, not measured: style-match risk is inferred from each model's known
rendering family (diffusion architecture + training-distribution "look") relative to
Gemini's painterly output, not from a side-by-side render — this is exactly what the bake-off
in §6 would settle empirically.

### Volume cost at a 15-skin batch

- **(a) today, ~0.3 repairs/skin → 4.5 repairs/15-skin batch:**
  - LaMa: **$0**
  - Z-Image Turbo: $0.045
  - Qwen Inpaint: $0.135
  - Bria GenFill: $0.18
  - FLUX Pro Fill: $0.225
  - Vertex (current): **$0.612**
- **(b) seed-mining, 10-30 repairs/batch** (reading the given figure as already batch-scoped,
  not per-skin — see note below):
  - LaMa: **$0**
  - Z-Image Turbo: $0.10 – $0.30
  - Qwen Inpaint: $0.30 – $0.90
  - Bria GenFill: $0.40 – $1.20
  - FLUX Pro Fill: $0.50 – $1.50
  - Vertex (current): **$1.36 – $4.08**

Note on scenario (b)'s units: the brief gives "10-30 repairs/batch" directly, so it's taken
as already describing a full batch (e.g. heavy seed-mining on a handful of stubborn controls
across the roster), not per-skin. If it were meant per-skin (×15), all figures above scale
by up to 15× and the case for a cheap tier strengthens considerably — worth confirming before
acting on this.

## 5. Recommendation

**Don't build a router yet.** At scenario (a) — today's actual volume — the entire batch
costs $0.61 on the current all-Vertex path. That's noise; the engineering cost of adding
routing logic (a "how ornate is this defect" classifier, two code paths, two failure modes to
maintain) exceeds the savings. Per `restraint-rule`: no build without a present, not
speculative, purpose.

**Do add a free LaMa pre-pass once scenario (b) volume actually materializes.** At 10-30
repairs/batch, Vertex-only costs $1.36-$4.08/batch — real money if seed-mining becomes a
regular workflow. LaMa costs literally nothing and, per §4, is *lowest*-risk on exactly the
case that dominates simple/flat-channel repairs (no foreign-model style to clash with — it's
pixel-statistics continuation, not a repaint). The natural shape, reusing the pipeline's
existing gate infrastructure (`placement-invariants-rule`'s verify-in-DOM discipline already
requires a real inspection step per repair):

1. **Tier 0 — LaMa, local, $0.** Attempt every repair here first.
2. **Gate the output** — a cheap automated check (edge/texture continuity heuristic, or a
   ~$0.01 VLM judge call per `verify-outputs-rule`'s two-stage crop+VLM discipline) decides
   PASS/FAIL. LaMa should clear most flat-channel, simple-geometry repairs.
3. **Tier 1 fallback — Vertex `gemini-3-pro-image` crop (current path), $0.136/repair,**
   reserved for LaMa-FAIL cases: ornate/multi-highlight material, or defects whose repair
   needs semantic reconstruction LaMa can't do (no visible undamaged reference nearby).

This keeps the current, proven, lowest-style-risk path as the fallback rather than replacing
it, and only pays for it on the harder subset. A middle fal tier (Z-Image Turbo or Qwen
Inpaint, both prompt-capable and 4-13× cheaper than Vertex) is a plausible tier-1.5 for
"simple but not LaMa-clean" cases, but adding it before the bake-off below would be guessing
at a threshold with no evidence.

### What a ~$1 bake-off would need to settle it (spec only — not run)

1. **Pull ~10 real crops** from actual detected defects already in the pipeline (seek
   grooves, sockets), spanning both flat/simple material and ornate/complex material —
   reuse crops the existing detector already produces, don't synthesize new ones.
2. **Run each crop through:**
   - LaMa (all 10, $0)
   - Z-Image Turbo Inpaint (all 10, ~$0.10 at 1MP)
   - Qwen Inpaint (all 10, ~$0.30 at 1MP)
   - Vertex `gemini-3-pro-image` (a 4-crop subset only, to stay near budget: ~$0.54)
   - Total: ≈ $0.94, under the $1 cap.
3. **Judge with the project's existing verify discipline**, not a new one: per
   `verify-outputs-rule` §1b / `label-overlays-rule`, crop each seam at 3-5× and run the
   independent VLM cross-check, scored per-repair on (1) defect fully removed, (2)
   material/texture continuity at the seam, (3) no new artifacts introduced. Adjudicate any
   VLM MISPLACED/FAIL claim against the actual pixels before trusting it — same rule as
   placement checks.
4. **Decision rule:** if LaMa clears ≥50% of the flat-channel subset at PASS, ship the tier-0
   pre-pass. If a cheap fal model's cost-adjusted pass-rate beats Vertex specifically on the
   flat/simple subset, promote it to tier-1 ahead of Vertex; keep Vertex as the final tier for
   the ornate subset and everything tier-0/1 failed, exactly matching `fix-generalizable-rule`
   (a pipeline-level routing rule, not a per-skin patch).

## Sources

- [Vertex AI Generative AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing) — Gemini 3 Pro Image token rates, 1K/2K/4K tiers.
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) — cross-check, same rates.
- fal MCP `search_models` (queries: "inpaint", "eraser object removal", "fill mask", "edit mask image", "kontext", "ideogram inpaint edit", "recraft inpaint") — live catalog, 2026-07-12.
- fal MCP `get_pricing` per endpoint listed in §2 table — live prices, 2026-07-12.
- fal MCP `get_model_schema` per endpoint listed in §2 table — live input-param inventory (mask/prompt support), 2026-07-12.
- [LaMa (advimman/lama)](https://github.com/advimman/lama) — original repo, WACV 2022.
- [simple-lama (okaris)](https://github.com/okaris/simple-lama) — local HF-Hub wrapper.
- [opencv/inpainting_lama](https://huggingface.co/opencv/inpainting_lama), [michaelgold/big-lama](https://huggingface.co/michaelgold/big-lama) — open weights.

## Bottom line

Today's repair volume makes the model choice irrelevant ($0.61/batch worst case on the
current path). The real lever is seed-mining volume: if/when that hits 10-30 repairs/batch,
Vertex-only costs $1.36-$4.08/batch vs. effectively $0 for a LaMa pre-pass that's *also* the
lowest style-risk option for the flat-channel case it's suited to. Stay on Vertex crops now;
spec'd bake-off above is the fast, cheap way to confirm the LaMa-first hybrid before building
it for real. **The bake-off ran** (`docs/experiments/2026-07-12-inpaint-bakeoff.md`) — Vertex
5/5, LaMa 50%, Bria Eraser promising on 2 crops, Z-Image/FLUX-Fill 0% (hallucinated fake UI
elements). §6 below is the follow-up full-catalog walk requested to confirm nothing cheaper
or better was missed in either Vertex or fal before finalizing that routing chain.

## 6. Full-catalog walk (2026-07-12) — confirming neither catalog was under-searched

The sweeps above used targeted keyword searches. This section is a genuine enumeration pass
— paged `search_models` to `has_more:false` on fal, and a direct read of Vertex's own
deprecation/pricing docs — done specifically to check for gaps before trusting the bake-off's
routing recommendation as final.

### Vertex/Google — the headline finding changes the picture

**`imagen-3.0-capability-001`, the Imagen mask-based inpaint/remove-mask model, is
deprecated with a stated shutdown of June 30 2026 — already past as of today (2026-07-12).**
No current official Google page lists a per-image price for it; the only $0.02-0.04 figures
findable are third-party/unverified, not Google's own. A Google-forum thread (2026-03-26)
confirms Google's own engineers acknowledge **there is no mask-based-editing replacement** —
the Gemini image models (`gemini-2.5-flash-image`, `gemini-3-pro-image`, `gemini-3.1-flash-image`)
all edit via `:generateContent` with **instruction-only, no explicit mask parameter**. This
directly explains why `genskin.py:edit_vertex()` already does crop+recomposite instead of a
native mask call — there IS no native Vertex mask API to use; the crop *is* the de facto mask
mechanism. Nothing was missed on the Vertex side; the "~$0.02 Imagen inpaint" figure that
seeded the original pricing question should be dropped as unverifiable/dead, not corrected to
a real number. Model Garden also hosts self-deployable LaMa/SDXL-inpainting notebooks
(GPU-hour billing, not per-image) — not evaluated here since local LaMa (already in the mix,
$0) covers the same ground for free.

### fal — two gaps found, worth a follow-up bake-off arm

Full paging (queries: edit/inpaint/fill/erase/remove/restore/retouch, each to
`has_more:false`, category filter cross-checked and confirmed broken — `category=image-editing`
returns 0 results on this catalog, unfiltered keyword search is the only reliable path)
confirms the earlier sweeps already found the right candidate set — Z-Image Turbo, Qwen
Inpaint, FLUX Fill family, Bria GenFill/Eraser, Finegrain — and correctly excluded LaMa/IOPaint/
SeedEdit/"magic eraser" (none exist on fal under any name). Two mask-conditioned erase
endpoints were **not** in either prior sweep or the bake-off:

| Model | Price | Mask | Prompt | Note |
|---|---|---|---|---|
| `fal-ai/flux-pro/v1/erase` | **$0.004/MP** | ✅ required | ❌ none (dedicated erase, not fill) | Cheapest mask-based option by ~2.5x over Z-Image Turbo; has a `dilate_pixels` param for edge blending. Distinct BFL endpoint from `flux-pro/v1/fill` (which WAS tested and scored 0/5). Same "no prompt" shape as Bria Eraser, which was the one hallucination-free cheap arm in the bake-off — worth testing given that pattern. |
| `fal-ai/object-removal/mask` | $0.006/img (flat) | ✅ required | ❌ none | Unclear provenance, untested; cheap enough to be worth a throwaway check given the no-prompt/no-hallucination pattern above. |

Both share the "no prompt, mask-only" shape that the bake-off's own working hypothesis
(§ Results, "prompt-conditioned fill models treat 'remove X' as a generation instruction
rather than a conservative erase") flags as the safer family — Bria Eraser (no-prompt) was
the standout cheap performer; Z-Image/FLUX-Fill (prompt-required) were the 0%-usable failures.
`flux-pro/v1/erase` fits the winning pattern at ~10x lower cost than Bria and wasn't tried.

**Recommendation:** before promoting Bria Eraser to production tier-1 (bake-off's own next
step), add `fal-ai/flux-pro/v1/erase` and `fal-ai/object-removal/mask` to that same
5-crop validation run (~$0.03 combined at these prices — trivial against the existing $2-3
bake-off budget). If either matches Bria's restrained-removal behavior, it beats Bria on cost
by roughly an order of magnitude for the identical no-prompt-eraser mechanism.

Sources: cloud.google.com/vertex-ai/generative-ai/docs/image/{overview,edit-images},
.../docs/release-notes, .../pricing (Agent Platform, checked 2026-07-12), ai.google.dev/gemini-api/docs/pricing,
firebase.google.com/docs/ai-logic/{imagen-models-migration,edit-images-imagen-remove-objects},
Google developer forum thread on `imagen-3.0-capability-001` retirement (2026-03-26); fal MCP
`search_models` (7 broad queries, each paged to `has_more:false`, both with and without
`category=image-editing`) + `get_pricing`/`get_model_schema` on all candidates, 2026-07-12.
