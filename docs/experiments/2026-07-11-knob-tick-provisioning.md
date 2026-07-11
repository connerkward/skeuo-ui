# 2026-07-11 — Knob tick-mark provisioning + in-call rotation metadata

## Question

Can the paint model be PROVISIONED via prompt to (a) bake a themed tick-mark / start-end
indicator system around each knob socket onto the skin, and (b) in the SAME generation call,
return the knob's rotation range as machine-readable JSON (`{vol:{start_deg,end_deg,zero}}`)?
Two prompt arms: **ticks01** (0..1 single sweep, min+max marks + minor ticks) and **ticks_ctr**
(-1..0..+1 balance sweep with a distinct 12-o'clock CENTER/DETENT mark).

## Method

- Harness: [`tools/mask-align-exp/gen12/knobticks/gen_knobticks.py`](../../tools/mask-align-exp/gen12/knobticks/gen_knobticks.py)
  — imports mainline `genskin.py`'s constants/blueprint/prompt machinery unmodified (templated
  mode, solid guides, the abshape-verdict winner); adds ONLY the tick-arc clause + a JSON
  metadata ask, and calls Vertex `gemini-3-pro-image-preview` with
  `responseModalities=["TEXT","IMAGE"]` (the untested mode flagged in
  [`docs/design/2026-07-11-semantic-emissive-research.md`](../design/2026-07-11-semantic-emissive-research.md) §4).
  `imgjson/` was EMPTY at this experiment's start; the parallel
  [imgjson experiment](./2026-07-11-image-model-json-output.md) landed mid-run and independently
  established the same ask-shape (TEXT must ride WITH IMAGE modality; TEXT-alone = 400;
  `responseSchema` on the image model = hard 400) — this experiment's plain-prose JSON ask was
  the right call, and both experiments converge on "the image model's text side-channel is not
  a usable measurement" (theirs: bbox y-frame broken, IoU 0.003; here: verbatim prompt-echo).
- 2 themes (steam-porthole, fa-pod) × 2 arms × 2 seeds = **8 generations**, 4K, 5:4.
- Scoring: [`score_knobticks.py`](../../tools/mask-align-exp/gen12/knobticks/score_knobticks.py) —
  deterministic knob-socket crops at KNOWN template coords + a radial tick-angle detector
  (coarse, flagged as such), plus a SOTA-eye pass (`google/gemini-2.5-pro` via fal
  `openrouter/router/vision`, `reasoning:true`) per gen. VLM treated as a **witness, not judge**:
  every verdict adjudicated against direct full-res crop inspection —
  [`adjudication.json`](../../tools/mask-align-exp/gen12/knobticks/adjudication.json).
- Angle convention = the shipped runtime knob technique (−135°..+135°, see
  [2026-07-01-knob-rotation.md](./2026-07-01-knob-rotation.md)).
- Results page: `tools/mask-align-exp/gen12/knobticks/index.html` (served; per-gen crops,
  verdicts both raw-VLM and adjudicated, model + cost banner).

## Results

**Generation reliability of the TEXT+IMAGE mode itself:** 7/8 calls returned an image;
**fa-pod-ticks01-501 returned thought-text-only with NO image on 3 consecutive attempts**
(seed-bumped retries). The metadata ask can kill image output entirely.

**Tick-arc presence:** 6/7 painted gens rendered a themed tick arc at the knob socket
(fa-pod-ticks01-502 rendered none). Presence is easy; the full contract is not:

| gen | VLM witness | adjudicated | killing defect |
|---|---|---|---|
| steam ticks01 s401 | UNRELIABLE | FAIL | uniform ring, start/end marks disputed (L-brackets clipped from VLM crop); socket floor reads as installed knob |
| steam ticks01 s402 | RELIABLE | **FAIL (override)** | knob displaced off template socket; guide-colour icon bleed on all 5 buttons; pointer notch misaligned |
| steam ticks_ctr s401 | UNRELIABLE | FAIL | beautiful 12-o'clock diamond, but start/end/center marks identical to each other; icon bleed |
| steam ticks_ctr s402 | RELIABLE | **FAIL (override)** | literal words **"CENTER", "MIN", "MAX" baked into the housing** (VLM read the text yet said DAMAGE NONE) |
| fa-pod ticks01 s501 | — | FAIL | **no image at all**, 3 attempts |
| fa-pod ticks01 s502 | UNRELIABLE | FAIL | no tick arc; "MIN"/"MAX" text engraved on a slot |
| fa-pod ticks_ctr s501 | RELIABLE | **FAIL (override)** | tick arc excellent but ENTIRE layout rearranged (knob at 0.35H vs template 0.57H); VLM's crop contained no knob — verdict confabulated |
| fa-pod ticks_ctr s502 | UNRELIABLE | FAIL | start/end marks identical to minor ticks; "MIN"/"MAX" text baked |

**Arm split (VLM witness):** ticks01 1/3, ticks_ctr 2/4 RELIABLE. **Adjudicated: 0/8 PASS.**

**Metadata half:** text part returned 7/7 — but it is dominated by "thought" narration;
a parseable JSON object appeared in only **4/7**. Critically, **all 4 parsed JSONs echo the
prompt's example values verbatim** (`start_deg:-135, end_deg:135`) — zero evidence the model
measured its own painted marks (the painted marks visibly vary: VLM independently read 7/5
o'clock on some gens, 8/4 o'clock on others). Agreement with the deterministic pixel spans:
0/4 within ±15° (the detector is noisy — it fires on knurling/gear teeth and full rings — but
the echo pattern alone disqualifies the JSON as a measurement). The self-report is a parrot,
not a report — confirming the circularity risk flagged in the semantic-emissive research doc §4.

**Collateral damage (the clause is not free):**
- **Text contamination in 3/7 painted gens** — the clause's own vocabulary (MIN/MAX/CENTER)
  leaked as literal engraved labels despite the production ABSOLUTELY-NO-TEXT clause. Directly
  attributable to the tick/metadata clauses; production gens don't bake these words.
- Guide-colour icon bleed on 2/7 (steam s402/ctr-s401 button icons tinted exactly their guide
  keys) and layout drift up to full rearrangement on 2/7 — both are KNOWN baseline failure
  modes (twoimg/abshape), so attribution to the new clause is uncertain, but the 8-roll sample
  ran hotter than the gen12 production batch's.

## Human verdict

Adjudicated by the running agent (crop-level inspection + VLM cross-check), 2026-07-11, for
Conner's review:

**Baked ticks: UNRELIABLE** (0/8 full-contract passes; 6/7 render *an* arc, but distinct
start/end marks at consistent angles WITHOUT text contamination or layout damage never
co-occurred). **In-call metadata: UNUSABLE** (4/7 parse rate, and every parse is a verbatim
echo of the prompt's example — circular, measures nothing).

## Spend

8 Vertex 4K gens (incl. the 3-attempt no-image failure ≈ 10 image-attempt calls, ~7 billed
with image output) ≈ **$1.90**; 8 SOTA-eye calls ≈ **$0.16**. Total ≈ **$2.10** (≤$3 budget).

## Changed as a result

- Recommendation recorded (below); no pipeline change — the tick clause does NOT graduate to
  `genskin.py`. Experiment code + record committed in this change (see commit for SHA).
- `docs/design/2026-07-11-semantic-emissive-research.md` §4's "image-model self-report is
  circular" hypothesis is now empirically CONFIRMED (echo behavior observed live).

## Recommendation

**CSS-tick fallback test warranted: yes.** What it should use: keep the paint prompt
tick-free (production prompt unchanged); render tick arcs as a CSS/SVG overlay ring in
`build_player.py`, positioned from the KNOWN socket centre/radius already in `regions.json`
(matte-hole centroid — deterministic, material-agnostic), sweeping the fixed runtime
convention −135°..+135° (`zero:"start"` for volume, `zero:"center"` reserved for balance-type
knobs), themed via the director's existing `css` schema colours (`css.track`/`css.accent`) +
a `mix-blend-mode` (multiply/overlay) pass so ticks read as engraved rather than stickered.
Rotation metadata then needs no model at all — it's authored, exact, and identical across
every skin.
