---
name: "parallel-by-default-rule"
id: "parallel-01"
description: "Fan out independent work concurrently: batch independent tool calls in one message, spawn subagents for independent strands, escalate to a Workflow only on explicit opt-in."
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

# Parallelize by default — fan out independent work

When a task decomposes into pieces that don't depend on each other, run them
**concurrently**, not one after another. Sequential-by-default wastes the user's
wall-clock time; independent work has no reason to be serialized. Default to
parallel; fall back to sequential only when there's a real dependency.

## The reflex

Before doing N things in a row, ask: *does step 2 need the output of step 1?*
- **No** → do them at once.
- **Yes** → sequential is correct; don't force it.

## Three levers, smallest first

1. **Batch independent tool calls in ONE message.** Multiple reads, greps,
   bash commands, web fetches with no data dependency → emit them together, not
   in a chain of single-call turns. This is the cheapest win and the most-missed.
2. **Fan out subagents (`Agent` tool) for independent investigation or edits.**
   Searching several subsystems, reviewing many files, researching parallel
   questions, applying the same transform across many sites → one `Agent` per
   strand, launched in a single message so they run at once. Each returns its
   conclusion; you synthesize. Use `isolation: "worktree"` when agents mutate
   files in parallel and would otherwise collide.
3. **Orchestrate a `Workflow`** for structured multi-phase fan-out (decompose →
   parallel cover → verify → synthesize). This is the heavyweight option and
   requires explicit user opt-in (the keyword "ultracode", "use a workflow", a
   skill that calls it, etc.) — do NOT launch it unprompted. **When a task looks
   like it would genuinely benefit from a Workflow (broad audit, large migration,
   multi-phase review), say so and ASK whether to run one** — give a one-line
   sketch of what it'd do and a rough cost — rather than either launching it
   silently or staying quiet. Levers 1 and 2 need no opt-in; use them freely.

## Don't defer what you can do now

When the user asks for something **actionable and independent of your current
work, do it NOW — don't say you'll "do it later."** "I'll fold that in after",
"I'll get to that next", "noted, will handle it later" are deferrals, and a
deferral of an independent task you could fan out is the failure: it makes the
user wait on, and re-ask for, something a batched tool call or a spawned
subagent would have finished in the same turn. The concrete miss: the user
asked for a thing mid-task, and instead of just doing it in parallel right
then, the assistant promised to "fold it in later."

The reflex: a new ask lands → ask *does this depend on what I'm doing?*
- **No** → kick it off immediately alongside the current work (lever 1 or 2
  above — a batched call, a parallel `Agent`). Both finish this turn.
- **Yes** → say so and sequence it; that's the only license to defer.

"Later" is for genuinely blocked work, not for independent work you'd rather
not interrupt your flow for. Parallelize and complete it.

## When NOT to parallelize

- **Genuine data dependency** — step N consumes step N-1's output. Pipeline it,
  don't fake concurrency.
- **A coupled pipeline split across agents = seam bugs.** When a feature is a chain
  whose stages share data shapes (names, coordinate spaces, formats, decode method),
  do NOT fan it out to parallel agents and hope the seams line up — they won't. Each
  agent guesses the contract differently and you spend longer reconciling the
  mismatches than the parallelism saved. Burn (skeuo-ui, 2026-06-23): a
  blueprint→prompt→cut→detect→render pipeline split across agents produced
  incompatible sprite-naming, cut geometry, and decode methods at every seam. If you
  must split coupled work, **write the exact seam contract FIRST** (the types, names,
  coordinate spaces, formats both sides must honor) and hand it to every agent;
  otherwise do the chain as one coherent pass. Independent *fan-out* (N files, N
  finders, N searches) is still the default — this exception is only for a single
  data-dependent chain.
- **Shared mutable state** without isolation — two agents editing the same file
  on the same branch stomp each other (see `web-dev-rule`). Isolate or serialize.
- **Trivial / tiny tasks** — spinning up agents for two quick edits costs more
  setup than it saves. Match scale to the work.
- **Order matters for safety** — migrations, destructive steps, anything where
  interleaving changes the outcome.

## Match scale to the task

A two-file question is a batched read, not an agent fleet. A broad audit across
twenty modules is a real fan-out. Don't under-parallelize routine sweeps; don't
over-engineer a fleet for what one batched message handles. The goal is the
user's time, not agent count — see `software-engineering-rule` (autonomy: don't
waste my time) and `restraint-rule` (don't build more than the task needs).
