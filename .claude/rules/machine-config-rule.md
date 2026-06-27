---
name: "machine-config-rule"
id: "machine-config-01"
description: "Document every persistent system-config change in the per-host machine doc with a reversal recipe, then export+push central. Triggers and detail in the machines skill."
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

# Machine config — document persistent system changes

Machine state is not git-tracked. Whenever you modify persistent system config — anything
that survives a reboot, affects other processes, or is invisible from inside a repo
(`/etc/hosts`, pf rules, LaunchDaemons/Agents, `defaults write`, hostname, Homebrew
services, cron, firewall, kernel/system extensions, any non-trivial `sudo` edit) — **record
it in `central/skills/machines/personal-machines/references/per_<host>.md`** with what
changed, where (full paths), why, and a one-line reversal recipe; then run the central
export and push in the same session.

Full trigger list, what does NOT count, and the per-host doc structure: load the
**`machines`** skill (it owns this now). An undocumented system tweak is a future trap for
you and every other agent in the fleet.
