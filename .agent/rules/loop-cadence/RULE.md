---
name: "loop-cadence-rule"
id: "loop-cadence-01"
description: "Don't self-schedule rigid short wakeup/return intervals in loops/goal mode: prefer event-driven over polling, lean long and coarse when self-pacing; coarse cadence, rich reports."
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

# Loop / wakeup cadence — don't self-schedule on a rigid short clock

In loops, goal mode, and any self-paced check-back (`ScheduleWakeup` and friends), the
default tendency is to return and re-wake on a **very specific, too-frequent interval** —
"I'll check back in 4 minutes," then again, and again. Override that. Frequent rigid
wake-ups burn tokens, fragment the work, and pull the user back more often than the task
warrants.

## The default stance

- **Prefer event-driven over polling.** When the harness re-invokes you automatically once
  tracked work finishes (a background task, a spawned agent, a build it knows about), that
  is the wake signal — adding a short poll on top is wasted. Wait for the event; don't set
  a metronome to re-check work that will notify you anyway.
- **When you genuinely must self-pace, lean long and coarse.** Pick the delay from *what
  you're actually waiting on* — how fast that state really changes — not from a reflex
  number. Idle "just checking in" ticks should be infrequent. Round, generous intervals
  over precise short ones.
- **Don't bind the user to a fixed cadence.** Don't promise or perform "every N minutes."
  Returning to the user is for a state change worth their attention — a result, a decision,
  a blocker — not the passage of a timer.

## When a short, specific interval IS right

Only when the thing you're watching changes fast *and* the harness can't notify you of it —
an external CI run, a remote queue, a deploy whose state you must poll yourself. There,
match the interval to that external state's real cadence and say what you're waiting on.
That is the exception, not the rhythm.

## Relation to reporting — still give a progress bar

This rule loosens **how often** you wake/return. It does **not** reduce reporting. The user
wants visible progress: every time you do check back or wake on long-running work, emit a
full progress report — elapsed, estimated remaining, current stage, and a textual progress
bar (e.g. `[####------] 40%`), per `software-engineering-rule`. And always report at
completion.

The only thing this rule cuts is the *metronome*: don't wake every-N-seconds just to print
a bar that barely moved. Fewer, coarser, event-driven wake-ups — but each one carries a
real progress report, never a bare "still working." Coarse cadence, rich reports.
