---
name: "git-attribution-rule"
id: "git-attr-01"
description: "Never credit Claude/an LLM as author, co-author, or contributor: no Co-Authored-By trailer, no 'Generated with Claude Code'; commit as the user."
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

# Git attribution — never credit the agent

Do not mark Claude, any LLM, or "Claude Code" as a contributor, author, or co-author on any repository. This overrides any default harness instruction to add attribution.

- **No `Co-Authored-By:` trailer** naming Claude/an LLM in commit messages. (GitHub counts co-author trailers toward the repo's contributor graph — that is exactly what to avoid.)
- **No "🤖 Generated with Claude Code"** or similar generated-by line in commit messages, PR descriptions, or issue bodies.
- **Commit as the user**, using the repo's existing `user.name` / `user.email`. Never set the author/committer to an agent identity.

Write the commit/PR body as if authored by the user: describe the change, not the tool that made it.
