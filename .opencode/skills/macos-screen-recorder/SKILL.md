---
name: macos-screen-recorder
description: Headless macOS screen recorder that captures the main display PLUS system audio via ScreenCaptureKit — no BlackHole/loopback driver, no sudo, just the standard Screen Recording permission. Use when you need to script a screen recording WITH system sound on macOS from the CLI (demos, captures, voice-demo recording) — the case QuickTime and `screencapture -v` can't cover without a virtual audio device.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# macos-screen-recorder (sck-record)

`sck-record.swift` → compiled `sck-record` (binary gitignored; built by `setup-machine`, or
`swiftc -O sck-record.swift -o sck-record`). Records the main display + system audio via
ScreenCaptureKit.

```
./sck-record <out.mp4> <seconds>
```

**The one true differentiator:** system audio from the CLI with **zero install** — no
BlackHole / loopback virtual device, no sudo; only the standard Screen Recording permission
(granted once to whatever app shells out). It is *not* a general "better than OBS/Screen
Studio" tool — it fills exactly the headless-CLI-with-system-audio gap.

The broader record→polish workflow lives in the [[screencast]] skill, which calls this; the
post-production studio is [[screenstudio-alt]]. Published publicly as
`macos-screen-recorder-system-audio` via [[publish-skill]] (repo is a tool + skill, not a
pure skill).
