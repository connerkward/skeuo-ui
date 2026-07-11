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
- **Superseded same-day by the human-overrule axis-separated re-score** (see that section
  below) — the 0/8 full-contract number stands as "not ship-ready as prompted," but tick
  DRAWING quality itself is re-scored 6/7 present-and-coherent, 5/7 shape-distinct. Rehab is
  now recommended (light clause, director-gated), not abandoned.

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

**Shipped same-day as the fallback (commit `d2271894`): `KNOB_TICKS_ENABLED` CSS/SVG ticks in
`build_player.py`.** See the human overrule below — this fallback's framing changes (director
fallback, not the sole path) but the code itself was correct to ship as a working baseline.

## Human overrule + axis-separated re-score (2026-07-11)

Conner overruled the 0/8 verdict above (verbatim, recorded as human-labeled gold per
[[human-labeled-data-rule]]):

> "also the baked tik marks are all actually perfect, except maybe the baked text. other than
> that the ticks look near perfect, unless i am missing something."

He additionally directed (verbatim, folded in below): *"also adding ticks or not should be up
to the director if it matches the theme. dont overconstrain tick marks style. they look great."*

**Why the 0/8 number was misleading.** `adjudication.json`'s `adjudicated` field was a
**full-contract AND-gate**: any single defect — text leakage, layout drift, icon-colour bleed,
*or* weak tick distinctness — failed the whole gen. That's the right bar for "is this
ship-ready as tested," but it silently buries the question this doc's title actually asks
("can the model bake tick marks") under three largely unrelated failure modes. Re-scoring the
same 7 painted gens (no new generations — direct full-res crop re-inspection of the existing
`paint.png`s, this $0 pass) on **separated axes** — full working data in
[`axis-rescore.json`](../../tools/mask-align-exp/gen12/knobticks/axis-rescore.json):

| gen | Axis 1 — TICK QUALITY ONLY | Axis 2 — text | Axis 3 — layout | Axis 4 — icon bleed |
|---|---|---|---|---|
| fa-pod ticks_ctr s501 | **EXCELLENT** — diamond CENTER@12, tapered minors, distinct longer start/end bars ~8/4 o'clock, no text | none | MAJOR (knob at ~0.45,0.40 vs template 0.42,0.57 — template spot shows a toggle instead) | none |
| fa-pod ticks_ctr s502 | **EXCELLENT** — diamond CENTER, tapered minors, glowing LED-style end markers (shape-distinct even without the words) | MIN/MAX baked | MAJOR (knob at ~0.64,0.34) | none |
| fa-pod ticks01 s501 | N/A — no image, 3 attempts | — | — | — |
| fa-pod ticks01 s502 | **ABSENT** — single diagonal slot, no radial system at all (the one genuine tick-drawing miss) | MAX baked | none (on-template) | none |
| steam ticks01 s401 | **GOOD** — full ring + L-bracket end-stop at ~4-5 o'clock (confirmed via a wider crop this pass; the earlier "disputed" call came from a 1.9r crop that clipped the bracket) | none | MAJOR (knob at ~0.75,0.68) | none |
| steam ticks01 s402 | **GOOD** — evenly-spaced ring + confirmed L-bracket end-stop, taller top-of-sweep tick | none | MAJOR (knob at ~0.42-0.55,0.72) | 5 icons tinted to guide keys |
| steam ticks_ctr s401 | **GOOD, PARTIAL** — diamond CENTER distinct; minor ticks uniform, no shape-distinct start/end (the one real axis-1 shortfall) | none | minor (knob slightly low) | 5 icons tinted to guide keys |
| steam ticks_ctr s402 | **GOOD, TEXT-DEPENDENT** — clean gear-ring + triangle CENTER pointer, but MIN/MAX/CENTER *words* are the primary differentiator, not shape alone | CENTER/MIN/MAX baked | minor | none |

**Deterministic-detector caveat found this pass:** the harness's own pixel-angle detector
(`score_knobticks.py::detect_ticks`) crops from the fixed template `knob_center_frac`
(0.42, 0.57). On **4/7 gens** (fa-pod-ticks_ctr-501/502, steam-ticks01-401/402) that crop
missed the real knob entirely (layout drift moved it) — those 4 `span_deg` values in
`scores.json` measure unrelated content (toggles, buttons, screens), not the ticks. Flagged
per-card in the rebuilt results page rather than silently trusted.

**Ticks-only score: 6/7 painted gens render a coherent, theme-appropriate tick/mark system at
the socket** (all except fa-pod-ticks01-502). **5/7 have start/end-or-center marks that are
visually distinct BY SHAPE, independent of any text** (fa-pod-ticks_ctr-501/502,
steam-ticks01-401/402, steam-ticks_ctr-402); only steam-ticks_ctr-401 has a truly uniform ring
where shape distinctness fails, and fa-pod-ticks01-502 has no tick arc at all.

**Angle spread (hand-verified clock-position reads from full-res crops this pass, NOT the
compromised detector spans above):** every tick-bearing gen places its start mark at 7-8
o'clock (≈ −120° to −150°) and its end mark at 4-5 o'clock (≈ +120° to +150°) against the
shipped −135°/+135° convention — a spread of roughly **±25° around the target, consistent
across both themes, both arms, and every seed that produced a tick arc.** The model is not
guessing angles randomly; it's converging on the intended register.

**Revised verdict:** the user's overrule holds. Tick-*drawing* quality is strong-to-excellent
on 6/7 and shape-distinct on 5/7, independent of the collateral axes. The prior 0/8 correctly
flags "not ship-ready as prompted" but was never evidence that the model can't paint good
ticks — the failures cluster almost entirely in **collateral that has known, separate fixes**:

- **Collateral A (baked text) — PROMPT-FIXABLE.** `tick_clause()` in `gen_knobticks.py`
  repeats the literal words MIN/START, MAX/END, CENTER/DETENT throughout — the exact
  negative-prompt backfire already diagnosed and fixed for ON/OFF/I/O tokens (commit
  `3eeccc55`, "remove literal ON/OFF/I/O tokens from prompt (negative-prompt backfire baked
  them as text)"). Per Conner's directive above, the rehab clause must be **light**: describe
  that tick/indicator marks exist around the knob sweep, in the device's own material
  language, and nothing more — no label vocabulary, no style prescription (style is
  unconstrained; the 6/7 sample already spans diamonds, LEDs, L-brackets, gear-tooth rings,
  and all read well).
- **Collateral B (layout displacement) — a KNOWN, pre-existing baseline failure mode**
  (blueprint-trial-arm / seed layout drift, tracked separately in this repo's generation-system
  work), not something the tick clause introduced. 6/7 painted gens show it at some severity,
  which is roughly in line with the wider gen12 batch's drift rate, not obviously hotter.
- **Collateral C (guide-colour icon bleed)** — 2/7, same known systemic issue the leak-gate
  work is already fixing; unrelated to ticks.

**Product decision — baked vs CSS ticks (open, not implemented here):**
- **Baked (paint-time)** — painterly integration (ticks sit IN the material — backlit,
  engraved, gear-toothed — reading as part of the object, not an overlay), per-skin unique
  style with zero extra authoring. Costs: paint-time risk (text/layout collateral above,
  though independently fixable), no guaranteed presence (fa-pod-ticks01-502 skipped it
  entirely), and no free machine-readable rotation metadata (the in-call JSON self-report is
  a verbatim prompt-echo, confirmed unusable this experiment).
- **CSS (`KNOB_TICKS_ENABLED`, commit `d2271894`)** — deterministic, free, geometrically exact
  (computed from `regions.json`'s known socket centre/radius), uniform across every skin
  regardless of paint-time luck. Costs: reads as an overlay rather than a baked material
  feature; less per-skin visual variety unless themed hard via `css.accent`.
- **Recommendation, reflecting the user's lean:** pursue **baked ticks, gated by the DIRECTOR
  per theme** (does ticks fit THIS theme — cross-ref
  [`gen12/TODO.md`](../../tools/mask-align-exp/gen12/TODO.md) "Let the DIRECTOR decide whether
  optional pipeline stages are worth running per skin"), with the light rehab clause above,
  **unconstrained style** (no shape/label prescription). CSS ticks become the *fallback* for
  skins where the director says ticks-fit-the-theme but the paint roll didn't produce them
  (mirroring fa-pod-ticks01-502's miss), or stay off entirely on skins whose baked ticks
  already render. Rehab path: reword the clause, ~2-4 validation gens, ~$1 — well under the
  original $3 budget.

Revised results page (per-gen axis-1-only badge + collateral breakdown, plus this section's
banner): `tools/mask-align-exp/gen12/knobticks/index.html` (served).
