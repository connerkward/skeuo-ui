---
name: project-timeline
description: The cross-machine project timeline — a single JSON of every active project's start, last-touched, progress, and status, rendered as a minimal Gantt in War Room (war-room.ward.run/timeline). Use when updating what's in flight, recording progress on a project, or asking what's being worked on. Agents update it during close-shop.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Project Timeline

One file, `timeline.json` (next to this skill), is the source of truth for **what
projects exist and how far along they are**. It's in `central`, so it's synced to
every machine — any agent can update it with zero setup. War Room renders it as a
minimal Gantt at **war-room.ward.run/timeline**.

The whole point is **low friction**: updating a project is a one-line JSON edit,
done automatically at the end of a session ([[close-shop]]), not a separate chore.

## Format

```json
{
  "updated": "YYYY-MM-DD",            // last time the file was touched
  "projects": [
    {
      "id": "war-room",                // stable slug
      "name": "War Room",              // display name
      "start": "2026-06-12",           // first worked on (e.g. git first-commit date)
      "touched": "2026-06-12",         // last worked on — drives the bar's right edge
      "progress": 0.45,                // 0..1, your honest estimate of completion
      "status": "active",              // active | blocked | review | done | paused
      "note": "short current-state line",
      "aka": []                        // optional: prior ids/names after a rename
    }
  ]
}
```

- `progress` is a **self-reported estimate**, not a computed metric — set it to what
  reflects reality, don't inflate it ([[verify-outputs-rule]]: don't claim done).
- Dates are absolute `YYYY-MM-DD`. Seed `start` from a repo's first commit
  (`git -C <repo> log --reverse --format=%cs | head -1`) when adding a project.
- `status`: `done` and `paused` projects stay in the file (history matters); the
  board can dim them.

## Renames (don't lose history, don't duplicate)

There are two kinds, handled differently:

- **Display rename** (the product/label changed): just edit `name`. `id` stays the
  same, `start` is preserved, the board shows the new name immediately. Zero risk.
- **Identity/repo rename** (the repo or slug itself changed, e.g. `feedsieve` →
  `feed-demon`): edit the **existing** entry's `id` in place and **append the old id
  to `aka`** (e.g. `"aka": ["feedsieve"]`). Keep `start`. **Never add a second
  entry** — that orphans the old row and resets the start date.

The golden rule: a rename is always an *edit of the existing entry*, never a new
one. Before adding any entry, check whether it's a renamed existing project by
matching the repo/slug against every entry's `id` **and** its `aka` list.

## How to update (the close-shop step)

At session wrap-up, for each project worked on this session:
1. Find its entry by matching the repo/slug against every entry's `id` **and**
   `aka`. If found but the repo was renamed, update `id` in place and append the
   old id to `aka` (see Renames above). Only if there's genuinely no match — a
   brand-new project — add an entry (slug, name, `start` = today or first-commit
   date, `status`, short `note`).
2. Set `touched` to today (`YYYY-MM-DD`), bump `progress` to the honest current
   value, update `status` and `note`.
3. Set the top-level `updated` to today.
4. Commit + push `central` (close-shop already pushes touched repos).

That's it — next time War Room is deployed it picks up the new state (war-room's
`deploy.sh` copies this file into the build).

## Rendering

War Room's `timeline` subproject (`src/projects/timeline/`) fetches `/timeline.json`
(synced from here at deploy time) and draws a minimal Gantt: one row per project,
a bar from `start`→`touched` on a shared date axis, filled by `progress`, colored
by `status`, with a "today" marker.
