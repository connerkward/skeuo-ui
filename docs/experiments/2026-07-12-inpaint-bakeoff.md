# 2026-07-12 — inpaint bake-off: erasing baked slider handles, 6 models on 5 real defects

## Question

`docs/design/2026-07-12-inpaint-pricing.md` priced Vertex `gemini-3-pro-image` (the
incumbent crop-repair path) against 12 fal-hosted candidates and local LaMa, purely from
`get_pricing`/`get_model_schema` — no generations. Two follow-ups: (1) re-verify that
pricing sweep against the fal catalog before spending (had it missed or misjudged
candidates?), and (2) actually run the finalists on real baked-slider-handle defects and
score them — deterministic detector + VLM witness + direct human-eyes inspection — to turn
the pricing table into an evidenced routing recommendation.

## Phase 1 — re-verified fal catalog sweep (live, 2026-07-12)

Searched fal `search_models` with 5 query wordings (inpaint, fill mask, eraser object
removal, edit mask image, retouch) + `search_docs`; pulled `get_model_schema` +
`get_pricing` for every mask-conditioned candidate found. All prices matched the
2026-07-12 pricing doc exactly (no drift in the ~1 day since) — see table below.

| Model | Endpoint | Price | Mask | Prompt | Verdict |
|---|---|---|---|---|---|
| Z-Image Turbo Inpaint | `fal-ai/z-image/turbo/inpaint` | $0.01/MP | required | required | kept (user-named) |
| Qwen Image Edit Inpaint | `fal-ai/qwen-image-edit/inpaint` | $0.03/MP | required | required | kept (user-named) |
| FLUX.1 [pro] Fill | `fal-ai/flux-pro/v1/fill` | $0.05/MP | required, must match input dims | required | kept (user-named) |
| FLUX.1 Kontext-LoRA Inpaint | `fal-ai/flux-kontext-lora/inpaint` | $0.035/MP | required | required | **DROPPED** — schema also requires a **`reference_image_url`** (a second image supplying the fill content), not just mask+prompt. This task has no natural "reference photo" of the correct material — the whole point is to CONTINUE the existing paint, not reference a different source image. Swapped for the same-price Dev Fill variant instead. |
| FLUX.1 [dev] Fill w/ LoRA | `fal-ai/flux-lora-fill` | $0.035/MP | required | optional (default `""`) | **substituted in** for Kontext-LoRA — plain mask+image+prompt fill, matches the task shape; also exposes `paste_back` (auto-composites outside the mask) |
| Vertex `gemini-3-pro-image` (incumbent) | `genskin.py:edit_vertex()` | see correction below | none (crop+recomposite) | required | kept, capped |
| LaMa | local, `.venv-biref` + `simple-lama-inpainting`, MPS | $0 | required | none | kept (pricing-doc recommendation, additive) |
| Bria Eraser | `fal-ai/bria/eraser` | $0.04/generation | required | **none** | not a finalist, but added as a **bonus arm mid-run** — see finding below |
| Finegrain Eraser | `fal-ai/finegrain-eraser/mask` | $0.045/image | required | none | checked, not run — same no-prompt shape as Bria, redundant given budget, flagged for future follow-up alongside Bria |
| Bria GenFill v2 | `bria/genfill/v2` | $0.04/MP | required | required (`instruction`) | checked, not run — same prompt+mask shape as Qwen/Z-Image, held in reserve |
| Bria Fibo Edit | `bria/fibo-edit/edit` | n/a | optional | optional, needs `structured_instruction`/`original_vgl`/`new_vgl` JSON scene-graph objects | **DROPPED** — the schema's real interface is a VGL (visual-grounding-language) JSON contract, not a plain mask+instruction call; too complex/undocumented a contract to fit this task without separate integration work |

**Vertex pricing correction (found live, not from memory):** `genskin.py`'s shared
`edit_vertex()` helper (which `erase12.py`'s `erase_model()` already reuses in production)
hardcodes `generationConfig.imageConfig.imageSize: "4K"` on every call — **regardless of
the input crop's size**. Google's output-image pricing is tiered by the REQUESTED output
size, not the input: 1K-2K tier = 1120 tokens = $0.134/image, 4K tier = 2000 tokens =
$0.24/image. Because every real `edit_vertex()` call always requests 4K, every Vertex
repair — including this bake-off's own 1024px crops — actually lands in the **4K tier**.
Corrected total: input $0.00112 + output $0.24 + instruction text ~$0.0003 ≈ **$0.241/repair**,
not the ~$0.136 the 2026-07-12 pricing doc recorded from crop-size reasoning alone. This is
exactly the kind of miss "re-verify before spending" was meant to catch — the earlier doc's
pricing math was right in isolation, but never checked what `imageSize` value the actual
shipping code requests.

## Phase 2 — the bake-off

### Defect crops

5 genuine baked-slider-thumb defects, one per skin, pulled from real production runs (NOT
synthesized): `diablo-gothic`, `fallout-pipboy`, `fallout-vault`, `n64-cutscene`,
`wc-goldshield` — sourced from `erasegallery/mainline/assets-<skin>/before.png` (the
pre-erase full 2304x3712 paint) with the exact `bbox_px` from each skin's own
`erase12-log.json` (the SAME detector the shipping `erase12.py` gates on). `claymation` was
deliberately excluded — `erase12.py`'s own docstring records it as a detector **false
positive** (a rounded end-cap mistaken for a baked part on a genuinely empty groove), so
it is not a genuine defect.

Every finalist model received the **identical** 1024x1024 native-resolution crop (padded
around the bbox, no upscaling) and the identical binary erase-mask (bbox dilated 14px) —
the controlled-comparison contract, per `parallel-by-default-rule`'s "write the seam
contract first."

**Diablo-gothic is the deliberately-hard case:** its logged bbox only spans the TOP of an
ornate skull-shaped grip (production status: `erased-still-failing` after 3 real Vertex
attempts) — used as-is (the pipeline's own, imperfect, detection), not hand-corrected, since
trusting the given detector output was the task's own framing.

**Concurrent-agent coordination:** a separate sweep agent was writing to
`erasegallery/work/` during this run (confirmed via `ps aux` — an `extract12.py` process
against `/tmp/erasesweep-scratch/...`). Checked its output directory twice (read-only,
untouched): it landed 9 additional defect-crop candidates (mostly alt-seed variants of
`fallout-pipboy`/`steam-porthole` plus unrelated `abshape`/`jsonspec`/`knobticks` experiment
assets) but never produced a saved pre-erase `before.png` I could safely and correctly
reconstruct without risking a wrong crop. Given the 5 in-hand defects already span both
flat/simple and ornate/complex material and were sufficient to produce a decisive result
(below), these were **not folded into this bake-off** — flagged here as a ready follow-up
sweep once that agent's WIP formally lands.

### Generation — 30 cells (5 skins x 6 models) + 2 bonus cells

All 4 fal models run directly via `fal_client` (same REST API the fal MCP wraps — the real
service, not a reimplementation) using `FAL_KEY` from `central/.env`. LaMa run locally via
`.venv-biref`'s torch/MPS (`simple-lama-inpainting`, `--no-deps` install to dodge an
unrelated Pillow build-version pin). Vertex run via `genskin.py:edit_vertex()` directly
(reused, not reimplemented) on 4 of the 5 skins; `diablo-gothic`'s Vertex cell was **reused
from production** (`assets-diablo-gothic/paint.png`, 3 prior real Vertex attempts already
logged there) rather than a fresh spend — `generation-spend-rule`'s cheapest-first applied
to "don't re-buy evidence you already have."

Same prompt template across all prompt-capable arms: *"...A slider thumb/handle/grip
currently sits in a recessed groove and must be REMOVED... Erase it completely and continue
the {material} SEAMLESSLY underneath..."*, `{material}` filled per-skin.

### Scoring — three signals, human eyes adjudicate

**(a) Deterministic** — re-ran `erase12.py`'s own `detect_bbox()` + `seam_delta()` (not a
reimplementation) on each result composited back into the skin's real pre-erase full paint.
**Bug caught and fixed mid-run:** the raw "is anything anomalous in the whole device window"
signal is NOT scoped to the repaired region — `detect_bbox()` scans the entire groove, so it
flags unrelated content elsewhere in frame (a rivet, another control) regardless of repair
quality. Confirmed live: `fallout-vault`'s flagged anomaly sat 300+px from the actual defect
site. Fixed to score overlap between the detected anomaly and the ORIGINAL defect bbox
specifically — `verify-outputs-rule` §6's "could this metric pass on garbage" check, applied
to my own scoring code before trusting it.

**(b) VLM witness** — `openrouter/router/vision`, `google/gemini-2.5-pro`, `reasoning=true`
(same endpoint+model `semissive/sota_eval.py` already proved live 2026-07-11). Sent
BEFORE+AFTER crop pairs, asked for `removed`/`seamless`/`no_new_artifacts`/`verdict`. Total
cost: **$0.350** across 30 calls (~$0.012/call, cheaper than the $0.02-0.03 estimate).

**(c) My own eyes, full-res, every cell** — per `verify-outputs-rule` §1b/§6, opened every
result at 2-5x zoom against its BEFORE, including a wide-context re-check on 2 cells where
the VLM disagreed with my first pass.

**Adjudication (VLM overruled twice, both directions):**
- `diablo-gothic` x `flux-pro-fill` and x `flux-dev-fill`: VLM said **PASS** on both. Direct
  pixel inspection showed flux-pro-fill hallucinated a **readable UI tooltip caption**
  ("Slider thumb in si-ter mood brom-controls", a fake "RAVOB" label, a compass-wheel icon)
  and flux-dev-fill hallucinated a **fully-realized fake slider-widget UI element** (ornate
  bezel + glowing orange progress bar) — neither is a "removed, seamless, no artifacts"
  result by any reasonable read. VLM overruled to FAIL on both.
- `diablo-gothic` x `vertex` and `n64-cutscene` x `vertex`: VLM said **FAIL** on both
  (`seamless=False`/`artifacts_ok=False`). Re-inspected at 2x wide-context zoom (full groove,
  both ends) on each — found a clean, natural material continuation on diablo-gothic and a
  plausible rounded slider-track end-cap (not a defect) on n64-cutscene. VLM overruled to
  PASS on both.

This is the exact discipline `verify-outputs-rule` describes: the VLM is a witness, not a
judge — every claim gets checked against pixels, and it was wrong in **both directions**
here (2 false PASS, 2 false FAIL), which is why the human-eyes column is authoritative in
the results page, not the VLM column.

## Results

Full per-cell grid, thumbnails, full-res click-through, and per-model scoreboard:
[`tools/mask-align-exp/gen12/inpaintbake/index.html`](../../tools/mask-align-exp/gen12/inpaintbake/index.html)
(served locally — see Review section of the delivering message for the live URL). That
page's `crops/`/`results/`/`web/` folders are bulk generation scratch (gitignored,
regenerable via the committed scripts) — the durable, git-LFS-tracked archival record is
the per-skin comparison strip below (BEFORE + all 6 finalists, one row per skin):

- ![diablo-gothic](assets/2026-07-12-inpaint-bakeoff-diablo-gothic.jpg)
- ![fallout-pipboy](assets/2026-07-12-inpaint-bakeoff-fallout-pipboy.jpg)
- ![fallout-vault](assets/2026-07-12-inpaint-bakeoff-fallout-vault.jpg)
- ![n64-cutscene](assets/2026-07-12-inpaint-bakeoff-n64-cutscene.jpg)
- ![wc-goldshield](assets/2026-07-12-inpaint-bakeoff-wc-goldshield.jpg)

| Model | PASS rate (by eye, n=5) | avg $/repair | $/effective PASS |
|---|---|---|---|
| Vertex (incumbent) | **100%** (5/5) | $0.241 (0.193 amortized w/ 1 reuse) | $0.241 |
| LaMa (local) | 50% (2.5/5 partial-weighted) | $0 | $0 |
| Bria Eraser (bonus, n=2) | ~63% | $0.04 | ~$0.064 |
| Qwen Image Edit Inpaint | 50% (2.5/5) | $0.031 | $0.063 |
| Z-Image Turbo Inpaint | **0%** (0/5) | $0.010 | n/a — unusable |
| FLUX.1 [pro] Fill | **0%** (0/5) | $0.052 | n/a — unusable |
| FLUX.1 [dev] Fill | **0%** (0/5) | $0.037 | n/a — unusable |

### The headline finding

Three of the four cheap prompt+mask fal models — **Z-Image Turbo, FLUX Pro Fill, FLUX Dev
Fill** — scored **0/5 by eye**, not from imperfect edges but from **hallucinating unrelated
content**: a shiny chrome part with a racing stripe, a green plastic corner, a toggle
switch, a screw/dial, literal readable text ("...REMOVED" on a fake hazard sticker), a fake
UI tooltip caption, a fabricated slider widget. Every one of these looks like a plausible
*something* at a glance — which is exactly why a cheap automated gate (the deterministic
detector, and even the VLM witness) missed several of them, and only direct full-res human
inspection caught the pattern. Cost advantage does not offset a 0%-usable-output rate.

**Working hypothesis (untested further here):** prompt-conditioned "fill" models treat
"remove X, continue Y" as a generation instruction rather than a conservative local erase.
Support: **Bria Eraser**, the one no-prompt dedicated eraser tested (bonus arm, added
mid-run for $0.08 to check this hypothesis), did **not** hallucinate on either of the 2 hard
crops it was run on — it made restrained, plausible removal attempts, coming close to
Vertex quality on the hardest case (`diablo-gothic`) at ~6x lower cost.

## Routing recommendation

1. **Keep Vertex as the reliable fallback tier** — 5/5 clean in this sample, corrected cost
   ~$0.241/repair. Same model that painted the skin; lowest structural style-risk.
2. **Add LaMa as a genuine $0 tier-0 pre-pass**, gated by the (now site-scoped)
   deterministic detector + a quick visual check — free, 50% success on flat/simple
   material, actively worsens ornate material (wc-goldshield), so the gate matters.
3. **Promote Bria Eraser to a full 5-crop follow-up run (~$0.20)** before shipping it as a
   tier-1 fallback ahead of Vertex — the 2-crop bonus evidence is promising but too small a
   sample to route production traffic through alone.
4. **Drop Z-Image Turbo Inpaint, FLUX Pro Fill, and FLUX Dev Fill from the candidate list**
   for this specific task. Not disqualified forever — a much more restrictive prompt ("do
   NOT generate any new object/icon/text, only extend surrounding material, nothing else")
   might fix the hallucination, but that's an unverified hypothesis, not a reason to ship
   any of the three as-is today.
5. **Qwen Image Edit Inpaint** is a middle case (50% by eye) with a comparatively SAFE
   failure mode (a flat black void, not a hallucinated object) — keep only as an optional
   pre-Vertex tier if a gate is built to catch the void-failure case specifically.

**Proposed chain:** LaMa ($0) → Bria Eraser ($0.04, pending the full validation run) →
Vertex ($0.241, reliable final fallback).

## Spend

Generation: LaMa $0 + fal (z-image/qwen/flux-pro/flux-dev, 5 crops each) $0.655 + Vertex (4
fresh + 1 reused) $0.964 + Bria Eraser bonus (2 crops) $0.08 = **$1.70**.
VLM judging: 30 calls = **$0.350**.
**Total: ~$2.05**, under the $3 cap.

## Artifacts

- `tools/mask-align-exp/gen12/inpaintbake/build_crops.py` — crop+mask extraction (native-res,
  identical inputs across arms).
- `tools/mask-align-exp/gen12/inpaintbake/run_bakeoff.py` — fal/LaMa/Vertex generation.
- `tools/mask-align-exp/gen12/inpaintbake/score.py` — deterministic detector scoring
  (site-scoped fix documented inline).
- `tools/mask-align-exp/gen12/inpaintbake/vlm_judge.py` — SOTA-eye witness scoring.
- `tools/mask-align-exp/gen12/inpaintbake/my_eyes_verdicts.json` — authoritative per-cell
  human verdicts + adjudication notes.
- `tools/mask-align-exp/gen12/inpaintbake/index.html` (+ `build_page.py`) — the results page.
- `tools/mask-align-exp/gen12/inpaintbake/crops/`, `results/`, `web/` — inputs, raw model
  outputs, and display thumbnails/full-res.

## Addendum (2026-07-12) — Arm 2: whole-slot masking (Vertex vs Bria vs LaMa)

Question: does giving the eraser the ENTIRE slider slot (mask the whole groove, repaint a
clean track) blend more coherently than a tight patch around the baked thumb?

Method: 3 skins (diablo-gothic, wc-goldshield, fallout-vault), slot geometry from each
`regions.json` `seek.device` rect (no hand coords), crop aspect expanded to nearest
Vertex-supported enum (ai-image-coords-rule). Ran LaMa ($0) / Bria ($0.04) / Vertex ($0.13);
z-image dropped (hallucinator). Composited back with erase12's feather. Spend $0.52.

Result — **whole-slot masking is NEGATIVE for generative erasers:**
- diablo-gothic: LaMa partial · Bria FAIL (quilted-texture hallucination) · Vertex FAIL (added rune glyphs, didn't erase)
- wc-goldshield: LaMa PASS · Bria FAIL (thumb untouched) · Vertex FAIL (thumb untouched)
- fallout-vault: LaMa partial · Bria PASS · Vertex PASS

Inversion vs Arm 1 (tight crop): there Vertex was the reliable 5/5; at whole-slot scale it
fails 2/3. A wide unmasked context reads as "design permission" to a prompt-driven model
rather than "match this material." Only LaMa (classical, no hallucination capacity) stays
consistent at slot scale.

**Routing decision: keep erase12's mask TIGHT for generative erasers (Vertex/Bria). Only
pair whole-slot masking with a classical eraser (LaMa).** Do not widen the erase mask as a
blanket policy. Page: `inpaintbake/slotwide/index.html`.
