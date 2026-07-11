# gen12 TODO

## Media policy (2026-07-11) — paid outputs now committed to git

`joint-4k.png`/`paint.png`/`mask.png` (paid Vertex rolls) and `assets-*_biref/*.png`
(runtime-required cut sprites `player.html` loads from `../assets-<theme>_biref/`) are now
committed for all 15 skins (~699MB, plain git objects — no LFS is set up for gen12, matching
the existing plain-PNG convention in `twoimg/`/`bproof/`; repo LFS exists but is currently
scoped only to `docs/experiments/assets/*.png|*.jpg` — recommend extending LFS to gen12's
`assets-*` media in a follow-up rather than this being retrofitted unilaterally here).
`blueprint.png` ($0 deterministic) and `assets-*_biref/` as a bulk ignore pattern stay/stayed
ignored — see `.gitignore` for the itemized policy comment.

## Think-about notes (2026-07-11) — emissive, director-vision, drift-clause bisect

Three open design questions written up as decision-ready options + recommendations, none
implemented: [`docs/design/2026-07-11-think-about-notes.md`](../../../docs/design/2026-07-11-think-about-notes.md).

- **§1 Emissive rethink** — `pbr_pass.py`'s baked glyph-emissive (top-hat extraction) is
  disabled (`EMISSIVE_ENABLED=False` in `build_player_pbr.py`); options for what replaces
  it. Rec: (d) deterministic `css.glow` on known elements via the already-live
  `registerEmissiveSource()` — near-zero new code.
- **§2 Director-vision step** — should `src/generate/director.ts` see the painted image to
  pick `css`/`lighting` values instead of guessing pre-paint. Rec: scope to `css.*` only
  first (lower circularity risk than re-deriving director-authored `lighting`).
- **§3 Drift-clause bisect** — the roster adherence audit (`twoimg/roster_audit.json`,
  `twoimg/results.html` Task 2, commit `91c01139`) found 4/6 templated-passing skins
  drifted MORE from their template than the original `794da20e` batch (pipboy
  143px→950px). Cheapest decisive bisect design (2 themes × 2 seeds × 2 variants, ~$1.92,
  NOT run) is in the doc, including a verify-rule flag: the suspected clause's wording is
  actually unchanged since baseline, so the bisect must isolate it from other confounds
  (conditioning-arm draw, extraction-algorithm changes) rather than assume it's guilty.

## Review the longitudinal blueprint-conditioning randomization study (once n accumulates)

Wired 2026-07-10: mainline `genskin.py` now randomly draws a blueprint guide-STYLE arm on every
**templated**-mode generation — `solid` (75%) vs `outline` (25%), weighted toward the incumbent
(abshape A/B winner, `abshape/verdict.json`) per generation-spend-rule, so more evidence
accumulates on the arm already ahead while `outline` stays in rotation because the user isn't
yet convinced it's categorically worse (small n=4/arm sample). The draw is deterministic —
seeded from the generation's own `seed` via `pick_blueprint_arm()` — so re-running the same seed
reproduces the same arm; no separate stored draw-seed, no Math.random-style nondeterminism.

**Where it's logged:** additively in each skin's `results.json` (genskin's own persisted meta):
`blueprint_trial_enabled`, `blueprint_arm` (what the draw picked: solid|outline),
`blueprint_arm_draw_seed` (== the generation seed), `blueprint_twoimg` (bool, see below),
`blueprint_conditioning` (the arm ACTUALLY used to build the blueprint — equals `blueprint_arm`
unless twoimg overrode it). **Caveat:** `extract12.py`'s `regions.json` writer builds its output
from a fixed literal field list (devFrac/buttons/sprites/extras/roles/templated/keys/keyNames/
regions/template) — it does NOT passthrough arbitrary `results.json` keys, so the arm currently
lives ONLY in `results.json`, not in `regions.json`/the dashboard. Wiring it into `regions.json`
needs a small additive line in `extract12.py` (owned by another lane, not touched here) before
the dashboard can show it directly — until then, cross-reference `assets-<id>/results.json`.

**What to analyze once enough n has accumulated across future batches** (auto-reroll is OFF, so
each generation = 1 roll unless someone explicitly retries — n grows slowly, for real):
- per-arm **gate pass rate** (extract12's emptiness gate + genskin's own leak gate)
- per-arm **emptiness-fail rate** specifically (the abshape-verdict discriminating signal:
  solid won emptiness 3:1 pooled over outline in the small sample — does that hold at scale?)
- per-arm **guide-hue residue** (the coloured-ring-around-a-button defect outline produced in
  3/4 abshape gens) — visual spot-check, the automated leak-gate% doesn't discriminate reliably
- per-arm **layout/registration drift** (region-misplaced flags, template drift metric)

**Two-image conditioning (`BLUEPRINT_TWOIMG` / spec `"conditioning":"twoimg"`) is NOT part of
this trial arm draw** — scope changed mid-implementation: the twoimg construction code (clean
edit-target canvas + a second solid-filled guide-layout reference image, via `edit_vertex_multi`)
is ported into mainline `genskin.py` and ready to flip, but stays a separate opt-in flag
(default `False`) since the `twoimg/` experiment already FALSIFIED it as a bleed fix (see below)
and the neutral-reference variant is now also RESOLVED (2026-07-11): rejected — digit
contamination did NOT happen (user's prediction refuted, 0/4 numerals) but neutral lost on
every other axis (0/4 layout adherence, 0/4 clean emptiness, 3/4 guide-hue residue incl.
exact-key gems sourced from the TEXT prompt's mask-column colour spec — a third bleed pathway
no image topology removes). See the twoimg section below.

Verified 2026-07-10 (dry run, zero spend — `--blueprint-only` against 3 seeded specs, then
deleted the throwaway `assets-drytest-*/` dirs): `solid` arm blueprint has filled guide shapes
(23.4% saturated-guide-pixel coverage of the device column); `outline` arm has stroked outlines
only (5.3% coverage, same positions/sizes); `twoimg` mode's edit-target `blueprint.png` has ZERO
guide-coloured pixels (0.00%) while its separate `blueprint-guided.png` reference exactly
reproduces the solid arm's guide pixels (538794 px both) — confirms the twoimg guided reference
is built with the proven solid guide style, matching `twoimg/genskin_twoimg.py`'s design. Arm
logging into `results.json` confirmed present and correct across all 3 dry runs.

## Ambient video loops — round 5: Cinemagraph LoRA used CORRECTLY + anti-glow brief — DONE 2026-07-10

Round 4's diablo "PASS" was overruled by the user. Root cause: rounds 3–4 used the Lightricks
Cinemagraph LoRA naively. Round 5 re-ran it per the HF model card (trigger word `CINEMAGRAPH_MOTION`,
non-distilled endpoint `fal-ai/ltx-2.3-22b/image-to-video/lora`, training res 512×704, card sampling
steps=30/cfg=4/stg=1) with a hard anti-glow constraint (motion = particles/smoke/dust only; glow/fire/
emissive in the negative). 3 gens, ≈$0.174. See `docs/experiments/2026-07-09-ambient-video-loops.md`
round 5 + `ambientvid/jobs5-ltx.json`.

Findings: (1) The dominant lever is `num_frames` = **training length (25)**. 121-frame clips (rounds
3–5) drift/hallucinate; the **25-frame steam clip is the best LTX result of all rounds** (button glyphs
legible, gauge holds). (2) Correct usage **helped steam** (25f clean; 121f keeps legible buttons vs
round-4's blank dials) but **worsened diablo** — non-distilled + high card-guidance + trigger word
over-generates on dark/low-detail UI art and hallucinated a whole new **glowing** device (banned).
(3) Seedance 1.0 pro fast (round 2) remains the identity-preservation champion, BUT its diablo win was
rune-glow (now banned) — its no-glow/particles behavior is untested. (4) fal storage/CDN hosting is FREE.

Open follow-ups (not done): **re-benchmark Seedance under the no-glow / particles-only brief** (its
wins relied on glow); if LTX is kept, run it **only at ~25 frames** and only on detail-dense subjects,
extending via ping-pong/crossfade — never 121 frames; wire the round-3b temporal-std **hard-composite
mask** as the standing safety net regardless of model.

## Ambient video loops — round 6: research Lightricks' EXACT recipe, diff it, find the gap — DONE 2026-07-10

User: *"their LTX cinemagraph examples are so much better — verify you're using it correctly or find bugs."*
Read the HF model card + the ComfyUI workflow it links, diffed vs round 5, ran 2 corrected probes (≈$0.052).
See `docs/experiments/2026-07-09-ambient-video-loops.md` round 6, `ambientvid/jobs6-ltx.json`, `ambientvid/round6.html`.

Findings: (1) **The real gap is INPUT DISTRIBUTION** — the LoRA's 4 published examples are all *photographs*
(beach+sunglasses, man+cow+clouds, woman+tears, motel neon); our subjects are stylized dark single-object
UI paintings = out-of-distribution. That, not a slider, is why theirs look better. (2) **Two real round-5
mis-settings, both fixed:** `video_stg_scale=1.0` was a *global* knob, NOT the card's block-29-targeted STG
(which is ComfyUI-only) → set to **0**; and `use_multiscale` was left at fal-default **true** (low-res first
pass drives glyph resynthesis) → set **false**. (3) **fal cannot express the full recipe** — STG block-29 +
the card's RES4LYF distilled sampler graph are ComfyUI-only; only a global STG + black-box sampler are
exposed. (4) Corrected probes: **P1 steam 768×1024/25f = best LTX steam of all rounds** (identity holds,
glyphs legible), but **P2 diablo still HARD FAIL** (fully resynthesized — glowing buttons, app-icon strip,
cartoon in screen), so the corrected knobs help detail-dense subjects and do nothing for OOD dark ones.
(5) The card's linked workflow keeps the distill LoRA at 0.2/0.5 → round-5's "zero them" caveat was wrong.

Recommendation unchanged: LTX+LoRA only on detail-dense subjects at ~25f/768×1024/STG=0/multiscale=false;
Seedance for dark stylized skins (still needs the no-glow re-benchmark); temporal-std hard-composite mask
as the standing safety net. To run the card's *exact* graph would need local ComfyUI-LTXVideo (22B dev ckpt
≈46GB + distill LoRA + Gemma encoder) — a multi-GB stand-up, not started.

## Director-specified CSS chrome colors (`css` schema, sibling of `lighting`) — DONE 2026-07-10

Added a `"css": {"track","fill","accent","glow"}` block to the theme-spec schema (documented
in `WIRE-pbr.md` next to `lighting`) and populated it in all 15 `theme_specs/*.json`, hex-picked
from each theme's own `palette`/`lighting.emissive_color` so the seek-track/fill/visualizer-accent
read as part of the device instead of a generic slider. `build_player.py` now prefers
`css.track`/`css.fill`/`css.accent` (falling back to reading `theme_specs/<id>.json` directly
since `results.json` carries no `css` passthrough — same fallback pattern `pbr_pass.py` already
uses for `lighting`); paint-sampling remains the fallback for a spec without the block.

Verified deterministically across all 13 currently auto-passing skins (`orch.json.passed`;
`fa-sky`/`ps1-wild` excluded, auto-fail on unrelated defects): rebuilt `player.html`,
`getComputedStyle(.pseek-track/.pseek-fill).backgroundColor` and the embedded `const acc=`
literal exact-match the spec hex on every skin, and DOM order always has `.pthumb` appended
after `.pseek-track`/`.pseek-fill` (thumb stays on top, no z-order regression). SOTA-eye
(Gemini 2.5 Pro via fal `openrouter/router/vision`) reviewed screenshots + seek close-up crops
per skin; two early FAIL calls were refuted by the deterministic check + a direct look at the
raw paint (diablo-gothic's "purple fill" and wmp-quicksilver's "pink outline" are a
baked-in decorative ring in the ORIGINAL sprite art around the seek slot, not the CSS layer —
same class of thing for fallout-pipboy's "rusty" read, which was the paint showing through the
semi-transparent near-black track). Several other early FAILs were a screenshot-methodology
artifact (thumb parked at 0% progress hides the fill sliver under itself) — re-shot at 50%
progress, confirmed PASS on wmp-vario.

## observe12.py --vlm will break: fal vision endpoint now requires `reasoning: true`

Verified live 2026-07-10 (twoimg experiment): every `openrouter/router/vision` call with
`google/gemini-2.5-pro` and no `"reasoning": true` in the body now returns
`{"detail": "Reasoning is mandatory for this endpoint and cannot be disabled."}` instead of a
verdict. `observe12.py` doesn't set it (line ~80) — its next `--vlm` run will write UNPARSED
verdicts. One-line fix when the current batch is done (not touched now — live re-roll running):
add `"reasoning": True` to the body dict. `twoimg/sota_eye.py` has the fixed call shape.

## twoimg experiment (2026-07-10): two-image conditioning FALSIFIED — keep single canvas

`twoimg/` tested sending the guide layout as a 2nd reference image with a guide-pixel-free
edit canvas. Result: bleed still happens (3/4 treat gens, incl. exact-key vol ring + purple
seek flood transferred semantically from the reference), AND layout adherence collapses
(4/4 treat gens drift from the locked template vs 0/4 control). Verdict + full record:
`twoimg/results.html`, `docs/experiments/2026-07-10-twoimg-conditioning.md`. Do not adopt.

**Neutral arm (2026-07-11): colourless numbered line-art reference — also rejected.** The
digit-contamination prediction was REFUTED (0/4 gens baked numerals; SOTA-eye digit hunt over
all 40 crops, detector proven over-sensitive on control/treat tick-marks), but neutral lost
everywhere else: 0/4 layout adherence, 0/4 clean cavity emptiness, 3/4 guide-hue residue —
including wc-neutral-134's next/repeat/shuffle gems in their EXACT named keys with verifiably
colourless input images. That isolates a THIRD bleed pathway: the TEXT prompt's mask-column
spec (each control's colour name + RGB) semantically leaks into the paint. No conditioning
topology removes it while the joint-canvas mask column exists. Also learned: fal
`openrouter/router/vision` caps images at 30MB of ENCODED (base64) payload — `twoimg/sota_eye.py`
auto-falls-back to full-res JPEG q90 crops past 24MB encoded.

## BIREF_LOCAL / PAINT_VERTEX flags

Both landed flag-gated OFF, then were flipped ON 2026-07-10 (user call, batch drained —
see `.claude/rules/generation-spend-rule.md` and `.claude/rules/feature-flag-rule.md`).
Flip only **between** batches, never while `orchestrate12.py` is mid-run.

### `biref12.py: BIREF_LOCAL` (now `True`)

- **What it does when `True`:** runs BiRefNet locally via `transformers`
  (`trust_remote_code=True`) on MPS instead of the fal
  `fal-ai/birefnet/v2` endpoint. $0/matte, no fal dependency.
- **Requires:** the `.venv-biref/` venv in this dir (torch/torchvision/transformers/
  huggingface-hub/accelerate/scipy/pillow/requests/numpy — already created + populated
  on this machine). `biref12.py` auto-re-execs itself under `.venv-biref/bin/python3`
  if the current interpreter lacks `torch`, so `orchestrate12.py`'s
  `["python3", "biref12.py", ASSETS]` call keeps working unmodified.
- **Checkpoint: `ZhengPeng7/BiRefNet_HR` @ 2048 input** (switched from general@1024
  after a bench, 2026-07-10). What fal's "General Use (Heavy)" actually is: fal's own
  schema maps it to `BiRefNet_lite`, but the same schema describes Heavy as "slower
  but more accurate" (lite is the 44M fast model) — the Light/Heavy rows are almost
  certainly swapped in fal's doc, and the bench can't discriminate. IoU vs the fal
  Heavy matte on fallout-vault: HR@2048 **0.9978**, general@2048 0.9979, lite@1024
  0.9976, general@1024 0.9973 — all within 0.0006 (noise). HR chosen: full 220.7M
  checkpoint TRAINED at the 2048 operating resolution the fal call uses, IoU ≥ the
  previously shipped general@1024.
- **Verified:** `True` — end-to-end via the real shipped biref12.py: IoU 0.9978,
  all 4 strip parts (vol/seek/shuffle off+on) matched at 98–100% mask-cell overlap,
  visually identical side-by-side. ~31s/matte at 2048 on MPS incl. model load
  (~5s inference once warm).

### `genskin.py: PAINT_VERTEX` (default `False`)

- **What it does when `True`:** calls the same `gemini-3-pro-image-preview` model
  direct via Vertex AI (`aiplatform.googleapis.com`, `gcloud auth print-access-token`
  — no ADC file needed, same pattern as `bproof/run_bproof_vertex.py`) instead of
  fal's `fal-ai/gemini-3-pro-image-preview/edit` wrapper.
- **Price (verified live, 2026-07-10):** fal is $0.15/image at 1K/2K but **$0.30/image
  at 4K** (genskin requests `resolution: "4K"` — fal's own pricing page states 4K is
  2x the base rate). Vertex direct at the same 4K tier is **$0.24/image** (2000 output
  tokens x $120/1M, per the Vertex AI generative-pricing page) + ~$0.001 input tokens.
  **Vertex is ~20% cheaper than fal for this exact call**, in addition to removing the
  fal-billing-lock dependency (fal 403'd the whole pipeline once already, per the
  generation-spend rule).
- **Requires:** `gcloud` CLI authenticated as a user with Vertex AI access on project
  `muser-2605300220` (or set `VERTEX_PROJECT` env var) — already working on this
  machine, no ADC file present or needed.
- **Verified:** `True` — one test generation (`steam-porthole` spec, shortened test
  prompt, not the full production prompt) returned a real, correctly-themed image in
  45s at 4608x3712 (aspect 1.241 vs requested 5:4=1.25). Full production-prompt
  parity not re-tested (contract — image in/out, aspect, seed — is what changed;
  prompt text is unchanged either way).
- `genskin.py:edit_vertex()` matches (diffed line-for-line, only cosmetic naming
  differs) `abshape/genskin_ab.py:edit_vertex()`, which already ran 4 real
  generations today on this same project/auth — independent convergence on the
  same proven call shape, not a fresh untested integration.
