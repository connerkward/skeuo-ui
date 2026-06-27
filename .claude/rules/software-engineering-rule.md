---
name: "software-engineering-rule"
id: "se-rule-01"
description: "When doing software architecture or code. Simplicity, delete-first, autonomy, test before returning."
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
- **Simplify and delete.** Don't over-engineer. Liberally delete and streamline; if you aren't forced to add at least 10% back later, you aren't deleting enough. Offload complexity to others code, like packages, assuming they are vetted and reliable. DRY; centralize duplicated data or logic. "Best Part is No Part" — software is a liability. Produce less. Via Negativa: remove what makes the system fragile before adding features. Accelerate cycle time; radical simplicity. Don't optimize problems that should not exist. Question the user if requirements dont make sense to you. Avoid writing over package, comfyui custom node, or externally created code unless truly truly necessary.
- **Autonomy.** DO NOT WASTE MY TIME. Minimize human time spent; maximize importance of time spent. Test code yourself before returning. If you can run a command, run it. Never hand back untested code. Do not waste the user's time. If you can watch a log live while I have to manually test it, do so. I should not need to prompt you again to check the log on a long running task. Use sleep command to watch it. THE ULTIMATE GOAL SHOULD BE AS LITTLE HUMAN TIME WASTED / SPENT!
- **Long-running work.** Progress indicator or time estimate for batch jobs, IO, API loops, large iterations. Prefer autonomous check-back (e.g. sleep based on estimate); don't return until the task is completed. Always surface a progress report: every ping carries (1) time elapsed, (2) estimated time remaining, (3) current stage/step, (4) a textual progress bar (e.g. `[####------] 40%`), and you report again at completion. **How OFTEN you wake to do this is governed by [[loop-cadence-rule]] — coarse, event-driven cadence, not a rigid short clock — but each wake still carries the full bar/report; the cadence rule loosens the interval, never the content.** Compute elapsed portably — macOS `ps` has no `etimes` keyword (Linux-only); use `stat -f %B <logfile>` (file birth epoch) or a recorded `date +%s` delta instead.
- **Debugging discipline.** Investigate the root cause before fixing — read the full error, reproduce it, check what changed recently; never patch a symptom. Trace a bad value *backward* up the call chain to where it originates and fix it there, not where it surfaces. After ~3 failed fixes, stop and question the architecture/assumptions instead of trying a 4th patch. In *test code*, wait by polling for the actual condition, not `sleep()` — arbitrary sleeps pass locally and go flaky under load (distinct from the Autonomy rule's "sleep to watch a long-running log," which stays fine).
- **Make green mean something.** "I tested it" isn't enough — the test must be *able to fail*. Avoid the vacuous-green traps: asserting a mock exists or was constructed, adding test-only methods to production code, mocking a dependency you don't understand, partial mocks that don't mirror the real API, treating tests as an afterthought. A test that passes without exercising real behavior is worse than none — it hides the gap behind a green check.
- **Reversibility** Be extremely liberal when modifiying code that has been git tracked/commited, as it is reversible. Be very conservative when modifying systems, like OS, AWS, etc, as these may break, and code that has not yet been commited.
- **Always commit and push.** When you make changes to a git repo, always commit and push without asking. Do not ask for confirmation — just do it.
- **Use less tokens, use existing tools** For example, rather than reading files and outputing them during a copy operation, just literally use command line tools to copy.
- **No auto-memory.** Do not use Claude Code's auto-memory feature (the `memory/` directory). All durable knowledge belongs in `central` (skills, rules, references). Auto-memory creates drift and confusion across machines.