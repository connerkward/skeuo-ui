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

## Follow-ups
- [ ] **Isolate the reference-steering effect.** Mechanism is wired + runs, but the winamp material prompt already implies chrome, so War Slab doesn't independently prove the ref moved the output. Generate a no-ref control of the same blueprint and diff, OR steer with a strongly off-prompt reference (e.g. a bright reference on a dark style) to confirm influence.
- [ ] **Capture real homage references.** WMP9 / Halo 2 / noirotic / Illusion screenshots were never obtained as files. Drop them in `assets/refs/` and regenerate `wmp` / `halo` with `--ref` so the homages actually trace the source UIs.
- [ ] **Diversity is 3 new bodies, not a sweep.** The older blob-like sculpts (frog2, burger2, bondi2, toilet2, biomech2, fiend2) predate the relaxed prompt. Regenerate them to break the morphological sameness across the whole set.
- [ ] **Wide/low bodies must route to `capsule`/`minimal`.** The vertical-stack grammars (classic/hero/flank) need a portrait torso; a squat body fails `usable()`. Consider auto-selecting the grammar from the silhouette's aspect ratio instead of passing it by hand.
- [ ] **EQ/playlist crowding on hero (obelisk).** The hero center-play band is busy on a tall body; revisit spacing.
