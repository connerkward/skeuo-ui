# TODO — studio.py

Three deferred items (FCPXML pan calibration, naming/marketplace prep, speed-map
dedup) — see **Open / deferred** below. Nothing blocking.

## Done

- Frame styling (backdrop gradient + padding + rounded corners + drop shadow) — live preview + export. ✓ (2026-06-11)
- Crisp synthetic cursor (4× supersampled macOS arrow, fixed screen-size). ✓ (2026-06-11)
- Background-aware click ripple (dark ring on light, light on dark). ✓ (2026-06-11)
- Smooth cursor always-on (removed the checkbox). ✓ (2026-06-12)
- Motion blur removal (parameter, code, UI). ✓ (2026-06-12)
- **NLE-style speed editing — the final model.** Three iterations to get here; what
  was wrong and what's right, so it isn't relearned:
  1. ✗ Edge-drag retimed the idle RANGE (which footage is sped) — wrong thing to edit,
     and the fit-to-width bar rescaled everything on each change (read as jank).
  2. ✗ Removing speed editing entirely — too far; the RATE must stay adjustable.
  3. ✓ **Fixed ruler + rate-only editing** (FCP retime handle / Premiere Rate Stretch):
     bar width = source duration, never rescales → upstream always planted. Speed
     blocks render at output-time width (`L/speed`); source range locked. Select →
     inspector slider, or drag right edge = rate-stretch (`sp = L/(cursorOut − oL)`,
     exact, no feedback). Changing a rate ripples downstream only; a dimmed
     `.tlend` shade marks empty track past end-of-content. Verified in-browser:
     left edge + upstream planted, downstream slides, slider + stretch both live,
     preview playbackRate clamped to the browser's 16× cap. ✓ (2026-06-12)
- **Click sound** = freesound #735771 "Mouse Clicking" (BiORNADE, CC0), picked by ear
  from an 8-candidate audition (`~/Desktop/click-sounds/`). ✓ (2026-06-12)
- README + screenstudio-alt SKILL.md updated to match. ✓ (2026-06-12)
- **Single-screen app shell** — rebuilt from a scrolling page into a fixed-viewport
  tool: `overflow:hidden`, topbar / preview-monitor + style rail / docked timeline.
  Overflow gate clean at 390 / 1024 / 1440. ✓ (2026-06-13)
- **Docked inspector** — the floating idle popover now docks at the right of the
  timeline (Fitts: clip props adjacent to the clip, not a far panel). Empty state +
  `has-sel` populated state. ✓ (2026-06-13)
- **Undo / redo** (⌘Z / ⌘⇧Z) over `{regions, speedSegs}` JSON snapshots, debounced
  per gesture; Delete key removes the selected clip. ✓ (2026-06-13)
- **Real progress ring** — export polls `/progress` (written by `render.py
  --progress-file`) and drives a circular SVG ring, replacing the fake time estimate. ✓ (2026-06-13)
- **Named, actually-downloading export** — `Content-Disposition: attachment` +
  `<stem>-studio.mp4` save-as name (was served inline → browser just played it). ✓ (2026-06-13)
- **Fit + background options** — `--fit cover/contain` for non-16:9 sources and a
  blurred-backdrop style (`--bg blur`); fixed the double-resize that broke fill crops. ✓ (2026-06-13)
- **Timeline fits width by default** — ruler now spans the OUTPUT duration so the cut
  fills the track at zoom 1 (dropped the `.tlend` headroom shade referenced above);
  `#tzoom` slider zooms 1–8×. ✓ (2026-06-13)
- **FCPXML export** (`fcpxml.py`) — split asset-clips with adjust-transform
  scale/position keyframes baking the cosine ease + per-clip speed timeMap; auto-download
  from the editor. Pan still needs a real Resolve round-trip to calibrate. ✓ (2026-06-13)
- **Multi-platform CI** (`.github/workflows/ci.yml`) — python-smoke matrix
  ubuntu/macos/windows × py3.11/3.12 + macOS swift build; 7/7 green after the portable
  font fix (`load_font` / `_load_font`, was hardcoded macOS Helvetica). ✓ (2026-06-13)
- **design-ux audit** — ran a fresh-eyes heuristic audit (new `central/skills/design/design-ux`);
  all 5 flagged blockers (single-screen, docked inspector, progress, named export,
  fit-crops) resolved and independently re-audited. ✓ (2026-06-13)

- **Multi-clip NLE window (`sequence.py`)** — the other half of the tool: arrange several
  clips end-to-end on a single track, trim edges (source in/out), reorder by dragging the
  clip body (live reflow, Movie-Maker style), scrub/play straight through (one preview
  `<video>` swapping src across boundaries), delete. Clips seed from CLI args / a folder or
  upload in-browser (＋ Add clips). Export concatenates the trimmed clips with ffmpeg:
  each normalized to the **first clip's frame** (scale-to-fit + pad), **silent audio
  synthesized** for clips that have none so mixed-audio sequences concat cleanly; encoder =
  videotoolbox→libx264 (reuses `render.has_videotoolbox`/`_ENC_FLAGS`), real progress ring,
  auto-download. Verified end-to-end: 3-clip export (mixed audio + 1280×800/640×480/1080²
  sources) → boundary frames confirm order + correct pillarboxing + trims; UI model
  (`locate`/reorder/trim) unit-checked in-browser. Hard cuts only — no crossfade/split/
  per-clip effects (deferred below). ✓ (2026-06-13)

- **Bugfixes (2026-06-13)** — two real wrong-output bugs found in a fresh-eyes
  pass and fixed with independent verification:
  1. `studio.py` speed-clip drag mapped the cursor against source duration
     (`*dur`) instead of the stable excluding-map's output duration
     (`mouseO(ev,rect,Mx)`); with ≥2 idle clips the dragged clip jumped ~17% of
     the ruler off the cursor (round-trip error 0.169 → 0, verified in-browser).
  2. `fcpxml.py` chained clip offsets by independently rounding each float output
     start, producing ±1-frame gaps/overlaps on the spine (the fixture spec hit
     **two** 1-frame overlaps). Now offsets chain from one integer-frame
     accumulator; `_self_test` asserts the spine is exactly contiguous and ends at
     the sequence duration. (Distinct from the pan-calibration item below.)

- **Robustness fixes (2026-06-13)** — five lower-severity issues from the same
  bug-hunt pass, each verified:
  - **A** `studio.py` serializes exports behind a `threading.Lock` — concurrent
    /render or /fcpxml (double-click, 2nd tab, refresh mid-render) no longer
    interleave the shared `OUT/*` files and corrupt each other.
  - **B** `polish.smooth_positions` guards empty `moves` (events file with
    clicks/keys but no move lines) → returns a zero track instead of `IndexError`.
  - **C** `do_POST` wraps the Content-Length/JSON parse → malformed body returns
    a `400 {"error":…}` envelope (verified) instead of dropping the connection.
  - **D** `render.py` warns to stderr when `assets/click.wav` is missing under
    `--clickfx` (was a silently-empty click track).
  - **E** `render.py` writes `progress.json` atomically (tmp + `os.replace`) so the
    `/progress` poll can't read a torn file mid-write.

- **Demo recording + publish (2026-06-17)** — shipped the public-facing demo and the
  tooling that makes it reproducible:
  - **Deterministic frame-stepping recorder** (`test/record-demo.js`) — steps the studio
    timeline frame-by-frame (`v.currentTime = O2S(i/fps, speedMap())` → wait `seeked` + 2
    RAFs → screenshot → assemble at the same fps), giving perfect CFR. Replaces Playwright
    `recordVideo`, whose VFR→CFR conversion duplicated/dropped frames and juddered on the
    auto-zoom. Verified: 0 frozen-mid-motion frames across all zoom bands, loop-seam ~0.5.
    Documented in SKILL.md (+ a Gotcha) and docs/ARCHITECTURE.md; contrasted with
    [[macos-screen-recorder]] (`sck-record`), which can't be frame-stepped.
  - **Server-side text-callout persistence** (`/callouts` GET+POST, debounced autosave) —
    manual callout placement survives reload AND is visible to the headless re-record.
  - **Timeline UX** — fixed inspector height so selecting a clip no longer jumps the
    timeline (`.insp` locked to 140px, internal scroll; verified Δy=0 with the inspector
    filled); cmd/shift multi-select within a lane; drag-to-select rubber band.
  - **Inspector declutter** — Text callouts moved into its own collapsible drawer; stray
    "· auto · own track" subtitle removed from Keystroke chips; all four drawers collapse
    by default.
  - **Published demo** — HD annotated NLE demo (callouts: 🔍 auto-zoom, ⏩ fast-forward,
    🎹 keystroke events) is now the README hero in central, the public repo, and the
    `ckw-skills` marketplace (embedded via raw link). Posted to X.

## Open / deferred

- **sequence.py fast-follows** — deferred from the v1 multi-clip window (kept rudimentary
  per ask): crossfade/dissolve transitions (ffmpeg `xfade`+`acrossfade`), split-at-playhead
  (razor), and per-clip Screen-Studio effects (zoom/speed/cursor from `studio.py`).
  Follow-ups SHIPPED since: double-buffered playback (2nd `<video>` pre-seeks/buffers the
  next clip → instant swap at cuts, no boundary hiccup; verified the now-active element IS
  the preloaded one, no src reload); smooth fixed-px-per-second dragging (frozen scale mid-gesture,
  edge tracks cursor 1:1), FCPXML export in the sequence window too (`to_fcpxml_sequence`,
  multi-asset spine — both editor windows now offer video + FCPXML), 60fps export default,
  and 1080p output default (16:9 / 9:16 / 1:1, orientation auto from first clip). CI now
  parses `sequence.py` + the fcpxml self-test covers the sequence path. ✓ (2026-06-13)
- **Study competitor auto-zoom implementations** — clone the comparable open-source
  Screen Studio alternatives and read how each does activity-aware / cinematic auto-zoom
  (zoom target selection, easing/spring, when-to-zoom heuristics), to improve ours
  (esp. screenize's Apple-Vision UI-element targeting — the one idea better than ours;
  see [[D]] note below). Repos:
  - `git clone https://github.com/syi0808/screenize` (macOS; auto-zoom + Vision UI-element detection; dev paused)
  - `git clone https://github.com/WizardofTryout/recordly` (mac+Windows; zoom spans + cursor pipeline)
  - `git clone https://github.com/tamnguyenvan/screenarc` (cross-platform; cinematic pan-and-zoom on clicks)
  - `git clone https://github.com/siddharthvaddem/openscreen` and `git clone https://github.com/imbhargav5/open-recorder` (auto-zoom from click telemetry; clip split/speed)
  Our auto-zoom currently fires on click clusters + standalone typing bursts (cursor-centred);
  scroll/drag aren't logged. Worth comparing: do they detect scroll/drag, and how do they
  pick the zoom *target* (raw cursor vs. detected UI element)?
- **FCPXML pan calibration** — `CALIBRATION` constant in `fcpxml.py` is a guess; needs a
  real DaVinci Resolve import round-trip to verify position keyframes match the preview.
- **Naming / marketplace prep** — repo stays `screen-studio-alternative` for now (naming
  explored ~18 rounds, aborted); Claude-marketplace listing / rename / llms.txt deferred.
- **JS↔Python speed-map duplication** — `speedMap()` (studio.py) and `time_maps`
  (render.py) reimplement the same segment math; only bites sub-0.3s blocks. Unify if it
  ever diverges.

## Note

This skill lives fully in central (`central/skills/screenstudio-alt/`). It publishes
outbound to `connerkward/screenstudio-alternative-skill` via the publish-skill flow — central
is the source of truth, the public repo is a sanitized derivative.
