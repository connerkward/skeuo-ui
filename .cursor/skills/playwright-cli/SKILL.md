---
name: playwright-cli
description: Playwright CLI usage (codegen, test, show-report, show-trace, install). Use when recording/running/debugging Playwright tests, opening trace viewer, or working with playwright.config.* / *.spec.ts files. This is for TEST-SUITE work; for visual "does it render right on Safari/iOS" checks use cross-browser-preview instead.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

Prefer this CLI over the Playwright MCP for: recording flows (`codegen`), running an existing test suite, opening HTML reports, and trace viewer. The MCP is for ad-hoc browser control (click/type/screenshot) — not test authoring or report viewing.

## Run tests

- `npx playwright test` — run all tests headless.
- `npx playwright test path/to/file.spec.ts` — run one file.
- `npx playwright test -g "pattern"` — filter by test name regex.
- `npx playwright test --project=chromium` — single project (see `playwright.config.*` for names).
- `npx playwright test --headed` — show the browser window.
- `npx playwright test --ui` — interactive UI mode (watch, time-travel, picker). Best for iterative authoring.
- `npx playwright test --debug` — pause on first action, opens Playwright Inspector.
- `npx playwright test --workers=1` — serial; use when debugging flake.
- `npx playwright test --update-snapshots` — refresh visual/text snapshots.
- `npx playwright test --reporter=list` — override reporter (list, line, dot, html, json).

## Record / generate

- `npx playwright codegen <url>` — open browser, record clicks → emit test code.
- `npx playwright codegen --target=javascript <url>` — pick output language.
- `npx playwright codegen --device="iPhone 13" <url>` — emulate device.

## Reports & traces

- `npx playwright show-report` — open the last HTML report.
- `npx playwright show-trace trace.zip` — open a trace file (capture via `trace: 'on-first-retry'` in config or `--trace=on`).

## Install

- `npx playwright install` — install browser binaries (run after `npm install`).
- `npx playwright install --with-deps` — also install OS deps (Linux CI).
- `npx playwright install chromium` — single browser only.

## Misc

- `npx playwright --version` — print installed CLI version.
- `npx playwright test --list` — print matched tests without running.
- `npx playwright test --last-failed` — re-run only failures from the last run.
- `npx playwright test --repeat-each=N` — flake hunt.

## Stealth mode — evading aggressive bot-detection (Google, Cloudflare)

Some sites (Google Maps/Accounts, Cloudflare-protected apps) detect Playwright/CDP and
**sign out or block** the automated session within minutes — vanilla `--headed` + a real
login is not enough. The counter is the **stealth plugin**, which masks the fingerprints
they check (`navigator.webdriver`, CDP runtime markers, plugin/permission anomalies, etc.).

```bash
npm i playwright-extra puppeteer-extra-plugin-stealth   # no browser download needed if using channel:'chrome'
```

```js
const { chromium } = require('playwright-extra');
const stealth = require('puppeteer-extra-plugin-stealth')();
chromium.use(stealth);

const ctx = await chromium.launchPersistentContext(profileDir, {
  channel: 'chrome',            // real Chrome, not bundled Chromium — far less suspicious
  headless: false,              // user logs in once; session persists in profileDir
  viewport: null,
  args: ['--disable-blink-features=AutomationControlled', '--start-maximized'],
  ignoreDefaultArgs: ['--enable-automation'],   // drop the "Chrome is being controlled" flag
});
```

Key points that made a Google Maps mass-save actually stick (it was killing the session
without stealth): **stealth plugin + `channel:'chrome'` + drop `--enable-automation` +
persistent profile** (login survives restarts). Real-browser clicks also carry the
**transient user-activation** that activation-gated handlers (Maps "save to list") require —
something the claude-in-chrome extension's injected clicks do *not* provide.

**Do NOT enable stealth by default.** It spoofs fingerprints, so a detector that catches the
spoof mismatch can flag you *harder* than vanilla; it masks signals (`navigator.webdriver`)
you sometimes want visible when testing your own bot-handling; the plugin lags Chrome
releases and breaks; and test suites want the real, unpatched browser to catch genuine bugs.
**Turn it on per-task only when you're specifically fighting bot-detection.**

Worked example: `~/Desktop/legokink1-maps-migration/import.js` (Takeout saved-places →
Google Maps "Want to go", fully automated after one login).

## Playwright MCP: two servers — headless default, headed opt-in

Two Playwright MCP servers are registered (user scope, `~/.claude.json`). **The agent
picks per task** by choosing which server's tools to call:

| Server | Mode | Tool prefix | Use when |
|--------|------|-------------|----------|
| `playwright` | **headless** (default) | `mcp__playwright__*` | almost everything — verify a localhost change, screenshot, DOM check, click-through. No window, never touches your screen or focus, screenshots work. |
| `playwright-headed` | headed (visible) | `mcp__playwright-headed__*` | only when watching the flow live actually helps — debugging a flaky interaction, demoing, or when you need to see rendering in real time. |

Both run `--isolated` (fresh profile per session, so two Claude windows don't collide on
the persistent-profile lock — see `web-dev-rule.md`).

**Default to `playwright` (headless).** Reach for `playwright-headed` deliberately, and
say why ("opening headed to watch the login redirect"). Note `@playwright/mcp`'s own
shipped default is *headed* — we override to headless because invisible + screenshots-work
is the right default, and you opt into a window only when it pays for itself.

**Why headless is the default (not a hidden-window hack):**
- Headless has **no window at all** — nothing to hide, no focus steal, no Space clutter, no flicker. Verified: launches with `window_visible=false`, `page.screenshot()` returns a real PNG (16577B).
- The previously-attempted "headed but hidden" approaches all failed on macOS Tahoe 26.5: **minimize / off-screen** make `page.screenshot()` hang (macOS stops compositing non-visible windows, 8–15s timeout); **maximize-behind** can't stay behind because Playwright re-raises its own window on every action, so it flickers to the front and is visible most of the time; **own Space** needs `hs.spaces.moveWindowToSpace` (silently no-ops on 26.5) or yabai (partial SIP disable, fragile across updates). Headless sidesteps all of it.

**Gotcha:** MCP arg/registration changes need a **Claude Code restart** to take effect.
Verified macOS Tahoe 26.5. (Hammerspoon is no longer used for this — the watcher was removed.)
