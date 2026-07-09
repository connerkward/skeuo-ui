# WIRE-pbr — hooking the PBR/emissive pass into mainline gen12

The pass itself is self-contained in **new files** (built while a full roster regen held
`build_player.py` / `extract12.py` / `genskin.py` / `orchestrate12.py` / `build_dashboard.py`):

- `pbr_pass.py <assets-dir>` — per-skin: ONE `fal-ai/patina` call (5 maps, ~$0.02/skin at
  1.6MP), glyph-emissive extraction (top-hat method, honors the spec's `lighting` section),
  paint-derived per-region glass masks (viz/art), btn-ids, point lights → `assets-<id>_pbr/`.
  Idempotent: skips when `meta.json` src sha matches `paint.png` (`--force` to redo,
  `--no-patina` to skip the hosted call).
- `build_player_pbr.py <assets-dir>` — emits `assets-<id>/player-pbr.html` (PBR-lit
  interactive player; links back to `player.html`).

## Feature flag (feature-flag-rule — gate BOTH ends, default OFF)

- **Pipeline:** `PBR_PASS_ENABLED` in `pbr_pass.py` (default `False`) gates the orchestrate
  hook below — flipping it on adds ~$0.02–0.03/skin patina spend to every roll. Direct CLI
  runs are explicit opt-ins and ignore the flag.
- **Per-spec:** `"lighting": {"enabled": false}` in a theme spec skips the pass entirely
  for that skin (no patina call, no extraction, no player build) even when run directly.
- **UI:** the PBR player is a separate `player-pbr.html`; `player.html` stays the default.
  It links back; the forward link + dashboard offer are the hooks below.

## Pending 1–3 line hooks (apply after the regen agent's commits land)

1. **genskin.py** — pass the director's lighting through to the pipeline (pbr_pass falls
   back to reading `theme_specs/<id>.json` directly, so this is a nicety, not a blocker):
   ```python
   # in the res dict (~line 191):
   "lighting": spec.get("lighting", {}),
   ```

2. **orchestrate12.py** — after the `build_player.py` run (~line 49):
   ```python
   from pbr_pass import PBR_PASS_ENABLED   # or read the const via import
   if PBR_PASS_ENABLED:
       run(["python3", "pbr_pass.py", ASSETS])
       run(["python3", "build_player_pbr.py", ASSETS])
   ```

3. **build_dashboard.py** — per-skin card: when `assets-<id>/player-pbr.html` exists, add a
   second link next to the player link:
   ```python
   pbr = os.path.exists(os.path.join(assets_dir, "player-pbr.html"))
   # in the card html: f'<a href="assets-{sid}/player-pbr.html">✨ dynamic lighting</a>' if pbr else ''
   ```

4. **build_player.py** (plain player) — optional opt-in toggle in the `.sub` header line:
   ```python
   # only when the sibling exists:
   ' · <a href="player-pbr.html" style="color:#8fb4ff">✨ dynamic lighting</a>'
   ```

## Theme-spec `lighting` schema (director-authored, all 15 specs populated)

```json
"lighting": {
  "enabled": true,                       // per-skin kill switch for the whole pass
  "emissive_hint": "the red runes …",    // prose for humans + future prompt use
  "emissive_color": [255, 90, 40],        // hue bias for the extractor, or "auto"
  "pulse": "ember|phosphor|breathe|none",// player pulse style
  "intensity": 1.3,                      // 0..2 — player default emissive intensity
  "viz_emissive": true,                  // visualizer registers as an emissive source
  "beat_couple": 0.07                    // 0..0.15 — subtle BPM-coupled pulse component
}
```

## Player-side dynamic-emissive-source registry (for future director-declared sources)

```js
window.registerEmissiveSource({
  name: 'seek-underglow',
  rect: [x, y, w, h],              // src-uv (x/W, y/srcH)
  canvas: htmlCanvas,              // OR draw(ctx, w, h, t)
  mask: {img, rect},               // optional paint-derived shape clip
  intensity: 1, enabled: true,
});
```
All sources are composited into a two-level low-res gather (tight+wide blur) each frame; the
shader lights the body from it. The visualizer is source #0; `?emdemo=1` registers demo
sources (seek-slot underglow, knob-pointer glow). `?bpm=` sets the shared beat clock
(default 118 — future: Spotify tempo).
