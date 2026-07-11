# gen12 TODO

---
## Director-decided knob tick provisioning: css vs baked, per axis — DONE 2026-07-11

User directive: *"allow director to decide css vs baked skin side knob ticks, same for
sprite-side knob ticks."* The prior `KNOB_TICKS_ENABLED` was a single global flag rendering
the SAME deterministic CSS/SVG tick-arc-ring (skin axis) + live needle (sprite axis) for
every skin regardless of theme. Added a `"ticks":{"skin","sprite"}` block to the theme-spec
schema (documented next to `css`/`lighting` in `WIRE-pbr.md`), each axis independently one of
`"baked"|"css"|"none"`. `genskin.py` now emits a LIGHT, per-user-directive-constrained prompt
clause ("dont overconstrain tick marks style" — the failed 2026-07-11 knobticks experiment's
MIN/MAX/CENTER vocabulary is exactly what leaked as literal baked text) when an axis is
`"baked"`; `build_player.py` renders its existing CSS ring/needle ONLY when that axis is
`"css"`, splitting what was one `if(KNOB_TICKS_ENABLED)` block into two independently-gated
halves sharing the same SVG/geometry setup. `KNOB_TICKS_ENABLED` stays as a master
kill-switch over both axes. Backward-compat: a spec without the block behaves as
`{"skin":"css","sprite":"css"}` (the prior shipped behavior, unchanged for any future spec
that omits it).

**Per-theme director choices** (all 15 `theme_specs/*.json` populated):

| theme | skin | sprite | rationale |
|---|---|---|---|
| claymation | none | none | handmade/imperfect clay theme explicitly rejects technical/digital-smooth markings |
| diablo-gothic | baked | baked | carved-stone/runes theme fit; also targets the documented CSS-tick legibility clash with this skin's own busy gear-cog ring texture (see the CSS-tick-ship entry below) |
| fa-pod | css | baked | glossy modern bezel suits a crisp CSS ring; a single pointer dot is a classic hi-fi knob detail |
| fa-sky | css | css | templateless + already flagged auto-fail-prone (orch.json) — no added baked risk |
| fallout-pipboy | baked | baked | theme prompt literally names "analog dials"; templated mode = lower layout-drift risk than templateless |
| fallout-vault | baked | baked | Vault-Tec gauge/calibration-panel aesthetic |
| myst-arcanum | baked | baked | "intricate clockwork ornament"; cap already organically bakes carved marks (see the knob-zero-fix entry's myst-arcanum note) |
| n64-cutscene | css | css | flat-shaded low-poly visual language doesn't suit fine engraved detail |
| n64-prerender-character | css | css | creature/mascot bust has no dial-panel semantics |
| ps1-crunchy | css | css | warped/dithered "crunchy" texture risks illegible baked fine detail |
| ps1-wild | css | css | already one of 2 roster skins auto-failing on unrelated defects (orch.json); no added risk |
| steam-porthole | baked | baked | theme prompt literally names "pressure-gauge dials" + "engraved filigree"; existing baked cap pointer already lands cleanly on the CSS major tick (see the CSS-tick-ship entry) |
| wc-goldshield | baked | baked | ornate baroque filigree/runed crest; same clean baked-pointer/major-tick alignment already verified |
| wmp-quicksilver | css | baked | "understated" clean chrome favors the CSS ring; one pointer dot is a minimal, period-correct hi-fi detail |
| wmp-vario | css | css | theme's "illuminated ELECTRIC-BLUE ringed control cluster" is better served by the CSS ring (themed via `css.accent`) than baked geometry |

**CRITICAL caveat, stated honestly:** choosing `"baked"` does NOT retroactively add ticks to
an EXISTING `paint.png` — all 15 skins' current paint predates this schema. So today, the
6 `"baked"`-skin themes above (diablo-gothic, fallout-pipboy, fallout-vault, myst-arcanum,
steam-porthole, wc-goldshield) show **no tick ring at all** until regenerated — choosing
`"baked"` right now visibly REMOVES the CSS ring that was there before, in exchange for a
not-yet-realized future bake. Full explanation in `WIRE-pbr.md`'s `ticks` schema section.

**Open question (not resolved, no policy invented):** should `build_player.py` auto-fall-back
an axis to `"css"` when a `"baked"` spec's paint is detected to actually lack the marks? No
detector for "does this paint have a baked tick ring" exists (`knob_zero_deg` only detects the
CAP's pointer notch, not a bezel ring) — building one, or deciding the fallback policy without
one, is future work, not invented here.

**Verified:** deterministic DOM check (real shipped `player.html` via Playwright, no proxy) —
all 15 skins render EXACTLY the `<svg class=pknob-ticks>` line/group count their spec
predicts (0 lines for baked/none axes, the 22-line 2-group ring for `skin=css`, +1 needle line
for `sprite=css`), 15/15 PASS. SOTA-eye cross-check (`google/gemini-2.5-pro` via fal
`openrouter/router/vision`, `reasoning:true`, ~$0.043 for 3 calls) on 3 skins spanning all
three states (wmp-vario css/css, steam-porthole baked/baked, claymation none/none): 2/3
agreed with the deterministic result; the wmp-vario call falsely reported no ring/needle on a
138×138px raw crop — overruled per verify-rule (a 552×552 upscaled re-crop plus the
deterministic DOM count both independently confirm the ring+needle ARE present and correctly
rendered). Net: all 3 sampled skins' actual behavior is correct per spec once adjudicated.

---
## PARKED for skeuo v2 (2026-07-11) — emissive / PBR, NOT v1 work

> **Everything in this section is explicitly parked, not active.** v1 finishing work in the
> rest of this file is unaffected. Full user verdict + distilled reading:
> [`docs/experiments/2026-07-11-semantic-emissive-prototype.md#human-verdict-2026-07-11`](../../../docs/experiments/2026-07-11-semantic-emissive-prototype.md#human-verdict-2026-07-11).
> Short version: the 2-stage semantic-judge + SAM-3-refiner direction is "very interesting"
> and directionally validated, but SAM-3 missed one of fallout-pipboy's two vacuum tubes,
> the left tube's glow floods the whole glass envelope instead of the filament (the right
> tube's subtle filament glow is the quality bar), and fa-pod's button glow is "a bit
> questionable." Park for skeuo v2, alongside other PBR-related tasks.

- **§1 Emissive rethink** (moved from "Think-about notes" below) — `pbr_pass.py`'s baked
  glyph-emissive (top-hat extraction) is disabled (`EMISSIVE_ENABLED=False` in
  `build_player_pbr.py`); options for what replaces it were written up in
  [`docs/design/2026-07-11-think-about-notes.md#1-emissive-rethink`](../../../docs/design/2026-07-11-think-about-notes.md#1-emissive-rethink)
  (rec'd (d): deterministic `css.glow` on known elements via the already-live
  `registerEmissiveSource()` — **this part is NOT parked, it's orthogonal and near-zero new
  code, ship it independent of the semantic direction below**).
- **Semantic-emissive prototype** (2-stage VLM-judge + SAM-3-refiner,
  `tools/mask-align-exp/gen12/semissive/`) — built, run, and human-judged 2026-07-11. Beat
  the classical top-hat baseline on semantic correctness on all 3 test skins; human verdict
  above is the disposition. Full record:
  [`docs/experiments/2026-07-11-semantic-emissive-prototype.md`](../../../docs/experiments/2026-07-11-semantic-emissive-prototype.md).
- **PBR mainline flip** (`PBR_PASS_ENABLED` in `orchestrate12.py`) — do not flip until the
  semantic-emissive rework above is revisited in v2; see root `TODO.md`'s PARKED section for
  the full roster-run status/blockers.

**Next resumption step (v2, not now):** re-read the prototype doc's verdict, then either
re-run judge/refine on a paint roll with genuinely-lit screens, or fix `genskin.py`'s
screen-lighting prompt upstream first; tighten Stage 2b's local gate toward the
right-tube-class result the user named as the quality bar. Fold into v2's broader PBR/
material work, not a standalone resume.
---

## Let the DIRECTOR decide whether optional pipeline stages are worth running per skin (2026-07-11, user directive)

Not implemented. Currently every flag-gated optional stage (`PBR_PASS_ENABLED`,
`DIRECTOR_REVIEW_ENABLED`, and any future one — see `orchestrate12.py`'s flag block, ~L52-67)
is a global on/off: flip it `True` and it runs for **every** skin, flip it `False` and it runs
for none. That's the wrong granularity — a matte-clay theme has no business paying for an
emissive pass (nothing should glow), while an ember-runes theme clearly does. The fix isn't
per-skin hand-toggling (that's the `fix-generalizable-rule` anti-pattern); it's letting the
DIRECTOR decide, per skin, from the theme spec.

**Where the decision hook lives:** `orchestrate12.py`'s flag block, right before each stage's
`if <FLAG>_ENABLED: run([...])`. When the global flag is `True`, don't unconditionally `run()`
the stage — first call a cheap director gate (a new thin wrapper, or a mode flag on
`director_review.py`) that reads the theme spec and returns a verdict; only run the stage if
the verdict says to. Global flag semantics change from "always run" to "director MAY choose to
run" — the global flag becomes a *permission*, not a *command*.

**Spec surface to decide from:** the director already has the right context object —
`director_review.py` loads `theme_specs/<id>.json` (`spec_path`, ~L49) and already extracts
`spec.get("css", {})` (~L132) and `spec.get("lighting", {})` (~L133, incl. `emissive_hint` /
`pulse`) for its existing judgment prompt. The new per-stage gate reuses that same load — no
new spec-reading code, just a narrower prompt asking "does THIS theme spec warrant stage X" vs
the existing prompt's "how good is the finished render." Eventually (per the semantic-emissive
research doc below) this could also see the painted image, not just the spec text — but the
first cut should be spec-only, text-only, to keep it cheap and fast (see cost logic below).

**Decision shape:** a structured JSON verdict, `{"run": bool, "why": "<one-line rationale>"}`
per candidate stage, logged into `orch.json` (the per-skin run summary `orchestrate12.py`
already writes) under a `director_decisions` key — e.g.
`{"emissive": {"run": false, "why": "matte clay theme, no light-emitting elements in spec"}}` —
so a skipped stage is auditable after the fact (why didn't ember-runes get its glow pass? check
`orch.json`, not tribal memory or a re-run).

**Cost logic — only worth it when skip-rate is meaningful:** a director gate call is
text-only-on-spec, so it's cheap (~$0.01/call range, well under `director_review.py`'s own
~$0.02-0.05 full-render judgment) but it's not free, and it's an extra round-trip added to
every roll. It only pays for itself when a real fraction of skins would otherwise burn spend
on a stage they don't need — e.g. gating a ~$0.03+ emissive/PBR pass ($0.01 gate ADDS cost on
skins that WOULD run it, but SAVES the full $0.03+ on skins that wouldn't) nets positive once
skip-rate is meaningful (rough breakeven: skip-rate > gate-cost / stage-cost, i.e. >~33% skipped
for a $0.01 gate vs $0.03 stage). Don't wire this for a stage where every skin in the roster
would say yes anyway — check the roster's actual theme_specs distribution before implementing,
not after.

**Generalizes to:** any future flag-gated optional stage, not just emissive/PBR — the pattern
(global flag = permission, director spec-read = per-skin verdict, verdict logged to `orch.json`)
should be the default shape for the *next* optional stage added, not a one-off for emissive.

**Note (2026-07-11): this stage-gating PATTERN stays open/general — it is v1-relevant for
any future optional stage** (e.g. `DIRECTOR_REVIEW_ENABLED` below). Its *emissive/PBR example*
specifically is now **PARKED for skeuo v2** (see the section at the top of this file) —
don't implement the emissive gate as a first proof-of-concept; pick a still-active stage if/
when this pattern gets built.

**Cross-links:**
- Emissive rethink (§1, this doc's neighbor "think-about notes") — the concrete first use case:
  [`docs/design/2026-07-11-think-about-notes.md#1-emissive-rethink`](../../../docs/design/2026-07-11-think-about-notes.md#1-emissive-rethink)
- Semantic-ML emissive landscape (2-stage VLM-judge + SAM-3-refiner) — a heavier per-skin
  judgment call this pattern could eventually route into:
  [`docs/design/2026-07-11-semantic-emissive-research.md`](../../../docs/design/2026-07-11-semantic-emissive-research.md)
- `DIRECTOR_REVIEW_ENABLED` in `orchestrate12.py` (~L65) — the existing flag this pattern
  generalizes; `director_review.py` — the existing director spec-read surface to reuse
  (`spec_path`/`css`/`lighting` extraction, ~L49-158).
- **Knob tick-mark provisioning — a second concrete candidate stage (2026-07-11 human
  overrule + axis-separated re-score):**
  [`docs/experiments/2026-07-11-knob-tick-provisioning.md`](../../../docs/experiments/2026-07-11-knob-tick-provisioning.md#human-overrule--axis-separated-re-score-2026-07-11).
  Whether a skin's paint prompt should ask for baked tick marks is exactly a per-theme
  "does this stage fit this theme" call (matte-clay: maybe not; a gauge/dial-heavy theme:
  yes) — the same shape as the emissive gate. Tick presence itself becomes the director
  verdict; `KNOB_TICKS_ENABLED` (CSS/SVG overlay, commit `d2271894`) is the deterministic
  fallback for a director-says-yes skin whose paint roll didn't produce ticks.

## Position-mask correlation experiment (2026-07-11) — poscorr/

Pure-control (non-skin, abstract) feasibility test: can `gemini-3-pro-image-preview` correlate
an output mask CELL to its template REGION by POSITION ALONE (reading-order convention, no
colour/number in the prompt), vs an explicit NUMBER-tag convention, vs today's COLOUR-key
convention? Motivated by the twoimg NEUTRAL-arm finding that guide-colour bleed persists via
the TEXT PROMPT (the mask spec must NAME each colour) even with a colourless reference image —
this asks the prior question of whether position-only correlation is reliable enough to drop
colour from the mask column entirely. Self-contained harness: `poscorr/template.py` (synthetic
8-region template + ground truth), `poscorr/gen_poscorr.py` (Vertex gen, reuses
`twoimg/genskin_twoimg.py`'s proven `edit_vertex_multi`), `poscorr/score_poscorr.py` ($0
deterministic IoU/occupancy/contamination scoring), `poscorr/build_results.py` (results page).
Record: `docs/experiments/2026-07-11-position-mask-correlation.md`.

## Director final-review stage added (2026-07-11) — flag-gated OFF

`director_review.py` <assets-dir> — renders the REAL served `player.html` via a throwaway,
isolated Node/Playwright driver (its own `chromium.launch()`, never the shared
claude-in-chrome browser), captures a full screenshot + the standard per-control crops
(knob, seek-at-mid, switch, buttons, screens), and sends them to gemini-3.1-pro-preview via
Vertex (gcloud-token auth, same pattern as `genskin.py`'s `edit_vertex()`) with a
DIRECTOR-persona prompt judging the FINISHED render against its own `theme_specs/<id>.json`
brief — cohesion, material fidelity, control legibility, seating, what to improve. Writes
`<assets-dir>/director-review.json` (model id + cost estimate recorded in the output).
~$0.02-0.05/skin, ~11s/call. Distinct from `observe12.py` (geometry/defect verification,
not aesthetic judgment) — see both files' docstrings.

Wired into `orchestrate12.py` behind `DIRECTOR_REVIEW_ENABLED = False` (after
`build_player.py`, alongside the existing `PBR_PASS_ENABLED` flag) — **disabled by
default**, not yet proven across the roster. Verified once live against
`assets-diablo-gothic`: valid JSON landed, verdict FAIL / score 4, and the notes correctly
called out the neon-colored per-control rings visible in the real render (independently
confirmed by opening `assets-diablo-gothic/director/full.png` — the borders are genuinely
in the shipped output, not a hallucination) — a real, actionable defect the geometry pass
doesn't check for. Next step before flipping the flag on: decide whether those neon rings
are a `build_player.py`/`extract12.py` regression (they look like the `regions.json` debug
`keys` per-control colors leaking into the actual control render) — worth investigating
before enabling this stage broadly, since it'll fail most/all skins on that same defect
until fixed.

## Media policy (2026-07-11) — paid outputs now committed to git

`joint-4k.png`/`paint.png`/`mask.png` (paid Vertex rolls) and `assets-*_biref/*.png`
(runtime-required cut sprites `player.html` loads from `../assets-<theme>_biref/`) are now
committed for all 15 skins (~699MB, plain git objects — no LFS is set up for gen12, matching
the existing plain-PNG convention in `twoimg/`/`bproof/`; repo LFS exists but is currently
scoped only to `docs/experiments/assets/*.png|*.jpg` — recommend extending LFS to gen12's
`assets-*` media in a follow-up rather than this being retrofitted unilaterally here).
`blueprint.png` ($0 deterministic) and `assets-*_biref/` as a bulk ignore pattern stay/stayed
ignored — see `.gitignore` for the itemized policy comment.

## Media policy revisit (2026-07-11, later) — non-vital bulk moved to Drive — DONE

**COMPLETED (2026-07-11, latest):** the blocker below was cleared (`gdrive:` remote
re-authenticated interactively). All 36 offload files (358,544,116 bytes) uploaded to
`gdrive:skeuo-ui/gen12-media/2026-07-11/<repo-relative-path>` via
`rclone copy --files-from --checksum`; post-upload `rclone check` = 36 matching / 0
differences (Drive md5 vs local). Per-file sha256 + bytes + Drive share links recorded in
`MEDIA-MANIFEST.md` (human) / `media-manifest.json` (machine) — all 36 `rclone link` calls
succeeded, no manual sharing needed. `.gitignore` rewritten (offload patterns + a
`!assets-steam-porthole_biref/global-matte.png` negation keeping the dashboard explainer's
one runtime matte tracked); the 36 files `git rm --cached`-ed (kept on disk, now
untracked-ignored). Render verify: dashboard12.html's only offload-class request is
steam-porthole's global-matte (200); steam-porthole player.html renders with zero console
errors and zero requests to offloaded files; the two dashboard player-pbr.html 404s
(claymation, fa-sky) are pre-existing — those files never existed on disk. History-reclaim
(filter-repo) remains a flagged, NOT-done decision (see "History honesty" below).

<details><summary>Original blocked-state record (kept for provenance)</summary>

User correction of the commit above: don't commit large non-vital volume media, store in
Drive and link in. Re-classified the ~786MB currently tracked under `assets-*` by hard
evidence (grep for actual runtime `img`/`url()`/`fetch` refs in the *committed* `player.html`
/ `player-pbr.html` / `dashboard12.html`, not assumption):

**Stays committed (runtime-required):**
- `assets-*/paint.png` (149MB/15) — `player.html` background + `player-pbr.html` `loadImg`.
- `assets-*/mask.png` (77MB/15) — `player.html` line ~224, `new Image(); mi.src='mask.png?v='+V`
  compositing. (A parallel-lane message claimed this was non-runtime and safe to offload —
  **false**, verified by grep across all 15 `assets-*/player.html`; did not act on it.)
- `assets-*_biref/{device,seek,vol,shuffle_off,shuffle_on,extra-*}.png` (~242MB) — `BREF` path
  loaded by both players.
- `assets-*_pbr/{basecolor,normal,roughness,metalness,glass,btn-ids,emissive,art-mask,
  viz-mask,meta.json}` (~83.6MB) — `player-pbr.html` runtime loads.
- `assets-steam-porthole_biref/global-matte.png` only — `dashboard12.html`'s embedded
  `explainer_anim.js` hardcodes `KNOB_SKIN="assets-steam-porthole"` and `loadImg`s this exact
  file for the committed interactive pipeline walkthrough. The other 14 skins' copies are not
  referenced by anything.

**Non-vital, offload-intended (NOT yet moved — see blocker below), ~341.8MB/36 files:**
- `assets-*/joint-4k.png` (231MB/15) — 4K joint sheet, no runtime ref anywhere; paid Vertex
  roll (not free to regenerate) but already fully recoverable from origin's git history
  (commit `39d76200`) regardless of a Drive copy.
- `assets-*_pbr/height.png` (2.4MB/7) — no runtime ref anywhere (checked `player-pbr.html`,
  `build_player_pbr.py`, `pbr_pass.py`).
- `assets-*_biref/global-matte.png` EXCEPT steam-porthole (108.4MB/14) — no runtime ref;
  documented elsewhere as $0-recomputable via local BiRefNet (`BIREF_LOCAL=True`).

**Drive offload — BLOCKED, not attempted beyond a mechanism test:**
- `rclone`'s configured `gdrive:` remote has an empty/expired OAuth token
  (`rclone lsd gdrive:` → "empty token found — please run rclone config reconnect gdrive:").
  Reconnecting is a one-time interactive browser OAuth flow — a legitimate human handoff, not
  something to do headlessly.
- Fell back to the claude.ai Google Drive MCP connector (`mcp__claude_ai_Google_Drive__*`).
  Created the target folder `skeuo-ui/gen12-media/2026-07-11/` (empty, ready:
  https://drive.google.com/drive/folders/1k7qEh9sfYBSu-xCUqzLpPTSCLBTmL03r). Its `create_file`
  tool only accepts inline `base64Content`/`textContent` — no file-path/streaming/URL upload,
  no chunked/append write. Tested with the smallest real offload candidate
  (`assets-fallout-vault_pbr/height.png`, 277KB raw / 370KB base64): **both** the `Read` tool
  (256KB text cap) and the `Bash` tool's own stdout capture (same ~256KB cap, "Output too
  large") refuse to surface the base64 text into a tool-call parameter. Ceiling is a hard
  ~190KB raw / ~256KB base64 per file — every one of the 36 offload candidates (277KB–17MB)
  exceeds it, and zipping would make it worse (constraint is per-call payload size, not file
  count), so no partial/half upload was attempted.
- **Unblock:** run `rclone config reconnect gdrive:` interactively once, then
  `rclone copy <files> gdrive:skeuo-ui/gen12-media/2026-07-11/` streams natively with no
  context/payload bottleneck — trivial once the token is valid.
- No files were `git rm --cached`, `.gitignore` was left as-is, and nothing was pushed for
  this reclassification — untracking now, with no working Drive mirror, would leave the
  manifest linking to nothing. Re-run once `rclone` is reconnected.

</details>

**History honesty (for whenever the offload+untrack does complete):** removing files from the
tip does NOT shrink `origin`'s already-pushed pack — `39d76200`'s blobs stay in history until
a coordinated `git filter-repo`/BFG rewrite + force-push. Repo-wide (not gen12-scoped)
`git count-objects -vH` right now: 5364 loose + 19867 in-pack objects, 16.68 GiB total,
5.25 GiB in 18 packs — a tip-level `git rm --cached` changes none of this; only a history
rewrite would, and that needs explicit user sign-off (shared `main`, force-push implications).

## knobticks: baked knob tick-arcs + in-call rotation metadata — DONE 2026-07-11, UNRELIABLE

Can the paint prompt provision a themed tick/start-end system around knob sockets AND
self-report the sweep as JSON in the same TEXT+IMAGE Vertex call? Harness + adjudicated
results page: `knobticks/` (`gen_knobticks.py`, `score_knobticks.py`, `adjudication.json`,
`index.html`); write-up:
[`docs/experiments/2026-07-11-knob-tick-provisioning.md`](../../../docs/experiments/2026-07-11-knob-tick-provisioning.md).
Headlines: 2 themes × 2 arms (0..1 / −1..0..+1) × 2 seeds — tick-arc PRESENCE 6/7 painted
gens, but the full contract passed **0/8** after adjudication (VLM witness said 3/7): the
clause's own MIN/MAX/CENTER vocabulary baked in as literal engraved TEXT on 3/7, knob/layout
drift broke socket adherence on 2/7, and 1/8 gens returned thought-text with NO image at all
(3 retries). Metadata half: JSON parsed 4/7 and every parse is a **verbatim echo of the
prompt's example (−135/+135)** — a parrot, not a measurement (confirms the
semantic-emissive-research §4 circularity prediction; sibling finding to imgjson's broken
bbox frame). Verdict: baked ticks UNRELIABLE, in-call metadata UNUSABLE. Recommendation:
CSS/SVG tick overlay in `build_player.py` from `regions.json` socket centre/radius + the
fixed −135..+135 runtime convention, themed via director `css` colours — no model needed.
Media policy: paint.png + crops committed (page-referenced evidence); joint-4k/mask/blueprint
gitignored per the media-policy revisit above (add knobticks to the Drive offload list when
rclone reconnects).

## imgjson: image-model JSON output + structured-I/O sweep — DONE 2026-07-11 (ROUND 2 CORRECTION below)

Answered "can gemini-3-pro-image-preview emit usable JSON (bbox manifests) alongside its
image output" + a structured-I/O viability sweep. Harness + results page: `imgjson/`
(`run_tests.py`, `run_structured.py`, `score.py`, `diagnose.py`, `index.html`); full
write-up: [`docs/experiments/2026-07-11-image-model-json-output.md`](../../../docs/experiments/2026-07-11-image-model-json-output.md).
Headlines: image-model text output is real (TEXT must ride WITH IMAGE modality; TEXT-alone
= 400) but its bbox y-coords come back in an internal frame → raw IoU 0.003, unusable for
manifests or detection; `responseMimeType/responseSchema` on the image model = hard 400.
Text model (`gemini-3.1-pro-preview`): ~13 px mean centers on unambiguous controls;
`responseSchema` costs nothing and guarantees field/enum completeness → **worth adopting on
the director's calls** — **DONE, commit `4535f8f3`**: `src/generate/director.ts`
`directorChat` now takes an optional `schema` and every `deriveMaterial`/`deriveLayout`/
`extractSlots`/`extractMasks` call passes one; `director_review.py` too. Structured
(fenced-JSON) prompts: measured neutral on extraction; paint-side tested separately, see
jsonspec entry below.

**ROUND 2 CORRECTION (2026-07-11, jsonspec bonus + stability probe):** the "raw IoU 0.003,
unusable" headline above was measured against an AD-HOC 0-1 `{x,y,w,h}` convention this
experiment invented — not how Google documents boxes for this model. Asked in Google's own
`box_2d=[ymin,xmin,ymax,xmax]@0-1000` convention (`jsonspec/bonus_probe.py` +
`jsonspec/stability_probe.py`, 4 calls total ≈ $0.20), the SAME image model's boxes are
real: best-reading mean IoU **0.79 / 0.72 / 0.54 / 0.37** (seeds 71-73 wc-goldshield, 74
diablo-gothic), per-control centers ≤26px for 9/10, 9/10, 8/10, 5/10 controls. BUT the
element order is **UNSTABLE call-to-call** — seed 71 emitted `[ymin,xmin,xmax,ymax]`
(transposed), seeds 72/73/74 emitted the documented order — and 2/4 calls carry
whole-control semantic swaps (vol/shuffle→strip sprites 1852/1130px; visualizer↔album_art
~1090px). `imgjson/index.html` and `imgjson/explain.html#round2` both carry a "ROUND 2
CORRECTION" section/banner now — the original tables are left intact (real, reproducible
artifacts of the convention actually asked) but are no longer the final word on whether
this model CAN report boxes at all.

**VERDICT — is the image model's native-convention box output witness-grade (a cheap
second signal alongside extract12, never load-bearing placement, per
`ai-image-coords-rule`)? NO.** The spatial sense is real (11.6px mean centers on its best
call), but (a) element order flips call-to-call → every consumer needs per-call order
disambiguation (untested heuristic), (b) 2/4 calls contain ≥1 whole-control miss ≥278px,
(c) per-call quality swings 0.37–0.79 mean IoU, and (d) the TEXT model
(gemini-3.1-pro-preview + responseSchema) already gives ~13px centers under a STABLE
convention at lower per-call cost — it dominates the image model for any witness role. If
a VLM witness is ever wired over extract12, use the text model; the image model's boxes
stay a documented curiosity. Numbers: `jsonspec/stability_probe.json`.

## Think-about notes (2026-07-11) — emissive, director-vision, drift-clause bisect

Three open design questions written up as decision-ready options + recommendations, none
implemented: [`docs/design/2026-07-11-think-about-notes.md`](../../../docs/design/2026-07-11-think-about-notes.md).

- **§1 Emissive rethink** — moved to the
  [PARKED for skeuo v2](#parked-for-skeuo-v2-2026-07-11--emissive--pbr-not-v1-work)
  section at the top of this file (`css.glow` (d) is the one part NOT parked — ships
  independently).
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

### Knob baked-rotation fix (`extract12.py` + `build_player.py`, 2026-07-11)

- **Bug:** knobs started at a non-zero rotation on several skins (steam-porthole,
  ps1-crunchy, myst-arcanum, fallout-vault) — the cap sprite is cut with its painted
  pointer/notch baked at whatever angle the model drew, and the player rotated
  RELATIVE to that raw cut, so value-0.5/init showed the indicator at the baked
  angle instead of straight up.
- **Fix (generalizable, both stages):**
  - `extract12.py`: new `detect_knob_zero_deg()` — material-agnostic, relative-signal
    detector. Finds the painted pointer/notch as a local radial anomaly in the cut
    cap sprite's own gradient-magnitude angular profile (robust median+MAD z-score
    vs the cap's otherwise radially-symmetric body), rejects anomalies that are
    angularly WIDE (a directional specular highlight streak, not a carved notch).
    Emits `regions[knob].knob_zero_deg` in degrees CW-from-up, or `null` when no
    anomaly clears the bar (diablo-gothic, n64-prerender-character correctly null —
    no reliable indicator, never guessed).
  - `build_player.py`: counter-rotates the cap by `knob_zero_deg` so value 0.5/init
    shows the indicator at 12 o'clock regardless of the raw cut's baked orientation;
    documented convention: value 0 → -135° (~7 o'clock), value 1 → +135° (~5 o'clock).
- **Verified:** re-extracted + rebuilt the 4 named skins + 2 regression skins
  (fa-pod, n64-cutscene) from their EXISTING paints (no re-rolls); driven in the
  real shipped `player.html` via Playwright (synthetic pointer drag), close-up
  element crops at init + after-drag, cross-checked by `google/gemini-2.5-pro` via
  fal `openrouter/router/vision` (reasoning:true) — VERDICT: PASS, all init crops
  read pointer-at-12-o'clock, all drag crops read correct clockwise rotation, both
  regression skins visually unchanged (fa-pod -4°, n64-cutscene 0°, imperceptible).
- **Known limitation — myst-arcanum:** the cap sprite carries TWO carved marks (a
  V-notch near 0° and a thin wedge slit at 94°) rotating together as one rigid cap.
  The detector's relative-signal metric picked the wedge (z=17.3, ~4.8x the next
  peak) as the stronger local radial anomaly; the VLM cross-check independently
  argued the V-notch (design convention: indicators default to 12 o'clock) is more
  likely the "intended" pointer. Neither geometric feature (fill-ratio, radial span)
  disambiguates — the two marks measure nearly identically. This is a genuine
  ambiguity in the SOURCE ART (two plausible indicator-like carvings baked onto one
  sprite), not a detector bug to special-case per-skin (disallowed by
  `fix-generalizable-rule`). The render is now internally consistent either way
  (the sweep tracks correctly from whichever mark was chosen) and gate-PASSes;
  flagging for human judgment call if the wedge reading looks wrong on review.

- **USER OVERRULE + re-verification (2026-07-11, same day):** the VLM-witnessed PASS
  above was overruled — *"did you even cross check with vlm? these lines are off.
  near, but off and noticeably."* A VLM cannot judge single-digit angular error
  (witness, not judge — `verify-rule` §1b), and the proof page's overlay arrows were
  drawn by a script that **reimplemented** the detector's centroid/radius geometry
  instead of reading its stored output (`verify-rule` §7 proxy trap). Replaced with a
  deterministic, $0, VLM-free closed loop: render the real `player.html` in a
  throwaway isolated Playwright, crop the real `.pknob .cap` DOM element, re-measure
  with the SAME detector algorithm on the RENDERED pixels. Root cause found: the old
  detector returned the winning angular bin's leading EDGE with zero sub-bin
  refinement (every stored `knob_zero_deg` was an exact multiple of 2° — proof of the
  bug), a real, generalizable +1.0–1.9°/skin bias, smaller than the "5–20°" hypothesis
  but real. Fixed in a new shared module `knob_angle.py` (imported by both
  `extract12.py` and the verifier — one implementation, not two). Rotation-center and
  CSS transform-origin were investigated and ruled out (measured <0.3° contribution).
  Post-fix render error, all 6 skins: 0.44°–2.32° (was 0.56°–3.72° pre-fix; only
  n64-cutscene was over the 3° bar pre-fix, now under). Full writeup + numbers:
  [`docs/experiments/2026-07-11-knob-zero-closed-loop.md`](../../../docs/experiments/2026-07-11-knob-zero-closed-loop.md),
  results page `knobzero-proof.html` (regenerated, reads overlay geometry from stored
  `regions[knob].knob_zero_geo`, never re-derives it). myst-arcanum's two-mark
  ambiguity above is unchanged and still pending human call.

## Knob tick marks shipped as a CSS/SVG overlay, not baked into the paint (2026-07-11)

`KNOB_TICKS_ENABLED = True` in `build_player.py`. Baked-tick provisioning was tried and
rejected first — see
[`docs/experiments/2026-07-11-knob-tick-provisioning.md`](../../../docs/experiments/2026-07-11-knob-tick-provisioning.md)
(0/8 adjudicated PASS: text contamination `MIN`/`MAX`/`CENTER` baked as literal labels,
layout drift, no reliable start/end marks, and the in-call rotation self-report was a
verbatim prompt-echo, not a measurement) — which recommended exactly this fallback.

**Design:** an SVG ring drawn from the SAME socket centre/radius (`cx,cy,w`) already used
for the cap, sharing the cap's `-135°..+135°` sweep convention. 11 ticks (3 major: start,
12-o'clock centre, end; 8 minor between), a dark `multiply` pass + a 1-tick `screen`
highlight pass so they read engraved rather than stickered, colored by the director's
`css.accent` when the theme spec supplies one (else a neutral fallback). A subtle needle
tracks live `val` independent of the cap's own baked pointer (useful when
`knob_zero_deg` is `null` — no baked pointer at all). `r.zero||'start'` is read but only
`'start'` is exercised today; `'center'` (a bigger detent mark at the middle major tick)
is wired and is one skin-side field away, per the task's ask.

**Verified:** rebuilt all 15 skins. Close-up crops (init + post-drag) on diablo-gothic,
fa-pod, steam-porthole, wc-goldshield, driven via a real `pointerdown`/`pointermove` on
the shipped `player.html` (Playwright), cross-checked by `google/gemini-2.5-pro` via fal
`openrouter/router/vision` (`reasoning:true`, ~$0.034 total for 4 calls). 3/4 clean PASS
(fa-pod, steam-porthole, wc-goldshield — wc-goldshield's drag crop shows the cap's baked
pointer land exactly on the start major tick at val=0). diablo-gothic's VLM verdict was
FAIL ("forms a full 360° circle, no major ticks") — **overruled**: the DOM has exactly 11
`<line>`s whose angles are provably `-135..+135°` by construction (same unmodified
function that rendered a correct, VLM-confirmed 270° gapped arc on the other 3 skins), and
a wide crop shows the skin's OWN baked gear-cog ring already runs the full 360° with
tooth-valley shadows that visually mimic a continuous tick ring — a legibility clash with
that one skin's busy source art, not a code defect. No pipeline change from this — a
single busy-texture skin isn't grounds for a generalizable color/contrast rule
(`fix-generalizable-rule`); revisit only if this recurs across more of the roster.

## Crop discipline rule added — mainline harness fixed, experiment scripts NOT retrofitted (2026-07-11)

`.claude/rules/sota-eye-review-rule.md` gained a "Crop discipline" section (full frame always
attached, crops anchored on detected `regions.json` positions not template-expected ones,
≥2x padding, VLM prompt licenses CROP-MISS, a returned CROP-MISS is unmeasured not FAIL) —
written from two confirmed burns: `knobticks/` skin `steam-porthole-ticks01-402` (VLM judged a
template-anchored crop that actually framed the button row, not the drifted knob, and said
RELIABLE) and the knob-angle detector measuring noise as the indicator on 4/7 gens from a
template-sized window. `observe12.py` (the mainline observation harness) is fixed to comply —
verified live: re-ran on `assets-fallout-vault` with `--vlm`, the model correctly returned
`CROP-MISS` for 2 of 10 controls (`prev`, `repeat`) and those landed in `unmeasured_crop_miss`,
not counted as broken, while the full-frame fallback still caught a real defect (`shuffle:
BROKEN (baked text label)`) → overall `VERDICT: FAIL`, correctly.

**`knobticks/`, `semissive/`, and any other one-off experiment harness's own eye/judge script
(`gen_knobticks.py`, `score_knobticks.py`, `semissive/judge.py`, `semissive/sota_eval.py`, etc.)
predate this rule and are NOT being retrofitted** — they're closed experiments, not the
production path. The rule binds **future** experiment harnesses and the mainline pipeline
(`observe12.py`) going forward.

## Human review round PREPPED — one link, ready for re-rolls to land (2026-07-11)

Milestone 1's gate (checklist item 6, `docs/SKEUO-V1.md`) needed a **current, non-stale** review
round — the only `review.json` on disk was a 0/15 all-fail round from 2026-07-09 that predates
knob-zero, tick provisioning, and the crop-discipline protocol. Prepped so the round is one click
once the in-flight re-rolls land:

- **`review_server.py` verified against the CURRENT `dashboard12.html`** end-to-end, real shipped
  path (not a reimplementation): killed a 2-day-old orphaned instance on `:54731` (predated the
  file's `ThreadingMixIn` fix), started fresh on `:61171`, drove the actual page via headless
  Playwright — toggled `claymation` to PASS + typed a note, confirmed the debounced `POST /save`
  landed in `review.json` on disk with the correct current 15-skin roster. `ThreadingMixIn` +
  `daemon_threads=True` (the idle-Chrome-preconnect wedge fix) confirmed already in place, no
  code change needed.
- Confirmed the dashboard's persistence model: verdicts live in the browser's `localStorage`
  (keyed by page origin) and mirror to `review.json` only on save — so a **new server port is
  automatically a blank round** (new origin → empty `localStorage`); no code change needed to
  "reset" the UI, only the on-disk file.
- **Archived, never deleted** (human-labeled-data-rule): the pre-existing
  `review-2026-07-09.json` (13:02 snapshot) was already a dated copy but a *later* stale state
  existed too (`review.json` as of 14:15 — extra `_pbr`/`n64-lowpoly` stale keys, differing
  `fallout-pipboy` verdict); that later state is now preserved as `review-2026-07-09-archived.json`.
  `review.json` reset to `{}` for the new round.
- **`REVIEW-ROUND.md`** written: the gate criteria (controls seated, no guide rings, no baked
  text, two-state toggle, full slider throw, theme-correct ticks, true knob zero, overall
  aesthetic), how verdicts persist, and the served URL. Server left running —
  [`.review-url`](.review-url) → `http://localhost:61171/dashboard12.html`.
- **Not done in this pass** (owned by other agents per this task's scope): the actual re-rolls
  (`fa-sky`, `ps1-wild`) and prompt-clause fixes (checklist items 1-5) that should land BEFORE the
  user spends the review round on them — reviewing pre-fix skins wastes the round. This prep only
  makes the round itself frictionless once those land.

## `PROMPT_JSON_SPEC` flag adopted into genskin.py, default OFF (2026-07-11)

Ported the jsonspec/ experiment's fenced-JSON control-spec encoding into mainline `genskin.py`
as `PROMPT_JSON_SPEC` (flag-gated, default `False`, byte-identical prose prompt when off —
diff-verified against pre-edit `genskin.py` for 2 themes via `--blueprint-only`). When `True`,
only the templated + `conditioning == "solid"` path (the only arm jsonspec/ actually tested)
swaps the per-control roster/position/size/guide-colour/strip-order/congruence spec for one
fenced ```json``` block with narrative clauses kept as prose; `outline`/`twoimg` conditioning
and templateless mode are untouched regardless of the flag (dry-verified: forcing the `outline`
arm with the flag `True` still produced the prose prompt, `prompt_json_spec: false` recorded).
Tick-provisioning bullets (a feature that shipped before jsonspec/ ran and that harness never
referenced) are spliced into the JSON-spec prompt at the same textual position as production, so
`ticks: baked` skins don't silently lose that clause when the flag is on.

**Flip `PROMPT_JSON_SPEC` after the current re-roll batch drains; expected effect: reduced
guide-hue bleed, no drift change** (jsonspec/verdict.json: bleed 5.04%→1.56% mean, 4/4 paired
gens lower, gate 3/4 vs 2/4; layout drift unaffected, ~690px both arms). Do not flip mid-batch
(generation-spend-rule). See jsonspec/verdict.json, docs/experiments/2026-07-11-jsonspec-paint.md,
commit 8abf3e8a for the underlying evidence.
