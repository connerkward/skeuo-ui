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

## Theme-spec `css` schema (director-authored, CSS-rendered player chrome)

Sibling of `lighting` — the director's spec also fixes the **flat CSS colors** the plain
player (`build_player.py`, `SEEK_TRACK_CSS_ENABLED`) paints for chrome it renders itself
(no sprite/paint pixels involved): the recessed seek track, its progress fill, and the
canvas visualizer's accent. Additive to every `theme_specs/<id>.json` — a spec without
this block still works (see fallback below).

```json
"css": {
  "track": "#232120",   // recessed seek-groove tone — dark, low-chroma; the "shadow" the
                         // thumb rides in. Usually a darkened tarnished/dark-metal/ink palette entry.
  "fill":  "#d27828",    // progress-fill tone — the theme's signature material/metal color
                         // (brass, ember, phosphor-green, gold…), read at full saturation.
  "accent":"#961e1e",    // visualizer-bar / highlight accent — a contrasting pop color from
                         // the palette, distinct from `fill` so the bars read against the track.
  "glow":  "#ff5a28"     // glow/pulse tint — matches `lighting.emissive_color` when the spec
                         // defines one (ember, phosphor, LED…), else a lightened palette entry.
                         // Reserved for future glow/pulse effects in the plain player and for
                         // pbr_pass's dynamic-lighting pass to consume as a director-fixed hue.
}
```

Choose each hex from the spec's own `palette` (or `lighting.emissive_color` for `glow`) so
the chrome reads as *part of the device*, not a generic UI overlay — e.g. diablo-gothic's
`fill` is its `ember` palette entry, fallout-pipboy's `fill` is `phosphor_green` (its CRT
color), wc-goldshield's `accent` is `royal_blue` against a `gold` fill.

**Fallback (no build_player.py hard-require):** when a spec has no `css` block (or a key is
missing), `build_player.py` samples the groove/visualizer-region paint pixels itself (the
prior behavior) — same avg-pixel-tint mechanism as the knob specular tint. Director colors
are preferred; paint-sampling is the safety net, never a silent break.

## Director-specified knob tick provisioning (`ticks` schema, sibling of `css`/`lighting`) — DONE 2026-07-11

The volume knob has TWO independent visual axes for a tick/index-mark treatment, and the
director decides EACH separately, per skin:

```json
"ticks": {
  "skin":   "baked" | "css" | "none",   // the tick-arc / index marks framing the SOCKET BEZEL
  "sprite": "baked" | "css" | "none"    // the pointer/indicator treatment on the rotating CAP
}
```

- **`skin`** — the static ring of tick/index marks on the panel immediately surrounding the
  knob socket. `"css"` renders `build_player.py`'s deterministic SVG tick-arc ring (11 ticks,
  3 major/8 minor, `multiply`+`screen` engraved-look pass, computed from `regions.json`'s
  KNOWN socket centre/radius — themed via `css.accent` when the spec supplies one). `"baked"`
  asks `genskin.py`'s paint prompt to bake an equivalent mark system into the panel material
  itself (light clause — see below) and suppresses the CSS ring so the two never double up.
  `"none"` renders neither.
- **`sprite`** — the moving indicator on the knob cap: a short needle tracking live `val`
  (`"css"`, independent of any baked pointer — matters most when `knob_zero_deg` is `null`),
  a prompt-requested painted pointer/notch on the cap itself (`"baked"` — the SAME kind of
  mark `extract12.py`'s `detect_knob_zero_deg()` already looks for), or neither (`"none"`).
- **Backward-compat default:** a spec without a `ticks` block behaves as
  `{"skin":"css","sprite":"css"}` — the prior, pre-director-schema global `KNOB_TICKS_ENABLED`
  behavior. `KNOB_TICKS_ENABLED` itself stays as a master kill-switch over BOTH axes.

**Why per-axis, not one flag:** the baked-tick experiment
([`docs/experiments/2026-07-11-knob-tick-provisioning.md`](../../../docs/experiments/2026-07-11-knob-tick-provisioning.md))
found 0/8 adjudicated PASS for a heavier clause that named positions (`MIN`/`MAX`/`CENTER`
baked in as literal engraved TEXT). The clauses now shipped in `genskin.py`
(`ticks_skin_bullet`/`ticks_sprite_bullet`) are deliberately LIGHT — they describe the
physical mark only ("a swept ring of tick or index marks", "one small pointer or index
mark"), never a position-label word, never an angle number — an explicit user directive
("dont overconstrain tick marks style") in response to that experiment's failure mode. This
is a NEW, untested-at-scale clause, not a re-run of the failed one; treat "baked" specs as an
open bet on the next regen, not a proven result.

**CRITICAL caveat — "baked" only manifests on FUTURE regenerations.** Choosing `"baked"` for
a skin does NOT retroactively add ticks to its EXISTING `paint.png` — that pixel data was
generated before this schema existed and simply has no baked tick marks to show. So for the
14/15 skins whose paint predates this change (see population table below), the *only*
observable effect of choosing `"baked"` right now is that the CSS tick overlay on that axis
**disappears** (a visible regression versus the prior all-CSS shipped behavior) until the
skin is regenerated through `genskin.py` with the new clause live and the paint verified to
actually carry the marks. This was verified directly: `assets-steam-porthole/player.html`
(spec: baked/baked) shows a plain knob with no CSS ring and no baked ring either — the correct,
if visually poorer, behavior for an as-yet-unregenerated "baked" choice.
**Open question (not resolved here, tracked in TODO.md):** should `build_player.py`
auto-fall-back to CSS when a "baked" spec's actual paint is detected to lack tick marks (no
robust detector for that exists yet — this is not the same signal as `knob_zero_deg`, which
only detects the CAP's pointer, not a bezel tick ring), or should "baked" always mean "no CSS
overlay, whether or not the paint delivered"? Left as an explicit open question rather than an
invented policy.

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
