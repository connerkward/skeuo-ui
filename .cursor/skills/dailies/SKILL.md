---
name: dailies
description: Autonomously capture short screencasts and stills of dev work in progress (lookdev studios, browser previews on localhost, UI/canvas/GLSL files), transcode to modern compressed formats (HEVC/AVIF/GIF), and file them under ~/ideas-syncthing/proj-dailies/ with scannable filenames. Use proactively when iterating on visuals — the user wants a corpus of "dailies" they can scroll later to remember what was worked on. Built atop the screencast skill; dailies is the policy/orchestration layer that decides WHEN to record, what to record, and how to name/store/digest it.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# dailies — autonomous dev-work documentation

The user wants a flat archive of short clips and stills capturing iteration moments. You decide when to fire. Don't ask permission per capture — announce in chat with a single line so they can find it in scrollback.

**Folder:** `~/ideas-syncthing/proj-dailies/` (flat, syncs across machines).

**Filename:**
```
<repo>__<topic>__<YYYY-MM-DD>-<HHMM>__<sessionhash>.<ext>
# portfolio-2026__lookdev-framing__2026-06-04-1430__3a7c92.mp4
# portfolio-2026__hero-crop__2026-06-04-1432__3a7c92.avif
```

## Invocation

```bash
~/dev/central/skills/dailies/dailies.sh capture <topic> [--still | --seconds N]
~/dev/central/skills/dailies/dailies.sh capture-pair before <topic>
~/dev/central/skills/dailies/dailies.sh capture-pair after  <topic>
~/dev/central/skills/dailies/dailies.sh save-last
~/dev/central/skills/dailies/dailies.sh digest --summary "$(cat <<EOF
short markdown summary
EOF
)"
```

After each capture, announce in chat (one line, no preamble):
```
[record: portfolio-2026 / lookdev-framing / 6s]
[shot:   portfolio-2026 / hero-crop]
```

## NEVER auto-record (default policy)

For the AUTONOMOUS firing path (`capture` driven by the time-cooldown + dice
gate), skip these surfaces — they're noise, not iteration:

- **Playwright / headless / automation windows** when Claude is driving them
  for verification screenshots, dev checks, etc. The reflexive "I just took
  a Playwright shot" should NOT also fire a daily.
- **Terminals.** Terminal / iTerm / cmux / Ghostty / WezTerm. The `entire`
  skill captures CLI sessions; dailies stays out of that lane.
- **System UI.** Menu bar, Finder, system prefs.
- **The user's personal apps.** Slack/Mail/iMessage/Notes/Browser-with-non-dev-tabs.

## When to fire

ALL three must hold:

1. **Visual context active** — at least one of:
   - A lookdev studio is open (you built one this session, or a `scripts/.lookdev-*` URL is on screen)
   - A dev server is running and a browser tab points at it
   - You're iterating on a UI file: HTML / CSS / `.glsl` / `<canvas>` / `.html` template

2. **Meaningful event just happened.** Something visibly changed. Examples that count:
   - A deploy succeeded (`./deploy.sh` or similar)
   - You just finished a lookdev iteration (anchor tuning, slider sweep, etc.)
   - A CSS / template edit was deployed and the screenshot you took looked different
   - The user said "looks good" / "ship it" / "that's right" — a moment worth capturing

3. **Cooldown gate passed.** The script enforces a ≥90-second real-time cooldown since the last *attempt* (the last_epoch is persisted on every attempt, including dice-skipped ones, so a skip still locks out the next 90s). There is no event counter — the gate is purely time + dice. You can call it freely; it'll noop if gated.

THEN the script samples with ~55% probability. Even when all conditions hit, ~45% of moments aren't captured — by design, to avoid spamming. You don't manage the dice.

## Pick still vs video

| Use video (`capture <topic> --seconds 6`) | Use still (`capture <topic> --still`) |
|---|---|
| Slider drag, scrub, animation | Static layout landed |
| Multi-step UI interaction | A new rendered state |
| Lookdev tuning sequence | Code/markup commit moment |
| Anything with motion | "Before / after" snapshot |

Default to **6 seconds** for video. Cap at **15s**. For lookdev sweeps, **8–10s** captures a few slider drags nicely.

## PUBLIC demo captures — clean-room protocol

When a capture is destined for a public surface (repo README/docs, social posts via
`announce`, a shared demo), the live-desktop rules change: dailies' "capture the
moment" default is exactly wrong, because the moment includes your tabs, callsign
overlays, and notifications. (Real incident, 2026-06-11: a recorder self-demo was
trashed because personal browser tabs and a Claude notification card landed mid-frame.)

Before recording:

- **Do Not Disturb ON** (Focus). Notifications are the #1 leak and arrive at any time.
- **Stage the frame**: fullscreen the subject window, or capture a window/region —
  never the open desktop. No menu-bar clutter in frame if avoidable.
- **Sweep the subject itself**: browser shows only the demo tab; terminal history
  cleared if visible; no real tokens/emails/paths in any visible UI.

After recording, BEFORE publishing:

- **Scrub the actual frames** (`ffmpeg -vf "fps=1" thumbs_%02d.png` and look, or
  scrub in QuickTime) for notification cards, personal tabs, overlays, autocomplete
  dropdowns. The leak is always mid-clip, never frame one.
- If anything leaked: **trash the take and re-shoot** — don't crop/blur around it.

A leaked take is unrecoverable once pushed (git history, CDN caches). Re-shooting
costs 2 minutes; scrubbing a published leak costs a force-push and it's still cached.

**Record public demos with `screencast.sh --demo`.** It logs input events alongside
the capture and auto-polishes (idle speed-up, auto-zoom on clicks, keystroke chips)
AND emits a 9:16 vertical — vertical output is DEFAULT for anything social-facing,
since a raw 16:9 screen crammed into a phone feed is unwatchable. Engine:
the `screenstudio-alt` skill.

## EXPLICIT OK — user-driven Playwright recordings

When the user EXPLICITLY asks for a capture / dailies / video / recording of
a specific feature ("get a video of the 3D viewport orbiting", "capture
parallax scrolling", "film the entire smart-objects page"), Playwright IS
the right tool. The autonomous skip rule above only applies to reflexive
agent-driven Playwright moments. For user-explicit captures:

- Use **headed Playwright** (the user wants to see / share what's captured;
  also so the page renders with fonts/animations properly).
- For **stills**: take Playwright screenshots of specific page states /
  scroll positions, then route through `transcode.sh still <png> <avif>`
  and append to INDEX.md via the same naming convention.
- For **video** (parallax scroll, 3D viewport orbit, lookdev tuning, etc.):
  use the generic driver at `~/dev/central/skills/dailies/playwright-capture.js`.
  Write a small JSON config (URL + viewport + preload + scenes) — see
  `examples/bmw-smart-objects.json` for a working reference. The driver
  uses headed chromium + CDP screencast and writes JPEG frames +
  `scene-timestamps.json` to `~/Desktop/dailies-scratch/<stamp>/`, which is
  then a valid queue item for `encode-queue.sh`. Action primitives:
  `wait`, `scroll-to-top`, `scroll-into-view`, `raf-scroll`, `raf-orbit`,
  `click`, `hover`, `keyboard`.

  ```bash
  NODE_PATH=$HOME/dev/punku-web/node_modules \
    node ~/dev/central/skills/dailies/playwright-capture.js \
    ~/dev/central/skills/dailies/examples/bmw-smart-objects.json
  # then:
  ~/dev/central/skills/dailies/encode-queue.sh encode
  ```

  (`recordVideo: { dir }` is an alternative but yields a VP8 webm that
  smears text — prefer the CDP screencast path above.)
- Use `dailies.sh capture` with `FORCE_CAPTURE=1` + the resulting file as
  the source so it lands in the index with the right name/session/etc.
  (The encode-queue already writes canonical filenames + appends to
  INDEX.md — separate `dailies.sh capture` call only needed for stills.)

In other words: the autonomous gate exists so dailies doesn't fight the
verification workflow. When the user explicitly says "capture this", that
gate isn't relevant — produce what they asked for.

## Deferred encoding — split capture from encode

The exec-quality libx265 encode is heavy (~3-5 min for a 4-scene 60s set,
8 cores burning, 1.2 GB peak RAM). Don't run it interactively during a
working session if the user has anything else going on. Pattern:

1. **Capture now** (cheap): Playwright + CDP screencast writes JPEG frames
   to `~/Desktop/dailies-scratch/<timestamp>/`. CPU during capture is tiny
   (chromium does the encode in its own threads). The scratch dir IS the
   queue item — no separate state file.
2. **Encode later** (heavy): `~/dev/central/skills/dailies/encode-queue.sh`
   walks the scratch roots (`~/Desktop/dailies-scratch/` first,
   `~/.scratch/dailies/` as fallback) and processes everything queued.
   Output mp4s land in `$DAILIES_DIR`; the scratch dir is trashed on
   success (per the media-rm rule).

**Subcommands:**

```bash
# Show pending captures
~/dev/central/skills/dailies/encode-queue.sh list

# Encode everything pending NOW (interactive)
~/dev/central/skills/dailies/encode-queue.sh encode

# Wait for AC power + ≥10 min idle, then encode. Optional [seconds] arg.
# Run before leaving the desk / before sleep.
~/dev/central/skills/dailies/encode-queue.sh encode-when-ready [seconds]

# Produce an H.264 sidecar (.h264.mp4) for Slack/Teams/GitHub/Twitter/Notion,
# where the HEVC hvc1 mp4 doesn't play inline. Hardware-encoded via
# h264_videotoolbox (no CPU cost). Accepts a path OR a slug substring to
# glob $DAILIES_DIR.
~/dev/central/skills/dailies/encode-queue.sh share-h264 <hevc.mp4|slug>
```

The `encode-when-ready` polls `pmset -g batt` for AC and `ioreg -c
IOHIDSystem` for idle every 60s. Once both conditions hold, it kicks off
the queue. Defaults to 600 seconds (10 min) idle threshold.

**When to defer vs. encode now:**

- **Defer** when the user is actively working, on battery, or asked for
  a daily mid-session and doesn't want to wait. Just capture and walk away.
- **Encode now** when the user explicitly asks to see the result, when
  shipping the clip is the next step, or when the queue is single-digit
  short and you want it done before the session closes.

**Scratch location — why Desktop:**

`~/Desktop/dailies-scratch/<timestamp>/` is the default because (a) it's
visible — user sees the folder in Finder if they want to manually delete
or inspect, (b) survives reboots unlike `/tmp` (which macOS clears), (c)
the encode-queue trashes scratch dirs on success, so they're recoverable
for 30 days via Finder's Trash if the user wants to re-encode at different
settings. Override with `DAILIES_SCRATCH=<path>` env var or pass as
positional arg to the driver.

**Recording mode — headed, not headless:**

Playwright's `chrome-headless-shell` doesn't expose Metal/GPU on macOS, so
WebGL falls back to swiftshader (software CPU rasterization). For pages
with a Three.js viewport (or anything GPU-bound), headless captures at
<1 fps. Use headed (`headless: false`); chromium picks up Metal natively
and the viewport captures at ~50 fps. The visible chromium window is
unavoidable on macOS but doesn't appear in the output — CDP screencast
captures only the page viewport (no chrome bar / tabs / address bar /
traffic lights), regardless of whether the window is visible to the user.

## Recording & encode quality (the scripts own the knobs — don't re-tune here)

Capture and encoding are knob-heavy, and the knobs live in the scripts with their rationale as inline comments. Don't re-derive codec settings from prose. Two takeaways to *know*:

- **Motion must be smooth for the codec.** Drive animation via in-page `requestAnimationFrame`, never per-step `setTimeout` from the driver — discrete jumps make the encoder smear text. Hold the final state ~1s; don't stack parallax on a scroll in one shot. (Pattern + details: `playwright-capture.js`.)
- **Encoding is text-tuned libx265**, single-pass from the master (`-crf 18 -preset slow`, psy-rd) — *not* hardware `hevc_videotoolbox`, which softens text edges. Don't touch the params; see `transcode.sh` (and its `TRANSCODE_SS/T` for single-pass scene splits).

## Topic slug

Use a kebab-case short descriptor of what's being worked on **right now**. Examples:

- `lookdev-framing` (in a lookdev for camera framing)
- `viewport-fov`    (tuning viewport FOV)
- `hero-crop`       (working the hero image crop)
- `nav-redesign`    (redesigning navigation)
- `cabin-passenger-edit` (editing the cabin photo)

Pull from the most recent lookdev folder name, the file being iterated on, or a high-level project area. NOT generic (`ui-work`, `stuff`, `iteration`).

## Before/after pairs

Right before a visible change is about to commit (you're about to run `./deploy.sh`, or push a CSS edit), capture a BEFORE:

```bash
~/dev/central/skills/dailies/dailies.sh capture-pair before <topic>
./deploy.sh
# wait for the visible change to land...
~/dev/central/skills/dailies/dailies.sh capture-pair after <topic>
```

The script pairs them by topic+session, saves as `__before.avif` / `__after.avif`. Pair lives next to other dailies in the same folder. Great for change-log scroll-back.

## End-of-session digest

When the chat is winding down OR the user asks for a "dailies digest" / "wrap up" / similar:

```bash
~/dev/central/skills/dailies/dailies.sh digest --summary "$(cat <<'EOF'
**What we worked on this session:**

- Iterated on the BMW iX viewport in §00: dual-anchor FOV lerp, V2→V1 wireframe transition by FOV 24
- Re-tuned tight anchor y/z/dist after lookdev studio session
- Removed camera frustums, simplified label offsets at wide zoom
- Added FOV indicator microtext + zoom controls + expand popover

**Outcomes:**

- Production viewer now lerps target + opacity + fade with zoom
- Lookdev studio at scripts/.lookdev-framing/ retained for future tuning
EOF
)"
```

You **compose the summary yourself** as a few markdown bullets covering what was iterated on and outcomes. The script builds an HTML contact sheet of every dailies file from this session (matched by `<sessionhash>` in filenames), embeds the summary at top, drops the HTML on the Desktop, and prints the path.

## "Save that one"

If the user says "save that dailies" / "keep that one" / "★ that" / similar, promote the most recent capture:

```bash
~/dev/central/skills/dailies/dailies.sh save-last
```

Moves the latest file to `~/ideas-syncthing/proj-dailies/keepers/` with a `★` prefix. The rest of the folder can be pruned/archived later without losing the highlights.

## Kill switches

- User says "no dailies this session" → set the per-session disable flag:
  ```bash
  touch "/tmp/dailies-disabled-${CLAUDE_SESSION_ID:-default}"
  ```
- Globally disabled: `~/.claude/no-dailies` exists (user-created file).
- `dailies.sh capture` checks both before doing anything; safe to call from anywhere — it'll noop.

## Output formats (handled by transcode.sh; don't think about these)

- **Video:** `.mp4` H.265 via **libx265** (software, CRF-tuned for text — see *Encode pipeline*). ~0.5–2 MB per 10s at 1080p.
- **Short-video alt:** `.gif` palette-optimised for clips ≤4s — shareable in Slack/email/anywhere image-only.
- **Video thumbnail:** `.thumb.avif` alongside the mp4 (Finder/QuickLook preview).
- **Still:** `.avif` (modern, ~30–60 KB at 1920px).
- **Index:** `INDEX.md` in the dailies folder — auto-appended with one line per capture (path, repo, topic, date, session#).

## Why dailies and screencast are separate skills

Same shell primitive (`screencast.sh`), different invocation patterns:

- **`screencast`** is user-invoked. They say `/screencast <name>` and pick a window. Reactive.
- **`dailies`** is agent-policy. You decide when based on session signals. Proactive.

Don't merge — the SKILL descriptions are explicit about routing so the right one fires for the right intent.
