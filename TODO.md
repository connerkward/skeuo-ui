# skeuo-ui — TODO

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

- [ ] **CD album-art visualizer — MERGE the `cd-visualizer` branch to main (2026-06-23).**
      It didn't regress and doesn't need git archaeology — it was **built this session on a
      branch and never merged**. The full feature lives on branch **`cd-visualizer`** (worktree
      at **`../skeuo-ui-cd-visualizer`**), 6 commits ahead of main:
      - `3bce622` player: add `cd` + `albumart` dynamicTypes (spinning mock-CD + bare album-art
        element), `Track.cover` plumbed from Spotify `album.images` in `useSpotify`, authorable
        in the wizard (screen palette cycles visualizer→cd→albumart→…).
      - `c874865`→`ad11bab`→`7c34add`→`9b060b4`→`1a6bdc0`: the disc look + motion — settled on a
        **silver data-side disc** (generated texture, recentred so it doesn't wobble) with an
        album-color tint, and a **physically-grounded spin-up / inertial coast-down** at
        full-speed cruise with speed-proportional motion blur. Verified live on the pebble skin.
      - **NEXT:** merge `cd-visualizer` → `main` (check it doesn't collide with the worker-cutout
        changes that landed on main since the branch forked; rebase if needed), `git worktree
        remove ../skeuo-ui-cd-visualizer`, then deploy. The `albumart` element gives the no-disc
        fallback for local/demo mode with no Spotify art.

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
