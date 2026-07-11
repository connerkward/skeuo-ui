# 2026-07-10 — Two-image conditioning vs single-canvas guide bleed

## Question

Guide-colour bleed — thin coloured rings/bezels of the alignment-marking hue left around
sockets and buttons (the defect the abshape A/B experiment, 2026-07-09, identified as the
dominant residual failure mode even under the winning SOLID-guide condition) — happens because
the colour-coded guide shapes are physically painted **into the same canvas the model edits**.
Does sending the layout as a **second reference image**, with a guide-pixel-free clean canvas
as the actual edit target, eliminate that bleed **by construction** (no coloured pixel exists in
the region being edited for a trace to survive), and at what cost to quality / layout adherence?

## Mechanism verification (done before spending anything, per verify-external-claims-rule)

- fal `fal-ai/gemini-3-pro-image-preview/edit` live schema (`get_model_schema`, 2026-07-10):
  `image_urls` is `array<string>` — already proven multi-image-capable (mainline `genskin.py`'s
  own `image_urls=[url]` is a 1-element instance of that same array type).
- Google's live docs (`ai.google.dev/gemini-api/docs/image-generation`, fetched 2026-07-10):
  Gemini image models explicitly support multi-image composition — "mix up to 14 reference
  images"; Gemini 3 Pro Image specifically: "up to 6 object images + 5 character images."
- **Chose Vertex AI direct** (not fal) — the already-proven, ~20%-cheaper path for this exact
  model (`gen12/TODO.md`'s `PAINT_VERTEX` note), needs no fal balance. Extended the proven
  single-image `edit_vertex()` (abshape/genskin_ab.py, mainline genskin.py) to N images by
  adding N `inline_data` parts before the text part in the same `contents[].parts` array — no
  new API shape, just more of the same part type.
- Before generating anything: confirmed programmatically that the TREAT arm's "clean scaffold"
  edit-target image contains **zero pixels** within RGB-distance 60 of any of the 10 guide keys
  (`0` hits, sampled the full 2400×1920 canvas), while the guided reference image contains
  ~538k such pixels — the two images differ EXACTLY on the variable being tested.

## Method

- Self-contained harness in `tools/mask-align-exp/gen12/twoimg/` (pattern: `abshape/genskin_ab.py`),
  mainline `genskin.py`/`extract12.py` untouched (a live re-roll batch was running against them).
- **CONTROL** — current single-canvas approach: one joint image, LEFT column = neutral
  placeholder body + SOLID FILLED colour-key guide shapes (device positions + 4-part sprite
  strip), RIGHT column = black mask target. One `edit_vertex()` call, 1 input image.
- **TREAT** — image 1 (the actual edit target) = clean scaffold: identical geometry/placeholder
  body/strip band, **zero guide-coloured pixels**, right column still black (mask target). Image
  2 = the SAME guided blueprint CONTROL uses, sent as a pure layout reference. Prompt explicitly
  labels image roles ("IMAGE 1 is the EDIT TARGET… IMAGE 2 is a LAYOUT REFERENCE ONLY… its
  colours must NEVER be painted anywhere in your output") and states every guide-colour NAME so
  the model can positively identify what must not appear.
- Both arms use SOLID FILLED guide shapes (the abshape 2026-07-09 verdict's winner over outline).
- Matrix: 2 themes × 2 seeds × 2 arms = 8 generations. Themes/seeds reused from the abshape
  experiment (`fa-pod`, `wc-goldshield`; seeds 121, 134) so results compose across experiments.
- Model: `gemini-3-pro-image-preview` via Vertex AI (project `muser-2605300220`, global), 4K, 5:4.
- Scoring: `../extract12.py` pass 1 (no matte) for the shared gates (leak %, emptiness,
  controls-detected, region-placement) PLUS a bespoke **perimeter-band hue-distance bleed-ring
  metric** (`score_twoimg.py`) — the shared leak gate under-counts thin rings per the abshape
  verdict, so this experiment measures a perimeter band (14% of each control's own bbox size,
  outer expand, interior excluded) around every control (all 10, not just vol/seek/shuffle — the
  abshape verdict found button-ring bleed too) for hue-proximity to that control's own guide key.
- Full-res, 2×-upscaled, labeled crops cut per control (`crop-<name>.png`) for every generation.
- SOTA-eye review (`sota_eye.py`): this agent is Sonnet (sub-SOTA) — per sota-eye-review-rule the
  final visual verdict is routed through Gemini via fal `openrouter/router/vision`
  (`google/gemini-2.5-pro`, same proven endpoint as `gen12/observe12.py`), one call per
  generation, sent the downscaled full paint + full-res vol/seek/shuffle/playpause/queue crops,
  each guide colour's human-readable NAME stated, asked for a per-control NONE/RING/FLOODED call
  + vol/seek/shuffle emptiness + one VERDICT: PASS/FAIL line.
- Cost: 8 gens × ~$0.24/4K image ≈ $1.92 generation + 8 VLM calls × ~$0.02 ≈ $0.16 review ≈
  **~$2.08 total**.

## Results

Full artifacts (paints, blueprints, masks, per-control labeled crops, metrics, per-gen VLM
verdicts): `../../tools/mask-align-exp/gen12/twoimg/results.html` (serves from the gen12 dir
server, path `/twoimg/results.html`).

| gen | leak (genskin gate) | extract12 gate | VLM (gemini-2.5-pro) | residue seen at full res |
|---|---|---|---|---|
| fa-pod-**control**-121 | 0.0000% | PASS | **PASS** | none — cleanest of the batch |
| fa-pod-**treat**-121 | 0.0000% | PASS | FAIL | colours clean; but thumb baked in seek groove, 2×2 button drift, "OFF/ON" text on strip |
| fa-pod-**control**-134 | 0.0347% | PASS | FAIL | all 5 button ICONS in exact guide hues (red/pink/magenta/orange/yellow) |
| fa-pod-**treat**-134 | 0.0002% | FAIL (region-misplaced) | FAIL | **violet ring on vol socket + seek groove flooded deep-purple = exact guide keys, from the reference image** |
| wc-**control**-121 | 0.0596% | FAIL (regions misplaced) | PASS (residue) | none; display split into 2 windows |
| wc-**treat**-121 | 0.0187% | PASS | FAIL | shuffle guide-hue ring; layout fully rearranged |
| wc-**control**-134 | 0.0013% | PASS | FAIL | prev/next/repeat/queue gems flooded in guide hues |
| wc-**treat**-134 | 0.0673% | PASS | FAIL | colours clean; layout fully rearranged |

- **Bleed:** guide-hue residue in CONTROL 2/4 gens vs TREAT 3/4. The decisive case is
  fa-pod-treat-134: vol/seek painted in their exact guide keys **although the edit canvas
  contained zero guide pixels** (verified programmatically pre-run) — the colour transferred
  *semantically* from the reference image. Removing guide pixels from the canvas does not
  remove the defect; the bleed pathway is not (only) pixel tracing.
- **Layout adherence:** CONTROL matched the locked template 4/4; TREAT drifted 4/4 (button
  rows collapsed/rearranged, screens relocated, one region-misplaced gate failure). TREAT also
  baked parts into must-be-empty cavities more often and introduced banned text labels.
- **Gate gap found:** extract12's emptiness gate (bright-interior >150 threshold) passed
  mid-tone/dark fills (the purple-flooded seek groove) that the VLM correctly called FILLED.
- **Metric caveat:** the bespoke perimeter-band hue metric false-positives on wc-goldshield's
  queue in both arms (8–39%) — the gold body hue (~42°) is inside the 16-step hue tolerance of
  the YELLOW guide key. Same-theme cross-arm deltas usable; absolute values not.
- **Ops notes:** Vertex 429s under 8-way concurrency (fixed with backoff + sequential retries);
  fal `openrouter/router/vision` with `google/gemini-2.5-pro` now REQUIRES `reasoning: true`
  (every call errors "Reasoning is mandatory for this endpoint" without it — observe12.py has
  the same gap and will hit this on its next `--vlm` run).

## Conclusion (agent, SOTA-eye-adjudicated)

**Hypothesis falsified.** Two-image conditioning does not eliminate guide bleed (3/4 treat gens
show residue, including exact-key rings/floods sourced from the reference image) and costs
layout adherence (4/4 drifted vs 0/4 control). Keep the single-canvas solid-guide blueprint
(abshape verdict stands). If bleed reduction is pursued, the lever is key selection (avoid keys
hue-adjacent to the theme palette) and an icon-specific no-echo prompt clause — icon fills were
the most common echo site — not conditioning topology. n=4/arm: directional, not conclusive.

## NEUTRAL arm (added 2026-07-11) — colourless numbered reference; digit-contamination hypothesis

**Question.** If colour is the bleed vector, does a COLOURLESS reference avoid it? Image 2
becomes thin mid-grey outline shapes with a small printed number (1–10) centred on each control;
the text prompt maps each number to its control and hardens against painting digits/outlines.
Image 1 stays the same clean scaffold as TREAT. The user's prior prediction — *"number tags will
just contaminate the input with numbers instead of colors"* — was the primary hypothesis under
test. 4 further gens (same 2 themes × 2 seeds), same model/path (`gemini-3-pro-image-preview`
via Vertex AI direct, 4K, 5:4). Scoring identical (extract12 gates + bleed-ring metric); SOTA
eye extended: per-control DIGIT hunt (DIGITS-NONE/DIGITS-FOUND, incl. tick-marks/tags,
faint/stylized) + a DIGIT-VERDICT line, run over ALL 12 gens for a uniform 3-way comparison
(`analyze_3way.py` → `threeway.json`).

| gen | extract12 gate | VLM verdict | DIGIT verdict | notes (agent eye + SOTA eye, adjudicated) |
|---|---|---|---|---|
| fa-pod-**neutral**-121 | PASS | FAIL | CLEAN | layout drifted (5-btn row, 1 window); vol/seek/shuffle FILLED; shuffle green rim |
| fa-pod-**neutral**-134 | FAIL (emptiness) | FAIL | CLEAN | device overflows canvas right edge; layout rearranged |
| wc-**neutral**-121 | FAIL (emptiness) | FAIL | CLEAN | layout rearranged; OFF/ON strip text (banned); runes are decor, not digits |
| wc-**neutral**-134 | FAIL (emptiness) | FAIL | CLEAN | **next/repeat/shuffle gems in EXACT named keys (ROSE PINK / SPRING GREEN / VIOLET-PURPLE) with zero coloured input pixels** |

### 3-way summary (n=4/arm)

| axis | CONTROL | TREAT | NEUTRAL |
|---|---|---|---|
| colour bleed (any RING/FLOODED, SOTA-eye) | 2/4 | 1/4 | 3/4 |
| DIGIT bleed — actual numerals baked in | 0/4 | 0/4 | **0/4** |
| digit-LIKE marks (raw detector, incl. tick/notch FPs) | 1/4 | 2/4 | 0/4 |
| layout adherence to locked template (visual) | 4/4 | 0/4 | 0/4 |
| cavity emptiness clean (gate + VLM) | 4/4 | 2/4 | 0/4 |
| extract12 gate PASS | 3/4 | 3/4 | 1/4 |
| SOTA-eye VERDICT PASS | 2/4 | 1/4 | 0/4 |

- **Digit verdict: the user's prediction is REFUTED at n=4.** Zero numerals baked into any
  neutral gen — DIGITS-NONE on all 40 per-control crops. The detector is demonstrably
  over-sensitive, not under-: it flags spontaneous knob pointer-notches/tick-marks in the
  CONTROL/TREAT arms, whose inputs contained no digits at all (that's its false-positive
  floor), yet found nothing in the arm that actually had printed numerals in its reference.
- **New finding — a THIRD bleed pathway: text-prompt semantic bleed.** Neutral's two input
  images are verifiably colourless, yet wc-neutral-134 painted its next/repeat/shuffle gems in
  their EXACT named guide keys. The only remaining colour source is the TEXT prompt: the
  right-column mask spec must state each control's colour name + RGB
  (`ROSE PINK region filled 255,0,128; …`). So the pathways rank
  **canvas-pixel < reference-image < text-prompt**, and no image-conditioning topology removes
  the text one while the joint-canvas mask column exists.
- **Neutral is REJECTED as a default candidate regardless of the digit result:** 0/4 layout
  adherence (all four rearranged the template; fa-pod-134 also overflowed the canvas), 0/4
  clean cavity emptiness (3/4 failed the deterministic gate), 0/4 SOTA-eye PASS. The line-art
  outline carries far less layout authority than solid filled shapes — consistent with the
  abshape solid-vs-outline verdict.
- Marginal cost: 4 gens × ~$0.24 ≈ $0.96 + VLM review of the 4 neutrals plus a uniform re-run
  of 7 stale/failed verdicts (12 calls total incl. 2 payload-cap failures) ≈ $0.25–0.35.
- Ops: fal `openrouter/router/vision` caps image payload at 30MB of ENCODED data-URI length
  (verified live: a 24.4MB-decoded/32.5MB-b64 batch was rejected) — `sota_eye.py` now re-encodes
  crops as full-res JPEG q90 when the encoded total exceeds 24MB.

## Roster template-adherence audit ($0, 2026-07-11)

The user's complaint — "the paint isn't following the template at all, controls have colour
contamination" — audited from data already on disk (no new generations): per-control drift
between the authored template centre and extract12's detected device centre, plus the twoimg
perimeter-band hue-contamination metric, over the currently gate-passing roster. 13/15 skins
pass the gate; only 6 of those are TEMPLATED mode (drift is meaningless for the 7
templateless). Full table: `results.html` Task-2 section; data `twoimg/roster_audit.json`.

| skin | mean drift | worst control | mean contam % | worst contam | drift vs orig batch (794da20e) |
|---|---|---|---|---|---|
| fa-pod | 503px | repeat (777px) | 0.0% | visualizer 0.002% | −99px (improved) |
| fallout-pipboy | 950px | album_art (2064px) | 0.08% | seek 0.77% | **+808px** |
| ps1-crunchy | 415px | vol (1380px) | 0.01% | visualizer 0.10% | +85px |
| steam-porthole | 858px | album_art (2043px) | 1.21% | visualizer 12.09% | **+335px** |
| wc-goldshield | 462px | next (837px) | 0.70% | queue 6.89% | −82px (improved) |
| wmp-quicksilver | 542px | vol (1550px) | 0.98% | seek 8.79% | **+250px** |

**Read:** the complaint is directionally CONFIRMED on drift — 4/6 templated-passing skins show
more template drift now than the original 2026-07-08 batch, with fallout-pipboy the worst
regression (143→950px mean; its album_art detects 2064px from its authored position) — and
mean drifts of 400–950px on a ~2300px canvas mean the paint treats the template as a loose
suggestion, not a lock. On colour contamination the picture is narrower than "all the
controls": mean per-skin contamination is under 1.3% everywhere, but the worst-control numbers
(steam-porthole visualizer 12.1%, wmp-quicksilver seek 8.8%, wc-goldshield queue 6.9%) are
consistent with visible guide-hue residue on a handful of controls per skin — with the caveat
that this metric false-positives when a theme's own palette sits hue-adjacent to a guide key
(the wc queue/gold case above), so the per-control numbers flag candidates for eye review
rather than prove residue. Historical contamination could not be compared ($0 scope — needs
the old paint pixels).

## Human verdict

**PENDING** — awaiting human review of `results.html`. No human has judged this experiment yet;
the automated gates/metrics/VLM calls above are evidence, not the verdict.
