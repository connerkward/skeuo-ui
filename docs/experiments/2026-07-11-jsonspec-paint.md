# 2026-07-11 — Fenced-JSON blueprint spec vs prose prompt, for PAINT generation itself

## Question

Does delivering the per-control blueprint specification (roster, guide-colour mapping,
positions/sizes as fractions, strip cell order, congruence constraints) as a **fenced
```json``` block** in the prompt — instead of the production prose encoding — change
image-GENERATION quality/adherence? The structured-I/O experiment
(`2026-07-11-image-model-json-output.md`) tested JSON-shaped prompts only for
**extraction** (neutral there) and explicitly flagged the paint side as untested. This is
that test.

## Method

Harness: `tools/mask-align-exp/gen12/jsonspec/` — `genskin_jsonspec.py` (both arms),
`run_batch.py`, `score_jsonspec.py`, `sota_eye_jsonspec.py`, `bonus_probe.py`,
`build_page.py` → `results.html`.

- **CONTROL** — the current production prose prompt **verbatim**: captured by *importing*
  `genskin.py` and running its own `main()` (module attrs `HERE` and
  `BLUEPRINT_ARM_WEIGHTS` monkeypatched in memory to redirect output into `jsonspec/` and
  force the 'solid' arm; the file is never edited). Byte-identical to a production
  templated/solid run.
- **TREATMENT** — identical semantic content, but the per-control spec is one fenced
  ```json``` block (per-control: id, role, guide_color name+RGB, icon, position fractions,
  size fractions; plus strip order + congruence rule) with a one-line "machine-readable
  spec; follow it exactly" preamble. The narrative clauses (theme, camera, no-text,
  empty-cavity, zero-residue, exact-fit, shuffle-states, mask column) stay prose,
  referencing "the spec" generically. Same information, different encoding.
- **Both arms share ONE blueprint image** — the treatment dir gets a byte-identical copy of
  the control arm's production solid-guide canvas. Prompt encoding is the only variable.
- Matrix: 2 themes (`wc-goldshield`, `fa-pod` — composes with abshape/twoimg) × 2 seeds
  (121, 134) × 2 arms = **8 gens**. Model `gemini-3-pro-image-preview` via Vertex AI
  (project `muser-2605300220`, global), 4K, 5:4, seeded.
- Scoring ($0, reused code): `extract12.py` gates (emptiness/leak/controls/region-placement/
  seek-cov); perimeter-band guide-hue **bleed-ring** metric (imported from
  `twoimg/roster_audit.py`, the stated-verbatim copy of `score_twoimg.py`'s); per-control
  **template drift** (roster-audit `drift_table`). SOTA-eye (`google/gemini-2.5-pro` via fal
  `openrouter/router/vision`, reasoning:true) for baked text / rearrangement / residue /
  quality, one call per gen; every VLM claim adjudicated against pixels
  (verify-outputs-rule).

## Results (full artifacts: `tools/mask-align-exp/gen12/jsonspec/results.html`)

| pair | gate C / T | mean bleed-ring C → T | mean drift C → T | notable (adjudicated) |
|---|---|---|---|---|
| wc 121 | FAIL (emptiness) / **PASS** | 1.45% → 0.13% | 468 → 877px | T: clean colours but thumb BAKED in seek groove (gate missed it) + rune glyphs on strip states |
| wc 134 | FAIL (emptiness) / FAIL (region-misplaced:visualizer, emptiness) | 7.53% → 2.40% | 565 → 576px | C: ALL 5 buttons + shuffle slot flooded in exact guide hues |
| fa 121 | PASS / PASS | 3.93% → **0.00%** | 734 → 466px | C: repeat/queue flooded + green stripe; T fully clean |
| fa 134 | PASS / PASS | 7.24% → 3.72% | 993 → 646px | BOTH arms' buttons echo guide hues; T's mask blob for `next` misplaced (1221px) |

Aggregates: gate PASS **2/4 control vs 3/4 treat**; bleed-ring lower in treat **4/4 pairs**
(mean 5.04% → 1.56%; 4/4 sign at n=4 is p=0.0625 one-sided — directional, not significant);
drift lower in treat 2/4 (mean 690 → 641px — both arms treat the locked template as a
suggestion on a ~2300px canvas).

SOTA-eye returned FAIL 8/8, but its dominant reason — "vol/seek/shuffle parts missing from
the device, sitting on a strip below" — is a **false flag on the before-assembly design**
(empty cavities + sprite strip ARE the spec; the eye prompt failed to say so — fixed
context for future eye passes). Its residue calls were confirmed by the pixel metric in
every flood case; its "next button absent" (fa-treat-134) and "shuffle cutout missing"
(fa-treat-121) claims were **overruled** by crops (misplaced mask blob and a
present-and-correctly-empty slot, respectively). Quality: it rated 6/8 gens
EXCELLENT-rendered regardless of arm.

## Verdict

**Neutral-to-mildly-helpful; not a fix.** The fenced-JSON encoding cost nothing measured
and directionally improved both residue axes (bleed lower in every paired gen; gate 3/4 vs
2/4). It does **not** fix the two dominant paint defects: layout drift is equally bad in
both arms, and guide-hue button echo still occurred in a treatment gen. Encoding the spec
as JSON doesn't make the image model *obey* it — it mainly seems to reduce how often the
guide-colour words get painted as pigment. Don't adopt as a fix; if adopted it appears
safe. The real levers remain key selection, icon-no-echo clauses, and mask-column
decoupling. n=4 pairs, single roll per cell — directional.

## Bonus — Google's bounding-box docs + convention probe

**Docs finding** (fetched 2026-07-11): Google documents bounding boxes at
`ai.google.dev/gemini-api/docs/image-understanding` — "The box_2d should be
[ymin, xmin, ymax, xmax] normalized to 0-1000" — under **image understanding** (examples
use `gemini-3.5-flash`; no definitive model roster). The image-GENERATION docs
(`.../image-generation`, covering gemini-3-pro-image / Nano Banana Pro) claim **no**
bounding-box, detection, or structured-coordinate capability anywhere. Google's own
dev-blog workflow for "bounding boxes + Nano Banana Pro" uses a *separate understanding
model* (Gemini 3 Flash + code execution) to compute boxes — the image model never emits
them. So "Google states this as a use case" holds only for the understanding models;
asking gemini-3-pro-image for boxes is off-label.

**Convention probe** (1 call, `bonus_probe.py` / `bonus_probe.json`): re-asked
gemini-3-pro-image for the wc-goldshield boxes using Google's exact documented convention
(box_2d, [ymin,xmin,ymax,xmax], 0-1000). Read as documented: mean IoU 0.096. But
inspection shows the model emitted the last two elements **transposed** —
`[ymin, xmin, xmax, ymax]` (every 3rd element matches gt xmax, every 4th gt ymax). Under
that reading: **mean IoU 0.79, 9/10 controls at 2–26px center error** (only album_art
misses — the known display-window ambiguity). So the 0-1000 box_2d framing **does fix the
broken y-frame** the imgjson experiment found with the ad-hoc 0-1 x/y/w/h ask (IoU 0.003,
y-scale ~0.66 ≈ a square-frame remap): the model reasons in its trained 0-1000 box space,
and our 0-1 normalized ask was the frame-breaker. Caveats: n=1 call; the element-order
transposition's stability is untested; and it emits thinking-prose before the JSON, needs
["TEXT","IMAGE"] modalities, and still can't be production placement-grade without an
order-tolerant parser + validation. `ai-image-coords-rule`'s "don't make a noisy VLM
load-bearing" stands, but its calibration note should record: with the documented 0-1000
convention (order-corrected), the image model's boxes are ~10× better than the imgjson
numbers suggested.

**Stability probe (same day, follow-up — the caveats above, tested):** 3 more calls in the
same documented convention (`stability_probe.py` / `stability_probe.json`; seeds 72/73
repeat wc-goldshield, seed 74 cross-checks diablo-gothic, ~$0.15). The frame fix is
**validated** — best-reading mean IoU 0.72 / 0.54 / 0.37 (vs 0.79 on the n=1 probe), with
per-control centers ≤26px for 9/10, 8/10, 5/10 controls respectively — but the transposition
is **refuted as a stable quirk**: seeds 72/73/74 all emitted Google's DOCUMENTED order
([ymin,xmin,ymax,xmax]); only the original seed-71 call transposed. Element order varies
call-to-call → a fixed slot-swap calibration is wrong on some calls; a consumer would need
per-call disambiguation (non-positive w/h under the documented reading flagged 4/10 boxes on
seed 71's call — a tell, untested as a discriminator). Whole-control semantic swaps also
recur (seed 73: vol+shuffle boxed the strip sprites, 1852/1130px off; seed 74:
visualizer↔album_art, ~1090px). Net: real spatial sense in the native convention, NOT
witness-grade — the TEXT model (stable convention + responseSchema, ~13px centers, cheaper
per call) dominates for any witness role; extract12 stays load-bearing. The imgjson
experiment's pages + doc now carry a ROUND 2 CORRECTION reflecting this
([2026-07-11-image-model-json-output.md](2026-07-11-image-model-json-output.md),
`imgjson/explain.html#round2`, `imgjson/index.html` banner).

## Ops notes

- `twoimg/score_twoimg.py` has an **unguarded top-level scoring loop** — importing it
  executes a full twoimg re-score and rewrites twoimg's git-tracked `regions.json` files
  (hit live; reverted with `git checkout`). `score_jsonspec.py` imports
  `roster_audit.py` (guarded) instead.
- `genskin.py:edit_vertex` (single-image) has **no 429 retry** (only `edit_vertex_multi`
  does) — one gen died to RESOURCE_EXHAUSTED under concurrency and was retried manually.
- fal `openrouter/router/vision` intermittently returns `output: ""` with ~300 completion
  tokens burned (3/8 first-pass calls) — delete the vlm.json and re-call.

## Reproduce / spend

- `cd tools/mask-align-exp/gen12/jsonspec && python3 run_batch.py && python3
  score_jsonspec.py && python3 sota_eye_jsonspec.py && python3 bonus_probe.py && python3
  stability_probe.py && python3 build_page.py` (gcloud auth on the project; FAL_KEY in
  central/.env). `stability_probe.py --rescore` rescores from the saved raw responses, $0
  (seed 72's raw was swept by the 2026-07-11 unscoped-commit incident — see
  `docs/INCIDENTS.md`; --rescore reconstructs it from the recorded box_2d arrays).
- **Spend:** 8 gens × ~$0.24 = $1.92 + bonus probe ~$0.05 (text-out only) + stability
  probe 3 calls ≈ $0.15 + 11 VLM calls × ~$0.02 ≈ $0.22 → **≈ $2.35 total**.
- Judged by: deterministic gates/metrics + SOTA-eye (gemini-2.5-pro) with per-claim pixel
  adjudication by the agent. **Human verdict: PENDING** — review `results.html`.
