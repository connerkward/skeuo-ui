---
name: "browser-tool-routing-rule"
id: "browser-routing-01"
description: "Route browser tasks to the right tool: Playwright MCP for dev verification, playwright-cli skill for tests, claude-in-chrome only when the user's real session is required."
applyTo: ["**/*"]
alwaysApply: true
priority: "high"
human-reviewed-at: 2026-06-16
human-reviewed-by: connerward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---
# Browser tool routing

Multiple browser tools are loaded simultaneously (`mcp__playwright__*`, `mcp__claude-in-chrome__*`, `mcp__chrome-devtools__*`, the `playwright-cli` skill, computer-use). They are NOT interchangeable. Pick by the task, not by what's most convenient or familiar.

**Default bias: prefer Playwright MCP for dev work. Reach for claude-in-chrome only when you specifically need the user's real Chrome session.** The most common routing mistake is using claude-in-chrome to verify a localhost change — that pollutes the user's actual browser, opens tabs in their working window, and is slower than a headless Playwright snapshot.

**Two Playwright MCP servers — default to HEADLESS.** `mcp__playwright__*` is headless: no window, never touches the user's screen or focus, screenshots still work. `mcp__playwright-headed__*` opens a *visible* window. **Default to the headless server for everything** — verification, screenshots, DOM checks, click-throughs. Modern Playwright Chromium ("new headless") renders identically headed vs headless, so headed buys nothing for correctness. Only reach for `playwright-headed` when the user **explicitly** asks to watch/record/demo a flow, or to debug a flaky interaction where seeing the live browser is the actual point — and say why ("opening headed to watch the redirect"). An unrequested headed run is an interruption: on macOS Tahoe 26.5 the window pops into the user's *active* desktop per session and can't be parked (minimize / off-screen / own-Space all fail there), so it can't be tucked away. When in doubt, headless.

## Decision table

| Task | Tool | Why |
|------|------|-----|
| Verify a frontend change on localhost (screenshot, DOM check, click-through) | **Playwright MCP** (`mcp__playwright__*`) | Headless, ephemeral, doesn't touch user's real browser. Fast DOM-aware automation. |
| Write/run/debug Playwright tests (`*.spec.ts`, codegen, trace viewer, `playwright.config.*`) | **`playwright-cli` skill** | The skill knows the CLI flags and viewer commands. Don't reinvent via Bash. |
| Drive a site that needs the user's logged-in identity (their Gmail, Slack web, GitHub-as-them, Linear, anything behind their auth/cookies) | **claude-in-chrome** (`mcp__claude-in-chrome__*`) | This is the *only* tool with access to the user's real session. |
| Inspect Chrome DevTools internals (performance trace, network throttling, coverage, CDP-only features) | **chrome-devtools MCP** (`mcp__chrome-devtools__*`) | Specialized for DevTools protocol features the others don't expose. |
| Native desktop app (Finder, System Settings, native Slack/Mail clients) | **computer-use** | The other tools can't see native apps. |

## When in doubt

Ask: *does this task require the user's logged-in state?*
- **No** → Playwright MCP. Default for anything on localhost or any public page.
- **Yes** → claude-in-chrome. Confirm with the user first if the action will modify state in their account (sending messages, posting, deleting, etc.).

## Anti-patterns

- ❌ Using claude-in-chrome to screenshot localhost — opens a tab in the user's working browser. Use Playwright MCP.
- ❌ Using claude-in-chrome to test a login flow you're building — use Playwright MCP with a fresh profile, not the user's real cookies.
- ❌ Running `npx playwright test` via Bash without consulting the `playwright-cli` skill — the skill exists precisely because the flags/output are non-obvious.
- ❌ Loading every browser tool "just in case" via ToolSearch. Decide which one fits, load only that one.
- ❌ Using `playwright-headed` (`mcp__playwright-headed__*`) for routine verification — it pops a visible window into the user's active desktop. Default to headless `mcp__playwright__*`; reach for headed only when the user explicitly asks to watch/record.

## Why this matters

claude-in-chrome is powerful *because* it has the user's session — and that's exactly why it's the wrong default. Every tab opened, every form filled, every click happens in their real browser, visible to them, against their real accounts. Reserve it for tasks where the session IS the point. For everything else, an isolated Playwright browser is faster, cleaner, and reversible.
