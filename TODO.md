# skeuo-ui — TODO

## GENERATION SYSTEM — full revamp / nuke from the ground up (2026-06-27) — #1, BRAIN WORK

User directive 2026-06-27: *"complete revamp / nuke of the entire generation system from the
ground up. brain work."* The whole pipeline (prompt → director → blueprint → paint → cutout →
composite → control placement) gets a ground-up rethink — design first, not more patches.

**Why now (this session's finding):** overlay-to-paint **alignment is the unsolved through-line.**
The painter drifts controls off the fixed blueprint sockets, so knob/slider/seek/visualizer
overlays don't sit on the painted controls. Detection to fix it is a **confirmed dead end** —
CV well-detect, gpt-4o boxes, SAM-3.1, and 2× Gemini 2.5 Pro passes ALL made it worse (0oyq
29→0; a SAM render scored 1/10). See `docs/DECISIONS.md` (2026-06-27). Baked buttons can't
visually misalign (bank evenness is now Gemini-gated via paint re-roll) — but the sprite/CSS
overlays (knobs/sliders/seek/visualizer) are the real problem and stay broken.

**Architecture is the question, not the code.** Directions floated but NOT chosen — decide first:
- (a) re-roll the paint until Gemini confirms controls land on the fixed boxes;
- (b) stronger blueprint socket guides so the painter stops drifting at the source;
- (c) clean-socket + sprite/overlay controls (painter paints empty recessed sockets the
  sprites drop into — minimize what can misalign).
Reusable: the Gemini-gated verification harness (`tools/align-verify/`, NOT my-eyes).

### Done this session (2026-06-26/27)
- Reverted the SAM-3.1 snap (`f1db039`) — detection makes alignment worse; re-litigated a settled call.
- Shipped Gemini-gated paint re-roll for even baked button banks (`cfd7fe5`, `5d7ed05` 3-run consensus).
- Cleaned 4 merged worktrees + 6 feature branches; audited dead code (`spriteSheet.ts`,
  `CutCompare.tsx` + the SAM/VLM arm ≈ 1,300 dead lines — see junk list, NOT yet removed).

## Template Studio
- [x] **Auto-snapping grid for Template Studio** — included in the use-gesture approach (element guidelines + snap thresholds via Moveable-like config, snappable via alignment hints).
- [x] **Template Studio gesture handling — MERGED (94bdc58, 2026-07-08).** C approach (pure SVG + @use-gesture/react) integrated as the production solution. Pointer-capture bug fixed (bind useDrag directly to control handles, not SVG root). Overlapping controls allowed. Snapping, alignment guides, corner-radius morphing, arc angle editing all working. Multi-select drag verified.

### Done this session (2026-07-07/08)
- Per-component HEX identity shared across panels / blueprint / output-mask / prompt-legend (`componentColors`).
- Diffuse corner-draggable rounded-rect shape (rect↔oval, Illustrator corner handles); slider geometry = line + partial-circle arc.
- Spotify-only control filter (drops balance / EQ / stop) + de-complexified random layouts; bind dropdown limited to Spotify-drivable binds.
- Full-height 3-panel layout (RAW / blueprint / painted) + FAL prompt moved to a bottom strip; PACKED hidden behind a `REPACK_ENABLED` flag; blueprint overlays default off + toggleable.
- **Overlap enforcement removed** (`917f083`): `enforceZeroDiff`/`resolveOverlaps` deleted, controls can now overlap freely. `justify-content: safe center` fixed left-panel masking.
- **Three-way gesture-handling bake-off** (2026-07-07): react-moveable (A), react-konva (B), use-gesture (C) — tested across select/drag/resize/corner-morph/arc-edit. **Selected C (use-gesture)** for production (snap-grid feel, arc placement, pointer-capture fix cleanest). Merged to main, cleaned up worktrees A & B.

## Cutout — coloured-backdrop matte: WIRED on branch `cutout-coloured-despill` (2026-06-23)

**Status: implemented + build-green + function-verified on real paints; pending a LIVE
end-to-end gen + a merge decision (interacts with the #1 spritesheet-pipeline cutout).**
The runtime now paints on a contrasting backdrop and keys it out with the color-aware
matte below (pure-JS color-key, no model — BiRefNet remains the server-side option on
the spritesheet branch). Changed: `pipeline.ts` (pickKeyColor + {BG} prompts + thread
keyColor), `blueprint.ts` (`cutoutColorAware` = key→colour-aware-fill→despill; `cutoutAlpha`
kept as the white fallback), `cutoutClient.ts`/`api.ts`/`handler.ts`/`CreateWizard`/`CreatePanel`
(thread `keyColor`). White key = legacy behaviour (translucent/iridescent route here).

Investigated fixing BiRefNet's two cutout failures (white enclosed pockets kept opaque;
dark glossy screens keyed out). Validated end-to-end on real ship paints (nano-banana-2)
+ real fal BiRefNet v2. Interactive lookdev preserved at
`~/Desktop/cc-skeuo/cutout-lookdev/index.html` (14 skins incl. the original problem
concepts regenerated on coloured bg — jelly/clamshell/pet/frog/mushroom/robot; toggle
stage + backdrop, green backdrop exposes keyed-out holes).

**Recipe (for the spritesheet pipeline's BiRefNet cutout step):** paint the device on a
flat CONTRASTING backdrop (a hue OUTSIDE the device palette, luminance-contrasting —
bright magenta/yellow/cyan; bright beats dark, dark risks eating black screens), then
matte = **BiRefNet alpha → colour-aware CUT (remove kept pixels that ARE the backdrop
colour — fixes backdrop leaking through thin gaps, e.g. obsidian comb slots) →
colour-aware FILL (fill enclosed non-backdrop holes — keeps dark screens) → despill
(chroma-suppress the backdrop hue, strength 1.0)**.

**Why coloured bg:** on WHITE bg a near-white screen == bg (can't tell a screen from a
gap); on a coloured bg screen≠bg so fill/cut are unambiguous. Also cleanly keys
white/silver devices that blend into white. Luminance-contrasting key → ~12× sharper edge
(green==steel luma was the worst; yellow sharpest).

**Caveats — route these to white-bg OR edge-only-unmix (NO global despill):**
- TRANSLUCENT (jelly) — backdrop glows through the body; despill flattens it.
- IRIDESCENT / PEARL — sheen spans the hue wheel incl. the backdrop hue; despill mutes real colour.
- MIRROR — reflects the backdrop into the body.
- PALETTE CLASH — never key on a hue the device contains (green bg ate the green LEDs).

**Next:** wire `cut → fill → despill` into the runtime cutout (`src/generate/cutoutClient.ts`
/ `functions/api/cutout.ts`) with material-class routing; choose the per-skin key colour in
the paint prompt (`src/generate/pipeline.ts`).

## Open

- [ ] **★ #1 PRIORITY — Merge `spritesheet-pipeline` → main: single-pass skin generation + sprite-sheet (decision A locked 2026-06-23).**
      **→ Full design + decisions + rejected approaches: [`docs/skin-pipeline-sota.md`](docs/skin-pipeline-sota.md) (READ FIRST).**
      ONE generative paint pass renders the device body + all button/knob/slider parts together
      (combined blueprint); then non-generative BiRefNet mask + local cut + heuristic snap. Generated
      skins render their OWN per-skin cut sprites (A). This is the top thing to land next session.
      The `spritesheet-pipeline` branch (worktree `../skeuo-ui-spritesheet`, tip `d88a4cc`, pushed)
      has the single-pass generation: ONE paint call renders the device body (grown around fixed
      sockets) + a bottom strip of bare control parts (`combinedBlueprint` in `blueprint.ts`,
      `PAINT_PROMPT` in `pipeline.ts`), BiRefNet device cutout (`functions/api/cutout.ts`), and
      per-skin control sprites cut from the strip + uploaded (`finalize` + `cutoutClient.ts`).
      **Keep this generation + spritesheet approach.**
      - **Merge state:** branch is 13 ahead / 26 behind main. Clean except **3 conflicts**:
        `src/generate/CreatePanel.tsx`, `CreateWizard.tsx`, `handler.ts` (main added the Director
        title/blurb/font + delete; branch changed the cutout wiring — reconcile, keep BOTH).
        Also overlapping: `src/App.tsx`, `src/generate/api.ts`.
      - **DECIDED (2026-06-23) — (a): generated skins render their OWN cut sprites.** Conner: "A is
        very important to me." So the merge KEEPS the branch's per-skin button-asset handling
        (`cutoutClient.ts` cut+snap, `Composite.tsx` per-skin sprite render, `skins.ts` sprite URLs)
        — NOT main's donor path. The 3 create-flow conflicts resolve by keeping BOTH: main's newer
        Director title/blurb/font + delete AND the branch's `finishCutoutFull` cutout/sprite wiring.
        The remaining real work is the **alignment** below (heuristic tuning, NOT SAM).
      - **Alignment = VLM, NOT heuristic/SAM (decided 2026-06-23).** The landed approach is a VLM
        (gpt-4o vision) — already implemented in `generation/freeform.py` `extract()`: send the
        device image + the template's control checklist, get back STRICT JSON of each control's box
        `{kind,x,y,w,h}` (center + size), then snap each cut sprite onto its box. Semantic → reads
        the painted ►/VOL icons so identity is correct by construction (no nearest-neighbor mishaps),
        one cheap call, returns centers AND sizes. Port `freeform.py extract()` into the runtime
        (a server `/api/extract` like `/api/sam`, FAL/OpenAI key server-side) and replace
        `cutoutClient.snapToSockets`. Dead-ends NOT to repeat: the dark-well heuristic (flaky per
        gen) and `sam_snap.py` SAM box-prompt (merges/misses on AI-painted devices — tried + reverted
        this session; the comfyui seg bake-off had already concluded zero-shot seg fails here).

- [ ] **Website redesign — follow-ups (2026-06-23).** The desktop + mobile shell was
      reworked + shipped to skeuo.fm this session (see Done below). Loose ends:
      - **Spotify still hidden + non-functional** — `CONNECT_ENABLED = false` in `App.tsx`
        gates the Connect pill on desktop AND mobile, so the player only drives the local
        demo. Real playback needs the BYO-Client-ID wizard (its own open item / prototype in
        `docs/spotify-byo-wizard-prototype.html`). Flip the flag once that lands.
      - **Generated-skin name/font unverified live** — the Director (`deriveMaterial`) now
        returns a concise `name`/`blurb` + a Google-Fonts `font` (now genre-rotated + recent-avoid
        for diversity, css2 cross-validated), threaded handler→api→`onCreated`. The font path is
        verified LOCALLY against gpt-4o (10/10 distinct), but the full paid end-to-end gen on PROD
        is still untested. Do one real "Create a skin" on skeuo.fm to confirm naming/font load +
        that the CF Pages OpenAI key + env are set. (This is TODO item "C" from 2026-06-23.)
      - **No un-hide UI** — the gallery × HIDES a generated skin (`hidden:true`, raw data kept
        in `localStorage["skeuo:skins"]`), but there's no restore affordance yet. (2026-06-23: a
        `?all` query param now reveals ALL hidden catalog bodies in the gallery — a dev/review
        affordance, not the real per-skin restore UI, but a starting point.)

- [ ] **Reactive music-player mascot — build the rig + groove layer (animation strategy researched 2026-06-23).**
      A `mascot` player region (like the `cd`/`visualizer` dynamicTypes) that idles when paused and
      grooves to the music when playing, blending smoothly + reactive to energy/BPM.
      - **Research (read first):** `docs/anim-pipeline-ideation.md`
        (substrate landscape) + `docs/anim-transitions-research.md`
        (transition mechanics — web-verified: Bollo inertialization GDC2018, Spine mixDuration/tracks,
        Mecanim blend-trees + additive layers, Live2D keyform interp, critically-damped springs).
        (both now in docs/.)
      - **Recommended approach:** generate the gremlin ONCE → BiRefNet matte → cut ~8 parts → a code
        **cut-out rig** (PixiJS/`pixi-spine` or hand-rolled canvas bones + Verlet jiggle on cap/tail).
        Drive dance as an **ADDITIVE groove layer** (bounce + head-bob + cap-tilt) scaled by `alpha=energy`
        — ghost-free by construction (composes transform deltas on one rig; avoids the "blend only similar
        poses" trap). Spring-smooth `energy` with the CD-spin envelope `v += (target−v)(1−e^(−dt/τ))`;
        bounce phase from a beat clock softly locked to the track so the downbeat lands on the beat.
        Reserve **inertialization** for reaction one-shots; keep authored "getting-into-it/settling" clips
        as accents + the fallback floor.
      - **Assets already made:** low-res idle/dance sprite frames `/tmp/cdtex/mascotA/frames/` + Desktop
        `mascot-react-*`; canonical refs `~/Desktop/cc-skeuo/mix-dk-red-a.png`, `/tmp/cdtex/eh0.png`.
        (Note: the early crossfade-sprite prototype GHOSTED — that's why the rig/additive approach.)
      - **Decisions to lock before building (my leans in parens):** rig substrate — cut-out 2D rig vs
        Dead-Cells 3D-render *(2D rig)* · dance depth — additive-bounce-only vs full body re-pose at high
        energy *(additive-only v1)* · beat-sync — strict live-beat lock vs smoothed BPM clock *(gentle)* ·
        reactions/inertialization in v1 *(defer)*.

- [x] **CD album-art visualizer — MERGED + baked + deployed (2026-06-24).** The
      `cd-visualizer` branch (cd + albumart dynamicTypes, spinning silver data-side disc,
      `Track.cover` from Spotify) merged clean into main (worktree removed). Bake on top:
      - **Hub recentred via circle-fit** on the hole edge (was ~8px high → wobble; now
        within 0.2px of center, fit residual 0.29px). The old centroid method was skewed
        by the gloss — fit a circle, not a centroid.
      - **Anti-strobe rotational motion blur**: the disc jumps 8–17°/frame at cruise and
        isotropic blur can't mask it, so `CdDisc` stacks 5 echo layers across ~1.4 frames
        of motion (oldest opaque, current on top) → smooth sheen. Isotropic softening 0.15px.
        Tuned in a lookdev studio (now torn down).
      - **Shows up in a final skin**: `wmp` (Media Capsule) is the one thematic built-in CD
        showcase (square visualizer region → cd). Every other skin + the wizard default +
        the 🎲 randomizer stay VISUALIZER; generated skins get a CD only when the prompt is
        music/disc-thematic (~70%) or rarely at random (~8%) — `maybeCdScreen()` in pipeline.
      - **Real album-art tint (local mode, no Spotify)**: fetched actual covers (iTunes) for
        the wmp trance playlist + the winamp fallback playlist → `public/demo-covers/`, wired
        `Track.cover`, so the disc tints to the playing song's real cover. Tint made WAY
        stronger (opacity .95 + a 2nd overlay-blend layer). Generated cd skins fall back to
        the covered winamp playlist, so they tint too.
      - NOT run-verified: the thematic-generated-CD path (would need a paid "boombox/cd"
        gen to confirm a generated skin actually gets a CD).

- [x] **More generative template heuristics — BAKED (2026-06-23).** The 10-archetype engine
      + repel/min-spacing pass is now `layoutRandom()` in `src/generate/layouts.ts`, wired to
      the wizard's 🎲 and verified live (arc + dial rolls, round controls, glass cleared, 0
      overlaps). Density varies per roll. Studio kept at `/tmp/lookdev-layout/` for further
      tuning. Still open below: weight curation / gridSnap exposure / lopsided-default are
      hardcoded to the dialed-in config — revisit if you want them user-tunable.
- [ ] **Wizard-randomizer polish (autonomous, low-stakes).** The 🎲 config is hardcoded in
      `layoutRandom()` (`src/generate/layouts.ts`). Optional next passes: expose `gridSnap` /
      archetype-weight / lopsided as user controls in the wizard; and/or auto-pick the archetype
      from the prompt/silhouette aspect (wide→console/split, tall→stack/dial) instead of pure
      weighted-random. Studio for tuning: `~/dev/central/scripts/serve /tmp/lookdev-layout --bg`.

- [ ] **(was) More generative template heuristics — original notes (kept for reference).**
      A layout-randomization studio was built (`/tmp/lookdev-layout/index.html`; re-serve with
      `~/dev/central/scripts/serve /tmp/lookdev-layout --bg`) to ideate graphic-design-informed
      layout heuristics for the wizard's 🎲 Randomize. It generates **10 archetypes** — stack,
      dial, split, mini-widget, console, **diagonal/Z, golden-section, Swiss grid, L-corner,
      arc/fan** — each a complete working player, run through a **repel + min-spacing validity
      pass** (`resolveOverlaps`) that guarantees 0 overlaps / no too-close controls (verified:
      400 seeds × every archetype → 0 overlaps, min gap 0.02). Controls carry a `nopush` flag on
      the dial glass + arc ring so things ride them intentionally.
      - **Tuned default config the user picked** (mini + arc heavy, full symmetry, sparse,
        max play-dominance): `{count:24,seed:9999,density:0,symmetry:1,bias:1,jitter:0,
        hierarchy:1,margin:0.14,gapScale:1.5,gridSnap:0,gridN:16,repel:1,spacing:0.02,
        wStack:0.4,wDial:0.5,wSplit:0.5,wMini:1,wConsole:0.45,wDiagonal:0.05,wGolden:0.6,
        wGrid:0.45,wCorner:0.2,wArc:1}` (now the studio's `DEFAULTS`).
      - **BAKE:** port the studio's archetype generators + `resolveOverlaps` into
        `src/generate/layouts.ts` (px-on-1024×1536, matching the existing `layout*()` fns) and
        wire the wizard's 🎲 to `layoutRandom()` drawing from them with these weights. Decide:
        all 10 in the 🎲 vs a curated subset; whether `gridSnap` is user-facing (only the Swiss
        grid benefits); lopsided as a frequent default vs gated to mini-widget. Then tear down
        the `/tmp` studio.

- [ ] **Mascot favicon — revisit (current SVG `public/favicon.svg` stays for now).**
      Want a favicon that keeps the skeuomorphic iOS-original tile + the existing
      chrome-knob + green-pointer/LED, with a *hint* of the mascot worked in. Explored
      (2026-06-22) and rejected: gremlin horns added to the knob; "horns-as-the-knob's-
      tick-marks" on a glossy bright-green tile with a dark knob (dark-on-green reads well
      at distance, but the execution was ugly). Variant generator + sized/16px lookdev:
      `/tmp/cdtex/fav/` (`gen.py`, `gen2.py`, `index.html`). Reactive-mascot / error-mascot
      art lives in `~/Desktop/cc-skeuo/` (`mascot-*`); error picks are matted to alpha
      (`mascot-error-*-cutout.png`). Direction still open — the hint just needs a better
      idea than horns/tick-marks.

- [ ] **Spotify BYO-Client-ID onboarding wizard — RESUME after the 24h Spotify
      app-creation cooldown (~2026-06-23).** Prototype built + verified, NOT yet wired
      into the React app. Goal: let any Premium user connect their OWN Spotify dev app,
      sidestepping the ≤5-user allowlist on skeuo's shared app.
      - **Prototype:** `docs/spotify-byo-wizard-prototype.html` (re-serve:
        `~/dev/central/scripts/serve docs --bg`, open the printed URL).
      - **Flow:** click "⧉ Float the setup helper" → an always-on-top Document-PiP helper
        opens (one window per gesture — you CANNOT open the dashboard tab + PiP from one
        click, hard browser limit, so the **"Open Spotify dashboard" button lives inside
        the float**) → copy app-name/description/redirect-URIs into Spotify's form → paste
        Client ID → the green **"Back to skeuo & connect"** handhold button closes the float
        and lands on Connect. Verified end-to-end in headless Playwright (PiP opens, copy
        works in-float, no scroll, handhold returns helper + advances, 0 console errors).
      - **NEXT (after cooldown):** test live with the EXISTING app `testapp` (Client ID
        `98e0d056151a4f84b42fefef4b9441e8`) via the wizard's **"I already have one"** mode —
        do NOT create a new app (Spotify now caps **one** Development-Mode app per person AND
        rate-limits creation). Add redirect URIs `https://skeuo.fm/callback` + `https://skeuo.fm/`
        (**https only** — Spotify rejects `skeuo://` custom schemes).
      - **Then the fork:** (a) wire the wizard into the app — a `CLIENT_ID` override in
        `src/spotify/auth.ts` read from localStorage + a React port of the wizard; vs
        (b) build a **zero-setup default engine** (local files / Audius/Jamendo) for casual
        visitors, with BYO-Spotify as the advanced path.
      - **Hard constraints learned (2026-06-22):** Spotify dev mode (Feb/Mar 2026) = 5 users
        max, owner must be Premium, one app per person; Extended Quota needs a registered
        business + ~250k MAU (unavailable to an indie) → public skeuo CANNOT control arbitrary
        users' Spotify. YouTube ripping AND hidden-player embed both violate ToS (App-Store
        rejection risk). Legal zero-setup catalog = local files + Audius (Open Audio Protocol)
        / Jamendo / Internet Archive.

- [ ] **Restore the "Play here" switch** (removed 2026-06-18). The in-page Web
      Playback SDK device (`playHere`/`setPlayHere` in `useSpotify`, `sdk.ts`,
      `initWebPlaybackSDK`) lets a Premium user play audio in the page/tab itself
      instead of on an external Spotify Connect device. The UI toggle was pulled
      from `SpotifyConnect.tsx` for now (the hook plumbing is left intact, just
      unused). Re-add the `<label className="sp-toggle">` checkbox (desktop/web
      only — gate with `!isMobileApp()`, since iOS WKWebView lacks EME/Widevine)
      when we revisit in-page playback.

## Done (2026-06-24) — Streaming loading preview + shape de-bias (shipped)
- [x] **Streaming "skin forming" loading preview** — `/api/generate` now STREAMS NDJSON:
      each pass emits `{stage,url}` as it completes (blueprint → grown body → painted skin),
      final `GenerateResponse` is the last line. `RuntimeDeps.onStage` → CF Function + dev
      plugin stream it; `postGenerate` reads line-by-line. Wizard showed the user's REAL
      artifacts forming. **HIDDEN behind `LIVE_PREVIEW_ENABLED=false`** (user's call) — the
      streaming infra stays live (harmless), only the in-loader card is gated off. Verified
      incremental on prod CF (blueprint@3s, envelope@29s, paint@60s, done@63s).
- [x] **Generated-skin name/font verified LIVE (TODO "C")** — the streaming gens this session
      returned real Director names ("Cute Red Mushroom", "Victorian Echo") + fonts on prod,
      with the OpenAI key confirmed working. (Earlier-flagged item, now confirmed.)
- [x] **Shape de-bias** — `ENVELOPE_PROMPT` no longer forces "horns, fins, tendrils, legs,
      jaws" on every sculpted body; the form now FOLLOWS the brief (no monster default unless
      the prompt calls for it). Root-caused the gallery's "evil" motif to this prompt + a
      legacy biomech-heavy catalog. (Affects the opt-in 2-pass sculpt path; default 1-pass was
      already neutral.) Catalog curation (hiding the horror cluster) NOT done — still an option.

## Done (2026-06-23, late) — Font polish + skeuo.fm prod-stability fix (shipped)
- [x] **Real font preload (kills the pop-in)** — `preloadSkinFonts` only injected the Google
      CSS `<link>`; the woff2 binary still lazy-loaded on first glyph render (the pop-in).
      `ensureGoogleFont` now forces the binary down via `FontFaceSet.load()` on link-load.
      Verified network-level: all visible faces fetch (200) + pass `fonts.check()` ~2s after mount.
- [x] **Font diversity system** — the Director anchored on the same few faces. Each gen now
      randomly favors one of 8 genre buckets (rotated exemplars) + a recent-fonts avoid-list
      threaded client→handler→director via `localStorage["skeuo:skins"]`. Live gpt-4o test:
      10/10 distinct fonts across 10 consecutive gens.
- [x] **Google-Fonts cross-validation** — LLM picks any family from memory, then `resolveFont`
      probes the css2 endpoint for THAT family (real→200, hallucinated→400; no API key, no
      1800-family catalog dump); a made-up name falls back to a style-appropriate face.
- [x] **Catalog font pass** — hand-picked a distinct, vibe-matched face for ALL 30 skins (was
      only the 10 visible); preload scoped to the visible roster so mount stays light. `?all`
      query param reveals the hidden catalog bodies in the gallery (dev affordance — see un-hide).
- [x] **skeuo.fm HANG fixed — poisoned Cloudflare edge cache.** A deploy-propagation race served
      not-yet-present hashed chunks as `200 text/html` (the single-page not_found fallback), frozen
      by the `immutable` `_headers` rule → a fresh browser got HTML for a JS module → app never
      mounted (`Failed to fetch dynamically imported module`). curl hit a clean variant (read as
      JS) which masked it; a fresh-profile headless browser reproduced it every time. Couldn't purge
      (API token lacks the perm) so: (a) moved hashed assets to `/assets/app/` — brand-new,
      never-poisoned URLs that bust both the edge entry AND any poisoned client caches; (b)
      `public/_redirects` makes a missing `/assets/*` return **404 `no-store`** instead of the
      HTML fallback (can't masquerade as a module, isn't cached → can't recur) + a `404.html`.
      Verified fresh-profile prod load now MOUNTS. Commits 279fc5e/f6bd8e0/4d3ee57/da68da1, deployed.

## Done (2026-06-23) — Website redesign: shell, thumbnails, cinematic titles (shipped to skeuo.fm)
- [x] **Desktop shell rebuilt** several times to the final form: a NARROW left gallery
      (scrolling skin list, animated thumbnails) + a FULL-HEIGHT skin (the hero, vw+height
      bounded so it never clips) + a cinematic title card whose text sits squarely centered
      between the skin's right edge and the frame edge. Flat `#08080a` bg, no gradient box.
- [x] **Baked thumbnails** — `scripts/bake-thumbs.mjs` renders each skin's real `<Composite>`
      (buttons/dials/screen, visualizer suppressed) → 256px WebP, so the gallery minis show
      actual controls, not empty wells. A guard skips skins whose `?skin=` id doesn't resolve;
      only the 10 visible skins were re-baked. Round-dial well-disc removed (the dial is baked).
- [x] **Per-skin logomark fonts** — `src/player/skinFonts.ts` maps id→a punchy Google font;
      loaded DYNAMICALLY (`ensureGoogleFont`, any family, not a fixed list) + preloaded on mount
      with an `isFontReady` cache check so switching skins doesn't pop in. `<CinemaTitle>` fits
      the title to its area and wraps to ≤2 whole-word lines (no offscreen flow). The Director
      picks a font for generated skins too (any family, dynamic-loaded).
- [x] **Director emits concise `name` + `blurb`** (no more "a fanged anglerfish · nano-banana-2"),
      threaded handler→api→`onCreated`, tidy prompt-derived fallback on the no-key path.
- [x] **Generated-skin × = HIDE not delete** — sets `hidden:true`, filtered from the gallery,
      raw materials kept in storage for future processing.
- [x] **Mobile/narrow bar matched to desktop** — Connect hidden, Template view axed, Share is a
      labelled pill, Create is the green CTA; skin title+blurb shown small in the stage corner.
- [x] **Connect (Spotify) hidden** behind `CONNECT_ENABLED=false` (desktop + mobile) until the
      playback path is fixed. Float-player stays behind `FLOAT_ENABLED=false`.

## Done (2026-06-22) — Float the player in the browser (Document Picture-in-Picture)
- [x] **"⧉ Float player — no install"** button (desktop, sidebar Connect group). Pops the
      running skin into an always-on-top OS window via `documentPictureInPicture.requestWindow()`
      — the in-browser equivalent of the Tauri widget, zero install. Implemented in
      `src/player/useDocumentPip.ts` (open/close + carry every same-origin stylesheet into the
      PiP doc) + `src/App.tsx`. The live `<Composite>` is rendered through a SINGLE
      `createPortal` whose container toggles between an in-page `.player-host` and the PiP
      window body, so floating/restoring never remounts the player — the same instance keeps
      driving Spotify; transport state is preserved. Stage shows a "floating…/Bring it back"
      placeholder while popped; `pagehide` (OS-close or our close) snaps it home. Gated on
      `'documentPictureInPicture' in window` (Chrome/Edge 111+; hidden on Safari/iOS). CSS in
      `app.css` (`.pip-body`/`.pip-stage`/`.stage-popped`). Verified end-to-end in headless
      Chromium: float → player in PiP doc (frame + regions render, 20 sheets carried), host
      empties, placeholder shows; bring-back → player returns, window closes, 0 console errors.

## Done (2026-06-13) — Tauri desktop widget + web→desktop handoff
- [x] **Tauri macOS app** (`src-tauri/`) reusing the same React bundle — `isWidget()`
      mounts `WidgetApp` (one transparent skin) instead of the website.
- [x] **Transparent, non-rectangular floating window** (`macOSPrivateApi` + `transparent`,
      no decorations/shadow); the skin's frame alpha is the shape. Crisp silhouette
      drop-shadow. Skin fits the window at 2:3, screenshot-verified.
- [x] **Manual window drag** (`setPosition` on pointer-move; controls opt out) — native
      startDragging/drag-region both no-op'd, so we move the window ourselves. Drag works
      from the skin body AND the fade-in top bar. (User-confirmed.)
- [x] **Menu-bar tray**: switch skin, toggle always-on-top, show/hide, quit. Always-on-top
      now OFF by default. Window is resizable.
- [x] **Remember position + size across reopens** (`tauri-plugin-window-state`; explicit
      save on tray-Quit + restore on launch).
- [x] **Per-pixel click-through** on transparent areas (`clickthrough.ts`): alpha hit-map
      (fetched PNG → `createImageBitmap`, avoids the asset-protocol canvas taint) +
      `setIgnoreCursorEvents` toggled by the cursor pos, with a standalone `cursorPos()`
      poll to re-capture. **Root-cause bug (fixed 2026-06-13):** the poll called
      `win.cursorPosition()`, but `cursorPosition` is a STANDALONE export of
      `@tauri-apps/api/window`, not a `Window` method → threw every tick, `.catch`
      swallowed it, window stuck click-through. Top ~38px (the fade-in bar) is always
      interactive so the bar stays clickable. User-confirmed working.
- [x] **web→desktop handoff**: site "Open in desktop player" → `skeuo://skin/<id>`; the
      built `.app` registers the scheme and switches skin live (verified `skeuo://skin/maw`).
      "Download for Mac" → GitHub Releases.
- [x] **Spotify on desktop**: reuses `src/spotify/*`; `platform.ts` swaps the OAuth redirect
      to `skeuo://callback` and opens `/authorize` in the system browser.

## Blocked on the user (desktop)
- [ ] **Sign + notarize** for distribution: no "Developer ID Application" cert is in this
      machine's keychain and no `APPLE_ID/APPLE_PASSWORD/APPLE_TEAM_ID` in env. Current
      `.dmg` is ad-hoc-signed (Gatekeeper right-click→Open). Install your cert + set those
      env vars, then `scripts/build-desktop.sh`.
- [x] **Spotify app configured** (2026-06-13): reused the existing `testapp` (dev-app limit
      hit). Client ID `98e0d056151a4f84b42fefef4b9441e8` in `.env.local`. Redirect URIs:
      `http://127.0.0.1:5173/`, `https://skeuo-ui.pages.dev/`, `http://127.0.0.1:14565/callback`.
      APIs: Web API + Web Playback SDK. **Spotify rejects custom schemes** (`skeuo://callback`),
      so desktop OAuth uses a 127.0.0.1:14565 **loopback** listener (`oauth_loopback` in lib.rs)
      instead. Set `VITE_SPOTIFY_CLIENT_ID` in the Cloudflare Pages env for prod web.
- [ ] **Live-test the Spotify flow** end-to-end (web: restart dev; desktop: Connect Spotify in
      the rebuilt app → browser → loopback → active-device control).

## Done (2026-06-12)
- [x] Round dial screens filled — radial spectrum + center clock/track (was a black void).
- [x] Seek arc aligned to the painted groove (stroke 3.4→7) + biomech rail brightened.
- [x] Asymmetric transport sizing (`BSIZE`: PLAY 1.5×, stop 0.82×) on radial/orbit/capsule/minimal.
- [x] `minimal` layout grammar — sparse now-playing puck. New skin **Pebble**.
- [x] `SIL_PROMPT` relaxed for tall/narrow, squat/wide, asymmetric, angular bodies; `usable()` gate loosened. New skins **Bone Totem** (tall), **War Slab** (wide).
- [x] Reference-style images passed directly to the paint model (`generate.submit` extra `image_urls`); CLI 6th arg.
- [x] `gen_buttons` split rewritten (column-alpha valley) — frog/biomech no longer FAIL.
- [x] README rewritten to the `wild_sculpt` pipeline + layout-grammar table.
- [x] **Deployed** to Cloudflare Pages: https://skeuo-ui.pages.dev (project `skeuo-ui`, CF creds in central/.env).
- [x] **Generate-from-prompt** UI + `/api/generate` Pages Function (TS port of layout-first pipeline, FAL_KEY server-side, per-IP + global cost cap). Draggable **template editor**.
- [x] **Spotify** connect & control (PKCE + Web API + Web Playback SDK); local demo mode preserved.
- [x] **Mobile**: responsive shell + swipe-to-switch + "generate your own" card.

## Blocked on the user
- [ ] **Enable live generation in prod**: `wrangler pages secret put FAL_KEY` (CF) — currently deployed WITHOUT the key, so `/api/generate` returns "server missing FAL_KEY". Decide the cost model first: eat fal cost (~$0.30/gen, $6/20-gen global cap is built in) vs require a user-supplied key vs paywall.
- [ ] **Spotify app registration**: create at developer.spotify.com → set `VITE_SPOTIFY_CLIENT_ID`; redirect URIs must be exactly `http://127.0.0.1:5173/` (Spotify rejects `localhost`) and `https://skeuo-ui.pages.dev/`. Then full OAuth + active-device control + "play here" (Premium) need a live test.
- [ ] **Name + domain decision** — see Naming section below. Leaning `.fm` TLD (reads as a radio station, carries "player"). Top live candidates, all confirmed FREE on `.fm` (~$85/yr): **guise.fm** (skins = a guise you put on), **ruckus.fm** / **coup.fm** (rebellion/noise), **fib.fm** (the liar→shapeshifter angle). Highest *squat/resale* value = the 3-letter words **imp.fm / vex.fm / fib.fm**, or **racket.fm** for music-buyer resale. Cheap holds: `fib.fun` (~$15), `guise.lol` (~$8). No domain bought yet — still on free `skeuo-ui.pages.dev`.

## Generation feature — production hardening (from the build agent)
- [ ] Loose alpha mask: `/api/generate` uses the constant region mask, so the silhouette doesn't trace horns/jaws like the Python pipeline (which thresholds the envelope PNG). Add a server-side envelope-threshold pass to tighten it.
- [ ] Frames returned as ~7.6 MB data: URLs — bind an R2 bucket (uncomment `SKINS` in wrangler.toml) and store + re-compress instead.
- [ ] Rate limit is in-memory (per-edge, not durable) — move to KV or Durable Objects for a real cap.
- [ ] Synchronous request (~75s) — a "pending" poll branch exists in the contract but no queue is wired; add one before real traffic.

## Naming (2026-06-13 exploration)
Direction landed on: a **smiling-guilty bratty 90s demon-child** mascot (Invader-Zim / lil' 😈 energy — NOT gross-out like Rat Fink). Naming mechanism that clicked: a word implying **deception/lying** doubles as the **shapeshifter/skins** concept, and **`.fm`** quietly carries "music player" — so the wordmark only needs to be cool + ownable, the mascot carries the devil, the product carries the skins.
- **By concept fit (skinnable player):** `guise.fm` ⭐ (a *guise* = a skin/assumed form), `vizard.fm`, `visage.fm`, `veneer.fm`, `hide.fm` (skin/pelt + conceal).
- **By rebellion energy:** `ruckus.fm`, `coup.fm`, `rumpus.fm`, `thrash.fm`, `mayhem.fm`, `sabotage.fm`, `uprising.fm`, `renegade.fm`, `putsch.fm`, `bedlam.fm` — all free `.fm`.
- **By squat/resale value:** 3-letter dictionary words win — `imp.fm` ⭐ (also on-theme: little devil), `vex.fm`, `fib.fm`; `racket.fm` for music-buyer resale.
- **Dead/taken:** Knobgoblin (NSFW collision), Beastbox (52TOYS), Boom-compounds (corny), morphonic/echomimic (coined → no resale), molt/morph/mimic/riot/rebel/anarchy/maverick/mosh/blitz (.fm taken).
- **Cost note:** `.fm` is ~$85/yr (premium ccTLD, normal price). Cheap holds: `fib.fun` ~$15, `guise.lol` ~$8. Recommendation: don't buy speculatively; rename repo/Pages to the pick (free), buy `.fm` at launch.

## Earlier follow-ups (still open)
- [ ] Isolate the reference-steering effect (no-ref control or off-prompt reference) — winamp material prompt already implies chrome, so War Slab doesn't independently prove the ref moved the output.
- [ ] Capture real WMP9/Halo2 references into `assets/refs/` and regenerate those homages.
- [ ] Regenerate the older blob-like sculpts (frog2/burger2/bondi2/toilet2/biomech2/fiend2) with the relaxed prompt.
- [ ] Auto-select layout grammar from silhouette aspect (wide→capsule, tall→classic/hero) instead of passing `variant` by hand.
- [ ] EQ/playlist crowding on hero (obelisk).

## Follow-ups
- [ ] **Isolate the reference-steering effect.** Mechanism is wired + runs, but the winamp material prompt already implies chrome, so War Slab doesn't independently prove the ref moved the output. Generate a no-ref control of the same blueprint and diff, OR steer with a strongly off-prompt reference (e.g. a bright reference on a dark style) to confirm influence.
- [ ] **Capture real homage references.** WMP9 / Halo 2 / noirotic / Illusion screenshots were never obtained as files. Drop them in `assets/refs/` and regenerate `wmp` / `halo` with `--ref` so the homages actually trace the source UIs.
- [ ] **Diversity is 3 new bodies, not a sweep.** The older blob-like sculpts (frog2, burger2, bondi2, toilet2, biomech2, fiend2) predate the relaxed prompt. Regenerate them to break the morphological sameness across the whole set.
- [ ] **Wide/low bodies must route to `capsule`/`minimal`.** The vertical-stack grammars (classic/hero/flank) need a portrait torso; a squat body fails `usable()`. Consider auto-selecting the grammar from the silhouette's aspect ratio instead of passing it by hand.
- [ ] **EQ/playlist crowding on hero (obelisk).** The hero center-play band is busy on a tall body; revisit spacing.

## 2026-07-09 — saved for later
- **Moiré "PCA cloud" aesthetic**: the dashboard PCA animation's chevron-wave pattern = moiré from
  stride-sampling a regular pixel lattice rendered at a non-integer scale (grid-vs-grid beat
  frequency). Terms: moiré pattern, lattice undersampling aliasing, ordered dithering. Replicable:
  sample every k-th pixel of a filled shape, draw at floor(x*s) with k*s non-integer. Consider as a
  deliberate visual style (viz mode / loading states / brand texture).
- [x] **Ambient-video masking problem**: find a reliable way to mask/limit modified areas in i2v
  ambient loops — diff-detect changed pixels vs source frame + hard-composite video only inside
  allowed-motion masks (reuse PBR glass/region masks). Seedance 1.0 pro fast = current winner.
  **Outcome (2026-07-10):** naive absdiff-vs-source doesn't work (11-22% false-touched from
  compression/grain noise); per-pixel temporal std-dev across the clip does (0.5-5.9%, matches
  human verdicts); hard-composite (force protected control boxes back to source, feathered)
  verified to eliminate leak with a close-up crop check. See
  [`docs/experiments/2026-07-09-ambient-video-loops.md`](docs/experiments/2026-07-09-ambient-video-loops.md#round-3-2026-07-10--ltx-23-cinemagraph-lora-benchmark--modified-area-masking-prototype)
  round 3, and the live page
  [`tools/mask-align-exp/gen12/ambientvid/maskexp.html`](tools/mask-align-exp/gen12/ambientvid/maskexp.html).
- [x] **Benchmark LTX-2.3 Cinemagraph LoRA** (HF terms accepted) vs round-2 Seedance/Wan results —
  same subjects + region-scoped prompts via fal ltx lora endpoint (~$0.10-0.15/clip).
  **Outcome (2026-07-10, round 3):** not usable via fal as attempted — the LoRA endpoint
  fetches `loras[].path` anonymously server-side, and HF's gate 403s that regardless of the
  account owner having accepted terms (confirmed via 2 live submitted jobs, both unbilled 422).
  **Round 4 (2026-07-10) unblocked it**: downloaded the gated safetensors via the user's own
  authenticated HF browser session (claude-in-chrome), re-hosted the 201MB file on fal's CDN via
  the real `fal_client` SDK (the naive single-PUT REST pattern 413'd above ~100MB — needed the
  SDK's multipart upload), then pointed `loras[0].path` at the fal URL. Both jobs generated real
  video. **Verdict: mixed, Seedance still wins overall** — diablo-gothic PASS (clean rune pulse,
  no ignition), steam-porthole FAIL (button/gauge icon glyphs dissolve mid-clip, same
  identity-drift failure round 2 saw on base LTX). Round-2 pick (Seedance 1.0 pro fast) remains
  the production model. See
  [`docs/experiments/2026-07-09-ambient-video-loops.md`](docs/experiments/2026-07-09-ambient-video-loops.md#round-4-2026-07-10--unblocking-the-gated-lora-via-browser-download--fal-re-host)
  round 4.
- **Enable emissivity/PBR pass in mainline**: flip PBR_PASS_ENABLED on (orchestrate12) once proven
  across the roster; wire the dashboard card link (WIRE-pbr.md, 2 lines); make the PBR player the
  featured path for skins with strong emissive themes.
  - **2026-07-10 status — dashboard hook wired (item 5 below, done); roster run BLOCKED mid-way
    on fal.ai billing** (`403 User is locked. Reason: Exhausted balance` on `storage/upload/initiate`
    — verified directly against the endpoint, not assumed). Of the 7 PASS skins: **diablo-gothic**
    and **fallout-vault** already had fresh `_pbr/` sidecars (built pre-session) and are dashboard-
    linked — verified live via Playwright, relit render not blank, emissive glows where the spec's
    hint says (diablo: rune/ember cracks; fallout-vault: amber lamps, though the "phosphor terminal
    glow" half of the hint has no coverage — paint's screens are flat/off, nothing bright to
    extract). **steam-porthole** also had a fresh sidecar but its `emissiveCoverage` is **0.0** —
    the paint has no baked bright content behind the portholes/tubes (checked the source paint
    crop: tubes are painted clear/unlit, gauge is a plain dial) — so the pass's headline feature
    is a no-op there; `build_dashboard.py` now gates the card link on `emissiveCoverage>0 or
    lights` (computed per skin, not hand-picked) so its "dynamic lighting" link is withheld rather
    than shown broken. **fa-pod, fallout-pipboy, n64-cutscene, wc-goldshield** never got a patina
    call — blocked on billing, not attempted with a degraded fallback. Re-run once the fal
    account is topped up: `python3 pbr_pass.py assets-<id> && python3 build_player_pbr.py
    assets-<id>` for those 4, idempotent via paint sha. Still gated OFF (`PBR_PASS_ENABLED`
    untouched) — flipping it on is the user's call after reviewing the linked players.

## 2026-07-09 — session close-out backlog

Open/missed/unreviewed items from today's gen12 session (2026-07-09), each written to be
executed cold. Does not duplicate the moiré / ambient-masking / LTX-LoRA / emissivity-mainline
entries already under "saved for later" above — those four stand as-is.

1. **PBR social video re-record — DONE (2026-07-10).** Delivered:
   [2026-07-10-pbr-social-9x16.mp4](file:///Users/conner/Desktop/cc-skeuo/2026-07-10-pbr-social-9x16.mp4)
   + [1x1 cut](file:///Users/conner/Desktop/cc-skeuo/2026-07-10-pbr-social-1x1.mp4) (+ posters,
   provenance sidecar). All spec items executed:
   - **Knob root cause found + fixed generically**: NOT the drift-correction — `diablo-meta3.json`'s
     knob seat came from mainline `assets-diablo-gothic/regions.json` `vol.seat`, and that file has
     been rewritten twice by regen runs since `diablo-src.png` was captured (and is a LIVE moving
     target — another session rewrote it again mid-fix). `extract3.py` now finds the round recessed
     sockets **directly in the rendered paint** (darkness → shape/aspect → radial rim-walk
     circularity), zero regions.json dependency, plus a drift guard that pins all other
     regions.json-derived meta3 fields unless `FORCE_REGEN=1` (a bare re-run had silently
     corrupted seek/shuffle/viz/buttons — reverted from git, guard prevents recurrence).
   - **Second knob added**: the detector finds BOTH sockets; left one now seats the same cap
     sprite, independently draggable (`knob2` in meta3/index.html, `?knob2=` URL param).
     Both knobs verified seated via real pointer-drag + close-up crops in the shipped page.
   - **Non-BPM lighting**: recorder simply doesn't pass `?bpm=` — the page's organic multi-octave
     flicker branch (already in `0a8d7512` as the non-BPM path) drives ember pulse + viz bars.
   - **Choreography re-ordered per spec**: press play FIRST (0-3s) → light sweeps the skulls
     (3-10s) → knob rotates −140°→140° (10-14s) → zoom into the TOP region, both skulls + central
     play/pause glow in frame (14-20s). Probe-verified per-beat before the full render.
   - Stepped frame-by-frame capture (record_social.mjs), 600 frames @30fps per cut, libx264
     crf15; ffprobe + mid-clip frame inspection passed (1080x1920 / 1080x1080 native).

2. **Outline-vs-solid template A/B — DONE, two rounds, verdict delivered.** (2026-07-10)
   Scored + built a served results page across TWO themes (round 2 added on top of the
   original 4-gen round 1, to check whether the finding held on a visually contrasting
   theme):
   - **Round 1 — fa-pod** (bright translucent cyan, `material_is_dark=False`):
     [assets-abshape-a-121](tools/mask-align-exp/gen12/abshape/assets-abshape-a-121),
     `assets-abshape-a-134`, `assets-abshape-b-121`, `assets-abshape-b-134`.
   - **Round 2 — wc-goldshield** (dark gold/royal-blue heraldic shield,
     `material_is_dark=True`): `assets-abshape-wc-goldshield-{a,b}-{121,134}`. Generated via
     `python3 genskin_ab.py ../theme_specs/wc-goldshield.json --cond {A|B} --seed {121|134}`
     from `abshape/` — runs through `genskin_ab.py`'s Vertex-direct `edit_vertex()`
     (gcloud access-token auth), **NOT fal**, so this round is unaffected by any fal
     account lock/unlock status either way.
   - Fixed a real bug in [score_ab.py](tools/mask-align-exp/gen12/abshape/score_ab.py):
     crop coordinates were pulled from the raw per-theme TEMPLATE fraction, but the paint
     model freely rearranges the whole device per generation, so crops landed on the wrong
     control entirely (e.g. "vol" crop showing the repeat button). Fixed to crop from
     `regions.json`'s extract12-DETECTED device bbox instead. Also made both
     `score_ab.py`/`genskin_ab.py` round-aware (theme id folds into dirname/scores-key for
     any non-fa-pod theme, so multiple themes' same seeds don't collide).
   - Served page: [tools/mask-align-exp/gen12/abshape/index.html](tools/mask-align-exp/gen12/abshape/index.html)
     (full-res paint + per-socket close-up crops + score table + verdict, both rounds,
     responsive, model+cost header) — served at
     [http://localhost:54966/abshape/index.html](http://localhost:54966/abshape/index.html),
     verified rendering via headless Playwright at 1400px and 390px.
   - **Verdict** (full text in [verdict.json](tools/mask-align-exp/gen12/abshape/verdict.json)):
     SOLID FILLED guides (B) beat OUTLINE guides (A) — a lean but consistent signal across
     both themes (n=2 seeds × 2 themes = 4 gens/condition; directional, not conclusive). The
     automated leak-% gate doesn't discriminate (~0.14% avg both sides) and MISSES a defect
     visible on every A generation at full-res: a thin ring/bezel in the exact guide hue
     wrapped around sockets and (on wc-goldshield) around transport buttons too — the literal
     un-erased alignment marking the prompt bans. B's guide-colour bleed-through, when it
     happens, gets absorbed as a coherent design element (candy-coloured button, gem medallion)
     instead of reading as a broken ring. The gate that DOES discriminate — emptiness — was a
     wash on fa-pod (1/2 each) but not on wc-goldshield (A 0/2, B 2/2; A baked a solid
     violet-glass fill into the shuffle slot both seeds). Combined emptiness: A 1/4, B 3/4.
     Recommend adopting SOLID guides as the templated-blueprint default. Separately,
     extract12's leak gate should sample button perimeters too (missed a defect obvious to
     the eye) — out of scope here, extract12.py is shared pipeline and wasn't touched.
   - **Not yet done** (left for a follow-up, outside this task's declared abshape/-only
     scope): a `docs/experiments/2026-07-10-abshape-outline-vs-solid.md` writeup per
     [[empirical-testing-rule]] — `verdict.json` + this TODO entry carry the full record for
     now; promote to `docs/experiments/` when next touching this area.

3. **n64-lowpoly disposition — ASK USER before acting.**
   [tools/mask-align-exp/gen12/review-2026-07-09.json](tools/mask-align-exp/gen12/review-2026-07-09.json)
   line 34 has `"n64-lowpoly": {"gate": "fail", "notes": "delete this"}` — an explicit
   human-labeled verdict to delete the theme (per [[human-labeled-data-rule]], this verdict must
   not be silently discarded). But the later 15-skin regen-all run
   (`tools/mask-align-exp/gen12/.regen-start`, `regen-monitor.log`) produced a FRESH
   `assets-n64-lowpoly` (+ `assets-n64-lowpoly_biref`) alongside the pre-existing
   `assets-n64-cutscene` theme. Before deleting anything: confirm with the user whether the
   fresh n64-lowpoly regen supersedes the "delete this" verdict (i.e. keep the new one, the
   complaint was about the OLD render) or whether the whole theme should still be cut. Do not
   delete unilaterally either way.

4. **B-pivot decision + its own experiment record.**
   [tools/mask-align-exp/gen12/bproof/](tools/mask-align-exp/gen12/bproof/) (commit `e8546e22`,
   "B-proof harness") CONFIRMED that heavy constraint-laden prompts measurably degrade paint
   quality — same model/seed/theme, comparing a lean froggo-style prompt (~618 chars,
   `froggo-diablo-gothic.png` / `froggo-steam-porthole.png`) against gen12's constraint-heavy
   prompt (~9k chars, `gen12-diablo-gothic-device.png` / `gen12-steam-porthole-device.png`); see
   the crop pairs (`crop-*-froggo.png` vs `crop-*-gen12.png`) and
   [run_bproof.py](tools/mask-align-exp/gen12/bproof/run_bproof.py) /
   `run_bproof_vertex.py` for the exact method. This was mitigated within gen12's existing
   architecture but the actual architectural fork was never decided or built:
   - **Decide**: adopt a froggo-style **two-pass architecture** — (1) one lean, unconstrained
     "beautiful" paint pass with no socket/legend clutter in the prompt, then (2) a SEPARATE
     detection/mask pass (VLM or CV) that finds control positions on the clean paint — vs
     staying single-pass with prompt engineering as the only lever.
   - **Write it up**: this result is currently only folded partially into
     [docs/experiments/2026-07-09-pbr-delight-emissive.md](docs/experiments/2026-07-09-pbr-delight-emissive.md)
     (which does NOT actually mention it — checked, no `B-proof`/`bproof`/char-count hits in that
     file). Write a standalone `docs/experiments/2026-07-09-bproof-prompt-length.md` per
     [[empirical-testing-rule]]: question, method (model/seed/char-counts), the crop comparisons
     as evidence, and the verdict once decided above.

5. [x] **Dashboard PBR-player link hook — DONE 2026-07-10.**
   [tools/mask-align-exp/gen12/WIRE-pbr.md](tools/mask-align-exp/gen12/WIRE-pbr.md)'s hook wired
   into [build_dashboard.py](tools/mask-align-exp/gen12/build_dashboard.py): per-skin card links
   `assets-<id>/player-pbr.html` when it exists AND its `_pbr/meta.json` shows real emissive
   output (`emissiveCoverage>0 or lights`) — not just file-existence, so a built-but-glow-less
   PBR player isn't advertised as "dynamic lighting". Also fixed the 18-vs-15 skin-count glob bug
   (excludes `_biref`/`_pbr` sidecar dirs and any `abshape/`/`bproof/` subtree). Roster run status
   (which skins actually got PBR'd): see the "Enable emissivity/PBR pass in mainline" entry above.

6. **User reviews pending (nothing acted on yet):**
   - **Vizlab visualizer lookdev pick** —
     [tools/mask-align-exp/gen12/vizlab/index.html](tools/mask-align-exp/gen12/vizlab/index.html)
     (commit `302a6cf3`, served at the time via `http://localhost:54731/vizlab/index.html` — reserve
     with `~/dev/central/scripts/serve tools/mask-align-exp/gen12 --bg` if the port is dead).
     8 theme-connected visualizer styles built (phosphor CRT, ember/lava sparks, fluid/ripple,
     brass steam gauges, low-poly dither, oscilloscope, emissive-bezel [PBR-coupled], aurora).
     Top-3 recommendation given but NOT confirmed: steam gauges → porthole theme, ember → diablo
     theme, emissive-bezel → universal (any PBR-enabled skin). Needs the user's actual pick before
     wiring a style into `build_player.py`.
   - **Template Studio agentic-canvas mode** — [src/generate/AgentObserver.tsx](src/generate/AgentObserver.tsx)
     + [src/generate/agentObserver.css](src/generate/agentObserver.css) (commit `4c7c177a`): a
     glowing-cursor reticle that stages the circle-fit knob snap and slider coverage-span walk as
     live "agent motion" on the template canvas, auto-opens with generation, manual "👁 Watch agent"
     toggle under the preview. Verified headless at 1400px/420px only — needs a live `npm run dev`
     look in the real app before calling it reviewed.
   - **ComfyUI workflow visibility confirm** — two workflows were exported this session into
     `~/ComfyUI-Installs/Local/ComfyUI/user/default/workflows/`:
     `jul0926-0914-skeuo-gen12.workflow.json` and `jul0926-1014-skeuo-gen12-local.workflow.json`
     (confirmed present on disk, graph-format). Per the `comfyui` skill/rule, verify against
     whichever ComfyUI install is actually the LIVE one (port 8188 `lsof` check) — this session
     did not confirm that install is the one the user has running, only that the files exist.
   - **3rd-pass specular subtlety verdict** — [build_player.py](tools/mask-align-exp/gen12/build_player.py)
     received successive specular/press-ink passes across commits `e8546e22` → `f80484b8` →
     `55d2dfcd` (material-tinted specular → luminance-adaptive press ink → subtler knob specular +
     exact-silhouette pressed-button depression). No recorded user sign-off on whether the 3rd pass
     (`55d2dfcd`, "subtler knob specular") actually reads correctly across the roster — needs a
     fresh-eyes look at rendered players, not just the commit log.

7. [x] **wmp-vario fresh-gen review — verify vertical seek + d-pad detection. DONE 2026-07-10,
   mixed result.** Verified against the REAL rendered `wmp-vario/player.html` (headless
   Playwright, not the extractor JSON alone): (a) **d-pad PASS** — playpause/prev/next/repeat/
   queue are 5 distinct detected regions with distinct icons, not merged into one blob; (b)
   **seek is HORIZONTAL in this committed generation, not vertical** — `regions.json`'s `seek`
   region has no `vertical` key (device bbox is wide/short: w=0.535 h=0.038), so it legitimately
   fell back to horizontal — the `templateless` theme_prompt never requested a vertical layout
   and this seed just didn't paint one; the tall vertical pill visible in the render is the
   `shuffle` toggle, not seek. This is NOT a code bug: `extract12.py`'s `VERT = (h>w*1.3)`
   detector correctly read the painted groove's real aspect. **No committed skin currently has
   `vertical: true` on its seek** — the vertical-slider code path (commits `8f8c38e5`/`7b5d0f22`)
   has never been exercised by a real generation. Sanity-checked the CODE PATH itself with a
   synthetic `regions.json` (fabricated `vertical: true` + tall device rect, scratch copy in
   `/tmp`, cleaned up after) — the thumb rendered on the vertical groove and `window.__seek(d)`
   moved it along Y correctly, so the rendering/drag logic works; it's just never been triggered
   by a real paint. Getting a real vertical-seek exemplar needs a regen with a prompt nudge
   toward a vertical layout (or luck) on some future roll.

8. **Fresh-regen landed — 7/15 PASS, committed `46574f6c`.** Per-skin history/reasons:
   `tools/mask-align-exp/gen12/assets-*/orch.json`. Follow-ups from closing this out below.

9. [x] **Gate bug fixes (user-approved 2026-07-09) — DONE 2026-07-10.**
   Do NOT restore mirror-opposite state scoring, user likes the protruding/asymmetric switch look:
   - **Fixed.** `state-align` gate in [extract12.py](tools/mask-align-exp/gen12/extract12.py)
     scored raw silhouette IoU≥0.9 between OFF/ON toggle cuts, penalizing legitimately
     creative/asymmetric switches (lever moved to the opposite end = different silhouette by
     design). Dropped the IoU floor to 0.05 (only catches near-total-disjoint/broken states);
     kept the existing scale-ratio bounds (0.7–1.4) as the "wildly different scale / collapsed
     speck" check — verified this still correctly fails `wmp-quicksilver` (scaleX 1.90/scaleY
     0.56, a genuinely broken ON-state render, confirmed by eye) while now correctly passing
     `claymation`/`fa-sky`/`ps1-crunchy` (legit asymmetric designs, IoU 0.58–0.79). Re-ran
     `extract12.py` against the existing committed assets (no fal spend) to confirm: 3 of the
     8 original FAILs (claymation, fa-sky, ps1-crunchy) now gate-PASS on their EXISTING paint —
     no regeneration needed.
   - **Fixed.** The gross-leak check (`leak > 0.003`) could set `PASS=False` with no matching
     `reasons.append` — added `reasons.append(f"leak={leak_val}")`. Confirmed live: re-extracting
     `ps1-wild` now reports `reasons=['leak=0.00739']` instead of an empty list.
   - [x] `build_dashboard.py` 18-vs-15 glob fix — done by another agent in `bf3366ab`.

10. [x] **N64 respec — DONE 2026-07-10.** User verdict: the old `n64-lowpoly` was "crap... i
    meant n64 cutscene render, not lowpoly n64 garbage... make it more a character stylized in
    that render style, not literally just n64 as the prompt." Retired `n64-lowpoly` entirely
    (`theme_specs/n64-lowpoly.json` + `assets-n64-lowpoly` + `assets-n64-lowpoly_biref`, via
    `trash`). Authored
    [theme_specs/n64-prerender-character.json](tools/mask-align-exp/gen12/theme_specs/n64-prerender-character.json)
    (id `n64-prerender-character`, templateless, same 10-control roster/lighting-block shape as
    siblings): a CHARACTER-CENTRIC mid-90s pre-rendered promotional CG look (Rare Ltd. Donkey
    Kong Country / Killer Instinct box-art register, SGI-workstation-cutscene register) — a
    stylized creature/animal-mascot bust sculpted into the top of the housing as the dominant
    feature, glossy injection-molded-plastic shading with soft raytraced highlight streaks,
    chunky gouraud-faceted forms. Prompt never uses the literal token "N64". Palette validated
    via `genskin.py --blueprint-only` (had to retune the 5 guide-key majors once — the first
    draft's saturated red/blue/near-white trio only left 7/10 usable guide keys; muted them
    to 14/10 survivors). **Generated 2026-07-10: PASS on roll 2 (seed 823)** — a glossy
    orange dinosaur-mascot bust fused with the player body, exactly the intended register;
    all 10 controls seated (observed + VLM-checked); one defect: baked "ON" on the toggle
    (see 11b).

11. [x] **Re-roll batch DONE 2026-07-10** (fal was exhausted-balance-locked in the morning —
    the cause of every `KeyError: 'upload_url'` in the `46574f6c` orch histories — user
    topped up same day, unlock re-verified by curl). 8 skins rolled through the FIXED gate,
    ≤4 concurrent, ~22 rolls total: **6 PASS** — claymation (r1), ps1-crunchy (r1),
    wmp-vario (r1), myst-arcanum (r2), n64-prerender-character (r2), wmp-quicksilver (r4) —
    **2 honest FAILs at 4 rolls** — fa-sky (emptiness), ps1-wild (region-misplaced:album_art
    + emptiness + state-align; its ON cut is a different housing WITH a baked "ON" label —
    the 1.4 scale bound caught a real break, not creative asymmetry). All FAIL reasons were
    model-side per the [generation-spend rule](/.claude/rules/generation-spend-rule.md);
    nothing was extractor-recoverable for $0. Dashboard rebuilt: **auto 13/15**.

11b. **Baked ON/OFF toggle text — the dominant remaining paint-defect class (4 of 7
    observed skins: myst-arcanum, wmp-vario, wmp-quicksilver, n64-prerender-character).**
    Found by the new observation pass ([observe12.py](tools/mask-align-exp/gen12/observe12.py)
    + [observe_drive.mjs](tools/mask-align-exp/gen12/observe_drive.mjs), per the
    skin-observation + sota-eye-review rules; per-skin verdicts committed in
    `assets-*/observe/observe.json`, eye = `google/gemini-2.5-pro` via fal
    `openrouter/router/vision` ~$0.02/skin; screenshot/crop PNGs regenerable, gitignored).
    genskin.py's prompt already forbids ON/OFF text but the model keeps labelling the ON
    state — the "OFF/ON state" wording itself is the likely semantic pull. Recommended
    generalizable fixes (NOT applied — needs seed-validation spend): (a) reword the SHUFFLE
    STATES clause to avoid the tokens ON/OFF ("state A / state B", "engaged / disengaged");
    (b) wire `observe12.py --vlm` into `orchestrate12.py` as a flag-gated post-PASS text
    gate so a labelled toggle re-rolls automatically. Also caught, gate-invisible:
    myst-arcanum icon-region mismatch (a ▶|| icon sits in the `prev` region while the
    `playpause` region is an iconless gear well — clicking the visible ▶|| fires prev) and
    claymation's degenerate 24×31px album_art region (min-region-size gate candidate).
    Adjudication note: the VLM also claimed myst's vol/seek sprites "missing" — overruled
    by direct crops (both clearly seated); its baked-text calls were all confirmed by eye.

12. **Human review of the 13 auto-PASSes — not yet reviewed.** The original 7 (diablo-gothic,
    fa-pod, fallout-pipboy, fallout-vault, n64-cutscene, steam-porthole, wc-goldshield) plus
    the 6 fresh 2026-07-10 re-rolls (claymation, myst-arcanum, ps1-crunchy, wmp-vario,
    wmp-quicksilver, n64-prerender-character — VLM observation verdicts + notes in each
    `assets-*/observe/observe.json`, 4 flagged for baked toggle text per 11b). User's note
    closing the previous session: "the skins are getting uglier tho" — the stricter gate may
    be passing technically-correct but less visually striking generations. Re-serve
    `tools/mask-align-exp/gen12` and open
    [dashboard12.html](tools/mask-align-exp/gen12/dashboard12.html) for the pass/fail/notes gate.

13. **Done — CSS seek progress track/fill, under the sprite thumb (`gen12/build_player.py`,
    `SEEK_TRACK_CSS_ENABLED` flag).** A subtle recessed track + brighter progress fill, colored
    by sampling the groove's own paint pixels and sized by an adaptive luminance-profile scan of
    the groove's cross-axis (not a hand-tuned constant — avoids bezel overflow across skins of
    different groove-to-bezel ratios), spans the full `travel` extent, updates live on drag and
    on arrow-key seek, handles horizontal + vertical orientation. Verified on diablo-gothic,
    fa-pod, steam-porthole (close-up crops at 3 drag positions each) + a synthetic vertical-seek
    rig (no passing skin has `vertical:true` yet, so the orientation branch was smoke-tested
    against a rotated copy of fa-pod's regions).
