# 2026-07-11 — Can the IMAGE model output usable JSON? (+ structured-I/O viability sweep)

> **ROUND 2 CORRECTION (same day, jsonspec experiment):** the "broken y-frame /
> uncalibratable internal frame" finding below was an artifact of THIS experiment's ad-hoc
> 0-1 `{x,y,w,h}` convention, not the model's spatial sense. The jsonspec experiment's
> bonus probe (`tools/mask-align-exp/gen12/jsonspec/bonus_probe.py`) re-asked in Google's
> documented `box_2d=[ymin,xmin,ymax,xmax]@0-1000` convention and got real boxes (mean IoU
> 0.79 under an element-order correction), and its stability probe
> (`jsonspec/stability_probe.py`, 3 further calls: seeds 72/73 repeat wc-goldshield, 74
> cross-checks diablo-gothic) measured best-reading mean IoU **0.79 / 0.72 / 0.54 / 0.37**
> across the 4 total calls — BUT found the element order **unstable call-to-call** (seed 71
> emitted `[ymin,xmin,xmax,ymax]`; 72/73/74 emitted the documented order) with
> whole-control semantic swaps in 2/4 calls. The operational verdict (not usable for
> manifests/detection; extract12 stays load-bearing) is unchanged; the mechanism claim is
> corrected. Full re-read: the "ROUND 2 CORRECTION" section of `imgjson/explain.html`; the
> "Bonus" section of [2026-07-11-jsonspec-paint.md](2026-07-11-jsonspec-paint.md);
> raw: `jsonspec/bonus_probe.json`, `jsonspec/stability_probe.json`. Still-standing
> round-1 claims (each re-checked against the probe outputs): thinking-narration prefix
> (re-confirmed in all 3 probe calls, ~880–905 chars), image-model
> responseMimeType/Schema hard-400 (not retested, nothing contradicts), TEXT-alone 400
> (not retested), interleaved-mode box collapse (not retested, n=1).

## Question

1. Can `gemini-3-pro-image-preview` (the paint model) return TEXT — specifically usable
   JSON such as control-bbox manifests — alongside or instead of its image output? Could
   that (a) give paint generations a self-reported mask-cell manifest, or (b) replace
   `extract12.py` detection?
2. (Scope expansion) The pipeline uses NO structured I/O anywhere — prose prompts in,
   freeform text parsed out. Is Vertex structured output (`responseSchema` +
   `responseMimeType`) viable for the director and for bbox extraction, and do
   JSON-shaped *prompts* beat prose?

## Method

Harness: `tools/mask-align-exp/gen12/imgjson/` — `run_tests.py` (modality probes + 3
scored calls), `run_structured.py` (schema/prompt-shape arms), `score.py` (IoU +
center-error vs ground truth), `diagnose.py` (affine frame-fit rescue analysis +
labeled overlays), `build_page.py` → `index.html` (results page).

- Models, both direct Vertex `generateContent`, project `muser-2605300220`, gcloud
  user-auth (the proven `genskin.py:edit_vertex` pattern): **`gemini-3-pro-image-preview`**
  (image) and **`gemini-3.1-pro-preview`** (the pipeline's director/text model, mirroring
  `src/generate/director.ts` config incl. `thinkingConfig: low`).
- Source image (read-only): `gen12/assets-wc-goldshield/paint.png` (2304×3712). Ground
  truth: its `regions.json` `regions[*].device` boxes (extract12-detected), verified by
  cropping to land on the painted controls before scoring.
- Ask: strict-JSON array of `{name,x,y,w,h}` normalized bboxes for the fixed 10-control
  roster. Scored: parse rate, per-control IoU, center error in px. Seeds fixed (71);
  single roll per arm — this is a capability probe, not a distributional study.

## Capability surface — documented vs observed

Docs (fetched 2026-07-11): `ai.google.dev/gemini-api/docs/image-generation` states
gemini-3-pro-image "can generate interleaved content — text blocks and illustrations
inside the same response"; no statement anywhere about `responseModalities` limits or
structured-output support for image models (several Google Cloud doc pages fetched as
nav-shells; the empirical rows below are the authoritative record).

Observed on Vertex (`imgjson/out/modality_probes.json`, `s3_*_raw.json`):

| generationConfig | Result |
|---|---|
| `responseModalities: ["TEXT"]` | **HTTP 400** "The request is not supported by this model" — TEXT-alone rejected |
| `["IMAGE"]` + JSON-only prompt | 200 but `finishReason: NO_IMAGE`, zero parts, ~3.1k thinking tokens burned |
| `["TEXT","IMAGE"]` + JSON-only prompt | works — text parts only, parseable JSON |
| `["TEXT","IMAGE"]` + JSON+re-render prompt | works — 15 text parts + 1 image part (814×1312, input aspect preserved) in one response |
| image model + `responseMimeType: application/json` (± `responseSchema`) | **HTTP 400** "Parameter response_mime_type is not supported for generating image response" |

Parse-rate gotchas (both hit, both now handled in `run_tests.py`):
- **Vertex splits the text stream into many `text` parts at arbitrary byte boundaries**
  (observed mid-number: `"0."` | `"3597"`). Join with `""`, never `"\n"`.
- **The image model ignores "STRICT JSON ONLY"** — ~2.5k chars of thinking-style narration
  precede the array every time; a prefix-tolerant extractor (raw_decode at each `[`/`{`)
  is required. The text model under `responseMimeType` returns one clean part.

## Accuracy vs regions.json (deterministic; `out/scores.json`, `out/diagnosis.json`)

| Test | parse | matched | mean IoU | mean ctr err | after frame-rescue* |
|---|---|---|---|---|---|
| A — image model, JSON-only ask | ✓ | 10/10 | **0.003** | 507 px | 0.53 / 49 px |
| B — image model, JSON + re-render interleaved | ✓ | 10/10 | **0.024** | 789 px | 0.04 / 385 px |
| C — text model, same ask (prose + mimeType) | ✓ | 9/10 | **0.499** | 340 px | (already frame-correct; rescue hurts) |

\* least-squares per-axis affine on centers + undoing A's visualizer/album_art label swap —
a diagnostic ONLY (requires the ground truth you wouldn't have in production).

The diagnosis is the interesting part: test A's x-coords come back at scale 0.999 but
**y in a compressed internal frame** (best-fit `gt = 0.66·pred + 0.12`, residual RMS
≈19 px over the 8 unambiguous controls). The image model *sees* the layout accurately —
it reports coordinates against some internal preprocessed view, not the supplied image's
pixel frame, making raw output unusable without per-image calibration. B (interleaved)
is genuinely noisy — box quality collapses when an image is generated in the same call
(unrescuable, 0.04 IoU). C's two big misses are the **vol/shuffle sprite-strip ambiguity**
(boxed the bottom-strip sprite copies instead of the device sockets — a prompt defect;
those controls appear twice in the paint) plus one dropped field (playpause without `h`).
On the 7 unambiguous controls C is genuinely good: IoU 0.55–0.83, centers 1–22 px.

Labeled overlays (GREEN=GT, RED=returned, ORANGE=affine-rescued):
`imgjson/viz/overlay-{a_text_only,b_interleaved,c_text_model}.png`; B's returned
re-render: `imgjson/out/b_interleaved_img0.png`.

## Structured-I/O sweep (`out/structured_results.json`, `out/structured_scores.json`)

- **s1 — director Material shape** (name/blurb/style-enum/materialPrompt/font, mirroring
  `deriveMaterial`), 3 prompts × 2 arms: prose-JSON (current) vs `responseSchema`.
  **Both arms 3/3 parse + 3/3 field-complete + valid enum styles.** Equal quality;
  schema additionally *guarantees* the enum/required constraints that `director.ts`
  currently re-validates by hand (its `DONOR_STYLES.includes` + missing-field fallbacks).
- **s2 — bbox extraction + responseSchema**: 10/10 rows with all 5 keys (the prose arm
  had silently dropped one field). Spatial quality unchanged (see table below).
- **s4 — fenced-JSON task spec in the prompt** (structured INPUT, no schema): identical
  scores to prose. Paint-generation-side structured prompts NOT tested (needs image
  gens, out of budget) — untested, not refuted.

On the 8 unambiguous controls (excl. the strip-ambiguous vol/shuffle;
`out/unambiguous_comparison.json`):

| arm | rows usable | mean IoU | mean ctr err | max ctr err |
|---|---|---|---|---|
| C — prose + mimeType (current pattern) | 9/10 | 0.642 (n=7) | 13.2 px | 22 px |
| s2 — + responseSchema | **10/10** | 0.553 | 12.6 px | 31 px |
| s4 — fenced-JSON prompt | 10/10 | 0.569 | 13.1 px | 20 px |

Centers are statistically indistinguishable (~13 px mean at 2304×3712); IoU spread is
box-tightness noise. Structure changes *reliability*, not *spatial quality*.

## Verdict

- **Image model text/JSON output: real but NOT usable** — for (a) mask-cell manifests or
  (b) replacing detection. TEXT must ride with IMAGE modality; no structured-output
  params (hard 400); narration prefix always present; and box y-coords arrive in an
  internal frame (raw IoU 0.003, only rescuable WITH ground truth) *(← this last clause
  withdrawn in ROUND 2, see the correction banner at top — convention artifact; "NOT
  usable" stands on order-instability + semantic swaps instead)*. Interleaved
  image+JSON works mechanically but box quality collapses (0.02–0.04 IoU).
- **Structured OUTPUT viable: director YES, extraction YES, image-model manifest NO.**
  `responseSchema` on the text model costs nothing in quality and deletes the
  parse/field-completeness/enum failure modes `director.ts` currently hand-validates.
  Worth adopting on the director's calls.
- **Structured INPUT: measured neutral** on extraction (13.1 vs 13.2 px) — not worth
  adopting for its own sake; paint-side untested.
- **Detection replacement: no.** Best VLM arm (~13 px centers) still carries 20–30 px
  tails and semantic-swap hazard vs extract12's pixel-space geometry. Plausible niche:
  cheap name↔position *sanity witness* over detection, not geometry. (Calibration note
  for `ai-image-coords-rule`: its "VLM boxes are noisy" warning was gpt-4o-era;
  gemini-3.1-pro is much better than that on centers but still not placement-grade,
  and the IMAGE model specifically is frame-broken — the rule stands.)

## Reproduce / artifacts

- `cd tools/mask-align-exp/gen12/imgjson && python3 run_tests.py && python3 run_structured.py && python3 score.py && python3 diagnose.py && python3 build_page.py`
  (needs gcloud auth on the project; ~$0.45 to re-run everything).
- Committed: all scripts, `index.html`, `out/*.json` (raw Vertex responses with the one
  returned image's base64 + opaque 2 MB `thoughtSignature` blobs stripped — decoded
  image kept as `out/b_interleaved_img0.png`), `viz/overlay-*.png`.
- Judged by: deterministic scoring (IoU/center-error vs regions.json) + agent inspection
  of overlays and crops; no human eval this round — capability probe, not a lookdev pick.

**Spend:** ≈$0.45 total (image-model: A $0.05, B $0.16, probes $0.04, ~3 debug rolls
$0.15; all 10 text-model calls ≈$0.04; s3 probes rejected = $0).
