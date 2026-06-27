---
name: machines
description: Fleet and environment context. Use when you need machine, network, or storage topology, or to identify the current host you're running on.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Machines (Orchestrator)

## Fleet Roster

| Machine | OS | Always on? |
|---------|-----|-----------|
| Desky | Windows 10 | Yes |
| Lappy | macOS (M1 Air) | No |
| LappyHeavy | macOS (M1 Max) | No |
| MoGo (XGIMI MoGo 2 Pro) | Android TV | No — projector, on when in use |

## Scope

By default, load only the per-machine doc for the current host from
[personal-machines/](personal-machines/) — its [SKILL.md](personal-machines/SKILL.md)
indexes the `references/per_<host>.md` docs (machine config, networks, storage).
Load the full fleet only when a task spans machines.

**Task skills:** [../linear/](../linear/), [../git/](../git/), [../python/](../python/), [../docs/](../docs/).

## Documenting persistent system changes (always do this)

Machine state is not git-tracked. Every time you modify persistent system config — the
kind of change that survives a reboot, affects other processes, or is invisible from
inside a repo — **record it in `personal-machines/references/per_<host>.md`**, then run the
central export and push in the same session. An undocumented system tweak is a future trap:
six months later "why does `muser.local` resolve?" has no answer except the per-machine doc.

**Triggers (document any of these):** `/etc/hosts`, `/etc/pf.conf`/anchors, `/etc/ssh/*`,
`/etc/sudoers*`, `/etc/synthetic.conf`, `/etc/resolver/*`; `/Library/LaunchDaemons/*`,
`~/Library/LaunchAgents/*` (any boot/login plist); `launchctl bootstrap`/`load` of a
persistent service; `defaults write` against system/app domains the user relies on;
`scutil --set HostName/LocalHostName/ComputerName`; `pfctl -E`/`-f`; Homebrew taps /
`brew services` / formula pinning; mDNS advertisements (`dns-sd`, `avahi-publish`); new
users/groups, ssh authorized_keys outside the default flow; kernel/system extensions, login
items, accessibility/automation grants; cron (`crontab -e`) / Windows `schtasks`; firewall
rules; any sudo edit under `/etc`, `/Library`, `/System`, `/usr/local/etc`, `/opt/homebrew/etc`.
If you reach for `sudo` and it isn't a one-off install, assume it's in scope.

**Does NOT count:** repo-local committed config; ephemeral `/tmp`/background processes;
export-pipeline-managed files (central's `.claude/` symlinks); standard package installs
with no persistent service (`brew install ripgrep`).

**Every entry needs a one-line reversal recipe** — e.g. "remove the line from `/etc/hosts`,
delete `/Library/LaunchDaemons/com.foo.plist`, `sudo launchctl bootout system/com.foo`,
`sudo pfctl -d`." Without a reversal you've created an artifact future-you can't safely undo.
Use headed sections by config type (`LaunchAgents`, `LaunchDaemons`, `Local hostnames`,
`pf rules`, `Shells`) so the next agent scans in seconds. Windows: `per_desky.md`, same pattern.

## Central Repo Sync

All machines auto-pull `central` every 1 minute via cron/scheduled task. Pulls never
trigger a push (no feedback loop); a push on any machine propagates within ~1 min.

| Machine | Mechanism | Central path |
|---------|-----------|-------------|
| Desky | schtasks `CentralSync` (1 min) | `C:\Users\conner\dev\central` |
| Macs | crontab (`* * * * *`) | `~/dev/central` |

To add a new machine: clone `central`, run `scripts/setup-machine` (wires the global
rule/skill symlinks and builds the in-repo Swift tools — `sck-record`,
`say-notify-overlayd` — from source), add a 1-minute `git pull --ff-only`
cron/scheduled task. All skills are self-contained in `central/skills/`; nothing is
cloned from external repos (publishing is outbound — see [[publish-skill]]).
