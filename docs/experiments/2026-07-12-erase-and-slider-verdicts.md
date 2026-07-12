# 2026-07-12 — Consolidated verdicts: erase-model bake-off, seek-slider overshoot, switch-slot housing, knob ticks, round-3 review

This is a **consolidation pass**, not a new experiment — it pulls together every empirical
decision made across gen12's erase/slider/switch/tick work this session so the record lives
in one place instead of scattered across per-experiment docs, commit bodies, and `TODO.md`.
Every number below is cited to its source; nothing here is invented. Per-topic detail lives in
the linked docs — read those for method; this doc is the index + the decisions.

## 1. Erase-model bake-off (arms 1–5) — the headline decision

**Question:** what model should `erase12.py` call to repair a baked slider-thumb defect
(remove a painted-in handle, continue the groove material seamlessly)?

**Arm 1 — original 6-model, 5-skin bake-off** (`diablo-gothic`, `fallout-pipboy`,
`fallout-vault`, `n64-cutscene`, `wc-goldshield`; tight crop around the logged defect bbox):

| Model | PASS rate (by eye, n=5) | $/repair |
|---|---|---|
| Vertex `gemini-3-pro-image` (incumbent) | 100% (5/5) | $0.241 (4K-tier, corrected — see below) |
| LaMa (local) | 50% (2.5/5, partial-weighted) | $0 |
| Bria Eraser (bonus arm, n=2) | ~63% | $0.04 |
| Qwen Image Edit Inpaint | 50% (2.5/5) | $0.031 |
| Z-Image Turbo Inpaint | 0% (0/5) | $0.010 |
| FLUX.1 [pro] Fill | 0% (0/5) | $0.052 |
| FLUX.1 [dev] Fill | 0% (0/5) | $0.037 |

Finding: the three cheap **prompted-fill** models (Z-Image, FLUX Pro/Dev Fill) don't fail on
imperfect edges — they **hallucinate unrelated content** (a fake UI tooltip caption, a
fabricated slider widget, readable text). A cheap deterministic gate and even a VLM witness
missed several of these; only direct full-res human inspection caught the pattern.
Source: [2026-07-12-inpaint-bakeoff.md](./2026-07-12-inpaint-bakeoff.md).

**Also found in Arm 1's Phase 1 re-verification:** `genskin.py:edit_vertex()` hardcodes
`imageConfig.imageSize:"4K"` on every call regardless of crop size, so every Vertex repair —
including 1024px crops — was silently billed at the **4K tier ($0.241)**, not the ~$0.136 a
crop-size-only estimate assumed. Fixed separately, commit
[`0c4b424c`](../../tools/mask-align-exp/gen12) (erase12's Vertex crop repairs silently billing
the 4K output tier).

**Arm 2 — whole-slot masking addendum** (mask the entire groove, not just the thumb; 3 skins,
LaMa/Bria/Vertex): **negative** for generative erasers — Vertex flips from 5/5 reliable (tight
crop) to 2/3 failing at slot scale (adds rune glyphs, or leaves the thumb untouched); only
LaMa (classical, no hallucination capacity) stays consistent. Commit
[`25b3c4eb`](../../tools/mask-align-exp/gen12) ("whole-slot masking — NEGATIVE for generative
erasers"); composite step [`2bc0da99`](../../tools/mask-align-exp/gen12). Routing decision: keep
the erase mask **tight** for generative erasers; only pair whole-slot masking with LaMa.

**Arm 3 — `inpaintbake/editors/`** (vertex / gemini-2.5-flash / gemini-3.1-flash / finegrain /
gpt-image-2, 3 skins — diablo-gothic, wc-goldshield, fallout-vault):

| Model | PASS (n=3) | Note |
|---|---|---|
| Vertex (incumbent) | 3/3 | Best-in-class; only Vertex preserves diablo-gothic's glowing rune-inlay crack |
| gemini-2.5-flash (no glow clause) | 2/3 | Removes the rune-glow entirely on diablo-gothic — loses a material feature |
| gemini-3.1-flash | 1/3 | Hallucinates a spiral/scroll motif on wc-goldshield; horn remnants left on diablo-gothic |
| finegrain (dedicated eraser) | 0/3 | Leaves object remnants on all 3, including the flattest material (fallout-vault) |
| gpt-image-2 | 1/3 | Borderline smudge/texture mismatch on 2/3 |

Source: [`inpaintbake/editors/verdicts.json`](../../tools/mask-align-exp/gen12/inpaintbake/editors/verdicts.json).

**Arm 4 — `inpaintbake/arm4/`** (dedicated erasers + a glow-preserve prompt clause, same 3 skins):

| Model | PASS (n=3) | Note |
|---|---|---|
| Vertex (reused baseline) | 3/3 | unchanged |
| gemini-3.1-flash (reused) | 1/3 | unchanged |
| gemini-2.5-flash-**glow** (new clause) | 2/3 | **Over-corrects**: hallucinates a NEW glow-chain/filigree pattern running the entire groove on diablo-gothic — not present anywhere else on the frame. A different failure mode than Arm 3's non-glow version (which erased the glow instead) but still a FAIL |
| flux-pro/erase (dedicated) | 0/3 | Barely touches the defect even on the flattest material tested (fallout-vault, "pixel form/highlights/shadows all intact") |
| object-removal (dedicated) | 0/3 | Same failure class — leaves an unchanged or smudged remnant, plus a new scratch artifact on fallout-vault |

Source: [`inpaintbake/arm4/verdicts.json`](../../tools/mask-align-exp/gen12/inpaintbake/arm4/verdicts.json).

**RULED OUT after Arms 1/3/4:** cheap dedicated (no-prompt) erasers — LaMa (50%), Bria (~63%,
too small a sample), finegrain (0/3), flux-pro/erase (0/3), object-removal (0/3) — none reach
production reliability, and the pure-object-removal models fail even on the simplest material
tested. These lack a world-model of "what should be here"; cost advantage doesn't offset a
largely-unusable output rate.

**Arm 5 — `inpaintbake/arm5/`, the deciding run** (gemini-2.5-flash vs gpt-image-2, **plain
erase prompt, no glow-preserve clause**, 5 skins incl. steam-porthole):

| Skin | gemini-2.5-flash | gpt-image-2 |
|---|---|---|
| diablo-gothic (ornate, rune-glow) | **PASS** — glow naturally preserved with NO glow instruction | SOFT — glow largely lost, groove reads muddy |
| fallout-pipboy | PASS | PASS |
| n64-cutscene | PASS | PASS |
| claymation | PASS | PASS |
| steam-porthole | HARD — ambiguous target (masked region is actually a play/pause button, not the slider thumb; model correctly declined to erase it) | HARD — **catastrophic**: solid black square over the entire masked region |

Source: [`inpaintbake/arm5/verdicts.json`](../../tools/mask-align-exp/gen12/inpaintbake/arm5/verdicts.json).

**gemini-2.5-flash: 4/4 clean on every genuine slider groove**, including the ornate
rune-glow case — at **$0.039/call** (~6× cheaper than the old 4K-tier Vertex default,
$0.241/call). gpt-image-2: 3/4 + 1 soft at $0.0548/call, plus a hard mask-collapse failure
mode on the ambiguous steam-porthole crop.

**The headline finding: the glow-preserve clause added in Arm 4 was the problem, not the fix.**
Arm 3's plain-prompt gemini-2.5-flash erased the glow; Arm 4 added an explicit
"preserve the glow" instruction and got a *worse* failure (hallucinated new glow ornamentation
never present in the source); Arm 5's plain prompt — no glow language at all — preserved the
glow correctly and naturally. Prompting harder for a specific material feature made the result
worse; the model handles it fine unprompted.

steam-porthole's HARD result on both models is a **detector bug, not a model failure** —
`detect_bbox()` in `erase12.py` picked a legitimate play/pause button as the crop, not the
seek slider thumb. Both models "failed" on garbage input. Carried forward as an open bug
(below).

**Whole-slot masking (deprecated Vertex Imagen mask-inpaint path):** the older Vertex Imagen
dedicated mask-inpaint endpoint has no drop-in replacement in the current Vertex/Gemini image
API surface; the shipped chain routes through `edit_vertex()`'s general image-edit call
instead (crop + re-composite, not a native mask-inpaint primitive).

### Final routing shipped

Commit [`fcab53d4`](../../tools/mask-align-exp/gen12) — `erase12.py`:

```python
ERASE_MODEL_CHAIN = ["gemini-2.5-flash", "gpt-image-2"]
```

`genskin.py:edit_vertex()` gained a `model=` override (default unchanged, every existing
caller byte-identical); `erase_model()` split into `erase_model_gemini25()` /
`erase_model_gpt_image2()` / `erase_model_vertex_pro()` (the old default, kept intact as a
deep fallback via `--method model-pro`), sharing one `_feathered_composite()` helper and the
same `ERASE_PROMPT`. `run_model_chain()` rescues the **first/primary** attempt on full-chain
failure, not the last — a live validation bug caught during shipping (see TODO.md's
"erase12 default erase model" entry): gpt-image-2's flat-fill failure mode scores a
*lower/smoother* `seam_delta` than gemini's correct-but-marginally-flagged result, so the
metric can't discriminate; only direct crop inspection caught it.

**Spend:** Arm 1 ~$2.05 total (generation $1.70 + VLM judging $0.35). Arm 2 $0.52. Arms 3–5
each ran within the same ≤$3 experiment budget; live-validation of the shipped chain on
fallout-pipboy ≈ $0.094.

## 2. Seek-slider-outside-slot fix

**Recurring cross-roster complaint** ("CSS slider outside slot", flagged on claymation,
diablo-gothic, fallout-vault, n64-cutscene, ps1-crunchy across round1/round2/round3 review).

**Root cause:** `extract12.py`'s seek-groove `travel` value stacked TWO widenings — the
intentional outward "coverage span" walk beyond the model's declared mask cell (correct, per
`placement-invariants-rule` §1), PLUS an unconditional, redundant **+2%-of-span pad** on top,
with `build_player.py` positioning the thumb's outer edges and the seek-track/fill overlay to
`travel`'s bounds with **no clamp against `device`** anywhere downstream.

**Fix:** (1) `extract12.py` drops the redundant pad — `travel = device`'s walked span, exactly.
(2) `build_player.py` hard-clamps `travel` to `device` at the single point both the thumb and
the track/fill overlay read it — a defense-in-depth floor that protects any already-baked
`regions.json` and any future extractor regression.

**Verification (real shipped `player.html`, Playwright `getBoundingClientRect`, not a
reimplementation):** overshoot measured at both travel extremes on all 5 flagged skins:

| skin | overshoot before | overshoot after |
|---|---|---|
| diablo-gothic | ~24px / 3712px tall (0.6%) | **0px** |
| fallout-vault | ~11px / 460px wide (2.4%, real-runtime measured) | **0px** |
| n64-cutscene | ~4.2px / 460px (0.9%) | **0px** |
| ps1-crunchy | ~4px / 460px (0.9%) | **0px** |
| claymation | ~3.2px / 460px (0.7%) | **0px** |

`gate.seek_cov` (travel span / device extent, 1.0 = exact): 1.039–1.04 → **1.0 exactly**, all
5 skins. Real-runtime thumb edges land on `device`'s bounds within ≤0.15px (float/CSS
`aspect-ratio` rounding noise) at both extremes. Diff-validated: re-extracting against a saved
pre-fix `regions.json` changed only `travel[0]`, `travel[1]`, and `gate.seek_cov` — no other
field moved.

Shipped commit [`0d750450`](../../tools/mask-align-exp/gen12). Full method + before/after
screenshots: [2026-07-12-seek-travel-overshoot.md](./2026-07-12-seek-travel-overshoot.md).
(A same-day prior fix, [2026-07-12-extract12-hitbox-and-travel-fixes.md](./2026-07-12-extract12-hitbox-and-travel-fixes.md),
already hardened the outward walk itself — saturated-walk distrust, direction-agnostic body
reference, progressive local-window widening — and reduced overshoot on some skins before
this second, independent bug was found and fixed.)

## 3. Switch-slot housing A/B/C bake-off

**Status: HELD, uncommitted** — this is a real experiment result but its working files
(`switchslot-compare/`, `switch-slot-compare.html`) are intentionally left untouched by this
consolidation pass (owned by the coherent toggle/switch rework). Recorded here so the decision
isn't lost; source: [`switch-slot-compare.html`](../../tools/mask-align-exp/gen12/switch-slot-compare.html)
(served page, verdict computed by `google/gemini-2.5-pro` via `openrouter/router/vision`
~$0.034/call, adjudicated against direct pixel inspection).

Three approaches to making the toggle housing match the switch's own silhouette instead of a
generic pill: **A** = $0 CSS-rendered shadow socket, **B** = masked AI inpaint of a shaped
recess (~$0.04/edit), **C** = the housing baked directly into the same paint call as the rest
of the device (~$0.24/regen).

**VERDICT: C wins on quality, B is the cost-effective runner-up, A is not shippable.**

- **C (baked)** — material/lighting 100% consistent (housing generated in the same call as
  the rest of the device: scratches, edge wear, rim bevel all match). Needed one real fix:
  `extract12.py`'s track-walk (tuned for plain channels) under-measured this dogbone housing's
  true width by **~13%** and mis-centred it — a generalizable finding: shipping this
  direction means widening the walk's shape assumptions, not just the prompt.
- **B (inpaint)** — genuinely strong for the price: reads as a real carved dogbone socket
  with plausible depth/rim, correctly occludes surrounding detail, needed **no** manual
  position correction. Best cost/quality tradeoff of the three.
- **A (CSS)** — not shippable as-is: reads as a flat CSS gradient with no metal texture, and
  the erase-classical cleanup underneath left a visible soft blur the rim doesn't fully hide.
  (The VLM overstated one claim here — said the dogbone waist silhouette was "completely
  lost"; false on direct inspection, the waist is visible — corrected per verify-rule's
  witness-not-judge adjudication.)

**Recommendation on file:** if per-skin spend is acceptable, ship C and fix the track-walk
width assumption in `extract12.py` so it generalizes past pill/channel shapes (a pipeline fix,
not a per-skin patch, per `fix-generalizable-rule`). If spend must stay near-zero, B is the
pragmatic middle. TODO'd as a bake-off in commit [`8eb20f51`](../../tools/mask-align-exp/gen12);
not yet landed in the shipping pipeline — gated on the switch-slot direction decision (A/B/C)
being made first, which this doc records but does not itself finalize.

## 4. Knob ticks — the record corrected

`docs/experiments/2026-07-11-knob-tick-provisioning.md`'s original headline ("0/8 adjudicated
PASS", "Baked ticks: UNRELIABLE") was a full-contract AND-gate score that reads, in isolation,
as "the model can't paint tick marks." **It cannot paint tick marks AND stay 100% clean of an
unrelated collateral defect (baked label text, layout drift, icon-colour bleed) in the same
roll — but tick-mark RENDERING itself is not the failure.**

Axis-separated re-score (same 7 painted gens, $0, direct full-res crop re-inspection): **6/7
render a coherent, theme-appropriate tick/mark system; 5/7 are shape-distinct without relying
on text at all** (diamonds, LED dots, gear-tooth rings, L-brackets). The one real recurring
defect is the clause's own `MIN`/`MAX`/`CENTER` vocabulary baking in as literal engraved TEXT
on 3/7 gens — a prompt-wording bug (same class as the already-fixed ON/OFF/I/O negative-prompt
backfire, commit `3eeccc55`), not a capability failure. The in-call JSON rotation self-report
is separately confirmed unusable — 4/7 parseable, and every parse is a verbatim echo of the
prompt's own example angles (measures nothing).

Correction shipped in commit [`1a45d88c`](../../tools/mask-align-exp/gen12) — a prominent
banner + closing section on the experiment doc itself, and stale `TODO.md` pointers annotated.
Full detail: [2026-07-11-knob-tick-provisioning.md](./2026-07-11-knob-tick-provisioning.md).

## 5. Round-3 human review (2026-07-12)

Commit [`36a0a9b3`](../../tools/mask-align-exp/gen12): **1 accept (diablo-gothic), 8 reject,
1 not reviewed (myst-arcanum)**. Verbatim human verdicts
(`review-round3-decisions.json`, preserved per `human-labeled-data-rule`):

| skin | disposition | note (verbatim) |
|---|---|---|
| diablo-gothic | **accept** | "near perfect. just the css goes outisde the bounds of slider slot (this is consistent needs to be fixed. switch needs rework, doesnt fit slot. maybe candinate for inpaint." |
| claymation | reject | "button alingment complete fail. css outside slot again on left side." |
| fa-pod | reject | "almost perfect. button silhouettes off for all buttons except play pause. swtich is way too huge and out of propotion. vlm should have caught this." |
| fallout-vault | reject (erase candidate: bria) | "swithc is also way oit of propotion. buttons depressions / not detected / not aligne.d css slider compeltely outside slot on both sides." |
| myst-arcanum | not reviewed | page failed to load during review (see "open bugs" below) |
| n64-cutscene | reject | "fine but CSS FOR SLIDER OUTSIDE SLOT!!!! switch doesnt match swtich slot." |
| ps1-crunchy | reject | "queue button not detected / working as button but baekd. two of same button baked. CSS OUTISDE SLOT FOR SLIDER!!! switch - same problem." |
| steam-porthole | reject (erase candidate: vertex) | "vertex is better but bria is acceptable. you didnt fix any of the issues i mentioned last time.!!!!" |

**Dominant systemic defects:** (1) CSS slider travel overshooting the slot — every single
flagged skin — now fixed, §2 above. (2) Switch/slot proportion and placement mismatch —
recurring across nearly every skin, still open (the switch-slot A/B/C bake-off in §3 is the
candidate fix, held for the coherent switch pass). **Erases approved this round:**
fallout-vault (bria), steam-porthole (vertex).

## Open bugs — carried into TODO, not solved by this consolidation pass

- **`detect_bbox()` mis-targets the wrong slot on ambiguous skins.** Confirmed by Arm 5:
  on steam-porthole the crop it selected was a play/pause button, not the seek thumb — doomed
  both erase models regardless of which model the chain picks. Next priority per the erase12
  TODO entry (commit `fcab53d4`'s follow-on note).
- **`sprite-fit:shuffle` gate regression, cross-roster**, timing-correlated with the
  in-progress `TOGGLE_TRACK_ENABLED` feature landing (commit `1a82751e`,
  [2026-07-12-toggle-track.md](./2026-07-12-toggle-track.md)). Round-3's re-extracts sit in
  `assets-<skin>/` uncommitted, held for the coherent toggle/switch pass per this task's own
  scope — not touched or diagnosed further here.
- **myst-arcanum vol-knob / page-load failure.** Round-3 review recorded no disposition for
  myst-arcanum because the review page failed to load for this skin (`page.waitForFunction`
  timeout, 0 `.pbtn` elements, a JS `pageerror`) — TODO.md traces one earlier instance of this
  same symptom to a race against a concurrent `extract12.py` re-roll rewriting `regions.json`
  mid-request (self-resolving once that batch lands), but that trace was for a *different*
  skin (`ps1-wild`) in a different session; whether round-3's myst-arcanum failure has the
  same cause is **not confirmed** — flagged, not diagnosed.
- **ps1-crunchy duplicate baked buttons.** Human note: "two of same button baked" — a
  generation-side defect (queue button rendered twice), needs a regen through the shared
  pipeline per `fix-generalizable-rule`, not a per-skin patch. Not investigated further here.

## Current state / what's next

- **Shipped and live:** the two-model erase chain (§1, commit `fcab53d4`) and the seek-travel
  clamp (§2, commit `0d750450`) are both in `erase12.py` / `extract12.py` / `build_player.py`
  today — no further action needed to benefit from either.
- **Decided but not yet landed:** the switch-slot housing direction (§3) — recommendation is
  "ship C, fix the track-walk width assumption" or "ship B if spend must stay near-zero" — is
  a real, evidenced decision sitting in an uncommitted experiment. Landing it is scoped to the
  coherent switch/toggle pass, deliberately not touched by this consolidation.
- **Corrected but inert:** knob ticks (§4) — the tick-drawing capability is confirmed good;
  whether to flip more of the 9 remaining `"css"`-default themes to `"baked"` is an open
  product call, not decided here.
- **Next real blocker:** the switch/slot mismatch that dominates round-3's rejections (§5) has
  no shipped fix yet — the A/B/C bake-off in §3 is evidence toward one, but landing it (plus
  fixing `detect_bbox()`'s mistargeting and the `sprite-fit:shuffle` regression) is what
  stands between round-3's 1/9 accept rate and a round-4 re-review.
