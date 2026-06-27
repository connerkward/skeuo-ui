---
name: "dev-server-chrome-tab-rule"
id: "dev-chrome-tab-01"
description: "When a local dev server is serving a page, always mirror its URL into one dedicated claude-in-chrome tab so the human can watch the app live; manage the tab on port change and close it when the server stops."
globs: ["**/*"]
applyTo: ["**/*"]
alwaysApply: true
priority: "high"
human-reviewed-at: 2026-06-16
human-reviewed-by: connerward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Dev server → its own Claude-in-Chrome tab (always)

When a local **dev server that serves a webpage** is running (Vite, Next, CRA,
Astro, `vite preview`, `python3 -m http.server`, a lookdev studio, any
`http://localhost`/`127.0.0.1`/LAN-IP page), **ALWAYS open its URL in its own
dedicated `claude-in-chrome` tab** so the human can watch the running app live in
their real browser. Do this as soon as the server is up and actually serving
(responds 200), without being asked.

## Rules

- **One tab per dev server.** Each running web dev server gets exactly one
  dedicated tab. Don't scatter the same app across multiple tabs.
- **Open the reachable URL** — the one the server actually prints / that responds
  (including LAN-IP binds like `http://192.168.8.x:5173`, not a localhost URL the
  server isn't listening on).
- **On PORT / URL / HOST CHANGE** (server restarts on a new port, Vite falls
  through 5173→5174, you rebind to a new host or LAN IP): open the **new** URL in
  a tab **and close the old / stale tab**. Never leave a dead tab pointing at a
  port nothing is listening on.
- **Reuse, don't spam.** If the URL is unchanged and a tab for it already exists,
  reuse it (navigate/refresh) instead of opening another. Only open a new tab when
  the URL changed; close the superseded one.
- **When the server stops** (you kill it, it crashes, task ends), close its tab —
  a stale tab on a dead server is noise.

## Why this is an exception to the default routing

`browser-tool-routing-rule` says *prefer headless Playwright for dev work and
reserve `claude-in-chrome` for the user's real session*. That still holds for
**your own automated verification** — keep doing screenshots / DOM checks /
click-throughs in headless Playwright. This rule is **additive and for the human's
visibility**: the `claude-in-chrome` tab exists purely so the user can see the
running app in their own Chrome and follow along. Use both — Playwright to verify,
the Chrome tab to show.

## Mechanics

- Load the chrome MCP tools once (`tabs_context_mcp` first to see existing tabs,
  then `tabs_create_mcp` / `navigate` / `tabs_close_mcp`).
- Track which tab belongs to which server URL so you can navigate/close the right
  one on a port change.

Related: `web-dev-rule` (server lifecycle, port isolation, never broad `pkill`),
`browser-tool-routing-rule` (which browser tool for what).
