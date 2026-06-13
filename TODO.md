# skeuo-ui — TODO

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
- [ ] **Name decision** (A Knobgoblin / B Beastbox / C Organa / D Frankenamp).

## Generation feature — production hardening (from the build agent)
- [ ] Loose alpha mask: `/api/generate` uses the constant region mask, so the silhouette doesn't trace horns/jaws like the Python pipeline (which thresholds the envelope PNG). Add a server-side envelope-threshold pass to tighten it.
- [ ] Frames returned as ~7.6 MB data: URLs — bind an R2 bucket (uncomment `SKINS` in wrangler.toml) and store + re-compress instead.
- [ ] Rate limit is in-memory (per-edge, not durable) — move to KV or Durable Objects for a real cap.
- [ ] Synchronous request (~75s) — a "pending" poll branch exists in the contract but no queue is wired; add one before real traffic.

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
