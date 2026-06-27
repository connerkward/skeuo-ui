# dailies skill — TODO / known gaps

Open items left at the end of the 2026-06-04 session. None are blocking; the
skill is usable as-is via the documented commands. These would make it more
robust or extend coverage.

## Resolved in this session

- ✅ **Productionized Playwright driver** — `playwright-capture.js` is now
  config-driven and lives in central. BMW iX smart-objects config in
  `examples/bmw-smart-objects.json`.
- ✅ **H.264 sidecar workflow** — `encode-queue.sh share-h264 <path|slug>`.
  Hardware-encoded via `h264_videotoolbox`, ~2× the HEVC file size, plays in
  Slack/Teams/GitHub/Twitter/Notion.
- ✅ **Smoke test for encode-queue.sh** — `tests/test-encode-queue.sh`
  synthesises 3 scenes × 10 JPEG frames, runs encode, asserts mp4 count +
  duration + INDEX.md rows + scratch trashed + queue list empty + share-h264
  round-trip. 15/15 assertions pass as of 2026-06-04.

## Still open

### Wrapper subcommand on dailies.sh

`dailies.sh capture-deferred <topic> [--config X]` doesn't exist yet — currently
you call the driver directly with the JSON config. A wrapper would let the
existing `capture` paths route through the queue (and pick up the topic-name
plumbing for free).

### Recipe variants for non-3D pages

The libx265 CRF 18 + tune-animation + psy-rd 2.5 recipe was tuned for screen
content with text plus a Three.js viewport. For other workloads:

- **Pure text/UI (no 3D)**: same recipe; CRF could go lower (16) for sharper.
- **Heavy video / cinematic content**: drop `-tune animation`, use `-tune film`
  or no tune; CRF 20-22; consider 8-bit yuv420p (fewer artifacts).
- **Pixel art / dithered content**: use `-x265-params "no-deblock=1"` to
  preserve hard pixel edges (deblocking smears them).

Bake these into `encode-queue.sh` as `--preset text | film | pixel` options.

## Alternative capture path: chromium `--app=URL` + screencapture

The current pipeline (CDP screencast → JPEG frames → libx265 software) is
~3 GB scratch + ~3 min encode for a 60s recording. An all-hardware path:

1. `chromium --app=URL --window-position=0,40 --window-size=1920,1080`
2. `screencapture -v -R 0,40,1920,1080 master.mov` (hardware H.264, ~10 Mbps)
3. ffmpeg `hevc_videotoolbox -b:v 10M` transcode (hardware, ~25s)
4. ffmpeg `-c copy` per-scene splits

Tradeoffs vs. current:
- ✅ **Zero scratch on disk** (mov streams direct from hardware encoder)
- ✅ **~25s total encode time** vs. ~3 min for libx265
- ❌ Visible chromium window during recording (can't use computer)
- ❌ Hardware HEVC at fixed bitrate lacks psy-rd / tune controls — text
  edges visibly softer than libx265 CRF 18 (tested in rounds 6/7/9).
- ⚠️ Chromium app-mode title bar still occupies ~28px; need a crop or
  Y-offset to hide it.

Add as `dailies capture-via-screencapture` for the "exec asked, I need it in
2 minutes" case where quality is acceptable and speed wins.

## Cron / LaunchAgent for nightly encode

`encode-queue.sh encode-when-ready` polls AC + idle in a foreground loop.
For truly unattended overnight processing, ship a LaunchAgent plist:

```xml
<!-- ~/Library/LaunchAgents/dev.connerkward.dailies-encode.plist -->
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" ...>
<dict>
  <key>Label</key><string>dev.connerkward.dailies-encode</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/conner/dev/central/skills/dailies/encode-queue.sh</string>
    <string>encode</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>2</integer><key>Minute</key><integer>0</integer></dict>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
```

`launchctl bootstrap gui/$UID ~/Library/LaunchAgents/dev.connerkward.dailies-encode.plist`
runs `encode` nightly at 2 AM. Add to the machine-config doc when activated.

## Validate per-scene queue metadata

Right now `scene-timestamps.json` is the only file the queue inspects. If the
driver crashes mid-recording, partial timestamps may be valid syntactically
but reference frames that don't exist. Add a sanity-check in `encode-queue`
that verifies `endFrame <= len(frames)` and skips/warns on inconsistent
captures.
