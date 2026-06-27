---
name: cross-browser-preview
description: Verify web UI changes in Chromium, real WebKit (Safari/iOS engine), and an iOS Simulator before reporting done. Use BEFORE saying "looks good" on any responsive/layout task, IMMEDIATELY when the user mentions Safari, iPhone, iPad, iOS, mobile, "still broken on…", or after any CSS change that touches font sizing, line-height, aspect-ratio, clip-path, position fixed/sticky, viewport units (vh/svh/dvh), or container queries. This is for VISUAL rendering verification; for authoring/running Playwright test suites use playwright-cli instead.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Cross-browser preview

The default `mcp__playwright__*` tools in this harness drive **Chromium only**. Safari and iOS Safari run on **WebKit**, which has materially different behavior for: unitless `line-height` below 1.0, `clip-path`, `aspect-ratio` inside flex children, viewport units (`100vh` vs `100svh`), container queries (`cqi`/`cqb`), and form/font defaults. Chromium screenshots passing ≠ Safari screenshots passing.

This skill gives you two ways to actually see WebKit + iOS Safari before you ship.

## When to invoke (mandatory triggers)

- Any responsive layout change (media queries, flex/grid, sizing)
- Anything touching: `line-height`, `aspect-ratio`, `clip-path`, `border-radius` with overflow, `position: fixed/sticky`, `100vh/100svh/100dvh`, `cqi/cqb`, scroll containers
- The user mentions Safari, iPhone, iPad, iOS, "mobile", or sends a screenshot of a phone
- Before saying "fixed" / "looks good" / "deployed" on any UI task
- The user complains the same thing twice — that means you didn't actually verify cross-browser

## Path 1 — Playwright WebKit + Chromium (works on any Mac)

WebKit is bundled with Playwright. Same engine that Safari and iOS Safari use. Catches ~95% of cross-browser layout bugs.

**First-time setup on this machine (idempotent, fast if already installed):**
```bash
npx -y playwright install webkit chromium
```

**Snapshot a URL across 5 viewports:**
```bash
bash ~/dev/central/skills/cross-browser-preview/preview.sh [URL-or-path]
```

- URL omitted → defaults to `http://localhost:4747/`
- Path-only argument (`/projects/bas/`) resolves against localhost:4747
- Outputs PNGs to `./scripts/.preview/<timestamp>/` in the **current working directory** so each project keeps its own history
- Engines/viewports captured (8 total): chromium-wide (1600×900), chromium-desktop (1280×800), chromium-medium (900×800), chromium-narrow (600×900), webkit-wide (1600×900), webkit-desktop (1280×800), webkit-medium (900×800), webkit-iphone (393×852)

After it runs, **Read the WebKit screenshots first.** If the user said something looked wrong on iPhone, look at `webkit-iphone.png` before doing anything else.

## Path 2 — Real iOS Simulator (closer to actual iPhone Safari)

Real iOS Safari, not just WebKit. Catches the last 5% — mainly touch behaviors, Safari's chrome (toolbars affecting `100vh`), font availability, and `text-size-adjust` quirks.

**Two ways to drive the simulator, in preference order:**

### 2a — `ios-simulator` MCP (preferred; live tool calls, no shell)

Project: <https://github.com/joshuayoes/ios-simulator-mcp>. Already installed on this machine:
```bash
claude mcp add ios-simulator -- npx -y ios-simulator-mcp
```

Exposes tools (prefixed `mcp__ios-simulator__*`): `get_booted_sim_id`, `open_simulator`, `launch_app` (e.g. `com.apple.mobilesafari`), `ui_describe_all`, `ui_describe_point`, `ui_find_element`, `ui_tap`, `ui_type`, `ui_swipe`, `screenshot`, `record_video`, `stop_recording`, `install_app`.

Prerequisite — Xcode (full, with iOS runtime) and Facebook IDB for the `ui_*` tools (`screenshot` works without IDB). To install IDB:
```bash
brew tap facebook/fb
brew install idb-companion
pipx install fb-idb
```
(IDB requires a current Xcode; if `brew install` complains the local Xcode is too old, the basic `screenshot`/`launch_app` tools still work via simctl underneath.)

**Typical flow via MCP:**
1. `mcp__ios-simulator__open_simulator` (or rely on it being booted)
2. `mcp__ios-simulator__launch_app` with `bundle_id=com.apple.mobilesafari`
3. Navigate by tapping the URL bar via `ui_tap` + `ui_type`, OR drop to shell:
   `xcrun simctl openurl booted https://…/`
4. `mcp__ios-simulator__screenshot` — returns inline

Inline screenshots = no disk hop, no Finder window, instant feedback. Use this loop for the bulk of iPhone-Safari debugging.

### 2b — `iphone-preview.sh` (shell fallback; multi-device batch)

Useful when you need to *batch* screenshots across multiple iPhones in one shot, or you don't want to babysit MCP calls.

**Prerequisite:** full Xcode + accepted license + an iOS simulator runtime installed:
```bash
sudo /Applications/Xcode.app/Contents/Developer/usr/bin/xcodebuild -license accept
sudo /Applications/Xcode.app/Contents/Developer/usr/bin/xcodebuild -downloadPlatform iOS
```

**Snapshot:**
```bash
# default: iPhone 16e, iPhone 16, iPhone 16 Pro Max
bash ~/dev/central/skills/cross-browser-preview/iphone-preview.sh [URL-or-path]

# custom device list (comma-separated; must match `simctl list devices` names)
bash ~/dev/central/skills/cross-browser-preview/iphone-preview.sh \
  https://example.com/ "iPhone 16,iPhone 16 Pro Max"
```

- Pre-warms Safari (dodges the privacy/new-tab splash)
- Waits 10s after navigation before screenshot (settles render)
- Outputs to `./scripts/.preview-iphone/<timestamp>/<device>.png` per device
- Exits with an install hint if Xcode / runtime / license is missing

## Reading the screenshots

When comparing `chromium-desktop.png` to `webkit-desktop.png`, look for:

- **Portrait/avatar shapes** — WebKit honors explicit-px `line-height` but ignores unitless < 1.0; round avatars built from text will go oval in WebKit
- **Vertical scroll where there shouldn't be** — `100vh` includes Safari chrome on iOS; use `100svh`
- **Text overflowing fixed/right-pinned elements** — Chromium can be more permissive
- **Clipped corners on rounded shapes** — `clip-path` + transforms behave differently
- **Form controls / button heights** — WebKit's defaults are taller

If a screenshot looks wrong, fix it before reporting back. If you can't tell from the screenshot, run the iOS Simulator path.

## Housekeeping

- **Don't open Finder.** The shell scripts no longer call `open` on the output directory; read the PNGs inline with the Read tool.
- **Clean up screenshots when verification is done.** Once the work is shipped, remove the run directories so they don't accumulate:
  ```bash
  rm -rf scripts/.preview scripts/.preview-iphone
  ```
  Both paths are already in `.gitignore` for typical project layouts; cleanup is just for disk hygiene.

## What this skill does NOT do

- Doesn't replace the `mcp__playwright__*` tools — those are still better for interactive DOM control (click/type/eval) in Chromium. Use them for *debugging*, use this skill for *cross-browser verification*.
- Doesn't auto-fix issues. It surfaces them. You read the PNG, you fix the CSS.
- Doesn't run dev servers. Start one yourself first — never hardcode a port; use `~/dev/central/scripts/serve <dir> --bg` per `central/rules/web-dev-rule.md`.
