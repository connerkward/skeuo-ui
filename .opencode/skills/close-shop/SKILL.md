---
name: close-shop
description: End-of-session wrap-up. Use when the user says "close shop" (or "wrap up", "shut it down", "end of session", "pack it up") — document what changed, update TODO, commit + push every touched repo, clean up loose ends (stray files, dev servers, background tasks), then report a per-repo summary.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Close Shop

The end-of-session ritual. When the user signals they're done ("close shop"), run this **autonomously, without asking for confirmation** — they've already opted in by saying it. Do every step that applies; skip silently any that don't.

A `UserPromptSubmit` hook fires deterministically on the phrase "close shop" and tells you to load this skill — but the skill is the single source of truth for *what the routine is*, so it also works via `/close-shop` or any wrap-up phrasing.

## The routine

1. **Docs / TODO.** Update the project's `TODO.md` / `README` / notes to reflect what changed this session: tick off completed items, add any new follow-ups or loose ends you discovered, and write dates as absolute (`YYYY-MM-DD`), not "today".

2. **Project timeline.** For each project worked on this session, update its entry in [[project-timeline]] (`central/skills/project-timeline/timeline.json`): set `touched` to today, bump `progress` to the honest current value, update `status`/`note`, and set top-level `updated`. Match the entry by `id` **or** `aka`; if the repo was renamed, edit that entry in place (append the old id to `aka`) rather than adding a duplicate. Add a new entry only for a genuinely new project. This is the low-friction tracker rendered as a Gantt at war-room.ward.run/timeline — keeping it current here is what keeps the board current everywhere.

3. **Commit.** Stage and commit *all* outstanding changes in every git repo you touched this session. Clear message describing the change, not the tool. Honor [[git-attribution-rule]] — no `Co-Authored-By` / "Generated with" lines, commit as the user. If you're on a protected default branch and policy requires a branch, branch first ([[software-engineering-rule]] reversibility).

4. **Push.** Push every repo that has an upstream remote.

5. **Clean up loose ends.**
   - Remove stray scratch / screenshot / temp artifacts you created (route media through `trash`, not `rm` — [[media-rm-rule]]; `/tmp` and `.scratch/` are fine to `rm`).
   - Stop any dev servers you started: `~/dev/central/scripts/serve --stop <dir>` (never a broad `pkill` — [[web-dev-rule]]).
   - Wind down background tasks / loops / Monitors you spawned.

6. **Report.** End with a concise per-repo summary: commit hash + subject, what was pushed, what was cleaned up, and anything left unresolved or needing the user's attention. Lead with the result, no preamble ([[anti-sycophancy-rule]]).

## Scope

"Repos you touched this session" — not a fleet-wide sweep. If `central` itself was edited (rules/skills), include the export step (run `export_config.py`, commit sources + regenerated exports together — see [[universal-rule-skill-export]]).
