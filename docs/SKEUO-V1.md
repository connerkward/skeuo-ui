# SKEUO V1 — inventory, milestones, checklist

**User's v1 definition (verbatim):** "i want the mobile app, webapp, and mac desktop widget
all updated and at feature parity (where it makes sense, obv the desktop widget wont have a
template editor) that have the newest confirmed human eye verified working pipeline."

This doc is split into two milestones per explicit user direction: **the pipeline must be
robust and human-eye-verified BEFORE roster parity / generation-port work matters.** Everything
in Milestone 2 is blocked behind Milestone 1's gate. The user does not care about roster parity
or the generation port until Milestone 1 is done — read/act on this doc in that order.

Audit method: parallel evidence-gathering agents read the actual source (`src/`, `src-tauri/`,
`tools/mask-align-exp/gen12/`), git log, and live `curl` against skeuo.fm — not memory. Findings
below cite file:line or commit SHA. Where I could not find evidence for an item named in scope
discussion, I say so explicitly rather than guessing (`verify-outputs-rule` / `verify-external-claims-rule`).

---

## MILESTONE 1 — `skeuov1-pipeline` (ACTIVE, FIRST, blocks Milestone 2)

**Goal:** make the gen12 skin-generation pipeline (`tools/mask-align-exp/gen12/`) robust enough
that a human can review the roster in the dashboard and gate every skin PASS/FAIL with
confidence the pipeline itself isn't the source of defects. **Definition of done: the human
review round in `dashboard12.html` is completed (every roster skin has a persisted verdict in
`review.json`) on the CURRENT pipeline state (post knob-zero fix).** Nothing in Milestone 2
starts until this gate passes.

### Current pipeline state (evidence, not memory)

- **Auto-gate: 13/15**, live-computed from each `assets-*/orch.json.passed`. Failing:
  `assets-fa-sky` (emptiness), `assets-ps1-wild` (region-misplaced:album_art + emptiness +
  state-align). Matches commit `92b95e17`'s "auto 13/15" (supersedes the older 12/14 figure —
  roster grew to 15).
- **Knob-zero fix: LANDED, at HEAD (`2685db4e`, 2026-07-11).** Root cause: `detect_knob_zero_deg()`
  used a 180-bin angular histogram with zero sub-bin refinement, so every stored angle was an
  exact multiple of 2° — this silently defeated an earlier VLM-witnessed "PASS" that can't judge
  single-digit angular error (see [`docs/DECISIONS.md`](DECISIONS.md), 2026-07-11 entry). Fixed
  by extracting a shared `knob_angle.py` used by both the extractor and a closed-loop Playwright
  re-verifier that measures the REAL rendered `.pknob .cap` DOM element (not a reimplementation).
  Post-fix render error 0.44°–2.32° across all 6 affected skins, all under the 3° bar. Evidence:
  [`docs/experiments/2026-07-11-knob-zero-closed-loop.md`](experiments/2026-07-11-knob-zero-closed-loop.md),
  [`tools/mask-align-exp/gen12/knob_angle.py`](../tools/mask-align-exp/gen12/knob_angle.py),
  [`tools/mask-align-exp/gen12/knobzero-proof.html`](../tools/mask-align-exp/gen12/knobzero-proof.html).
- **"Ring gate"** is not a distinct in-flight fix — `extract12.py`'s own docstring lists
  leak/emptiness/ring gates as existing, already-shipped auto-gate checks. If the ring gate needs
  further hardening, that's a fresh scope item, not something currently mid-flight; flag to user
  if more was meant by this term.
- **Baked ON/OFF toggle-text contamination — fix identified, NOT yet applied.** Dominant remaining
  paint-defect class (4 of 7 observed skins in the 2026-07-10 batch: myst-arcanum, wmp-vario,
  wmp-quicksilver, n64-prerender-character). `genskin.py`'s prompt already forbids ON/OFF text but
  the model keeps labelling the ON state. Recommended generalizable fixes (TODO.md, section 11b):
  (a) reword the SHUFFLE STATES clause to avoid the tokens ON/OFF entirely ("state A / state B");
  (b) wire `observe12.py --vlm` into `orchestrate12.py` as a flag-gated post-PASS text gate so a
  labelled toggle auto re-rolls. Needs ~2-4 validation gens (~$1) before landing — a
  `generation-spend-rule`-gated task, not free.
- **Director-gated knob ticks — rehab in progress, NOT yet implemented as designed.** User
  overruled an earlier 0/8 auto-score (the score measured the wrong thing — see TODO.md's "Knob
  tick-mark provisioning" section): re-scored 6/7 render coherent theme-appropriate ticks. Next
  steps (not yet done): (1) tick presence becomes a per-theme **director decision**, not a global
  flag; (2) reword `gen_knobticks.py`'s `tick_clause()` to drop MIN/START/MAX/END/CENTER/DETENT
  vocabulary (same negative-prompt backfire that baked ON/OFF as literal text); (3) validate the
  reworded clause (~2-4 gens, ~$1); (4) reframe `KNOB_TICKS_ENABLED` (CSS/SVG, `build_player.py`)
  as the FALLBACK when a director wants ticks but the paint roll didn't produce them, not a bare
  global flag. Currently `KNOB_TICKS_ENABLED` still ships as a bare flag, not the director-gated
  fallback design.
- **"Crop discipline" / render-and-remeasure verification protocol — established as pipeline
  practice, applies going forward.** Per the 2026-07-11 DECISIONS.md entry: placement claims at
  single-digit-degree/pixel precision require rendering the REAL shipped output, cropping the real
  DOM element, and re-measuring with the SAME detector algorithm — never a VLM alone, never a
  reimplementation. This is now the standard for any further gen12 placement work, not a discrete
  remaining task.
- **Architecture is settled, not open, for gen12 itself.** The 2026-07-11 DECISIONS.md entry
  ("gen12's heavy structural-constraint prompt STAYS the production architecture") closed the
  beauty-vs-constraint tradeoff question: gen12's ~9-11k char prompt (empty knob/seek/toggle
  cavities, blank screens, exact-fit sprite strip) costs measurable paint richness but is kept as
  the price of reliable empty sockets / runtime detectability. Not open for re-litigation without
  new evidence.
- **Human review: STALE — this is the actual gate blocking Milestone 1.** The only review record
  on disk, [`review.json`](../tools/mask-align-exp/gen12/review.json) (identical to
  `review-2026-07-09.json`), is a **0/15 all-fail round dated 2026-07-09** — it predates knob-zero,
  tick provisioning, and the crop-discipline protocol, so it does not reflect current pipeline
  state. A review server is running (`review_server.py`, confirmed listening on `:54731`) and an
  untracked `.review-url` file points at a fresh dashboard session, but **no new verdicts have been
  saved.** No skin can currently be called human-eye-verified.

### Milestone 1 checklist

| # | Item | Size | Blocking dependency | Who |
|---|---|---|---|---|
| 1 | Reword `genskin.py` SHUFFLE STATES clause to drop ON/OFF tokens; validate on 2-4 gens (~$1) | S | none | agent |
| 2 | Wire `observe12.py --vlm` into `orchestrate12.py` as a flag-gated auto re-roll gate for baked toggle text | M | item 1 landed first (same defect class) | agent |
| 3 | Reword `gen_knobticks.py` `tick_clause()` to drop MIN/START/MAX/END/CENTER/DETENT vocabulary; validate (~2-4 gens, ~$1) | S | none | agent |
| 4 | Wire tick presence as a per-theme director decision (not global flag); reframe `KNOB_TICKS_ENABLED` as the paint-miss fallback | M | item 3 validated | agent |
| 5 | Re-roll / fix the 2 auto-gate fails: `assets-fa-sky` (emptiness), `assets-ps1-wild` (region-misplaced + emptiness + state-align) | M | items 1-4 landed (avoid re-rolling into the same known defects) | agent, real $ spend |
| 6 | **Run the human review round to completion** — every roster skin gets a PASS/FAIL + notes in `dashboard12.html`, persisted to `review.json` | M | items 1-5 done (reviewing pre-fix skins wastes the round) | **user** (the actual eye) |
| 7 | Clarify "ring gate" scope if more than the existing leak/emptiness/ring auto-checks was meant | S | none — clarify in parallel | user |

**Milestone 1 gate:** item 6 passing (a real, current, non-stale review round with per-skin
verdicts) is what unblocks Milestone 2. Nothing below this line should start first.

---

## MILESTONE 2 — `skeuov1` (the release; BLOCKED on Milestone 1)

**Goal:** ship the verified roster across all three surfaces at feature parity, backed by a
versioned skin-registry so roster drops don't require app releases.

### 1. Surfaces — what exists today (evidence)

**WEBAPP (skeuo.fm)** — live, confirmed (`curl -I https://skeuo.fm` → `HTTP/2 200`, 2026-07-11).
- **Skin roster:** [`src/player/skins.ts`](../src/player/skins.ts) `skinList`, 33 static entries,
  23 `hidden:true` (donors/iterations) → **10 visible built-ins** by default (`?all` reveals all).
  Gallery also merges **cloud skins** (`GET /api/skins`, R2-backed) and **runtime-generated**
  skins (`localStorage["skeuo:skins"]`).
- **Player interactions — all working, not decorative.** Read in full from
  [`src/player/Composite.tsx`](../src/player/Composite.tsx): play/pause/prev/next/stop (real
  `onClick`), seek h/arc/path sliders (real pointer drag), volume/balance knob (real drag-rotate),
  toggle/switch (real click + sprite swap), EQ vertical sliders, segmented control, XY pad,
  playlist rows. Only `flourish` regions are genuinely static (intentionally baked decoration).
- **Create flow / pipeline** — [`src/generate/pipeline.ts`](../src/generate/pipeline.ts) (705
  lines, read in full): director → combined blueprint → **single fal paint pass**
  (`DEFAULT_MODEL = fal-ai/gemini-3.1-flash-image-preview/edit`, "nano-banana-2", $0.16/skin) →
  browser-side cutout (`/api/cutout`, server BiRefNet) → sprite cut → upload/finalize. No separate
  envelope pass (explicitly removed, comment at line 9-10). An **optional joint paint+mask mode**
  exists (two-panel canvas, mask read back via `maskAlign.ts`) — the TS port of the mask-align
  alignment work. **This is a separate, TypeScript-ported implementation from gen12** — different
  default model (webapp: Flash/"nano-banana-2"; gen12: Pro), different runtime (webapp:
  client-deferred cutout; gen12: offline batch harness with its own dashboard). They've absorbed
  some shared learnings (mask-align, coverage-span travel) but are not the same code path.
- **Template Studio** — [`src/debug/TemplateStudio.tsx`](../src/debug/TemplateStudio.tsx), reachable
  only via `?studio` **and gated `import.meta.env.DEV`** — **not present in production builds at
  all.** Real drag/resize/marquee-select (`@use-gesture/react`), undo/redo, snap-to-edges. No
  save/export/publish path found in the file. `REPACK_ENABLED=false`. Verdict: functional dev-only
  harness, not a shipped user feature — consistent with "the desktop widget won't have a template
  editor" (the webapp's version is dev-only too, at least in this build).
- **Share** — [`src/export/ShareModal.tsx`](../src/export/ShareModal.tsx): builds `/share?id=`
  (generated) or `/?skin=` (built-in) links, pre-generates PNG/GIF/Video exports of a live
  mounted `Composite`. Working.
- **PiP float** — [`src/player/useDocumentPip.ts`](../src/player/useDocumentPip.ts): full Document-PiP
  implementation, but `FLOAT_ENABLED=false` in `App.tsx:52` — code-complete, **disabled**, comment
  says the PiP window's browser-owned chrome can't be removed to match the transparent Tauri widget.
- **Spotify** — `CONNECT_ENABLED=false` in `App.tsx:54` — comment: "hidden until the playback issue
  is fixed." Gates Connect UI on **every** platform. Behind the flag: a full, non-trivial OAuth PKCE
  implementation (`src/spotify/auth.ts`, `api.ts`, `sdk.ts`, `useSpotify.ts`, ~850 lines total) —
  real code, currently gated off, not a stub.
- **Deploy** — [`wrangler.toml`](../wrangler.toml): Cloudflare Pages, R2 bucket `SKINS`, KV
  `RATELIMIT` with a documented $10 lifetime spend cap. `npm run deploy` → manual, **no CI**
  (`.github/workflows/` doesn't exist in this repo). Deploy tooling works; site confirmed live.

**MAC DESKTOP WIDGET (`src-tauri/`)** — Tauri shell, shares the webapp's player code (not forked).
- **Config:** [`src-tauri/tauri.conf.json`](../src-tauri/tauri.conf.json): 360×540 transparent
  window, `identifier: run.ward.skeuo`, `buildAndDist = ../dist` — **the same Vite build output**
  the webapp deploys, not a separate widget bundle.
- **What it renders:** [`src/widget/WidgetApp.tsx`](../src/widget/WidgetApp.tsx) imports the exact
  same `Composite` and `skinList` (33 skins) the webapp uses — no forked player logic under
  `src-tauri/`. **Drift found:** the Rust tray's hardcoded skin list in
  [`src-tauri/src/lib.rs:20-34`](../src-tauri/src/lib.rs) has only **13 of 33** current skin ids —
  the tray menu is stale relative to the live roster (a generalizable staleness bug per this
  repo's own `fix-generalizable-rule`: nothing computes the tray menu from `skinList`).
- **Interactions:** tray icon (skin submenu, always-on-top toggle, show/hide, quit), drag-to-move,
  per-pixel click-through, deep-link (`skeuo://skin/<id>`), window-state persistence,
  single-instance forwarding, close-to-tray. Spotify OAuth via a Rust loopback listener
  (`lib.rs:50-98`, port 14565) — real, functional. **No local audio engine** — always
  Spotify-driven per `WidgetApp.tsx` comment.
- **Last meaningful update: ~2026-06-17/18.** `git log -- src-tauri/` shows every commit since
  2026-06-25 is a **1-line version bump** (iOS TestFlight releases, unrelated to the widget's own
  functionality). Real functional widget work (click-through fixes, tray items) stopped
  2026-06-13 to 2026-06-18, right when effort pivoted to adding the iOS variant of this same Tauri
  shell. Meanwhile `src/` (webapp) has commits through today. **Widget is stale, not broken** — no
  build-breakage signals found (config coherent, deps pinned, no dangling file refs) but it hasn't
  tracked the roster or received attention in ~3.5 weeks.

**MOBILE — CONFIRMED: an existing native Tauri iOS app in THIS repo, shipped via TestFlight.**
(First pass under-searched; corrected on direct instruction to search harder / check the Tauri
mobile target specifically.) Evidence:
- [`src-tauri/gen/apple/skeuo.xcodeproj`](../src-tauri/gen/apple/skeuo.xcodeproj) +
  `.xcworkspace`, `Podfile`, `project.yml`, `LaunchScreen.storyboard`, `Assets.xcassets` — a real,
  generated (`tauri ios init`) Xcode project, not a stub.
- `package.json`: `"tauri:ios:dev": "tauri ios dev"`, `"tauri:ios:build": "tauri ios build"` — real
  build scripts.
- [`src-tauri/tauri.conf.json`](../src-tauri/tauri.conf.json) `plugins.deep-link.mobile` block
  registers the `skeuo://` scheme for the mobile target specifically (separate from the desktop
  block).
- `git log -- src-tauri/`: `97188ca9 "Add iOS app: full-screen skin (shares this Tauri shell)"`
  (2026-06-17), then a string of TestFlight version bumps through `0.1.8` (2026-06-25), plus prior
  commits fixing native OAuth account-chooser behavior, app icon, and `skeuo://` scheme restoration.
- Runtime: `isMobileApp()` in [`src/platform.ts`](../src/platform.ts) = `isTauri() &&
  /iPhone|iPad|iPod/.test(UA)` forces the same `MobileChrome` swipe-carriage shell the responsive
  web build uses ≤820px, but as a **full-screen native player**, not a widget — distinct code path
  from both the web mobile shell and the macOS widget (`docs/feature-parity.md`'s 4-shell table).
  OAuth uses an HTTPS→`skeuo://` deep-link bounce (loopback is unreachable once iOS suspends a
  backgrounded app — confirmed on-device, `docs/ios.md`).
- **No Android build wired** — `src-tauri/gen/` has only `apple/` + `schemas/`, no `android/`. The
  `mobile` cfg flags and deep-link entries in Rust/Tauri config are present but unused for Android.
  `docs/feature-parity.md:34-36` states this outright.
- No sibling repo exists (`ls ~/dev | grep -i -E "skeuo|player|music"` → only `skeuo-ui` and
  `skeuo-ui-jsonspec`, the latter a JSON-spec-only repo, not a mobile app). No PWA (no
  `manifest.json` with `icons`/`display`/`start_url`, no service worker, no `workbox`).
- **Conclusion: "the mobile app" = the Tauri iOS app at `src-tauri/gen/apple/`, already built,
  already shipped through TestFlight to 0.1.8.** It is not a separate project and needs no new
  scaffolding — it needs the same roster/robustness/parity work as the other two surfaces, plus
  closing its own known gaps (below).

### 2. Parity matrix

Legend: ✅ full · 🟡 partial/flagged-off · ❌ gap · — N/A by design.
Sourced from live code (`src/App.tsx`, `src/platform.ts`, `src-tauri/`) and the existing, current
[`docs/feature-parity.md`](feature-parity.md) (generated 2026-06-25, spot-checked against code
2026-07-11 by the audit above — still accurate). That doc is the deeper reference; this table is
the V1-relevant slice.

| Feature | Web | iOS (mobile app) | macOS widget | Notes |
|---|:--:|:--:|:--:|---|
| Skin roster rendering | ✅ 10 visible + cloud + runtime | ✅ same via `runtimeAsAssets`/`cloudAsAssets` | 🟡 single skin, tray list **stale** (13/33 ids) | fix tray-list generation from `skinList` |
| Button (play/pause/prev/next/stop) | ✅ | ✅ | ✅ | shared `Composite` |
| Seek (h/arc/path slider) | ✅ | ✅ | ✅ | shared |
| Volume/balance knob | ✅ | ✅ | ✅ | shared; knob-zero fix applies to gen12 output, not this runtime control |
| Toggle/switch | ✅ | ✅ | ✅ | shared |
| EQ vertical sliders | ✅ | ✅ | ✅ | shared |
| Segmented control | ✅ | ✅ | ✅ | shared |
| XY pad | ✅ | ✅ | ✅ | cosmetic under Spotify drive |
| Playlist | ✅ | ✅ | — | widget shows one skin, no playlist panel by design |
| Seek track + knob ticks + knob-zero (gen12 assets) | N/A — runtime controls, not gen12 skins | N/A | N/A | applies to the gen12 roster once ported (Milestone 2 item) |
| Director CSS colors | ✅ `componentColors` shared | ✅ | ✅ | one shared identity system |
| Skin switching | ✅ desktop rail / mobile carriage | ✅ swipe carriage | ✅ deep-link `skeuo://skin/<id>` | |
| Spotify playback binding | 🟡 `CONNECT_ENABLED=false`, real code gated off | 🟡 same flag, HTTPS bounce OAuth | 🟡 same flag, loopback OAuth | flag is global, one flip re-enables all three |
| Create flow (CreateWizard) | ✅ | ✅ | — (by design, no template editor on widget) | shared backend `/api/generate` |
| Template Studio | 🟡 dev-only (`?studio` + `DEV` gate), not in prod build | ❌ | — N/A by design | webapp's own studio isn't shipped either — re-check before calling this "webapp has it, widget doesn't" |
| Share | ✅ | ✅ native share | ✅ copy-link only | |
| PBR / emissive lighting | 🟡 built, `EMISSIVE_ENABLED=False`/`PBR_PASS_ENABLED` off | same flag | same flag | **explicitly PARKED for v2** — user verdict 2026-07-11, not v1 scope |
| Offline / asset source | R2 (canonical) + localStorage (runtime) | R2 + on-device cache (WKWebView) | R2, no local skin cache found | gdrive backup is a **secondary** portable backup, not a runtime source |

### 3. Skin-registry manifest (versioned, R2-backed) — NOT YET BUILT

User's V1 ask: "surfaces pull skins+regions+sprites, no app releases for roster drops." Currently:
- Web already does this for cloud/runtime skins (`GET /api/skins` merges R2-published skins with
  no rebuild needed — confirmed in `docs/feature-parity.md` §4.1).
- The **built-in** roster (`src/player/skins.ts` `skinList`, the gen12-verified skins would land
  here) is still bundled at build time — a roster change to built-ins currently DOES require a
  redeploy for web and a native rebuild for iOS/widget.
- No explicit **version** field or manifest schema was found gating what a client considers "the
  current roster" — this needs to be designed, not just wired.

### 4. Milestone 2 checklist

| # | Item | Size | Blocking dependency | Who |
|---|---|---|---|---|
| 1 | Design + build the versioned skin-registry manifest (R2), so all 3 surfaces pull skins+regions+sprites without app releases | L | Milestone 1 gate | agent |
| 2 | Decide generation-parity architecture: port gen12's verified pipeline into `pipeline.ts`, or keep them separate and just sync outputs (see options below) | M (decision) + L (impl) | Milestone 1 gate; **user decides which option** | user decides, agent implements |
| 3 | Publish the Milestone-1-verified gen12 roster into the skin registry as the "confirmed human-eye-verified" skins | M | items 1-2 | agent |
| 4 | Fix widget tray skin-list staleness (compute from `skinList`, not hardcoded) | S | none — can do anytime, low-risk | agent |
| 5 | Resolve `CONNECT_ENABLED=false` — either ship the BYO-Client-ID wizard prototype (`docs/spotify-byo-wizard-prototype.html`) or make an explicit call to leave Spotify off for v1 | M | user decision on scope | user decides, agent implements |
| 6 | Resolve `FLOAT_ENABLED=false` PiP — ship, drop, or redesign around the browser-chrome mismatch | S (decision) | user decision | user decides |
| 7 | Confirm Template Studio's intended v1 status (dev-only forever, or promote to a real editing surface for web) — note it's currently dev-only even on web, not just absent on widget | S (decision) | user decision | user decides |
| 8 | iOS: wire real device signing/provisioning (currently Simulator-verified only per `docs/ios.md`) if TestFlight/App-Store distribution is the v1 target | M | none | agent |
| 9 | Formalize the gen12 review-gate as the actual roster publish gate (a skin isn't in the registry until it has a saved PASS in `review.json`) | M | items 1, 3 | agent |
| 10 | Widget: last functional work was ~2026-06-17/18 — do a pass to confirm nothing else silently drifted while attention was on iOS/webapp (beyond the known tray-list bug) | M | Milestone 1 gate (so there's a stable pipeline to re-verify against) | agent |

**Generation-parity architecture — the a/b/c from the 2026-06-27 scope discussion, reproduced:**
(`docs/DECISIONS.md`, 2026-06-27 entry, and `TODO.md`'s "GENERATION SYSTEM" section)
- **(a)** Re-roll the paint until a VLM (Gemini) confirms controls land on the fixed boxes.
- **(b)** Stronger blueprint socket guides so the painter stops drifting at the source.
- **(c)** Clean-socket + sprite/overlay controls — the painter paints empty recessed sockets that
  sprites drop into, minimizing what can misalign.

**What actually shipped since:** detection-snapping (any variant of re-locating controls after
the fact) was rejected outright as a confirmed dead end (2026-06-27 DECISIONS.md entry — CV,
gpt-4o boxes, SAM-3.1, and two Gemini passes all made alignment WORSE). gen12 landed on something
closest to **(c)**: `genskin.py`'s heavy structural-constraint prompt paints empty knob/seek/toggle
cavities and blank screens for the runtime to fill, and this was reaffirmed as the stable
architecture on 2026-07-11 (accepting a measured paint-quality cost as the price of reliable empty
sockets). **The open question for Milestone 2 is whether `pipeline.ts` (webapp) should be ported
to gen12's empty-cavity architecture, or whether the two stay separate implementations that are
kept in sync by other means.** This is a real, undecided fork — user should pick before item 2 is
implemented.

---

## Open decisions — explicit tracking

| Item | Status | Owner |
|---|---|---|
| Mobile-app definition | **RESOLVED by evidence** — the Tauri iOS app at `src-tauri/gen/apple/`, already shipped through TestFlight 0.1.8. Confirm this is the intended v1 mobile target (vs. e.g. wanting a from-scratch native rewrite). | user confirms |
| Generation-parity architecture (a/b/c) | Open — see reproduction above; gen12 itself resolved on (c)-style empty-cavity prompting, but whether to port that into `pipeline.ts` is undecided | **user** |
| Myst pointer mark | **NOT FOUND via repo search.** Closest matches: myst-arcanum's icon-region mismatch (a ▶‖ icon sits in the `prev` region while `playpause` is an iconless gear well — TODO.md §11b) and its unresolved two-carved-marks knob-pointer ambiguity (`docs/experiments/2026-07-11-knob-zero-closed-loop.md` line 108). If "myst pointer mark" means something else, flag it directly — I could not confirm a match. | **user clarifies** |
| Baked-ticks-missing fallback | Mapped to the "Knob tick-mark provisioning" rehab in Milestone 1 — `KNOB_TICKS_ENABLED` (CSS/SVG) is the intended fallback for when a director wants ticks but the paint roll didn't produce them; not yet reframed that way in code (still a bare global flag). See Milestone 1 checklist items 3-4. | agent (design already specified in TODO.md) |
| filter-repo history reclaim | **NOT FOUND** — no evidence of a `git filter-repo` operation, planned or completed, anywhere in `TODO.md`, `docs/`, or git log (checked `git log -S"OPENAI_API_KEY=sk-"` / `-S"sk-proj"` across all refs — only unrelated `entire` checkpoint-repo commits matched, not real secret exposures in skeuo-ui's own history). If a real secret was committed to this repo's history, I have no evidence of it or of a remediation plan. | **user provides context** |
| OPENAI_API_KEY secret deletion | **NOT FOUND as a committed secret.** `.env`/`.env.local`/`.dev.vars` are correctly gitignored (`.gitignore:24-26`), never appear in `git ls-files`, and no literal key value was found in searched history. The only `OPENAI_API_KEY` references in-repo are config/doc mentions (e.g. `director.ts` reading it as an env var, gated feature comments). If this refers to a key exposed outside this repo (a screenshot, a different service, GitHub secret-scanning alert), I have no visibility into that — needs user context. | **user provides context** |
| Drive migration completion | Partially resolved: `~/dev/central/skills/gdrive/scripts/backup-skeuo-skins.sh` syncs `public/generated/` to a **secondary, portable** Google Drive backup (`gdrive:skeuo-skins/`) — R2 remains canonical. A prior session's checkpoint log shows a completed task titled "Finish Drive migration of bulk media," suggesting this may already be done as of this session. Not independently re-verified here (out of this task's file scope — `~/dev/central`, not `skeuo-ui`). | **user confirms** completion |

---

## Cross-references

- Full existing parity detail (per-platform OAuth paths, R2 layout, backend endpoints, build/deploy
  commands): [`docs/feature-parity.md`](feature-parity.md).
- Architecture decision history (why detection-snapping was rejected, why the heavy prompt stays,
  why joint mask was adopted, knob-zero root cause): [`docs/DECISIONS.md`](DECISIONS.md).
- gen12 knob-zero fix writeup: [`docs/experiments/2026-07-11-knob-zero-closed-loop.md`](experiments/2026-07-11-knob-zero-closed-loop.md).
- Knob tick-mark provisioning experiment + human overrule:
  [`docs/experiments/2026-07-11-knob-tick-provisioning.md`](experiments/2026-07-11-knob-tick-provisioning.md).
- PBR/emissive parked-for-v2 verdict: [`docs/experiments/2026-07-11-semantic-emissive-prototype.md`](experiments/2026-07-11-semantic-emissive-prototype.md).
- iOS build/OAuth specifics: [`docs/ios.md`](ios.md); desktop widget specifics: [`docs/desktop.md`](desktop.md).

*File: `docs/SKEUO-V1.md` — regenerate/update whenever Milestone 1's gate status changes, a
Milestone 2 item lands, or an open decision resolves.*
