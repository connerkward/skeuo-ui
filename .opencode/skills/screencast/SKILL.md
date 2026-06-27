---
name: screencast
description: Record a short video clip of a window, region, or full screen on macOS via the built-in `screencapture -v` and drop it on the Desktop. Supports audio capture (`--audio`; system audio via a BlackHole loopback) and a high-quality shareable mp4 transcode (`--mp4`). Use when the user wants to capture a quick clip of dev work — lookdev studio, browser preview, terminal demo — without breaking flow.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Screencast

Thin wrapper around macOS `screencapture -v` (built-in, no install) that records a video clip and writes it to `~/Desktop/screencast-YYYY-MM-DD-HHMM-<slug>.mov`, then reveals the file in Finder.

## Invocation

```bash
bash ~/dev/central/skills/screencast/screencast.sh "<description>" [flags]
```

Args:

- **Positional `<description>`** — free text; slugified for the filename (`"lookdev fov tuning"` → `lookdev-fov-tuning`). If omitted, slug is `clip`.
- **`--region`** — interactive region pick (drag rectangle). Default is window-pick (click a window).
- **`--screen`** — record the full main display, no picker.
- **`--seconds N`** — cap the recording at N seconds. Without this flag the recording runs until the user stops it from the menu bar (▢ stop button).
- **`--audio`** — capture the default audio **input** (adds `screencapture -g`). For a mic that's automatic; for **system audio** (the app's own sound, e.g. TTS / video playback) the default input must be a loopback device — see **Capturing audio** below.
- **`--mp4`** — after recording, transcode the raw `.mov` to a shareable, still-crisp H.264 `.mp4` (crf 20, ≤1920px, faststart, AAC audio). The raw `.mov` is large retina; this keeps quality high while shrinking it. Prefer this over hand-rolling `ffmpeg -crf 30` (which looks terrible).

## Capturing audio

`screencapture -v` records **no system audio on its own**. `-g`/`--audio` captures the
default audio **input**:

- **Mic** — works out of the box (`--audio`). Captures the room/voice, not the Mac's own output.
- **System audio** (TTS, video, app sound) — macOS has no built-in system-audio tap, so route
  the system **output** through a virtual loopback and capture it as the input:
  1. `brew install blackhole-2ch` (virtual 2-ch audio device; reversible: `brew uninstall blackhole-2ch`).
  2. In **Audio MIDI Setup**: create a **Multi-Output Device** = your real output (speakers/headphones) **+ BlackHole 2ch**, and set it as the system output — so you still HEAR audio while it's also fed to BlackHole.
  3. Set **BlackHole 2ch** as the default **input** (System Settings → Sound → Input), or pass it explicitly.
  4. Record with `--audio` — `-g` now grabs BlackHole = the system audio.
  This is a per-machine change (document in the machine's `per_<host>.md` per `machine-config-rule`).
  Note for the `say-notify` overlay demos: the `say` voices are system audio.

- **Public/social demo? Use `--demo`.** Logs input events during capture, then auto-polishes (idle speed-up, auto-zoom on clicks, keystroke chips) and emits a 9:16 **vertical** alongside the horizontal — see the `screenstudio-alt` skill. Pair with dailies' clean-room protocol.
- **No-loopback system audio (preferred):** `sck-record` records the main display **+ system audio** via ScreenCaptureKit — no BlackHole, no sudo, just Screen Recording permission. `sck-record` lives in the [[macos-screen-recorder]] skill (built by `setup-machine`); run `./sck-record <out.mp4> <seconds>`. Published publicly as `connerkward/macos-screen-recorder-system-audio` via [[publish-skill]]. This is how the say-notify voice demos get recorded with audio.

`screencapture -v` is a foreground command: it blocks until the recording ends (timer expires, or user clicks the menu-bar stop button). On first run macOS will prompt for Screen Recording permission for whichever app is shelling out (Terminal / iTerm / cmux); approve once.

**Agent note:** if you're invoking this from a Claude shell call, the call will hang until the recording stops. Always run it with `run_in_background: true` (or pass `--seconds N` so it auto-stops) — otherwise the conversation freezes waiting on a user click.

## Mapping from user phrasing

| User says | Run |
|---|---|
| `/screencast lookdev iteration` | `screencast.sh "lookdev iteration"` (window pick, no cap) |
| `/screencast --region browser preview` | `screencast.sh "browser preview" --region` |
| `/screencast --screen 5s demo` | `screencast.sh "5s demo" --screen --seconds 5` |

## Output

- File: `~/Desktop/screencast-YYYY-MM-DD-HHMM-<slug>.mov` (QuickTime H.264 .mov)
- Script echoes the absolute path on completion and runs `open -R "<path>"` so Finder pops with the file selected.
- Cite the path in chat as a clickable `file://` link per `central/rules/terminal-file-links-rule.md`.

## Why Desktop, not Downloads

Per `central/rules/file-output-rule.md`, generated artifacts default to `~/Desktop/`, never `~/Downloads` (the user's real browser-download space). Screencasts are agent-generated artifacts the user will triage and delete, so Desktop is the right home — they aren't repo-bound scratch.

## Quirks

- `-v` records video; without `-V <seconds>` it runs until manually stopped via the menu-bar stop button.
- Interactive mode (window/region) pops the standard macOS capture overlay; user clicks the target.
- Capturing remote (over SSH) requires the `launchctl bsexec` trick from `man screencapture`; local Terminal/cmux sessions don't.
- File extension determines container — script uses `.mov` (the macOS-native default for `screencapture -v`).
