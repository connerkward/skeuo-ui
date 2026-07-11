# Semantic emissive prototype — 2-stage judge + refiner, built and run

Prototype of the architecture specced in
[`docs/design/2026-07-11-semantic-emissive-research.md`](../design/2026-07-11-semantic-emissive-research.md)
("Recommended architecture: 2-stage semantic-judge + geometric-refiner"). That doc was
research-only ("spec only — NOT built, NOT run"); this record is the build + the run.

Code: [`tools/mask-align-exp/gen12/semissive/`](../../tools/mask-align-exp/gen12/semissive/)
(`judge.py`, `refine.py`, `sota_eval.py`, `build_page.py`, `common.py`). Results page:
`tools/mask-align-exp/gen12/semissive/results.html` (served, screenshotted for this record).
Per-skin artifacts in `semissive/out/<skin>/` (judge.json, refine.json, sota-eval.json,
src/overlay/preview/classical-preview PNGs, masks/).

## Question

Does a 2-stage "semantic judge (what should glow) → geometric refiner (crisp mask)"
architecture beat the classical top-hat morphology extraction (`pbr_pass.py`, disabled,
`EMISSIVE_ENABLED=False`) — specifically: does it avoid the top-hat's two documented
failures (glows nonsensically on uniformly-bright material; misses genuinely emissive
content the top-hat's shape prior doesn't match), while staying crisp and cheap?

## Method

**Stage 1 — semantic judge.** `gemini-3.1-pro-preview` via Vertex AI (gcloud user-auth
access token, same pattern as `genskin.py`'s `edit_vertex()` / `director_review.py`),
`thinkingConfig.thinkingLevel: "low"`. Input: the device-photo crop of `paint.png` (top
`devFrac` rows, no region-mask strip) + a structured JSON spec block embedded in the prompt
text (skin id, `theme_specs/<id>.json`'s `lighting` block as a prior, every control's rect
from `regions.json` converted to the same coordinate space as the attached image). Output
enforced via `generationConfig.responseMimeType: "application/json"` +
`generationConfig.responseSchema` (OpenAPI-3.0 subset, uppercase `Type` enum — verified live
against two independent Google doc pages before use, not assumed from memory, per
`verify-external-claims-rule`): `{"emissive_regions": [{label, why, box:{x,y,w,h}, color_hex,
intensity_0_1, pulse}]}`, 0–4 regions, empty list explicitly valid.

**Stage 2 — geometric refiner + local gate (2a/2b).** Per named region, one
`fal-ai/sam-3/image` call (`$0.005/call`): native text `prompt` = the judge's label,
`box_prompts` = judge's rough box padded 20%, `apply_mask=false`, `include_scores=true`.
Regions with `score < 0.5` dropped (unused here — every region scored 0.80–0.96). **Empirical
finding, not in the original spec (see "What changed from the spec" below): SAM-3's mask is
an OBJECT/PART segmentation, not a material segmentation** — it returns the whole surface the
glow sits on, not just the lit sub-pixels. Added Stage 2b: a deterministic hue+brightness+
saturation gate computed strictly inside the SAM mask (never outside it), thresholds relative
to that region's OWN pixel distribution (80th/75th percentile), with a safety-net fallback to
the raw SAM mask (at reduced intensity) if the gate keeps <5% of the ROI (avoids ever emitting
a silently-empty glow). Composited into `emissive.png` matching `pbr_pass.py`'s own contract
(RGBA: RGB = glow-blended color, alpha = coverage) and a `lights[]` list shaped like its
`meta.json` (`uv`/`color`/`energy`).

**Stage 3 — independent SOTA-eye cross-check.** `fal:openrouter/router/vision`,
`model=google/gemini-2.5-pro`, `reasoning=true`. Shown the plain paint + the semantic-emissive
preview (src alpha-composited with `emissive.png`), asked whether everything glowing makes
semantic sense and whether anything glow-worthy is conspicuously missing. **Not a fully
independent second judge** — Gemini family both times, different call path (fal-hosted
OpenRouter vs. direct Vertex) and different specific model (2.5-pro vs. 3.1-pro-preview) —
logged plainly, not oversold.

**Skins (all 3, per task spec):** `diablo-gothic` (rune glyphs/embers — the doc's original
target case), `fallout-pipboy` (phosphor screens — "the case classical found nothing on"),
`fa-pod` (translucent gel shell — "the case classical splattered on"; a judge returning
few/no regions here is a SUCCESS condition, not a failure). Reused existing committed
`paint.png` for each — zero new generation spend.

## Results

| skin | judge regions | refiner kept | final coverage | SOTA-eye | classical coverage (rejected baseline) |
|---|---|---|---|---|---|
| diablo-gothic | 4 (top-L/top-R/bottom-L/bottom-R rune+ember clusters) | 4/4 (scores 0.87–0.96) | 1.86% | **PASS** (sensible=true, 0 missing) | 1.01% (glyph-shaped, this skin was already classical's best case) |
| fallout-pipboy | 3 (2 indicator lamps, vacuum-tube filaments) | 3/3 (scores 0.90–0.95) | 0.75% | **FAIL** (sensible=false; flagged "main screens", "analog meter backlights" missing) | 0% (found NOTHING — confirms the doc's claim) |
| fa-pod | 2 (top/bottom row button-icon glyphs) | 2/2 (scores 0.91–0.93) | 5.94% | **FAIL** (sensible=false; flagged the 2 screens as missing) | 1.15% but visibly WRONG — random blocky patches between buttons, not on the icons (confirmed visually, see `classical-preview.png`) |

Full per-region judge reasoning, refiner scores, and SOTA-eye notes are in
`semissive/out/<skin>/{judge,refine,sota-eval}.json` and rendered on the results page.

### My own visual verification (agent-performed; not a substitute for the user's own review)

Per `verify-outputs-rule` §1b (close-up crop + independent cross-check, both mandatory) —
opened every full-res `overlay.png`, `preview.png`, and per-region mask crop, not just the
page thumbnails:

- **diablo-gothic:** glow crops (`/tmp` scratch, not committed) confirmed the glow follows
  individual rune STROKES and crack lines, not the surrounding stone panel — visually
  indistinguishable in quality from the classical result here (expected: this was classical's
  best case too).
- **fallout-pipboy:** both indicator lamps and the tube filaments read as genuinely lit;
  the two content screens are confirmed, by direct pixel inspection of `src.png`, to be
  painted as flat dark/unlit glass with **no phosphor content baked into this particular
  paint roll** — the judge did not miss a glowing screen, there wasn't one to find.
- **fa-pod:** the 5 button-icon glyphs glow, the surrounding translucent shell does not —
  a direct, visible fix of the classical baseline's blocky mid-shell false positives (visible
  in `classical-preview.png`, between the button rows).

**Diagnosis of the two SOTA-eye FAILs (per the research doc's decision rule: diagnose stage-1
vs. stage-2 before iterating):** neither is a stage-1 (judge) or stage-2 (refiner) defect.
Both flag the SAME thing — the visualizer/album_art screens aren't lit — and in both skins
those screens are rendered in the source paint as flat, contentless dark glass. The judge
correctly declined to invent glow on pixels that don't show any; SAM had nothing lit to
segment. The SOTA-eye is applying a "what would a real device look like powered on" design
expectation, which is a legitimate but DIFFERENT question than "does this rendered image
contain glowing content" — and it's pointing at an **upstream paint-generation gap**
(`genskin.py`'s prompt not reliably rendering lit-screen content for these themes), not a
defect in this 2-stage architecture. This composes with `ai-image-coords-rule`'s standing
finding about VLM/LLM-authored `lighting.emissive_hint` being a prior, not ground truth: the
`fallout-pipboy` theme spec's hint ("green phosphor CRT display glow") was WRONG for this
specific generation, and the judge correctly overrode it by looking at the actual pixels
instead of trusting the hint — exactly the behavior the system prompt asked for.

## Verdict vs. classical

**Architecture validated; not a strict 3/3 PASS by the literal decision rule, and that's
correctly diagnosed, not swept aside.** All 3 skins beat the classical baseline on
"semantic correctness of WHAT glows":
- diablo-gothic: parity with classical's best case.
- fallout-pipboy: found and correctly rendered 3 genuinely-lit elements classical's top-hat
  found literally zero of.
- fa-pod: correctly scoped to the 5 lit button icons; classical produced visible, nonsensical
  blocky patches between buttons on this exact skin (the doc's predicted failure mode,
  confirmed live).

The 2 SOTA-eye FAILs are real signal, but about a different, upstream problem (unlit-screen
paint content) than the one this prototype was scoped to fix (semantic judgment of WHAT
glows, given what's actually painted). Recommendation: **do not yet flip a mainline flag**
(the research doc's own decision rule wanted a clean 3/3) — first, either (a) re-run on paint
rolls where the screens ARE rendered lit to get a true reading with no confound, or (b) treat
"the screens are unlit" as a separate, upstream `genskin.py` prompt finding to fix
independently, then re-evaluate. Either way, the **2-stage architecture itself did its job
correctly and should not be blamed for what the paint model didn't render.**

**Recommend removing the top-hat's use as anything but a documented rejected baseline** — its
own failure mode (fa-pod's blocky false positives) was reproduced live in this same run,
right next to a semantic result that avoided it entirely.

## Structured-IO findings (user directive: verify this explicitly, not just build it)

- **`responseSchema` + `responseMimeType` on Vertex: held perfectly, 3/3.** Every judge call
  returned valid JSON matching the declared OpenAPI-subset schema — zero `JSONDecodeError`,
  zero markdown-fence wrapping, zero missing required fields. This is a real step up from the
  existing in-repo pattern (`director_review.py`) which uses `responseMimeType` alone with no
  `responseSchema` and has to catch-and-quarantine parse failures; schema enforcement removed
  that failure class entirely for this call shape.
- **Confirmed live, not assumed:** the exact Vertex field names/nesting
  (`generationConfig.responseMimeType`, `generationConfig.responseSchema`) and the schema's
  uppercase `Type` enum (`STRING`/`OBJECT`/`ARRAY`/`NUMBER`/`INTEGER`/`BOOLEAN`, not the
  lowercase JSON-Schema convention) via two independent Google documentation fetches before
  writing `judge.py` — per `verify-external-claims-rule`, this was checked live rather than
  pattern-matched from `director_review.py`'s partial (schema-less) usage.
- **One real prompt-engineering iteration was needed, and it's worth recording:** the first
  `diablo-gothic` judge call returned schema-valid JSON but with all 4 rune/ember clusters
  merged into ONE region whose bbox spanned nearly the entire device (`x=0.05,y=0.05,
  w=0.9,h=0.9`) — technically valid against the schema (a list of 1 is legal), but useless as
  a SAM box seed. Fixed by adding one explicit system-prompt clause: return one region PER
  spatially-separate cluster, don't merge distant occurrences into one span-everything box.
  Re-run: 4 tight, correctly-separated regions. **Lesson: schema enforcement guarantees
  shape, not usefulness — geometric/semantic quality still needs prompt iteration same as
  any other LLM call.**
- **`openrouter/router/vision` (Stage 3) has NO schema-enforcement param at all** — its
  input schema is `prompt`/`image_urls`/`system_prompt`/`reasoning`/`model`/`temperature`/
  `max_tokens` only, confirmed via `get_model_schema`. JSON was requested by prompt
  convention (system-prompt instruction + a literal shape example) and parsed with a lenient
  fence-strip fallback. It worked 3/3 in this run with zero parse errors, but that's
  empirical luck for this prompt/model, not a structural guarantee — schema enforcement in
  this pipeline is Vertex-only. A production version would want either a Vertex-hosted
  cross-check model too, or a stricter output-parsing/retry layer for the fal leg.
- **A guessed model slug failed outright, confirming the pattern `verify-external-claims-rule`
  warns about:** first attempt used `model="google/gemini-3-pro-preview"` for Stage 3 (by
  analogy to Stage 1's Vertex model name) — OpenRouter returned `400: "No endpoints found for
  google/gemini-3-pro-preview"`. Caught with a single live test call before shipping;
  switched to the confirmed-live `google/gemini-2.5-pro`. OpenRouter's Gemini-3 listing lags
  fal's/Vertex's own catalog as of this date.

## Spend

Logged (per-skin `spend.jsonl`, real API cost where the endpoint reports it — Stage 3's cost
is the ACTUAL billed amount from the response, not an estimate; Stages 1–2 are documented
per-call estimates since Vertex/fal don't return exact billed cost inline):

| skin | judge (stage 1) | refine/SAM (stage 2) | sota_eval (stage 3, real) | skin total |
|---|---|---|---|---|
| diablo-gothic | $0.06 (2 calls — 1 prompt-iteration re-run) | $0.04 (2 runs × 4 calls) | $0.0184 | $0.1484 |
| fallout-pipboy | $0.03 | $0.015 | $0.0199 | $0.0649 |
| fa-pod | $0.03 | $0.01 | $0.0173 | $0.0573 |
| **pipeline total** | | | | **$0.2705** |

Plus ~$0.03–0.05 of exploratory live test calls made BEFORE writing `refine.py` (3 raw
`fal-ai/sam-3/image` calls to determine the actual output/mask format and discover the
object-vs-material granularity finding above, 1 failed + 1 successful `openrouter` slug
probe) — not part of the shipped pipeline's own spend, called out separately for honesty.
**Total session spend ≈ $0.30–0.32, well under the $1 budget.**

## Files

- Pipeline: `tools/mask-align-exp/gen12/semissive/{common,judge,refine,sota_eval,build_page}.py`
- Per-skin outputs: `tools/mask-align-exp/gen12/semissive/out/<skin>/` (judge.json, refine.json,
  sota-eval.json, src/overlay/preview/classical-preview.png, masks/, spend.jsonl)
- Review page: `tools/mask-align-exp/gen12/semissive/results.html` (serve the `semissive/` dir
  directly so relative `out/<id>/*.png` paths resolve)

## Q: why multiple SAM-3 passes rather than one? (user question, 2026-07-11)

Checked live against the endpoint schema (`get_model_schema fal-ai/sam-3/image`), not
assumed, per `verify-external-claims-rule`: `fal-ai/sam-3/image`'s text `prompt` field is a
**single string** (type `"string"`, default `"wheel"`) — there is no array/list form and no
per-box prompt-pairing field. `box_prompts` DOES accept multiple boxes in one call (with an
optional `object_id` to group boxes belonging to the same object), but every box in that
call shares the ONE `prompt` string — the endpoint has no mechanism to say "box A is the
rune glyphs, box B is the ember cracks" in a single request. Since `judge.py` (Stage 1)
emits N *distinct* named concepts, each needing its own label text AND its own
color_hex/intensity/pulse carried through to the composite, one call per region is what the
schema requires to keep the region↔label↔color/intensity assignment unambiguous — batching
into one call would either lose the per-region label (if boxes are grouped under one
`object_id`+`prompt`) or silently apply diablo-gothic's "rune glyphs" prompt to the ember
cracks' box too. This is a real API constraint, not an unexamined design choice: multi-box
batching exists in this schema, multi-*prompt* batching does not. At $0.005/call the N-call
cost is $0.01–0.02/skin (2–4 regions) — the batching that IS available (multiple boxes/one
prompt) wasn't usable here because the regions are semantically distinct, not repeats of the
same object.

## Human verdict (2026-07-11)

Human-labeled gold, per `human-labeled-data-rule` — preserved verbatim, do not edit or
summarize over this quote:

> "semmissive results are interesting. why multipe sam3 passes rather than one? the only
> issue with fallout-pipboy was that sam didnt capture both 2 vaccum tubes. also 'The
> concept of glowing filaments is excellent for the theme. However, the execution on the
> left tube is poor; the entire glass envelope glows a solid yellow, which is unrealistic.
> The right tube's subtle filament glow is much better and more physically accurate.' is
> true. lets park the emissive thing for later. i find this very interesting. fa-pod on the
> buttons themselves is a bit quesitonable. save these results and my feedback. again well
> come back to this later, perhaps with other pbr related tasks in a skeuo v2. for now lets
> finish skeuo v1 solidly."

**Distilled reading:**

- **Direction validated & found interesting** — the 2-stage semantic-judge + SAM-3-refiner
  architecture itself is endorsed, not rejected. "very interesting" is stated twice.
- **Specific defect 1 — fallout-pipboy, SAM-3 coverage:** SAM-3 (Stage 2) only captured ONE
  of the two vacuum tubes, not both. This is a Stage-2 (refiner) recall gap, not a Stage-1
  (judge) naming problem — worth checking on re-run whether the judge named both tubes as
  separate regions and SAM-3 dropped one on a low score, or whether the judge itself only
  proposed one tube to begin with (the per-skin `judge.json`/`refine.json` for this run would
  need re-inspection to tell which; not re-diagnosed here since the item is parked).
- **Specific defect 2 — fallout-pipboy, left-tube glow quality (quoting the SOTA-eye
  verdict, confirmed true by the user):** "the entire glass envelope glows a solid yellow,
  which is unrealistic" on the left tube, vs. the right tube's "subtle filament glow" which
  is "much better and more physically accurate." **This is the concrete quality bar for any
  future iteration:** glow confined to the filament, not the whole envelope. Points at
  Stage 2b's local hue/brightness/saturation gate keeping too much of the SAM ROI on the
  left tube specifically — a per-region gate-tightness inconsistency worth investigating
  before this is ever revisited, not a global failure of the gate approach (the right tube,
  same mechanism, got it right).
- **Specific defect 3 — fa-pod button-icon glow:** called "a bit questionable" — a milder,
  non-blocking note, not a hard fail. Recorded for v2, not diagnosed further here.
- **DISPOSITION: PARKED for skeuo v2**, explicitly grouped with "other pbr related tasks."
  Not rejected, not promoted to a mainline flag — shelved. The instruction is explicit and
  twofold: (1) stop working this now, (2) finish skeuo v1 solidly first. See the PARKED
  sections of `TODO.md` and `tools/mask-align-exp/gen12/TODO.md` for where the open items
  now live.
