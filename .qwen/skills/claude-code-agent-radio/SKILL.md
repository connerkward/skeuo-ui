---
name: claude-code-agent-radio
description: RTS-style "incoming transmission" notifications for Claude Code — per-window callsigns, spoken radio chatter, a retro portrait overlay card, focus-aware quiet, and rate-limit "fuel gauge" callouts. Use when configuring, debugging, or extending the spoken/visual agent-notification system (the say-notify hook), changing callsign logic, the overlay daemon, phrase pools, voices, or the rate-limit fuel callout.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# claude-code-agent-radio

The skill's files live in this directory. `~/dev/central/scripts/agent-radio/` is a symlink
**into** this dir, so the machine wiring keeps resolving against a stable path:
- **Notification + Stop hooks** (`~/.claude/settings.json`) → `…/scripts/agent-radio/say-notify.sh`
- **Overlay daemon LaunchAgent** (`com.conner.say-notify-overlayd`) → `…/scripts/agent-radio/say-notify-overlayd` (compiled from `say-notify-overlayd.swift`, gitignored, rebuilt by `setup-machine`)
- The dev-server **statusline** (`central/scripts/statusline-devservers.sh`, machine-local) renders the rate-limit fuel gauge and fires `say-notify.sh` on a threshold crossing.

Published publicly as `connerkward/claude-code-agent-radio` via the [[publish-skill]] skill.

Read `README.md` for the full design; key files:
- `say-notify.sh` — the hook: callsign derivation, event routing, focus gating, TTS, fires the card + audio.
- `say-notify-overlayd.swift` → `say-notify-overlayd` — the persistent non-focus-stealing overlay daemon (card-request files in `$TMPDIR/say-notify-cards`).
- `say-callsign.sh` — name the current window's callsign.
- `say-notify-quotes.sh` / `say-notify-phrases.md` — phrase pools.
- `say-notify-devserver.py` — lookdev studio for tuning the card/voices.

Machine-specific wiring (hook registration, LaunchAgent, statusline) is documented in `central/skills/machines/personal-machines/references/per_lappy_heavy.md`.
