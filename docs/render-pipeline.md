# Render pipeline — IG-story exports + sequence-editor handoff

Runbook for reproducing the skin video/still exports and handing a reel off to the
multi-clip editor for beat-cutting. Written so a **fresh Claude Code window** can run
it top to bottom without re-deriving anything.

Two repos are involved:
- **this repo** (`skeuo-ui`) — generates the clips/stills (`capture.mjs`, `make_seq.py`, `scripts/render-pass.sh`).
- **the NLE skill** — `~/dev/central-skills/screen-studio-alternative` (`sequence.py`), the editor you drop the clips into. Central pointer: the `demo-polish` skill.

---

## 0. Start the dev server ON PORT 5210 (not the default)

`capture.mjs` hardcodes `BASE = http://localhost:5210/export.html`. Vite's config
serves **5173** by default, so you MUST override the port or capture hits nothing:

```bash
cd ~/dev/skeuo-ui
npm install                 # first time in a fresh checkout/worktree only
npm run dev -- --port 5210  # leave running; capture.mjs talks to this
```

Verify: `curl -s -o /dev/null -w '%{http_code}\n' http://localhost:5210/export.html` → `200`.

---

## 1. One-command full pass (singles + scenes + sequences)

```bash
bash scripts/render-pass.sh ~/Desktop/skeuo-skins/pass   # outdir is optional
```

Renders **sequentially** (live composites are heavy; concurrent captures stomp the
dev server — do NOT parallelize the captures). Produces, into the outdir:
- `hero-<skin>-1080x1920.{png,mp4,gif}` for the SINGLES list
- `mg-<scene>-1080x1920.mp4` for streams/swarm/parade/cascade/fan/fanout + orbit (maw, tomato centers)
- `seq-A/B/C-*.{mp4,gif}` reels

Edit the `SINGLES` / `SCENES_PLAIN` lists at the top of `scripts/render-pass.sh` to
change what gets rendered.

---

## 2. Granular commands (when you don't want the whole pass)

```bash
# hero single → still PNG + mp4 + 15fps gif (comma-list renders several)
node capture.mjs hero <outDir> frog,bondi,pebble "" 5

# motion-graphics scene (streams|swarm|parade|cascade|fan|fanout|orbit)
node capture.mjs mg <outDir> orbit "center=bondi" 9 mg-orbit-bondi
node capture.mjs mg <outDir> streams "skins=burger,bondi,biomech,pebble,wmp" 9

# static contact-sheet stills (grid|sprites|fan|center|scatter); "-" = default skins
node capture.mjs grid <outDir> frog,bondi,pebble,halo,burger,maw

# env knobs:
CAP_MAXRES=1 node capture.mjs hero <outDir> bondi "" 5   # 2160×3840 (max-res IG source) instead of 1080×1920
CAP_WARMUP=120 node capture.mjs mg <outDir> fanout ...    # lower warmup to catch a one-shot intro (e.g. fan-in fly-in)
```

Output is deterministic frame-stepped (CDP virtual time) — sharp @2x, zero dropped
frames, no stutter, no grey padding. Do not revert to `recordVideo`; that reintroduced
both the grey and the stutter.

---

## 3. Build a reel video ("sequence C" style)

`make_seq.py` concatenates per-skin hero mp4s (must already exist in `<outdir>` from
step 1/2), each shown `<dur>` s, hard cuts, in the order you pass:

```bash
python3 make_seq.py <outdir> seq-C-snap-1.2s 1.2 bondi,obelisk,maw,pebble,wmp,halo,burger,frog,biomech
```

The order is chosen so similar colors never sit adjacent. **Sequence C** (the one that
landed): `dur=1.2`, order `bondi,obelisk,maw,pebble,wmp,halo,burger,frog,biomech`.

---

## 4. Hand the clips to the editor (beat-cut handoff)

Instead of (or in addition to) a baked reel, drop the hero clips into the multi-clip
editor so you can reorder/trim/beat-cut interactively.

```bash
# render heroes for the skins you want (all live skins shown here; trim the list as needed)
node capture.mjs hero ~/Desktop/skeuo-skins/clips \
  frog,bondi,manray,maw,halo,wmp,burger,biomech,tomato,vortex,frog2,slab,mexico,flesh,bondi2,spore,scarab,toilet2,biomech2,pebble,fiend2,obelisk,burger2 "" 5

cd ~/dev/central-skills/screen-studio-alternative
rm -f .studio-out/seqclips/*.jpg     # IMPORTANT: clear stale thumbnail cache if clips changed (see gotcha)
# explicit file order == timeline order:
python3 sequence.py \
  ~/Desktop/skeuo-skins/clips/hero-frog-1080x1920.mp4 \
  ~/Desktop/skeuo-skins/clips/hero-bondi-1080x1920.mp4 \
  ~/Desktop/skeuo-skins/clips/hero-manray-1080x1920.mp4 \
  ...                                  # (or just pass the folder to seed alphabetically)
```

It prints an `http://127.0.0.1:<free-port>` URL. In the browser:
1. Click **▸ beat-cut** (the submode tab next to the title).
2. Type or tap the **BPM**, pick a segment length (½ / 1 / 2 / 4 beats), hit **Cut to beat** — every clip snaps to the same beat-aligned length, locked.
3. **Export video** (1080p 60fps mp4) or **Export FCPXML** (opens non-destructively in Resolve/FCP/Premiere). ⌘Z / ⌘⇧Z undo/redo.

### Available skins
Whatever directories exist under `public/skins/` are renderable. As of this writing:
`biomech biomech2 bondi bondi2 burger burger2 chacmool cupcake egypt fallout fiend2
flesh frog frog2 halo manray maw mexico obelisk pebble poophero scarab slab spore
stonehead toilet toilet2 tomato vortex winamp wmp worldcup`.

---

## Gotchas (these cost time before; don't rediscover them)

- **Port 5210, not 5173.** `npm run dev` alone serves 5173; capture silently hits nothing. Always `--port 5210`.
- **Stale thumbnail cache in the editor.** `sequence.py` caches clip thumbnails under
  `.studio-out/seqclips/<clipid>.jpg` keyed by clip id (`c0`, `c1`, …). If you re-seed
  with different clips in the same id slots, you get the *previous* run's thumbnails
  (this is how a blue Bondi once showed a color-bar test pattern). `rm -f
  .studio-out/seqclips/*.jpg` before relaunch whenever the clip set changes.
- **Render captures sequentially.** Live composites are heavy; parallel captures stomp
  the shared dev server and yield blank frames. The pass script is sequential on purpose.
- **The editor's preview can't decode video in the Claude-automation browser** (readyState
  stays 0, no error). That's a headless-decode limitation, not a codec bug — it plays
  fine in your real Chrome. Verify exports there, not in the automation tab.
