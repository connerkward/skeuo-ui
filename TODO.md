# skeuo-ui — TODO

## Open

- [ ] **Float the player as an always-on-top mini-player (Document Picture-in-Picture).**
      The `documentPictureInPicture.requestWindow()` API (Chrome 111+, verified mature 2026)
      floats arbitrary DOM in an always-on-top window — a perfect fit for skeuo.fm: a
      **"pop out"** button on the website that detaches the current skin's `<Composite>`
      into a floating mini-player the user keeps visible over other tabs/apps while they
      browse (the in-browser equivalent of the Tauri desktop widget, zero install). Carry
      the skin's stylesheet into the PiP doc, move the player node in, restore on close;
      transport keeps driving the same audio engine (local/Spotify). Requires a user
      gesture to open (browser anti-abuse rule — can't auto-fire on load). Prototyped the
      mechanics in the Spotify-connect wizard (`/tmp/skeuo-wizard/`, the "⧉ Float" button).

- [ ] **Restore the "Play here" switch** (removed 2026-06-18). The in-page Web
      Playback SDK device (`playHere`/`setPlayHere` in `useSpotify`, `sdk.ts`,
      `initWebPlaybackSDK`) lets a Premium user play audio in the page/tab itself
      instead of on an external Spotify Connect device. The UI toggle was pulled
      from `SpotifyConnect.tsx` for now (the hook plumbing is left intact, just
      unused). Re-add the `<label className="sp-toggle">` checkbox (desktop/web
      only — gate with `!isMobileApp()`, since iOS WKWebView lacks EME/Widevine)
      when we revisit in-page playback.

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
