# Think-about notes (2026-07-11)

Three open design questions, flagged "think about, not implement" by the user. Each ends
in lettered options + a recommendation. Nothing in this doc was implemented — no code
changed as part of writing it.

---

## 1. Emissive rethink

**Current state (verified by reading the code, not memory):** `pbr_pass.py` extracts a
*baked* glyph-emissive layer via relative top-hat morphology (two kernel scales for
stroke/crack features) gated by hue-window around the theme's `lighting.emissive_color`,
then a component-area + ring/rim rejector. `build_player_pbr.py` sets
`EMISSIVE_ENABLED = False` (user verdict 2026-07-10: "randomly making parts of the image
glow in nonsensical ways," even after a relative-gate fix in `29b961e9`). Full record:
[`docs/experiments/2026-07-09-pbr-delight-emissive.md`](../experiments/2026-07-09-pbr-delight-emissive.md).

**Important finding while reading `build_player_pbr.py`:** `EMISSIVE_ENABLED` only gates
the *baked* `emissive.png` texture (light-gather from the top-hat extraction). It does
**not** gate the dynamic `registerEmissiveSource()` path — the visualizer is *already*
registered as an always-on emissive source (line ~571, color = paint sample pushed toward
`lighting.emissive_color`), and two more dynamic sources (seek-underglow, knob-pointer)
already exist but sit behind `?emdemo=1`. So the disabled thing is narrower than "all
emissive" — it's specifically the baked-glyph-from-pixels layer. `css.glow` (added
2026-07-10, verified deterministic on all 13 passing skins) is defined per theme but not
yet consumed by the player at all.

- **(a) Director-authored emissive REGIONS in the spec.** Extractor only top-hats *inside*
  a region instead of the whole device. Works cleanly for **templated** mode (control
  positions are locked, so a region anchored to e.g. `regions.json`'s `visualizer`/`seek`
  glass windows is stable). Breaks down for **templateless** mode — the exact case that
  motivated emissive (diablo's freehand runes/cracks) has no fixed housing shape per
  generation, so a static per-theme region can't track where the model actually painted a
  rune this roll. Cost: one JSON field per theme (~$0, one-time authoring on 15 static
  spec files) for templated regions; templateless would need a *per-generation* region,
  which reduces to option (c) or (b). Validating evidence: re-run the existing top-hat
  extractor gated by the region on the 15 committed paints, spot-check glow lands on the
  intended feature vs. splatter elsewhere.
- **(b) Segmentation/VLM pass scoring "should this glow" per region.** `director.ts`
  already ships `extractSlots`/`extractMasks` — VLM box/polygon calls over a painted
  image. TODO.md documents that exact class of call as a **confirmed dead end** for
  control-box detection (0oyq 29→0, SAM 1/10, two Gemini 2.5 Pro passes all made it
  worse). Emissive scoring is a weaker ask (binary keep/reject on a candidate blob, not
  precise geometry) so may be more VLM-tractable — but per `verify-rule`'s noisy-VLM-
  geometry caveat, a VLM must never be the geometry source, only a gate on candidates a
  deterministic pass (the top-hat) already generated. Cost: ~$0.01–0.03/skin via the
  `openrouter/router/vision` infra already used by `observe12.py`/SOTA-eye. Failure mode:
  stacking a classifier on an already-noisy candidate generator is the exact
  "smart-step-on-a-noisy-signal" pattern `ai-image-coords-rule.md` warns against — it may
  reduce false positives without fixing "nonsensical," since the top-hat's candidate set
  is still whatever it is.
- **(c) Painting a dedicated emissive PASS via the image model** (a "glow mask" column,
  analogous to the existing right-column REGION MASK in `genskin.py`). Cost: extra
  $/gen — genskin.py's own documented pricing puts a same-resolution call at $0.24
  (Vertex, 4K) to $0.30 (fal, 4K), vs. $0 for the top-hat or $0.01–0.03 for a VLM gate.
  Registration risk is real but bounded IF piggybacked on the *already-proven* multi-
  column pixel-alignment pattern genskin.py uses for the region mask — a genuinely
  independent img2img call on the finished paint would reintroduce the exact drift
  problem section 3 measures. Recommend piggyback-only if pursued.
- **(d) Emissive only from director-CSS `glow` color on KNOWN elements — zero extraction,
  fully deterministic.** This is ~90% built already: `registerEmissiveSource()` ships
  live and unconditional for the visualizer; `seek-underglow`/`knob-pointer` exist behind
  `?emdemo=1`; `css.glow` is director-authored per theme but unused. The gap is small:
  default-enable the two demo sources as real player behavior, and source their color
  from `css.glow` (currently they reuse the viz's `emissive_color`-derived paint sample).
  No new extraction, no new model call, no registration risk — it can't glow somewhere
  wrong because it never searches pixels for "somewhere."
- **(e) Drop baked emissive permanently, keep dynamic-only lighting.** The de facto
  current state, made explicit and made cleanup: remove the top-hat extraction code and
  `emissive.png`/`meta.json` lights entirely rather than leaving it wired-but-disabled
  (`pbr_pass.py`'s own comment already frames this as "stays wired... for a future
  re-enable"). Cost: negative (deletes ~100 lines of morphology code); loses the
  self-emitting-rune LOOK the PBR experiment set out to get, which was explicitly praised
  ("great") in round 3 before the nonsensical-glow verdict on the *scaled* application.

**Recommendation:** (d) as the near-term ship — it's the cheapest, most deterministic,
already 90% built, and directly answers "randomly glows nonsensical" by construction
(nothing is searched, everything is named). Pursue (a) *only* for templated-mode skins as
a later enhancement layered on top of (d), scoped to the fixed control glass windows
(visualizer/seek) rather than freehand body regions. Do not pursue (b) — same
noisy-VLM-geometry trap already burned twice on this pipeline. Revisit (c) only if (a)+(d)
together are judged visually insufficient, and only via the proven multi-column pattern.

---

## 2. Director-vision step

**Current state:** `src/generate/director.ts` is Vertex Gemini 3.1 Pro, natively
multimodal, already wired for image input — `toImagePart()`/`directorChat()` accept
`imageParts`, and `extractSlots`/`extractMasks` already send the painted device image for
control-box/polygon detection (both documented dead ends for *that* task — see section 1b).
So the *infrastructure* for "hand the director the painted image" already exists in this
file; what's missing is a *new* call with a different, narrower ask: not "where are the
controls" (proven unreliable) but "given this painted image, what CSS/lighting values fit
it" (a judgment task, not a geometry task).

**Where it slots:** post-paint, pre-player-build — after `generateSkin()` in
`pipeline.ts` returns the paint URL, before `finalize`/composite. A new
`directorVision(paintUrl, theme) → { css, lighting, materialNotes }` call, additive to
the existing `deriveMaterial` (pre-paint, text-only, chooses the *prompt* material) — this
new call would run *after* the paint exists and only adjust presentation values, never
re-invoke generation.

**What it would decide:** `css.track/fill/accent/glow` hex values sampled/judged from the
actual paint instead of guessed from theme text; `lighting.emissive_hint`/`emissive_color`
picked from real glyph/screen pixels instead of imagined; optionally a material correction
note (e.g., "this rolled glossier than the theme text implied, use higher metalness") fed
into `pbr_pass.py`.

**Cost/latency:** one extra Vertex vision call per generation, same model already paid for
elsewhere in this pipeline (`extractSlots` at 3000 max tokens, `extractMasks` at 4000) —
call it ~$0.01–0.02 and a few seconds, negligible relative to the $0.24 paint call it
follows.

**Circularity risk (verify-rule §2):** the director *wrote the theme prompt* the paint
was generated from. Asking the same model to judge colors "from the pixels" of an image it
effectively steered risks reproducing its own priors rather than reading anything new —
a validation that shares the model/assumption of the thing being judged is circular by the
rule's own definition. This is milder than the classic case (it's judging *presentation*
values, not re-validating the *same claim* it made), but the risk is real for
`emissive_hint`/`emissive_color` specifically, since those already exist as *director-
authored text* pre-paint (`theme_specs/*.json`) — a vision pass re-deriving them from the
paint is checking whether the paint matches its own brief, not an independent signal.
`css.*` is lower-risk: those values are currently *paint-sampled* (fallback in
`build_player.py`) or hand-picked once per static theme spec, not model-authored per
generation, so a vision pass choosing them from the actual paint is a genuine improvement
over either path (paint-sampling is already the existing fallback; this just makes it
smarter, not more circular).

**What stays deterministic:** control geometry (never route through this — extract12's
compute-from-matte approach per `placement-invariants-rule` stays authoritative), the
paint generation itself (this step never re-prompts or re-rolls), and the emptiness/leak
gates (unaffected, run on the paint regardless of what the vision step decides).

- **(a) Do nothing — keep `css`/`lighting` as director-authored-pre-paint + paint-sample
  fallback.** Zero cost, zero circularity risk, but colors stay disconnected from what
  actually rendered (the whole reason this was raised).
- **(b) Add the vision step scoped to `css.*` ONLY** (not `lighting`/emissive) — the
  lower-circularity-risk half, and the piece that's currently a raw pixel-sample fallback
  rather than a judged value, so there's real headroom to improve.
- **(c) Add the vision step scoped to `css.*` AND `lighting.emissive_color`/`hint`,
  explicitly framed as "does the ACTUAL paint diverge from the intended brief" (a
  discrepancy check) rather than "pick fresh values" — mitigates circularity by making the
  model compare two things instead of re-deriving one.
- **(d) Full scope — css + lighting + material corrections feeding `pbr_pass.py`.**
  Highest value if it works, highest circularity exposure, and adds a second per-gen
  vision call on top of whatever section 1's emissive direction needs.

**Recommendation:** (b) first — it's genuinely lower-risk (replacing a naive pixel-sample
fallback, not re-deriving a director-authored value), cheap, and testable independent of
section 1's emissive decision. Fold `lighting` in later as (c) — framed as a divergence
check, never a fresh re-derivation — only if (b) proves the vision step earns its cost.
Skip (d) until both are proven; stacking scope before either is validated repeats the
"noisy-signal-becomes-load-bearing" pattern this pipeline has already been burned by.

---

## 3. Drift-clause bisect

**Confirmed via the audit + git history (not assumed):** the roster adherence audit
(`tools/mask-align-exp/gen12/twoimg/roster_audit.json`, `results.html` Task 2, commit
`91c01139`) shows 4/6 templated-passing skins with MORE drift now than at the original
14-skin batch (`794da20e`) — worst is `fallout-pipboy` 143px→950px (+808px),
`steam-porthole` 523px→858px (+335px), `ps1-crunchy` 330px→415px (+85px),
`wmp-quicksilver` 292px→542px (+250px). Two skins IMPROVED (`fa-pod` −99px,
`wc-goldshield` −82px).

**Verify-rule flag on the "prime suspect" framing:** `git log -S "BOLD, DISTINCTIVE"` and
a full diff show the bold-silhouette-freedom clause's *wording is unchanged* between
`794da20e` (the baseline batch) and `HEAD` for the outline-style templated prompt path —
it isn't a new addition, it was present in the original batch too. That doesn't rule it
out (its *interaction* with something else that changed could be the real driver — e.g.
the mask-cell-overlap cut rewrite in `ac28cd74`, the button-recolor fix in `a8bbaad0`, the
display-region refit in `86f69c75`, or simply that baseline is now drawn from a *random*
solid/outline conditioning arm (`pick_blueprint_arm()`, wired `8d580b74`) instead of
whatever single style the original batch used) — but it does mean the bisect must isolate
the clause from these confounds, not assume it's guilty going in.

**Noise floor, from the audit's own numbers:** two skins moved in the *opposite* direction
(−82 to −99px) under the identical current pipeline with no prompt change tested. A
"regression" below roughly 100–150px on a ~2300–3700px canvas is not yet distinguishable
from run-to-run variance; the bisect's decision rule needs a threshold clearly above that.

### Design

- **Fix the conditioning arm to `solid`** for every bisect gen (the abshape A/B winner) so
  arm-selection isn't a second confound layered on the clause test.
- **Pick the two worst regressors** (`fallout-pipboy` +808px, `steam-porthole` +335px) —
  biggest available signal per generation dollar.
- **Reuse the existing committed gens as the v0/baseline arm for free** (already scored:
  950px, 858px) — no need to regenerate the current prompt.
- **Two new prompt variants, same theme+seed pairs as baseline where possible** (control
  for per-skin/per-seed variance, which the audit shows is large):
  - **v1 — clause removed.** Replace "you are FREE and STRONGLY ENCOURAGED to sculpt a
    BOLD, DISTINCTIVE... ONLY the control positions stay fixed" with a neutral instruction
    to keep the housing close to the guide's rough shape.
  - **v2 — clause kept, strengthened position-lock addendum.** Keep the BOLD/DISTINCTIVE
    freedom language (it's plausibly load-bearing for the visual variety the pipeline
    wants), but append an explicit, harder constraint sentence (e.g. numeric/percentage
    tolerance language, or "regardless of housing silhouette, each control's centre must
    land within the guide shape's own footprint — reshape AROUND the guides, never THROUGH
    them").
- **Scale: 2 themes × 2 seeds (existing seed reused + 1 fresh) × 2 variants = 8 new gens.**
  At Vertex 4K pricing (`PAINT_VERTEX=True`, $0.24/gen) + $0 local BiRefNet
  (`BIREF_LOCAL=True`) ≈ **$1.92** — under the suggested $2–3 budget, leaves headroom for
  a 3rd variant or extra seed if the first pass is ambiguous.
- **Metric:** `roster_audit.py`'s existing `mean_drift_px` (already scripted, $0 to run)
  against each variant's fresh `regions.json`, same paired-seed comparison against the v0
  baseline already in the audit.
- **Decision rule:**
  - v1 (no-clause) drops mean drift by >300px on **both** themes/seeds, clearing the noise
    floor → clause confirmed as a major driver. Follow-up: soften or drop the clause in
    mainline `genskin.py`'s templated path, re-run the full 6-skin roster audit to confirm
    the fix generalizes (not a per-skin-patch — per `fix-generalizable-rule`).
  - v2 (strengthened-lock) matches v1's drift reduction AND keeps visibly more silhouette
    variety (spot-check by eye) → prefer v2 as the shipped fix — it keeps the design goal
    the clause was added for.
  - Neither v1 nor v2 clears the noise floor → clause is not the driver (or not the sole
    one). Follow-up: bisect the conditioning-arm switch (`outline`/`solid`/random-draw)
    and the extraction-algorithm commits (`ac28cd74`, `86f69c75`, `a8bbaad0`) instead —
    same paired-seed method, different variable held fixed.
  - Mixed (helps one theme, not the other) → likely an extraction-algorithm or
    theme-specific confound, not a clean prompt-clause effect; don't ship a global prompt
    change off a mixed result — narrow the bisect further before acting.

**Recommendation:** run v1+v2 exactly as scoped above (8 gens, ~$1.92) before touching
`genskin.py`. Do not skip the noise-floor threshold — the audit's own ±100px swings on an
unchanged pipeline mean a "the clause is the cause" conclusion drawn from under ~150px of
movement is not decisive. Prefer v2 over v1 if both clear the bar (keeps intended design
freedom); fall through to the conditioning-arm/extraction bisect if neither does.
