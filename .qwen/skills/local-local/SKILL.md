---
name: local-local
description: The local.local services dashboard on lappy-heavy — a status board of every local app/daemon (muser, feed-demon, ollama, caddy…). Use when adding a NEW local service/app that should appear at local.local, exposing an app at a <name>.local hostname via Caddy, registering a LaunchAgent for a local server, or asking what local services are running. Covers the machine's local-`.local` reverse-proxy convention.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# local.local — local services dashboard

**Repo:** `~/dev/local-local` (single-file stdlib dashboard; runs as the `com.local.serve`
LaunchAgent behind Caddy at http://local.local on lappy-heavy).

When the user wants to **add a service/app to local.local**, expose something at a
`<name>.local` / `<name>.localhost` hostname, or asks what's running locally:

1. Read `~/dev/local-local/CLAUDE.md` — it has the exact steps for adding a UI app
   (Caddy block — auto-discovered, no dashboard edit) vs a non-UI daemon (registry edit),
   the port/LaunchAgent/Caddy/`/etc/hosts` convention, and what needs sudo.
2. The deeper machine wiring (Caddy install, history, reversal recipes) lives in
   `central/skills/machines/personal-machines/references/per_lappy_heavy.md` →
   "Local hostnames → Caddy reverse proxy".

If `~/dev/local-local` doesn't exist on this machine, this skill only applies to
lappy-heavy (the dashboard is host-specific). On other hosts, the same *pattern* (Caddy
`.local` proxy + KeepAlive LaunchAgent) can be set up fresh from the CLAUDE.md recipe.

**After any machine-state change** (new Caddy block, `/etc/hosts` line, LaunchAgent),
document it in `per_lappy_heavy.md` with a reversal recipe and commit+push central
(machine-config rule).
