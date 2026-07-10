# On Fable/Opus, the main thread orchestrates — execution goes to subagents

Project rule (user directive 2026-07-10). When the MAIN conversation is running on a
SOTA-tier model (**Fable, Opus**, or any comparably slow/expensive tier), it must stay a
non-blocking orchestration loop: **by default, defer any non-orchestration task to a
background subagent** instead of executing it inline.

**Why:** inline main-thread work (multi-step edits, builds, verification passes, long tool
chains) blocks the user's ability to type feedback and get responses while it runs. Code
changes executing in background agents cost the user nothing — they can keep talking,
redirecting, and reviewing freely. The main thread's job is routing, synthesis, and
answering; heavy hands belong to agents.

**Main-thread-appropriate (do inline):**
- Answering questions, analysis, recommendations, plans.
- Orchestration: spawning/messaging/monitoring agents, routing user feedback to owners.
- Trivial single-shot actions cheaper than a spawn: a one-line edit + commit, a quick
  grep/read to answer "where is X", a status check, arming a watcher.
- Anything the user explicitly asks the main thread to do itself.

**Defer to a subagent (default for):**
- Multi-file or multi-step code changes, refactors, feature work.
- Build/regenerate/verify cycles (players, dashboards, experiments, videos).
- Investigations requiring many file reads or tool round-trips.
- Anything with an unbounded or >~1-minute inline tool chain.

**Rules of thumb:** if it needs more than ~3 tool calls of hands-on work, spawn it. Batch
independent spawns in one message ([[parallel-by-default-rule]]); give each agent explicit
file ownership (shared-checkout discipline). On non-SOTA main models (Sonnet, Haiku) this
rule is advisory — the blocking cost is lower — but the orchestration-first posture still
scales better whenever agents are already in flight.
