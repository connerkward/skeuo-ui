# Semantic emissive research — does an ML/VLM model belong in the "what glows" decision?

> **STATUS (2026-07-11): prototype BUILT and RUN**, not just specced — see
> [`docs/experiments/2026-07-11-semantic-emissive-prototype.md`](../experiments/2026-07-11-semantic-emissive-prototype.md)
> and `tools/mask-align-exp/gen12/semissive/`. Verdict: the 2-stage architecture beat the
> classical top-hat baseline on all 3 test skins on "semantic correctness of WHAT glows"
> (diablo-gothic parity, fallout-pipboy found 3 lit elements classical found zero of, fa-pod
> avoided classical's documented false-positive blotching). One real empirical addition to
> the spec below: SAM-3's text-prompt mask is OBJECT/PART-level, not material-level, so a
> Stage 2b local hue/brightness/saturation gate (scoped strictly inside the SAM mask) was
> added to isolate the actually-lit sub-pixels. Not yet promoted to a mainline flag — 2 of 3
> skins got a SOTA-eye cross-check FAIL, diagnosed as an upstream paint-generation gap
> (unlit screens in that specific paint roll), not a defect in the judge or refiner. Read the
> experiment record before extending this further.

Research task, not implementation. Triggered by the user's framing: *"i feel a semantic ml
model / llm needs to do this, not an older heuristic approach."* Read first:
[`docs/experiments/2026-07-09-pbr-delight-emissive.md`](../experiments/2026-07-09-pbr-delight-emissive.md)
(the classical top-hat extraction's full history and its "randomly glows nonsensically"
failure), [`docs/design/2026-07-11-think-about-notes.md` §1](2026-07-11-think-about-notes.md#1-emissive-rethink)
(current options analysis, rec'd deterministic `css.glow`), and
[`tools/mask-align-exp/gen12/pbr_pass.py`](../../tools/mask-align-exp/gen12/pbr_pass.py) (the
disabled heuristic — relative-gated morphological top-hat, `EMISSIVE_ENABLED=False` in
`build_player_pbr.py`).

## The framing question, restated precisely

Deciding **WHAT should glow** on a painted skin (runes glow, rust doesn't; a phosphor screen
glows, a shadow doesn't) is a semantic judgment about image *content*, not a photometric
property recoverable from pixel statistics alone. The top-hat extraction is a pure signal-
processing filter — bright + saturated + locally-thin — that has no concept of "rune" or
"screen"; it fires on anything that happens to match the filter's shape prior (measured:
fa-pod's uniformly-bright teal shell produced *more* candidate pixels than diablo-gothic's
actual glyphs). That is the concrete argument FOR routing this through something with
semantic understanding. The counter-argument, tested below: semantic understanding from a
model is not free — it costs money, latency, and (per `ai-image-coords-rule`) is unreliable
as a **geometry** source even when it's a good **judge**. The question this doc answers is
which combination gets semantic judgment without inheriting VLM geometric noise.

## Landscape (verified live, 2026-07-11 — HF hub/paper search + fal catalog, not memory)

| # | Approach | Model(s), verified live | Semantic quality | Geometric crispness | Cost/skin | Local/MPS | Integration effort |
|---|----------|--------------------------|-------------------|----------------------|-----------|-----------|---------------------|
| 1 | VLM-guided / text-prompted segmentation | `fal-ai/sam-3/image` ($0.005/call, native `prompt` text param), `fal-ai/evf-sam` ($0.005/call, text prompt + negative prompt + optional GroundingDINO backend), `fal-ai/sam-3-1/image` ($0.01/call, box-prompt only — already wired in `generation/sam_snap.py`) | Needs to be TOLD what to look for (a noun phrase); doesn't decide *itself* what's glow-worthy | High (SAM's specialty — pixel-accurate masks) | ~$0.005–0.01/call, 2–4 calls/skin | Hosted only realistically (see below) | Medium — mask reduction code already exists in `pbr_pass.py` lines 276–291 |
| 2 | Direct VLM region proposal (Gemini, already in-pipeline) | Vertex Gemini 3.1 Pro (`director.ts`'s existing plumbing) or `openrouter/router/vision` ($0.01/unit, verified live) | Good — a coarse "should this glow, name it" ask is classification, not geometric regression, which is what VLMs are actually reliable at | Low/untrustworthy for precise boxes (confirmed dead end for control-geometry in this exact repo — 0oyq 29→0) | ~$0.01–0.02/call | Hosted only (Vertex or fal) | Low — reuses existing Vertex call plumbing |
| 3 | Material-segmentation / intrinsic-decomposition nets | Swept fresh (see below) — none exist that emit an emission channel from a single flat image | N/A | N/A | N/A | N/A | Dead end, confirmed again |
| 4 | Image-model self-report (imgjson/ tie-in) | None built yet — `imgjson-exp` branch/worktree exists, dir is empty | Unverified, plausible but circular | N/A (would still need a second call for geometry) | Would reduce to #2 with an extra circularity risk | N/A | Speculative — flagged, not scoped here |

### 1. VLM-guided / text-prompted segmentation — what's actually live

Checked the fal catalog directly (not memory, per `verify-external-claims-rule`):

- **`fal-ai/sam-3/image`** — "SAM 3 is a unified foundation model for promptable segmentation
  in images and videos. It can detect, segment, and track objects using text or visual
  prompts." Schema confirms a native `prompt` string input (default value in the schema is
  literally `"wheel"` — a text noun-phrase prompt), plus `box_prompts`/`point_prompts` for
  visual grounding, `include_boxes`/`include_scores`/`return_multiple_masks`. Pricing: **$0.005/unit**.
- **`fal-ai/evf-sam`** (EVF-SAM2) — "combines natural language understanding with advanced
  segmentation... precisely mask image regions using intuitive positive and negative text
  prompts," with an explicit `use_grounding_dino` toggle and `negative_prompt` (useful for
  "glow, not reflection"-style exclusion). Pricing: **$0.005/unit**. This is the closest thing
  fal has to a packaged Grounded-SAM.
- **`fal-ai/sam-3-1/image`** — box-prompt only (no free-text field in its schema), **$0.01/unit**,
  and it's the model `generation/sam_snap.py` **already wires up** in this repo — full
  upload/box-prompt/status-poll harness with an adaptive-pad algorithm that shrinks a box to
  never merge into a packed neighbor. That harness is directly reusable for a *different* set
  of boxes (candidate glow regions instead of control regions) — swap `CTRL` region list for
  emissive-candidate boxes and the polling/upload code needs zero changes.
- HF hub search for "GroundingDINO grounded segment anything" and "SAM3 facebook/meta" via
  `hub_repo_search` returned **no matches** on two different wordings — this does NOT mean the
  weights don't exist (HF's own model card ecosystem is inconsistently tagged and the MCP
  search here is keyword-scoped), it means a **local HF checkpoint is not confirmed reachable
  through this search surface**. Per `verify-external-claims-rule`, absence-from-one-search
  isn't absence — but combined with `prefer-local-inference-rule`'s "pragmatic" carve-out
  (setup cost vs. $0.005/call hosted), standing up a local GroundingDINO+SAM stack for this is
  not worth chasing further: the hosted call is already cheaper than the engineering time to
  verify a local path exists, let alone build it.
- **Assessment:** text-prompted segmentation is the correct tool for *"crisply cut out the
  thing named X,"* not for *"decide what X should be."* It needs a caller that already knows
  the noun phrase — which is exactly what stage 2 supplies.

### 2. Direct VLM region proposal — reusing in-pipeline Gemini

`director.ts` already ships Vertex Gemini 3.1 Pro vision calls (`extractSlots`/`extractMasks`),
documented in this repo as a **confirmed dead end for precise control-box geometry** — SAM
1/10, two Gemini 2.5 Pro passes, all made 0oyq detection worse (TODO.md, `docs/DECISIONS.md`
2026-06-27). That failure is about VLMs doing **precise multi-object geometric regression**
across many small, densely-packed controls. Emissive scoring is a different, coarser ask: *"of
the things in this image, which ~2–4 should look like they emit their own light, and what are
their rough names/locations?"* — closer to open-set classification, which is what VLMs are
comparatively good at, and the geometry it needs to emit is only rough enough to seed a SAM box
prompt (SAM does the precision). `openrouter/router/vision` confirmed live at **$0.01/unit**
(Gemini/Claude/GPT/etc. via one endpoint) as a fal-hosted alternative if routing through Vertex
plumbing is undesirable for this narrow, occasional call.

This is exactly the shape `think-about-notes.md` §1(b) already flagged and rejected — but that
rejection was for VLM-gates-tophat-candidates (stacking a classifier on an already-noisy
heuristic signal, the "smart step on a noisy signal" trap `ai-image-coords-rule` warns about).
**VLM-proposes-names → SAM-text-prompt-segments** is a different composition: the VLM never
touches pixels for geometry, and SAM's candidate quality doesn't depend on the top-hat's
arbitrary kernel scales at all. It sidesteps the exact trap §1(b) was rejected for.

### 3. Material-segmentation / intrinsic-decomposition nets — re-swept, still a dead end

Ran fresh HF paper searches with multiple wordings beyond the 2026-07-09 sweep ("material
segmentation emissive region," "intrinsic decomposition emission light source estimation,"
"self-illumination emissive object detection glow segmentation 2026") to check for anything
newer per `verify-external-claims-rule`. Confirmed, not just re-asserted:

- **IDArb** (arXiv 2412.12083) — diffusion-based intrinsic decomposition, but needs **multiple
  views/illuminations** as input; N/A for a single flat paint.
- **Colorful Diffuse Intrinsic Image Decomposition in the Wild** (Careaga & Aksoy, 2409.13690)
  — single-image, outputs albedo/diffuse-shading/specular-residual. No emission class; emission
  gets buried in the specular residual exactly as the 2026-07-09 doc already found for other
  intrinsic models.
- **ReasonX: MLLM-Guided Intrinsic Image Decomposition** (2512.04222, Dec 2025) — genuinely
  novel and worth naming: uses an MLLM as a **comparative judge** (pairwise "which decomposition
  looks more physically right") to supervise intrinsic-decomposition **training**, not as an
  inference-time region proposer. Interesting pattern for a training-data pipeline; not a
  deployable model this pipeline could call per-skin.
- UnMix-NeRF, MatSpray, Material Palette — all need multi-view or NeRF reconstruction inputs.

**Conclusion: no single-image model outputs a first-class emission channel, confirmed again
against fresh search terms.** This branch stays closed; don't re-open it without new evidence.

### 4. Image-model self-report — the imgjson/ tie-in

Checked `tools/mask-align-exp/gen12/imgjson/` (empty directory) and the `imgjson-exp`
branch/worktree (`/Users/conner/dev/skeuo-ui-imgjson`, tip `b3eeae98` — same commit as
`think-about-notes.md`, no imgjson-specific content committed yet). **This is a reserved name,
not a running experiment** — nothing exists there to reuse or duplicate. Flagging the tie so a
future imgjson effort and this doc don't diverge on the same idea independently.

The concept: extend `genskin.py`'s existing proven multi-column pattern (it already emits a
right-column REGION MASK alongside the paint in one call — `think-about-notes.md` option 1(c)
cites this as the "already-proven pixel-alignment pattern") with a structured text/JSON
side-channel: "list the regions that should glow." Two problems surfaced by checking this
against the actual model contract rather than assuming it works:

- **No native structured-output-alongside-image mode.** nano-banana-2 / gemini-3-pro-image are
  image models, not JSON-mode LLMs with an image side-channel in the same call. Getting a
  region manifest still requires a **second, separate** text/vision completion — which makes
  this reduce to option 2 (VLM region proposal), just with the *generating* model doing the
  annotation instead of a fresh viewer.
- **Circularity risk is HIGH, higher than the analogous director-vision case.** `think-about-
  notes.md` §2 already flags "the director wrote the brief, asking it to judge the result from
  pixels is circular" as a *milder* risk for `css.*` values. Here it's the *same* model
  self-reporting on its *own* freshly-generated output — the strongest form of the trap
  `verify-outputs-rule` §2 names ("a validation that shares the model/assumption of the thing
  you tuned"). If pursued, it must never be the sole signal — only a candidate generator gated
  by an independent SAM mask + a second, different model's cross-check.

## Recommended architecture: 2-stage semantic-judge + geometric-refiner

```
theme_specs/<id>.json                 fal-ai/sam-3/image
  lighting.emissive_hint  ──┐          (or evf-sam)
  (existing, $0, authored)  │
                            ▼          text prompt = each
paint.png ──► VLM judge ──► named      named region ──► crisp mask + score
              (Vertex        regions                        │
              Gemini 3.1     (2-4,                           ▼
              Pro OR         rough box)              pbr_pass.py lines 276-291
              openrouter/                             (energy-weighted centroid,
              router/vision)                           top-6 point lights — REUSED
                                                        unchanged, just fed a
                                                        different source mask)
```

- **Stage 1 (semantic judge):** one VLM call per skin. Input: the paint image + the theme's
  already-authored `lighting.emissive_hint` (existing data, zero new authoring cost — this
  gives the judge a prior instead of guessing blind). Output: 0–4 named regions
  (`"rune glyphs"`, `"CRT screen"`, `"ember cracks"`) each with a rough bbox — rough is fine,
  it only seeds stage 2's box prompt the same way `sam_snap.py`'s adaptive-pad already
  tolerates drift for control geometry.
- **Stage 2 (geometric refiner):** one `fal-ai/sam-3/image` call per named region, `prompt=name`,
  `box_prompts=[stage-1 bbox padded ~20%]` (reuses `sam_snap.py`'s existing pad/box pattern) →
  a pixel-accurate mask + confidence score. Low-confidence masks get dropped (same
  `MIN_SCORE`-style gate `sam_snap.py` already uses for control snapping).
- **Stage 3 (reduction — code reuse, not new code):** feed the SAM mask through `pbr_pass.py`'s
  existing energy-weighted-centroid + top-6-point-lights code (lines 276–291), unchanged — it
  already expects "a mask + `emask`/`val`" and produces the `lights[]` array `meta.json`
  consumes. No new reduction logic needed.
- **Never geometry from the VLM directly** — this respects `ai-image-coords-rule`'s "don't make
  a noisy VLM load-bearing for precise geometry" exactly by construction: the VLM only ever
  emits a name + a rough seed box; SAM is the sole geometry source, same division of labor
  `verify-rule` §1b prescribes for placement claims generally (VLM = witness/judge, pixel
  measurement/SAM = geometry).

**Cost/skin:** ~$0.01–0.02 (VLM judge: Vertex reuse or `openrouter/router/vision` at $0.01) +
2–4 × $0.005 (SAM-3 text-prompt calls) ≈ **$0.02–0.03/skin** — same order of magnitude as the
$0.01–0.03 `patina` spend already gated behind `PBR_PASS_ENABLED`, so turning this on doesn't
change the pipeline's cost profile if/when PBR is flipped mainline.

**Latency:** VLM call (few seconds) + N sequential/parallel SAM calls (SAM-3 is described as
"real-time" per its fal tags) — sub-10s total, comparable to the existing patina round-trip.

### Runner-up: geometric-refiner-only (skip the VLM judge)

Keep candidate generation as the existing free top-hat morphology (`pbr_pass.py`, $0, already
coded) but replace its crude component-area/ring-rejector geometry cleanup with a SAM-3
text-prompt call seeded from the top-hat's own candidate location (`prompt="glowing marking"`
generic, or derived from `lighting.emissive_color`'s hue-window label). Cheaper (~$0.005×N, no
VLM call, no Vertex round-trip) and improves geometric crispness, but **inherits the top-hat's
actual failure mode** — its candidate SET is still whatever the morphology filter fires on,
including fa-pod's uniformly-bright-material false positives. This fixes crispness, not the
semantic-judgment failure that got the whole thing disabled in the first place. Recommend this
**only as a fallback** if the VLM-judge stage proves unreliable or its cost doesn't scale
(e.g., a future high-volume batch mode where $0.01–0.02/skin VLM calls add up).

## Smallest validating prototype (spec only — NOT built, NOT run)

- **Scope:** 3 skins already in the roster with known emissive material and committed
  `paint.png` — **diablo-gothic** (rune glyphs), **fallout-vault** (amber lamps), **steam-
  porthole** (glass/screen). Zero new generation spend — reuse existing paints.
- **Stage A:** one `openrouter/router/vision` call per skin. Prompt: *"List up to 4 regions in
  this image that should appear to emit their own light (glowing runes, lit screens, embers,
  indicator lamps). For each: a short noun-phrase name and a rough bounding box in 0–1 image
  fractions. If nothing should glow, say so explicitly."* Structured JSON response, temperature
  low.
- **Stage B:** for each named region, one `fal-ai/sam-3/image` call:
  `prompt=<name>, box_prompts=[stage-A bbox padded 20%], include_scores=true`.
- **Stage C:** reuse `pbr_pass.py` lines 276–291 unmodified on the SAM mask (swap the `emask`
  input) to produce `lights[]`; render a side-by-side comparison page — baked-emissive-OFF
  (current shipped state) vs. this semantic path — for human verdict.
- **Verification:** per `verify-rule` §1b, close-up crops of each glow region at full res +ˇ
  an independent VLM cross-check (a *different* model than stage A judged it, e.g. Claude via
  the same `openrouter/router/vision` endpoint) before calling it viable. Per `empirical-
  testing-rule`, record the human verdict in `docs/experiments/` if the prototype is actually
  run.
- **Cost estimate:** 3 skins × ($0.01 VLM + ~3 regions × $0.005 SAM) ≈ 3 × $0.025 ≈ **$0.075
  total**. Trivial to greenlight; the real cost is the human review time, not the API spend.
- **Decision rule:** all 3 skins pass close-up + cross-check (glow lands on runes/lamps/glass
  and nothing else) → promote to a flagged pipeline stage. Any skin fails → diagnose whether
  the failure is stage-1 (bad name/region proposal) or stage-2 (SAM mis-segmenting a correctly-
  named region) before iterating — don't patch blindly.

## Composition with `EMISSIVE_ENABLED=False` and `css.glow`

- **Does not require flipping `EMISSIVE_ENABLED`** or touching the baked top-hat path during
  prototyping. The prototype's outputs are new, standalone artifacts evaluated on their own —
  nothing wires into the disabled flag until/unless the human verdict from the prototype above
  is positive.
- **`css.glow` (think-about-notes.md §1 option (d), recommended near-term ship) is
  orthogonal, not competing.** It answers glow for **known, fixed elements** (visualizer, seek
  underglow, knob pointer) deterministically and cheaply — ship it regardless of this research's
  outcome. This semantic-ML direction answers a **harder, different** question: glow that
  tracks **freehand, per-generation content** (diablo's runes, steam-porthole's glass) that a
  static per-theme region can't anchor to (the exact case `think-about-notes.md` §1(a) says
  breaks down for templateless mode). The two are complementary layers, not alternatives.
- **If validated,** the semantic path becomes a **new** emissive source registered through
  `build_player_pbr.py`'s existing `registerEmissiveSource()` mechanism — the same registry
  the visualizer/seek/knob sources already use — gated behind its **own** flag
  (`SEMANTIC_EMISSIVE_ENABLED`, default `False`, inline comment: *"unproven at scale, adds
  ~$0.02-0.03/skin + 2 model calls per generation"*), independent of `EMISSIVE_ENABLED`. Per
  `feature-flag-rule`, gate both the pipeline call (no VLM/SAM spend when off) and the player
  registration (no dynamic source registered when off) — never just the UI half.
- **If validated, recommend removing the top-hat extraction entirely** (think-about-notes.md
  §1 option (e) — ~100 lines of morphology code in `pbr_pass.py`) rather than leaving it wired-
  but-disabled alongside a working replacement — a semantic path that actually names what it's
  segmenting fully supersedes a filter that was only ever guessing from local contrast.

## Summary verdict

The user's instinct is directionally right but needs the *specific* composition, not "an LLM
does it": a bare VLM asked to segment precisely repeats this repo's own confirmed dead end
(0oyq control-box detection). The fix is dividing labor — **VLM as semantic judge (what/named),
SAM-3 as geometric refiner (where/precise)** — which is both new capability (SAM-3's native
text-prompt mode, verified live on fal since the 2026-07-09 sweep didn't test it) and existing-
code reuse (Vertex plumbing from `director.ts`, the box-prompt/adaptive-pad harness from
`sam_snap.py`, the mask-reduction code already in `pbr_pass.py`).
