# gen12 TODO

---
## silcheck.py: deterministic silhouette-match check for baked icon buttons — DONE 2026-07-12 ($0)

Built per the verification-recalibration lane's finding (VLMs scored 0% recall on
silhouette-mismatch defects) that the fix has to be geometric, not another model call.
`silcheck.py` (new, read-only re: `extract12.py`/`build_player.py`/`observe12.py`/`genskin.py`
— none touched) checks whether a baked icon button's own painted silhouette actually sits
inside and fills the `device` bbox that `build_player.py`'s press-overlay positioning uses.
Two methods computed, one gates:

- **Gating — "maskKey"**: verbatim port of `build_player.py`'s own ink-silhouette extraction
  (crop mask.png around `maskDevice` ±10%, colour-key threshold <7000 sq-dist against
  `keys[<button>]`, tight-bbox/centroid vs `device`). Zero false positives across the 15-skin
  roster bar one genuine finding (below). MISS mode: anchored to `maskDevice`, which is
  upstream of the same detection `device` is snap-corrected from — a verify-outputs-rule
  circularity trap when the true offset exceeds `snap_to_paint`'s capped correction.
- **Advisory, non-gating — "paintVividnessAdvisory"**: 2-D extension of `extract12.py`'s own
  `snap_to_paint` icon-vividness heuristic, run independent of mask.png. Prototyped as a 2nd
  gating signal (it does catch myst-arcanum's degenerate icon content, area_ratio 0.06-0.21 vs
  every healthy button's ≥0.44) but DROPPED from gating: it measures near-zero "vividness" on
  every button of monochrome/engraved-icon skins (diablo-gothic, fallout-pipboy, ps1-crunchy)
  regardless of health — would have failed 3 entire unnamed skins outright. Kept as a recorded,
  non-gating diagnostic (restraint-rule: a signal that can't discriminate on a whole art-style
  class is worse than not having it).
- **Advisory, non-gating — "circleFitAdvisory"**: port of `extract12.py`'s knob `circle_fit`
  gradient-ring search, scoped to buttons. Measures the one real defect maskKey misses
  (fa-sky/playpause, confirmed by direct visual inspection) but produces comparable-magnitude
  noise on healthy buttons with a concentric two-tone bezel (verified false-positive:
  fa-pod/queue at the same offset magnitude as fa-sky's real defect) — reported for human
  triage, not gated.

**Calibration vs `review-2026-07-11-round1.json`** (the 4 named skins — fa-sky, myst-arcanum,
steam-porthole, wmp-quicksilver — must FAIL; the other 11 must not FAIL on button-silhouette):

| skin | expected | got | notes |
|---|---|---|---|
| steam-porthole | FAIL | **FAIL** | playpause iou<0.30; next/repeat/queue NO-SILHOUETTE |
| wmp-quicksilver | FAIL | **FAIL** | prev/next/repeat NO-SILHOUETTE |
| myst-arcanum | FAIL | PASS (miss) | playpause's mask blob is healthy-shaped (iou 0.80, area_ratio 0.97) — the painted CONTENT inside it is a decorative gear/clockwork cluster, no play/pause glyph at all. A content defect (wrong icon painted), invisible to any geometry-only check by construction; routed to genskin.py's prompt layer per fix-generalizable-rule, not this check's job. |
| fa-sky | FAIL | PASS (miss) | playpause's device bbox is visibly off-centre from the real chrome/glass button (confirmed by crop overlay) — `snap_to_paint`'s 20%-capped x-shift undershoots the true offset. circleFitAdvisory measures it (offset_frac_diag=0.102) but the same diagnostic false-positives at equal magnitude on confirmed-healthy buttons elsewhere (bezel-ring ambiguity) — not separable by threshold at the effort spent. |
| 11 unnamed | PASS | 10× PASS, 1× FAIL | fa-pod/prev FAILs maskKey NO-SILHOUETTE — traced the raw pixels: mask.png's guide colour there measures ~106px euclidean from its flat key, just over build_player.py's own <7000 (≈83.7px) threshold, even though the visible paint.png icon is a clean, correctly-placed rewind glyph. Since this is a verbatim port of the SHIPPING threshold, the real player very likely also silently falls back to a generic rounded-rect ink shape for this one button — probably a genuine, unlabeled defect rather than checker noise. Left un-tuned deliberately (the point is testing what ships). |

**12/15 skins classified exactly as expected.** Full root-cause trail, thresholds, and the
prototyping/rejection reasoning for the two dropped/advisory signals: `CALIBRATION NOTES` at
the bottom of `silcheck.py` (~60 lines) and the method docstrings at the top.

**Integration recommendation: extract12.py's GATE SUMMARY block, not observe12.py's VLM
merge.** `extract12.py` already has the exact shape needed (`region_misplaced`/
`region_degenerate` computed as lists, appended to `reasons`, folded into the `PASS` bool —
lines ~1296-1352) and already has mask.png/paint.png/regions.json open at that point; no new
I/O, no VLM call, runs at build time before any review round. `observe12.py` already asks a
VLM about a `silhouette-mismatch` tag per control (its `PER_CONTROL_TAGS`) — the recalibration
doc is exactly why that ask scores 0% recall; this check should REPLACE that tag's VLM
judgment, not average with it, but that call belongs to whoever owns observe12.py's taxonomy.
3-line snippet for the extract12.py lane (not applied — extract12.py is out of this task's
scope):
```python
sil = __import__("silcheck").run(OUT) or {}                      # after region_degenerate block
sil_flagged = [b for b, m in sil.items() if m.get("verdict") == "FAIL"]
for k in sil_flagged: reasons.append(f"silhouette-mismatch:{k}")   # + `and (not sil_flagged)` in PASS
```

**Usage:** `python3 silcheck.py <assets-dir>` (writes `<assets-dir>/observe/silcheck.json`,
one entry per button) · `python3 silcheck.py --all` (whole roster) · `python3 silcheck.py
--calibrate` (`--all` + the scorecard above, re-runs live against current `regions.json` —
this is a **shared checkout**, the extract-fix lane was actively landing hitbox corrections
mid-session, confirmed via `git diff`: myst-arcanum's `repeat` gained a device bbox partway
through this investigation that it didn't have at the start).

---
## Prompt provenance: every workflow prompt clause carries an inline citation, stripped before the API — DONE 2026-07-12 ($0)

USER DIRECTIVE: prompts across the workflow get a stored, ANNOTATED form — why each clause
exists, cited to git-tracked evidence — in the style of central's `provenance` skill
(HTML-comment notes in rule source, stripped at export). Implemented as inline
`⟦cite:ref;ref⟧` markers INSIDE the existing prompt string literals of `genskin.py`,
`observe12.py`, `director_review.py` (no restructuring of their conditional prompt assembly),
plus a new `prompt_provenance.py` helper:

- **`strip_cites()`** — one regex, the only hot-path piece: genskin strips right after prompt
  assembly (before the Vertex/fal call and before results.json's `"prompt"` field);
  observe12/director_review strip right after their prompt assignments. Marker chars are
  ⟦⟧ (U+27E6/7) — never collide with the prompts' own []/{}.
- **Byte-identical proof** — a pre-annotation baseline of the assembled prompt was captured at
  HEAD across **11 genskin flag configs** (PROMPT_JSON_SPEC / KNOB_POINTER_UP /
  SEEK_CLAUSE_LITE each both states; solid/outline/twoimg conditioning; templateless; baked
  ticks — exercised via genskin's own `--blueprint-only`, $0), then re-run after annotation:
  **all 11 byte-identical**. observe12/director prompts proven via static joined-string-constant
  comparison (they need a served player to run): all 3 byte-identical after strip.
- **`PROMPT-PROVENANCE.md`** — generated by `python3 prompt_provenance.py` (one command),
  renders the full assembled prompts with every citation visible; regenerate + commit whenever
  a marker changes. 10 sections, ~129 markers. Citations point at repo-relative evidence:
  `docs/experiments/*.md`, `review-2026-07-11-round1.json` (human review),
  `docs/DECISIONS.md`, `abshape/verdict.json`, `artdrift_data.json`, and commit SHAs
  (e.g. shuffle first/second-state wording → `3eeccc55` ON/OFF-token backfire; empty-cavity →
  bproof + DECISIONS 2026-07-11; EXACT-FIT → review round1 notes; ABOVE/BELOW art clause →
  `e8f249db` artdrift fix; SEEK_CLAUSE_LITE → `5c378e5b` + erase12; KNOB_POINTER_UP →
  its experiment doc, falsified, flag OFF).
- **Maintainability:** a clause added without a cite is loudly flagged (stderr WARN during doc
  regen), never blocked — 4 residual warnings today, all data-block/interpolation lines.
  Where provenance is genuinely unknown the convention is `⟦cite:unknown⟧` (renders as
  "provenance unknown — flagged, not invented"); zero needed today.

---
## KNOB_POINTER_UP experiment: paint-at-convention does NOT beat detect-and-counter-rotate — DONE 2026-07-12 (~$2)

Tested the user's inverted-architecture insight (verbatim: "maybe instead of all this bullshit
[detect-and-counter-rotate] you can just specify in prompt that the tick on knob face should
point upwards 0 degrees?"): a light, text-safe clause ("its pointer notch aiming straight up" —
no angle numbers/position words, per the knobticks MIN/MAX/CENTER text-bake lesson) added to
both genskin.py prompt paths behind `KNOB_POINTER_UP` (default OFF), then 2 themes
(steam-porthole templated + myst-arcanum templateless multi-mark) x 4 seeds with the clause ON,
compliance measured by the EXISTING knob_angle.py detector (its right role: verifier).

**Result: compliance LOW — 2/8 detector-measured within ±10° of up (0.10°, 0.51°), 3/8 adding
one visually-up cap the detector abstained on (embossed, z=4.2 < 5 bar). Flip threshold was
6/8.** And the pre-fix baseline was NOT random: 85.6/144/95/355/4/359 is BIMODAL — 3/6 already
within ±10° (errs 5°, 4°, 1°) vs a right-side ~85-145° cluster. Clause-ON (25-38%) ≤ clause-OFF
(50%): one light sentence does not override the model's right-side-pointer prior (4/8 gens here
at ~60-110°, one straight down). **Verdict: detect-and-counter-rotate stays PRIMARY;
KNOB_POINTER_UP stays default OFF** (kept flag-gated for a cheap future re-test with stronger
conditioning, e.g. the pointer drawn INTO the blueprint guide instead of described). No
build_player.py change specced — fallback demotion is moot at this compliance.

Measurement collateral (fixed $0, experiment-local): biref12's mask-cell island matching missed
the vol cap on 4/8 gens (parts-tray card / strip drift) — `knobup/recover_caps.py` recovers it
deterministically (circular strip-island off the existing matte, 0.80 fill floor + 1.02 overfill
ceiling after two visually-caught wrong-part picks, cell-crop + local-BiRefNet fallback);
recovery changes sprite ISOLATION only, never the measurement. Unattributed: 3/4 steam gens
FAILed emptiness (baked knob in socket) — no same-seed control arm, flagged not attributed.

Full record: `docs/experiments/2026-07-11-knob-pointer-up.md` + `knobup/index.html` (served) +
`knobup/results.json`.

---
## DETECT+ERASE for baked slider thumbs — new erase12.py, 4/6 review-flagged skins fixed live — DONE 2026-07-12

Answer to review-2026-07-11-round1.json's #1 recurring complaint (baked slider thumbs, 6/15
skins) after "harden the seek-empty-slot prompt clause" had already failed across many prior
rounds (see the many `SEEK IS JUST AN EMPTY SLOT` iterations already in `genskin.py`). Per
`fix-generalizable-rule` + the bproof lesson (constraint BULK costs quality, not just
precision): stopped fighting the model with more prompt words and instead shipped a
deterministic **detect+erase** post-process. Prior art: `tools/mask-align-exp/erase_baked.py`
(run9-era gate-driven repair, same floor-tone-fill idea) — this is the gen12 port plus a
model-edit escalation path and real per-erase verification.

**New `erase12.py <assets-dir> [--control seek] [--bbox f,f,f,f] [--method classical|model|auto]`.**
Detection is its OWN groove-shaped algorithm (1-D column-median/std profile along the groove's
long axis, edge-anchored, compact-run capped) — **not** a reuse of the existing emptiness gate's
18%-interior-shrink+bright>150 test, which is centre-biased and (confirmed live, all 6 named
skins) BLIND to a thumb resting near a travel EXTREME — every real bake in the review sits at
one END of the groove. This is a HEURISTIC candidate locator only; every result was visually
inspected before trusting it (verify-outputs-rule), and it correctly false-positived on
claymation (see below) — the tool prints a candidate + saves before/after crops rather than
silently trusting itself.

**Erase method — classical FIRST, empirically insufficient, model fallback used for all 4:**
tried OpenCV inpaint (TELEA and NS, several radii) $0 first per the task brief — it consistently
produced a visible "X"-shaped smear/blur artifact on every tested skin (the mask rectangle's
borders are too content-diverse — carved decorative horns vs. flat channel floor — for
PDE-based inpainting to bridge). Escalated to a targeted Vertex nano-banana-pro edit
(`edit_vertex`, reused from `genskin.py`) on a SQUARE crop around the defect (square sidesteps
`ai-image-coords-rule`'s aspect-mismatch trap by construction — no separate aspect-matching
logic needed) with a feathered composite back (hard-paste left a faint rectangle seam,
confirmed live on the first diablo-gothic/fallout-vault pass; a soft alpha ramp over the outer
~12% margin fixed it). One skin (fallout-vault) needed a further **$0 floor-darken finishing
pass** — the model kept regenerating a glossy highlight roughly where the removed knob's
highlight was, even after 2 rounds of prompt tightening (run_frac/peak barely moved,
0.080/1.29 → 0.081/1.31); a direct pixel correction pulling any still-flagged run back toward
the groove's own floor tone (same idea as `erase_baked.py`'s fill, iterated against this
module's own detector) closed it in one pass.

**Live validation, 5 of 6 review-named skins reachable this session** (fallout-pipboy was
excluded — another concurrent session was actively re-rolling `assets-fallout-pipboy/paint.png`
mid-session, confirmed by a paint.png sha mismatch against the review's recorded sha; not
touched, per `git-worktree-rule`):

| skin | verdict | evidence |
|---|---|---|
| diablo-gothic | ERASED, clean | model edit, ember/dragon-cap fully gone, seamless; extract12's own `baked-thumb` gate (landed mid-session) reads `run_frac=0.516 peak=2.56 ok` (its own lava-vein glow correctly reads as a broad gradient, not a discrete bake) |
| fallout-vault | ERASED, clean | model edit + floor_darken finishing pass; gate `run_frac=0.069 peak=0.50 ok` (down from 1.31 pre-finishing-pass) |
| n64-cutscene | ERASED, clean | model edit (2nd prompt iteration fixed a first-pass shape bug — see below); gate `run_frac=0.000 peak=1.38 ok` |
| wc-goldshield | ERASED, clean | model edit, ornate cap fully gone, clean pointed end-cap consistent with the theme; gate `run_frac=0.000 peak=0.75 ok` |
| **claymation** | **NOT erased — false positive** | direct high-zoom crop inspection (both before AND after my fix) shows a genuinely EMPTY groove, just organic clay creases/highlight gradient. Notably, extract12.py's OWN newly-landed `baked-thumb` gate ALSO flags it (`run_frac=0.147 peak=1.27 flag=true`) — a shared false-positive between both detectors on the same mid-groove highlight gradient. Flagging for whoever owns that gate: worth a look, not fixed here (out of scope — I own erase12.py/genskin.py, not extract12.py). |
| fallout-pipboy | not touched | another session is actively regenerating this skin's paint.png concurrently (sha changed mid-session); re-run `erase12.py assets-fallout-pipboy` once that settles |

**A real mid-fix bug worth recording:** n64-cutscene's first model-edit pass removed the bronze
cap but reshaped the recess to match the CAP's own rounded-square silhouette (a bulge) instead
of the channel's actual constant width — visible on close inspection, not caught by the
detector (which only checks brightness, not shape). Fixed by adding an explicit
"match the channel's own cross-section, not the removed part's silhouette" line to the erase
prompt; the second pass was clean. Lesson for anyone extending `erase_model()`: brightness-only
verification is not shape verification — LOOK at the crop, don't just trust the re-detect call.

**`extract12.py`'s `baked-thumb:seek` gate landed mid-session** (another concurrent lane) —
exactly the gate reason this task was told to coordinate through. Confirmed as the authoritative
check: re-ran `extract12.py` on all 4 erased skins post-fix and all 4 now read `baked-thumb`
`ok` (the only remaining `regions.json` gate FAIL reason on each is the pre-existing, unrelated
`sprite-fit:shuffle` — out of scope here). `erase12.py` does NOT import or depend on that gate
(by design, standalone tool per the task brief) but the two independently converge on the same
4 skins as fixed.

**genskin.py — `SEEK_CLAUSE_LITE` flag added, default OFF:** per the task, reduced the
two-bullet, multi-sentence seek-empty-slot hardening (one at the device level, one repeated at
the strip level, both duplicated a second time in the currently-unused `_build_json_spec_prompt`
path) to a single plain clause each, gated behind `SEEK_CLAUSE_LITE` (module-level flag near
`PROMPT_JSON_SPEC`). Verified default-OFF is byte-identical to the pre-change prompt
(`--blueprint-only` dry run, `prompt_len` unchanged at 11454 chars, both heavy-clause strings
present verbatim). NOT flipped on here — erase12.py needs a real batch's worth of validation
(beyond this one-off repair pass on 4 known-bad skins) before the trade (freed prompt budget vs.
a higher up-front bake rate that erase12.py must now always catch) is worth taking live.

**orchestrate12.py hook — NOT applied by me** (another lane owns that file this session; patch
snippet only). Insert right after the existing `gate = json.load(...)` line in the roll loop
(after the pass-2 `extract12.py` call, before `history.append(...)`):
```python
    if any(rr.startswith("baked-thumb:") for rr in gate.get("reasons", [])):
        run(["python3", "erase12.py", ASSETS])           # idempotent; no-ops if already clean
        run(["python3", "extract12.py", ASSETS])          # refresh the gate post-erase
        gate = json.load(open(os.path.join(ASSETS, "regions.json"))).get("gate", {})
```
`erase12.py` auto-detects the slider-role control from `regions.json` when called bare (no
`--control` needed — this roster has exactly one slider, `seek`); `--method` defaults to `auto`
(classical first, model-edit fallback, both proven live above). Idempotent by re-detection: a
second call on an already-clean groove is a fast no-op (see `erase12.py`'s module docstring).

**Housekeeping:** `assets-<skin>/erase-verify/` (before/after crops, 4x upscaled) and
`erase12-log.json` (per-erase provenance: method, before/after sha, bbox) are written per-run
but left **untracked** — consistent with this repo's existing convention for debug/verify
output (`observe/`, `director-review.json` are similarly untracked elsewhere in the roster).
Only `paint.png` + `regions.json` (both already git-tracked) were committed for the 4 fixed
skins.

**Visual proof page (added 2026-07-12):** [`erase-proof.html`](erase-proof.html) — real
before/after crops from the untracked `erase-verify/` dirs above for all 4 fixed skins, the
classical-inpaint X-smear exhibit, the n64-cutscene shape-bug story, and the disputed
claymation false positive, in the `imgjson/explain.html` register.

---
## Verification recalibration: review round used as an eval set — DONE 2026-07-11 (~$1.4)

The review round (`review-2026-07-11-round1.json`, 0/15 PASS) exposed that `observe12.py` +
`director_review.py` had mostly PASSed skins the human failed — the user: *"what the fuck is
this orientation? how did this get past the vlm gate?"* (`n64-prerender-character`). Coded the
human's notes into a fixed 10-class defect taxonomy (`human_defects.json`), scored the
verification stack's existing outputs against it (`score_verification.py`) — **baseline
either-recall 25.7% (9/35 human-flagged defects), with sprite-slot-mismatch and
silhouette-mismatch at literal 0%** — then rewrote both scripts' prompts/schemas to explicitly
interrogate each class per control (a fixed checklist + forced tag output for observe12; a
`defects`/`orientation_ok`/`device_defects` schema addition + hard verdict-gate rule for
director_review, enforced both in-prompt and server-side). Re-ran all 15 fresh:
**recalibrated either-recall 54.3% (19/35)**, and `n64-prerender-character` — the skin that
triggered this — now correctly flags `orientation` on both passes. sprite-slot-mismatch (8
instances, the most-flagged class) and silhouette-mismatch (5) stayed at 0% despite explicit
interrogation — inspected directly, this is a genuine VLM proportion/shape-judgment weakness
(consistent with this repo's own `ai-image-coords-rule` #2 finding), not a prompt-wording gap;
specced (not built) a deterministic geometric follow-up for `extract12.py`'s owner. Also caught
and fixed a pre-existing `AttributeError` crash in both scripts on a `null` region entry
(`n64-prerender-character`'s undetected `repeat` control). Full method, per-defect table, and
the concurrent-regeneration confound check (7/15 skins' `paint.png` no longer matches the
human-reviewed `paint_sha` — other agents re-rolling live in this shared checkout; a
paint_sha-matched 8-skin subset shows the same +44pp effect, ruling out the confound as the
driver): `docs/experiments/2026-07-11-verification-recalibration.md`.
**Not done here**: fixing the generator itself (why skins have baked thumbs / mis-scaled
switches) — out of scope, owned by `genskin.py`/`extract12.py`/`build_player.py`.

---
## User-loved generation identified: wc-goldshield jsonspec CONTROL-121 (2026-07-11, human-labeled gold)

Swept every `wc-goldshield` `paint.png` on disk (prod, `abshape` a/b, `twoimg`
neutral/control/treat, `jsonspec` control/treat, `driftbisect` a/b/c — 21 candidates) against
the user's description (lion-head crest + gauntlet claw are the giveaways). Exactly one match:
[`jsonspec/assets-jsonspec-wc-goldshield-control-121/paint.png`](jsonspec/assets-jsonspec-wc-goldshield-control-121/paint.png)
— sculpted gold lion-head on the upper-left edge, silver gauntlet claw gripping the right
screen edge, rune borders + blue gems, 5 round buttons w/ 2 clean empty sockets, knob+rune-
cylinder+2 cross-clasp-toggle sprite strip.

Full provenance + config-delta writeup: [`jsonspec/LOVED-wc-goldshield-control-121.md`](jsonspec/LOVED-wc-goldshield-control-121.md).
Short version: **jsonspec CONTROL arm** (verbatim production prompt, not a treatment), seed
**121**, `fal-ai/gemini-3-pro-image-preview/edit`, `blueprint_arm="solid"` (abshape-verdict
winner). Shipped production is seed **736** — same prompt content. Conclusion: this is
**seed variance**, not a prompt win to port forward; re-roll more seeds for "more like this"
rather than editing the prompt. Automated gate currently FAILs it (`emptiness` reason,
14.45% queue bleed ring) — noted for honesty, doesn't change the human aesthetic verdict.

Copied to `~/Desktop/cc-skeuo/2026-07-11-loved-goldshield-control-121.png` (+ `.txt`
provenance sidecar) for the user's keeping.

---
## Artdrift FIX: vpod art/viz gap widened + relative-position clause — DONE 2026-07-11 (~$0.75)

The one fix the artdrift triage prescribed (entry below, commit `c237f743`), applied to the
shared pipeline per fix-generalizable-rule:

- **`genskin.py` `_vpod`:** album_art/visualizer y-centres 0.15/0.335 → **0.13/0.36** — the
  near-hairline ~2.7%-of-DEV_H gap between the two near-identical dark-glass rects (the
  diagnosed cause: no visual cue to keep them stacked; 14/32 gens re-arranged them) widens to
  ~7.2%, with >2.5% margin above album_art and >2.9% before the seek groove. `_hcapsule`
  checked and left alone (its pair already sits ~12.6% apart). Both blueprints verified by eye
  via `--blueprint-only` renders — clean separation, no overlap. Corner-radius differentiation
  considered and skipped: the rects share template constants (ART_*/VIZ_*) with the mask-blob
  tracing clause; not worth fighting that contract for a second cue.
- **Prompt (one clause, both prose + jsonspec encodings), bproof lesson — light:** appended to
  the existing blank-screens bullet: *"The album-art window sits ABOVE the visualizer window,
  clearly separated — never side-by-side, never swapped."* genskin previously had ZERO
  relative-position language for the pair. No flag — corrects a diagnosed defect.

**Validation (3 gens, the 3 drift-fail themes, fresh seeds, full pipeline; note: the
orchestrate12 wrappers were killed mid-run by the harness after genskin — extract/biref/
extract/player were resumed manually, orch.json synthesized from the roll's real gate;
director_review was NOT run on these rolls):**

| skin (seed) | arrangement (analyze_artdrift classifier) | album_art drift | drift gate | overall gate |
|---|---|---|---|---|
| fallout-pipboy (951) | **SWAPPED** (viz above art per mask identity; pair also relocated right) | 1807.8px | FAIL mean 925.7px | FAIL `drift:album_art` |
| steam-porthole (952) | **STACKED-CORRECT** (whole layout shifted down uniformly, both @ 90.8°) | 541.6px | ok mean 540.8px (worst queue 753.7px) | FAIL `emptiness` (unrelated) |
| wmp-quicksilver (953) | **STACKED-CORRECT** | **194.2px** (was 1763.4px) | FAIL mean 934.4px (worst playpause 1609.0px) | FAIL `emptiness`, `drift:playpause` |

**Honest read (n=3 smoke test, not proof):** 2/3 stacked correctly; wmp-quicksilver's
album_art collapsed 1763→194px and steam-porthole cleared the 650px album_art gate (858 mean
pre-fix → 540.8) — but fallout-pipboy re-rolled into a swap again (its two CRT windows are
visually identical; identity comes from the mask column), so the clause+gap did NOT eliminate
the failure mode. Consistent with the triage's prior (~60-70% good-roll rate pre-fix): this
n cannot distinguish "improved rate" from luck. The two new gate-fails are OTHER defect
classes (emptiness; playpause drift on wmp) — pre-existing, not introduced by this change.

---
## Template-drift GATE: drift measured + surfaced per roll instead of cause-hunted — DONE 2026-07-11

Actionable conclusion of the drift-suspect bisect chain (root `TODO.md` "drift-suspect bisect
chain — CLOSED", commit `448d8f87`): three bisects (clause `218224f7`, extraction `892bf045`,
serving `448d8f87`) all exonerated their suspect and converged on "spend on a drift-gated
re-roll loop... which pays regardless of cause" instead of continuing to cause-hunt. This adds
the gate half of that (surfacing only — auto-reroll stays OFF by default, generation-spend-rule).

- **`extract12.py`, templated mode only:** per-control drift (px, on the skin's own paint.png
  grid) = distance between the blueprint-declared `template` centre and the detected
  `regions.<k>.device` centre. Ported VERBATIM from `twoimg/roster_audit.py`'s `drift_table()`
  (the exact metric all three bisects used) as a local `_drift_table()` — not reimplemented,
  not reforked; cross-checked bit-for-bit against `roster_audit.drift_table` on all 6 templated
  skins (all 6 means match to 0.1px). Controls that fell back to the raw template position
  (`fromTemplate`) are excluded from mean/worst — the same correction `driftbisect2/README.md`
  had to apply after finding fallback controls trivially read ~0px drift and deflated the mean.
  Writes a top-level `regions.json["drift"] = {per_control, excluded_fallback, mean_px, worst:
  [name,px], threshold_px}`, and a `gate.reasons` entry `drift:<worst-control>` (which also
  gates `PASS`, same as every other reason in this gate) when `mean_px` exceeds the threshold.
- **THRESHOLD = 650px**, calibrated against the live roster + the bisects' own 150px noise
  floor: today's healthy templated skins read 415–542px mean drift (fa-pod 502.9, ps1-crunchy
  415.4, wc-goldshield 461.6, and — pre-regression — wmp-quicksilver at its roster-audit-time
  542.2); the bisect chain's own worst regressors read 858–950px (fallout-pipboy 950.5,
  steam-porthole 858.3). 650px sits ~110px above the healthy ceiling and ~210px below the
  weakest regressor, outside the 150px floor on both sides, so a single session's per-gen
  variance (330–420px, per `servingbisect/README.md`) shouldn't flip a healthy skin to FAIL or
  a regressor to PASS on its own. Full rationale in `extract12.py`'s `DRIFT_THRESH_PX` comment.
- **`build_dashboard.py`:** one surface addition — each templated card's mono run-id line now
  shows `drift <mean>px (worst <control> <px>px)`, styled red (`.driftfail`) when over threshold.

**Validated $0 across all 6 templated-mode skins** (re-extracted from existing paint/mask/biref,
no new generations): fa-pod 502.9px PASS, ps1-crunchy 415.4px PASS, wc-goldshield 461.6px PASS
(all 3 match the roster audit exactly) — confirms the threshold correctly separates the
calibration set's healthy range. **fallout-pipboy 950.5px FAIL and steam-porthole 858.3px FAIL**
also match the roster audit exactly — the gate correctly flags both of the bisect chain's named
regressors. Gate-reason diff before/after on all 15 skins: the **only** new reasons anywhere in
the roster are the 3 `drift:album_art` entries above — zero regressions on any other gate
(emptiness/missing/seek-cov/state-align/biref-parts/leak/guide-ring/region-degenerate all
byte-identical); the 9 templateless skins are untouched (no `template` to drift against, skipped
by construction) and their `regions.json` files are byte-for-byte unchanged.

**Surprise: wmp-quicksilver now reads 1112.8px mean drift (worst album_art 1763.4px) and FAILs**
— substantially worse than its roster-audit-time value (542.2px, healthy). It was re-rolled
(commit `8c97ef9a`) to fix a guide-ring contamination defect *after* the roster audit snapshot
was taken; nobody was checking drift on that re-roll because this gate didn't exist yet.
Inspected directly: its `album_art` template centre is `(0.28, 0.225)` (left column) but the
detected device sits near `(0.70, 0.62)` (opposite quadrant) — a real, large layout departure,
not a metric artifact. This is exactly the failure mode the gate exists to catch: **roster-wide
auto-PASS count under the live `regions.json` gate drops from 13/15 to 10/15** (fallout-pipboy,
steam-porthole, wmp-quicksilver newly FAIL on drift; n64-prerender-character and ps1-wild were
already FAIL on unrelated defects). None of these 3 are re-rolled here — auto-reroll is OFF by
default; they now surface on the dashboard for human triage, per the task.

**Known dashboard staleness, not fixed here (pre-existing, out of scope for "one surface
addition"):** `build_dashboard.py`'s big auto PASS/FAIL badge and the top `npass` count prefer
`orch.json`'s CACHED `"passed"`/reasons over the live `regions.json` gate when `orch.json`
exists (`s["passed"] = orch.get("passed", gate.get("PASS"))`) — this predates the drift gate and
affects every gate reason, not just drift. Result: the dashboard header still reads "auto 13/15"
and the 3 drift-failing cards still show a green "auto PASS" badge, even though their run-id
line now shows a red drift-FAIL and the summary table's "auto-fail reasons" column correctly
lists `drift:album_art` (that column already falls through to the live gate). `orch.json` only
refreshes on a real orchestrate12.py roll — regenerating it here would mean burning a re-roll
just to update a cached label, which contradicts "surface, don't burn rolls." Flagged for
whoever owns `orch.json`/badge-precedence next, not resolved in this pass.

### Review-round triage: album_art drift-gate fails — analyzed, NOT random — DONE 2026-07-11 ($0)

Pre-review triage question: all 3 drift-gate fails (fallout-pipboy, steam-porthole,
wmp-quicksilver) share album_art as worst control. Systematic layout weakness, or random
variance? Full analysis (labeled crop overlays, per-gen drift vectors, hypothesis tests):
`artdrift.html` + `analyze_artdrift.py` + `gen_artdrift_crops.py` (new, this pass; see
`artdrift_data.json` for the raw per-gen table). $0 — read-only over existing paint/mask/
regions.json across the 6 mainline templated skins + 26 driftbisect/driftbisect2/servingbisect
experiment gens (32 templated data points total).

**Finding: systematic template weakness, expressed probabilistically — not random, not a
clean identity-swap.** The template puts album_art directly above visualizer with a near-
hairline gap (~2% of frame height in the vpod archetype; both are "dark recessed glass, no
coloured frame" — visually near-identical). The model has its own strong compositional prior
for this paired "twin display" element and reinterprets it as **side-by-side** (9/32 gens) or
**vertical-order-reversed** (5/32 gens) rather than obeying the template's specific stacked
position — confirmed both by the drift-vector table AND by directly opening the paint.png crops
(steam-porthole and fa-pod both show a literal side-by-side glass-window pair; fallout-pipboy
shows the pair in reversed vertical order). This happens even in PASSING gens (fa-pod's mainline
roll is a clean side-by-side pair that just stays under the 650px gate) — the 3 gate-FAILS are
the tail of a continuous distribution, not a distinct failure mode. Re-rolling a failing skin has
a real ~60-70% chance of landing on a correctly-stacked roll (servingbisect fresh re-rolls of
fallout-pipboy/steam-porthole: 5/8 stack correctly) but doesn't fix the underlying ~30-45%
miss rate for the next skin/seed.

**Hypotheses tested and refuted:** (a) clean art↔visualizer identity swap — refuted (visualizer
is never detected closer to album_art's template slot; it's a one-sided pull on album_art, not
a mutual swap). (b) model promotes album_art to a hero position — refuted (album_art moves DOWN
and away from its already-top template slot, not toward more prominence). (c) mask-vs-refit
pipeline bug — refuted; the independent BiRefNet-adjacent mask.png blob centroid agrees with
extract12's `regions.device` refit centre within ~10-20px wherever a blob was isolable, both
disagreeing with the template by hundreds/thousands of px in the same direction. Confirms
(again) **paint-driven, not detector-driven**, consistent with the prior bisect chain
(`892bf045`, `448d8f87`).

**The one fix (not applied here — analysis only, per task scope):** redesign the
album_art/visualizer sub-layout in `genskin.py`'s `_vpod`/`_hcapsule` LAYOUTS —
(1) widen the template gap between the two windows substantially (vpod's is currently ~2% of
frame height, effectively touching), and (2) add an explicit relative-position prompt clause
("album_art sits DIRECTLY ABOVE visualizer with a clear gap — never side-by-side, never
reversed") — `genskin.py` currently has ZERO ABOVE/BELOW/stacked language for this pair, relying
entirely on the guide blueprint's geometry, which the model treats as a loose suggestion here.
Per fix-generalizable-rule this belongs in the shared layout/prompt, not a per-skin patch.

## Freeze-on-PASS: paid baselines snapshotted the moment they first gate-PASS — DONE 2026-07-11

Guardrail closing the gap the drift bisect exposed (`892bf045`): every June baseline paint
was re-rolled before ever being preserved — the bytes are unrecoverable, which blocked a $0
re-extraction experiment and violates the spirit of generation-spend + empirical-testing
rules. New `freeze_baseline.py <assets-dir>`, called by `orchestrate12.py` inside the gate-PASS
branch behind `FREEZE_ON_PASS = True`:

- Uploads the one paid artifact that is NOT git-tracked per current media policy —
  `joint-4k.png` — to `gdrive:skeuo-ui/gen12-media/frozen/<skin>/<seed>-<date>/` via
  `rclone copy --checksum`, and appends a row (repo path, Drive path + share link, sha256,
  bytes, seed, gate-pass date) to `media-manifest.json` + a "Frozen baselines" section in
  `MEDIA-MANIFEST.md`. `paint.png`/`mask.png` are git-tracked (verified `git ls-files`), so
  git is their freeze — no redundant second copy.
- **Idempotent by sha256**, scoped to `kind=="frozen-baseline"` rows only — deliberately does
  NOT dedup against the earlier bulk-offload rows (first run surfaced this: every roster
  joint-4k already had a bulk row, which would have made freeze-on-pass a permanent no-op).
- **Never blocks a run:** any rclone failure (offline/missing/expired auth) logs loudly and
  exits 0, manifests untouched.
- Seed read from `results.json` (rewritten every roll, always matches the bytes on disk),
  NOT `orch.json` (only written after the loop — stale mid-loop). Gate-pass date from
  `regions.json` mtime (the file carrying the PASS verdict).

Verified live on `assets-fallout-vault` (seed 649): run 1 uploaded 16,403,300 bytes
(~2m50s), `rclone check --checksum` = 1 matching / 0 differences, both manifest rows
appended; run 2 skipped by sha, zero new rows; rclone-missing failure path (steam-porthole,
stripped PATH) logged loudly, exit 0, manifests byte-identical.

## Guide-ring residue + sprite key-echo + degenerate-region GATES; director review mainlined — DONE 2026-07-11

Followed the diablo-gothic director-review catch (neon guide-hue borders around every control
that the geometry/emptiness gate missed entirely). Three new deterministic checks in
`extract12.py`, all folded into `gate.reasons`/`gate.PASS` so `orchestrate12.py`'s roll loop
re-rolls on them:

1. **Guide-ring gate** (`guide-ring:<control>`): perimeter-band guide-hue scan around every
   control's device bbox — ported from `twoimg/score_twoimg.py`'s `bleed_ring_pct` (the
   experiment that established the shared leak gate under-counts thin ring residue). Two
   false-positive guards, both roster-calibrated: (a) hue must ALSO be an outlier vs the
   surrounding-chassis CONTEXT ring further out (kills the brass-bezel-vs-yellow-key trap:
   steam-porthole visualizer, myst-arcanum album_art), plus an angular arc-coherence floor
   (hits must wrap the control, not cluster in one specular); (b) **palette guard** — hits
   within hue-tol of the theme's own saturated `results.json palette` colours are THEMATIC
   (claymation's terracotta/teal clay, ps1-wild's magenta/toxic-green outlines), not residue.
2. **Sprite key-echo scan** (`guide-ring:sprite:<part>`): same defect family on the biref-cut
   moving parts — a part whose visible pixels are dominated by its OWN guide-key hue
   (wmp-vario's salmon-pink seek thumb on an all-silver theme, 99.9% own-key match; verified
   genuine against joint-4k.png's staged part swatch). Same palette guard. Threshold 40%
   (genuine leaks measured 59-100%, clean parts 0-19%).
3. **Degenerate-region gate** (`region-degenerate:<name>`): a detected region whose AREA
   collapsed below plausibility — the burn: claymation shipped a ~143x188px album_art sliver
   (0.42% of the device column) that passed every numeric gate. Templated: <25% of the
   blueprint-declared `<k>_rect` area. Templateless: <1.0% of devFrac (roster-calibrated:
   healthy regions 1.79-13.86%).

`DIRECTOR_REVIEW_ENABLED=True` mainlined in `orchestrate12.py` (proven by the diablo catch);
`build_dashboard.py` now surfaces each skin's `director-review.json` verdict/score/notes on
its card and folds the ~$0.02-0.05/skin director cost into the cost line.

Roster sweep with final gates (before re-rolls): 8/15 PASS; contaminated = diablo-gothic
(6 ring controls), n64-prerender-character (4 rings + 4 key-echo sprites), wmp-quicksilver
(seek rim), wmp-vario (seek thumb), claymation (degenerate album_art); honest fails fa-sky
(emptiness), ps1-wild (emptiness+misplaced+state-align+2 rings). All 7 re-rolled via
`orchestrate12.py <spec> 3`.

**Re-roll outcomes (15 real generations, ≈$3.9 incl. director reviews):** diablo-gothic
PASS roll 1 (director 8.5/10, was FAIL 4/10 — tarnished-iron rims + ember icons, zero neon,
crop-verified), wmp-quicksilver PASS roll 1 (8.5/10), claymation PASS roll 3 (9/10;
album_art now 744x860px vs the old sliver — and the degenerate gate live-caught a
degenerate visualizer on its roll 1, proving the gate in the loop), fa-sky PASS roll 3
(9/10, its long-standing emptiness fail cleared), wmp-vario PASS (graphite+electric-blue
thumb, crop-verified). **Still honest FAILs after 3 real rolls each:**
n64-prerender-character (sprite:vol key-echo + misplaced visualizer + missing repeat) and
ps1-wild (emptiness + misplaced/degenerate visualizer + rings) — both surfaced on the
dashboard for human triage; these two themes look structurally hard for the current prompt.
Roster now **13/15 auto-PASS under the hardened gates.** Side fix shipped:
`genskin.py edit_vertex` gained the 429 retry `edit_vertex_multi` already had (a Vertex
quota blip burned 12 orchestrator rolls with zero real generations before the fix;
3-way-parallel orchestration exceeds the quota — run re-roll batches sequentially).

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
  **RUN 2026-07-11** (`driftbisect/`, 12 gens ≈ $2.88, wc-goldshield + fa-pod × 2 seeds ×
  3 arms, conditioning forced solid): **clause NOT confirmed as the drift driver — no
  prompt change ships.** B (clause removed) was MIXED (fa-pod +230px better, wc −252px
  worse, consistent across seeds); C (clause + numeric 2%-centre lock) was worse than
  production on both themes. Neither cleared the 150px noise floor on both themes. Full
  record: [`docs/experiments/2026-07-11-drift-clause-bisect.md`](../../../docs/experiments/2026-07-11-drift-clause-bisect.md)
  + `driftbisect/results.html`. Fall-through next steps ($0-first): re-run CURRENT
  extract12 on the ORIGINAL `794da20e` baseline paints to bisect the extraction commits
  (`ac28cd74`/`86f69c75`/`a8bbaad0`); then repeat on the true regressors
  (fallout-pipboy/steam-porthole) if extraction is clean.

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

- **SECOND USER OVERRULE + re-verification, same day (2026-07-11):** the round-1 fix
  above was overruled with visual evidence — steam-porthole's stored `knob_zero_deg=85.59°`,
  "the annotation arrow hits the pointer notch's UPPER EDGE — the mark's visual center is
  ~6-9° further clockwise." Root cause: the detector locates a notch by its
  gradient-magnitude PEAK, which sits at the notch's sharpest EDGE, not its visual
  CENTER — round 1's parabolic sub-bin refinement only sharpened that SAME wrong target
  (interpolating the 3 bins around the peak edge), it never moved onto the run's true
  center. A triangular/wedge notch has TWO gradient edges (leading + trailing); the
  center lies between them. AND the render-side "closed loop" shared the exact same
  detector on both ends (extraction sets `knob_zero_deg`; the render check re-measures
  with the same algorithm), so the edge-bias cancelled between the two sides and the
  loop reported ≤1° error while a human eye saw the mark visibly off — circular
  validation (`verify-rule` §2).
  - **Fix:** `knob_angle.py:_run_centroid_deg()` — after finding the peak (unchanged
    gating), walks outward while the profile stays above a fraction of the peak's
    height over background (30% default) to find the FULL contiguous anomalous run,
    then returns that run's intensity-weighted circular-mean centroid. Guards against
    the run escaping into background noise (measured on fallout-vault's rust texture:
    an early z-score-relative run threshold ballooned to 46° of noise and produced a
    wrong 340° reading; switched to thresholding the run on the PROFILE VALUE itself
    — tied to the actual anomaly shape, not the noise floor — and capped by the same
    `max_width_deg` ceiling; a run that still escapes is REJECTED (`None`), never
    guessed). steam-porthole shifted +4.77° (85.59°→90.36°, its widest run in the
    batch, 16-18°, exactly the shape most punished by edge-bias); narrow-run skins
    (fa-pod, myst-arcanum) barely moved (<0.1-0.5°), as expected when peak≈centroid.
  - **Circularity broken:** added `knob_angle.py:texture_disruption_angle()` — an
    INDEPENDENT second signal binning LOCAL PIXEL-VALUE VARIANCE per angle (a carved
    notch disrupts the smooth radial-brush texture regardless of whether it reads
    darker or brighter) instead of gradient magnitude. Different physical channel,
    different code, doesn't share the gradient detector's edge-bias. (An earlier
    attempt at this independent signal — mean INVERTED luminance, "a notch is a dark
    depression" — measured too weak on real renders, peak prominence 0.7-1.9 across
    5/6 skins, and was replaced; the outline stroke is thin and a whole-ring mean
    dilutes it, while local variance catches the same disruption regardless of
    polarity.)
  - **Honest result:** only 2/6 skins (steam-porthole, n64-cutscene) get both signals
    to agree within 1° and both clear the ≤3° bar. The other 4 (ps1-crunchy,
    myst-arcanum, fallout-vault, fa-pod) have at least one signal reading well under
    2° (usually gradient) while the OTHER reads 4-6° due to material-specific noise
    (rust texture, chrome specular sheen, a V-notch's asymmetric walls, deliberately
    dithered texture) — disclosed per-skin, not hidden behind a passing aggregate.
    **Direct visual inspection of the real rendered pixels confirms all 6 are
    genuinely centered at 12 o'clock** (`knobzero-proof/visual_spotcheck.json`); the
    per-skin signal noise is a detector-calibration limitation on those specific
    materials, not a placement defect. Full writeup + numbers:
    [`docs/experiments/2026-07-11-knob-zero-closed-loop.md`](../../../docs/experiments/2026-07-11-knob-zero-closed-loop.md)
    (round-2 addendum), results page `knobzero-proof.html` (regenerated by
    `knobzero-proof/gen_proof.py` from stored `regions.json` + `verify_knob.py` +
    `visual_spotcheck.json` — never re-derives). myst-arcanum's two-mark ambiguity is
    still unresolved and still pending human call.

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

## Extraction-commit drift bisect DONE (2026-07-11, $0) — PAINT-DRIVEN, detector exonerated

Fall-through from the drift-clause bisect. Original plan (rerun current `extract12.py` against
the ORIGINAL `794da20e` baseline paints) was **impossible** — every templated-passing skin's
baseline paint was rerolled to a new seed before ever being git-committed; confirmed gone from
git history, Drive, `bproof/gen12ref`, and `entire`'s local checkpoints (transcripts only, no
file snapshots). Ran the paint-fixed / extractor-swapped substitute instead: same current paint,
both the `794da20e` and current (origin/main) `extract12.py` versions. **Verdict: real paint
drift, not a detector regression** — extractor-swap Δ stayed inside the 150px noise floor on all
3 skins (fallout-pipboy −66px, steam-porthole −10px, fa-pod +6px) while the paint-only Δ (same
old extractor, baseline vs today's paint) was 3.5–6× the floor (+874px, +345px, −105px for the
known improver). Full readout: [`driftbisect2/README.md`](driftbisect2/README.md) +
`driftbisect2/results.json`; doc: `docs/experiments/2026-07-11-drift-clause-bisect.md`
"Follow-up" section.

**Follow-up implied, not yet done:**
1. **Root cause is still open** — the clause bisect ruled out BOLD-silhouette specifically; this
   bisect ruled out extract12.py; remaining suspects for why generations are drifting further
   from their template layout over the Jul 8→11 window: Vertex-vs-fal serving switch, seed
   range, or accumulated unrelated `genskin.py` prompt edits across that window. Needs its own
   bisect if drift is worth chasing further (vs. accepting current drift and tightening the
   region-misplaced gate instead, which already exists and already catches the worst cases).
2. **Guardrail gap (real, found as a side effect, not a drift cause):** paid Vertex outputs stay
   gitignored until manually `git add`-ed, so a re-roll can silently overwrite the only copy of
   an expensive generation with no way back — this is what made the ORIGINAL bisect plan
   impossible. Freeze-on-first-gate-pass (auto-commit `paint.png`/`mask.png` the moment
   `gate.PASS` flips true, before any further reroll can touch them) closes this for good.

## Visual explainers — jsonspec paint verdict + media-tier proof (2026-07-11)

Two guided-tour pages in the register of `imgjson/explain.html` (real artifacts, plain-language
readings, computed-not-hand-typed numbers, bottom conclusion):

- [`jsonspec/explain.html`](jsonspec/explain.html) — "did fenced-JSON prompts help the paint?"
  Real prose-vs-fenced-JSON prompt excerpts (CONTROL roster_desc reconstructed from stored
  `keyNames` + `genskin.py`'s static `ICON` dict; TREATMENT block pulled verbatim from a stored
  `results.json.prompt`), per-pair paint thumbnails (4 pairs) with bleed/drift annotated,
  `PROMPT_JSON_SPEC` flag state (`genskin.py:80`, default `False`), the bonus box-convention
  probe in brief with a pointer to `imgjson/explain.html#round2`, bottom verdict (neutral on
  drift, mildly helpful on bleed — matches `verdict.json`).
- [`MEDIA-EXPLAIN.html`](MEDIA-EXPLAIN.html) — where gen12 media lives + proof it's safe. Three
  tiers visualized (211 files / 454.6MB git-tracked runtime; 36 files / 358.5MB Drive-offloaded
  bulk; 1 file / 15.6MB frozen baseline so far) computed from `git ls-files` +
  `media-manifest.json`, the 36/36 `rclone check` evidence quoted verbatim, every offloaded
  file's clickable Drive link in a table, an inline-SVG freeze-on-pass flow diagram, and the
  ~699MB pushed-pack history-reclaim item stated plainly as open + user-gated.

Small link-backs added: `jsonspec/results.html` header now points to `explain.html`;
`MEDIA-MANIFEST.md` header now points to `MEDIA-EXPLAIN.html`.

## Scripted JS-state probe (`probe12.py`) — the deterministic follow-up spec, built (2026-07-12)

Built the "Residual gaps" follow-up spec from `docs/experiments/2026-07-11-verification-
recalibration.md`: vision (observe12.py's VLM pass) cannot reliably tell a DEAD control from a
merely-static one — two screenshots are the wrong evidence for an interaction-testing
question. New files: `probe12.py` (Python orchestrator) + `probe_drive.mjs` (the actual
Playwright driver — own throwaway `chromium.launch()`, no shared profile/context with
`observe_drive.mjs` or anything else). `$0`, ~7s/skin, fully deterministic.

**Design, per control:**
- **Buttons** (playpause/prev/next/repeat/queue): a REAL `page.mouse.click()` at the
  control's own `getBoundingClientRect()` center — deliberately NOT `el.click()` (which
  `observe_drive.mjs` uses on purpose, for a different reason: dodging overlap flakiness to
  get a clean screenshot pair). A real hit-tested click is the whole point here — it's what
  catches a HITBOX/z-order defect (a sibling control silently swallowing the click), which
  `el.click()` cannot see by construction. `document.elementFromPoint()` at the click point
  is checked before clicking, so an occlusion produces a specific, named diagnosis ("point
  resolved to `next`, not `prev`") instead of a bare "nothing happened." Per-key expected
  state: `hint.textContent` for the generic buttons (`"<key> ▸"`, exact match against the
  shipped handler in `build_player.py`), `#queue`'s `open` class for `queue`, `dataset.m` +
  hint text for `repeat`.
- **Toggle (shuffle):** a generic style diff (`backgroundImage`/`left`/`top`/`transform`),
  intentionally mode-agnostic rather than branching on a `regions.json` field — checked: no
  skin's toggle region carries anything beyond `device`/`angle`/`stateAlign` today, so the
  "two-detent slider" mode the spec asks to "detect" doesn't exist yet to detect. The
  generic diff is correct for either representation without modification if/when that mode
  ships; the selector also probes for a `.pthumb[data-role="toggle"]` shape defensively.
- **Knob (vol):** drag test (same pointer sequence as `observe_drive.mjs`'s knob-drag),
  asserts the cap's `rotate(...)` transform actually changed.
- **Slider (seek):** value change AND clamp at BOTH ends — drag past max twice (2nd
  overshoot landing on the exact same position as the 1st IS the clamp proof), then past min
  twice, no `regions.json` travel-math replication needed (reads the live element's own
  rendered position after each drag).
- **Visualizer:** 600ms canvas pixel-activity sample in idle state (baseline) vs. 600ms
  after clicking playpause (playing state) — requires BOTH an absolute floor (4000) AND
  >2.5x the skin's own idle baseline, because idle already wobbles gently by design (the
  ps1-crunchy fix, commit `e2473221`) so a bare non-zero diff proves nothing.

**Self-test (mechanism verification, not just code review):** before trusting a clean "ALL
ALIVE" result, wrote a throwaway `/tmp` script (not committed) that force-overlapped
fallout-vault's live `prev`/`next` buttons via DOM mutation and re-ran the exact
`elementFromPoint` + click logic inline — confirmed it correctly reports `occluded: true`,
`occluderTitle: "next"`, and that the resulting click actually fires `next`'s handler
(`hint -> "next ▸"` instead of the expected `"prev ▸"`), i.e. the technique **can** fail a
control, not just always report alive.

**`observe12.py` hook (small, composable):** if `<assets>/observe/probe.json` exists, its
`dead_controls` are folded into `per_control_defects[k] += ["dead-control"]` and force
`verdict = "FAIL"` — belt-and-suspenders, same posture as `director_review.py`'s own hard
verdict-gate rule. `probe12.py` is never invoked from `observe12.py` (kept composable, per
task scope); the merge is a no-op if `probe.json` doesn't exist. `score_verification.py`
needs no change — it substring-matches the whole `observe.json` blob, and now finds the
literal `"dead-control"` tag automatically. **Verified live against the real shipping code
path** (not just read): ran `python3 observe12.py assets-ps1-wild --vlm` for real (one fal
call) — printed `VLM verdict FAIL ... [probe12 dead-control override: next]`, and
`observe.json` on disk shows `per_control_defects["next"] == ["dead-control"]`. Bonus: the
VLM's OWN line for that control was `next: CROP-MISS` — i.e. the vision pass couldn't even
measure `next` (crop-anchoring miss), while the deterministic probe caught the real hitbox
defect cleanly. Concrete illustration of why this is a complementary check, not a redundant one.

**Validation (4 skins, evidence read directly, not just verdict counts):**

| skin | result | notable evidence |
|---|---|---|
| `fallout-vault` | ALL ALIVE (9/9) | `prev`/`shuffle` — the human's "failed to work" complaint — read alive on the CURRENT `regions.json`. Confirmed via `git diff` this is a real fix already landed mid-session (`prev`'s `device` rect and `shuffle`'s `sprite_fit` gate both changed in the currently-uncommitted extract12.py re-roll) — the "if fixed, vault should pass" branch, not a probe miss. Caveat: `regions.json` (00:34) was newer than `player.html` (23:57) for this skin at validation time — the probe tests the ACTUALLY SERVED artifact, which is correct per verify-outputs-rule §7, but the result may change again once `build_player.py` reruns on the newest regions. |
| `ps1-crunchy` | ALL ALIVE (9/9) | `visualizer`: idle 600ms activity ≈3.1×10⁵, playing ≈1.6×10⁷ (≈51x margin, comfortably past the 2.5x/4000 gate) — the idle-wobble fix (`e2473221`) reads correctly as "alive" post-recalibration, closing the exact miss the recalibration doc flagged as needing this probe. |
| `claymation` | ALL ALIVE (9/9) | healthy control (human's only defects — sprite-slot-mismatch, baked-thumb — are non-interaction classes; probe correctly finds nothing to flag). |
| `wc-goldshield` | ALL ALIVE (9/9) | second healthy control (human's defects — baked-thumb, sprite-slot-mismatch — likewise non-interaction). |

**Bonus real-world finding (not one of the 4 required; `probe.json` NOT committed for these,
kept unscoped from this commit):** `ps1-wild`'s `next` button came back DEAD — see the
"verified live" paragraph above for the full trace. Interesting because `ps1-wild`'s only
coded human defect is a low-confidence catch-all (`placement-wrong`, from the vague note
"absolute failure" — the recalibration doc's own caveat on this skin) — this is plausibly
PART of what the human hit and couldn't articulate more precisely. Also surfaced a genuine
shared-checkout race: `n64-prerender-character`'s `repeat` control correctly reads DEAD
(`regions.json` has it as a bare `null` — matches the pre-existing `observe12.py` comment
about this exact skin), and `myst-arcanum` failed to load entirely (`page.waitForFunction`
timeout, 0 `.pbtn` elements, a JS `pageerror`) while another agent's `extract12.py` re-roll
was actively rewriting its `regions.json` mid-request — the probe correctly failed CLOSED
(every control marked dead with an honest "page failed to load" reason) rather than silently
reporting alive. Not chased further — outside this task's ownership (extract12.py/regions.json
generation) and self-resolves once that agent's batch lands.

**Not built (explicitly out of scope per spec):** no change to `extract12.py`,
`build_player.py`, or `genskin.py` — this pass only adds an observational check, per
`fix-generalizable-rule`'s boundary (a probe finding a hitbox bug is not the same as fixing
one; that's the extract/player-owning agents' lane).

## User decisions (2026-07-12)
- **Seed-mine/rescue: DROPPED** — user: "forget seed min thing." No mining round; roster quality comes from the fix chain + re-rolls.
- **Repeat button: STAYS, director-decided** — like ticks/optional stages, the director spec decides per theme whether repeat appears. (Roster schema: repeat becomes a director-optional control — implement with the next director-responsibilities pass, cross-ref the director-gates-stages TODO.)
