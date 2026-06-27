---
name: human-labeled-data
description: How to safely build read/write code for stores of human judgments — labels, flags, annotations, ratings, eval verdicts, curated names/merges. Use when writing or reviewing a label endpoint, a load→mutate→save cycle on a judgments file, or any bulk write to hand-entered data. The always-on floor ("human labels are GOLD, never lose them") lives in human-labeled-data-rule; load this skill for the four invariants in full, the concrete race-condition burn, and the concurrency-test checklist.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# human-labeled-data — protecting label stores (detail)

The floor is always-on in `central/rules/human-labeled-data-rule.md`: **files holding
human judgments are irreplaceable** (code regenerates, model outputs recompute, human
labels do neither). This skill carries the implementation depth.

## The concrete burn (2026-06-12, Muser)

A per-path bulk write looped full read→tmp-write→replace cycles on `eval_labels.json`.
Two concurrent requests collided on the SAME tmp filename, promoted corrupt JSON, and the
loader's `except JSONDecodeError: return {}` silently fell back to empty — so the user's
next single click "saved" a file containing only itself. **~1,800 labels (hours of human
triage) wiped by one race + one silent fallback.** Partial recovery was only possible
because a model trained on the labels survived.

## The four invariants (all mandatory for any label store)

1. **Never silently return empty on a failed read.** Missing file on first run → `{}` is
   fine. A file that EXISTS but fails to parse is an emergency: quarantine it
   (`<name>.corrupt-<ts>`), then **raise**. The silent `{}` is the data destroyer — every
   subsequent save clobbers from an empty base.
2. **Serialize read-modify-write.** Any load→mutate→save needs a lock (in-process
   `threading.Lock` minimum; file lock if multiple processes write). Bulk ops = ONE load +
   ONE save, never N per-item cycles.
3. **Guard against catastrophic shrink.** Before replacing, if new content drops a large
   fraction of entries (e.g. >50 entries AND >50%), snapshot the old file
   (`<name>.pre-shrink-<ts>`) first. Users un-label one at a time; only bugs delete hundreds.
4. **Rolling backups.** Keep a `.bak` updated on a ~5-min write-activity timer. Label files
   are tiny; the human time in them is not.

## Secondary lessons

- **Atomic ≠ safe.** `write tmp → os.replace` protects readers from partial writes but not
  from two writers sharing one tmp path, nor from atomically writing a bad state. Locks +
  guards do.
- **Keep derived artifacts.** Models/predictions trained on labels aren't a substitute, but
  enabled a 99.7%-precision partial restore here. Don't treat them as disposable while the
  source labels have no backup.
- **Fetch doesn't throw on 500.** Label-writing UIs must check `response.ok` and surface
  failure — a UI that says "saved" when the server 500'd hides exactly these failures.
- **Test concurrency before shipping.** Hammer the endpoint with parallel writers; any
  non-200 or lost update is a blocker, not a flake.

Related: `verify-outputs-rule` (the wipe surfaced during verification — check counts before
AND after), `media-rm` (same philosophy: unrecoverable user value routes through reversible
paths only).
