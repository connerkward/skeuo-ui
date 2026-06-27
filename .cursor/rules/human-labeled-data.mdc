---
name: "human-labeled-data-rule"
id: "human-labels-01"
description: "Human-labeled data is irreplaceable: never silently return empty on a failed read, serialize read-modify-write, guard catastrophic shrink, keep rolling backups. Detail in the human-labeled-data skill."
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

# Human-labeled data is GOLD — never lose it

Any file holding human judgments — labels, flags, annotations, ratings, eval verdicts,
hand-entered corrections, curated names/merges — is **hours of irreplaceable human time in
a small file**. Code regenerates, model outputs recompute; human labels do neither. Treat
label stores with the paranoia `media-rm-rule` applies to media: reversible everything.

When writing or reviewing ANY read/write code for such a store, the four invariants are
mandatory:

1. **Never silently return `{}` on a failed read.** A file that exists but won't parse is
   an emergency: quarantine (`<name>.corrupt-<ts>`) then **raise**. The silent fallback is
   the data destroyer — every later save clobbers from empty.
2. **Serialize read-modify-write** (a lock). Bulk ops = ONE load + ONE save, never N cycles.
3. **Guard catastrophic shrink** — snapshot before a replace that drops a large fraction of entries.
4. **Rolling `.bak`** on a write-activity timer.

This is failure-anchored: 2026-06-12 a tmp-filename race + a silent `except JSONDecodeError:
return {}` wiped ~1,800 labels. Full detail (the burn, secondary lessons, concurrency-test
checklist): load the **`human-labeled-data`** skill. Related: `verify-outputs-rule` (check
counts before AND after).
