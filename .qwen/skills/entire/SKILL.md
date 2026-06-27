---
name: entire
description: Entire CLI — captures Claude Code (and other AI agent) sessions alongside git commits, indexes them for search/recap/dispatch. On lappy-heavy, all ~/dev repos are auto-enabled with a private-checkpoint-repo privacy model.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Entire

**Repo:** `https://github.com/entireio/cli`
**Docs:** https://docs.entire.io/ · [Security & Privacy](https://docs.entire.io/security) · [Checkpoints](https://docs.entire.io/cli/checkpoints)

TRIGGER when: user wants to enable session tracking in a repo, asks about Entire CLI, asks about searching prior agent sessions, mentions checkpoints/recap/dispatch, or asks why a repo is/isn't tracked.

## How Entire stores data (the privacy-critical part)

Everything Entire records — **full transcripts, prompts, summaries** — is stored as git objects on an orphan branch `entire/checkpoints/v1`, and on `git push` that branch is pushed to a **checkpoint remote**. By default the checkpoint remote IS the code repo's own origin, so **on a public repo your full agent transcripts become public**. Secret redaction is best-effort (entropy + Betterleaks ~260 patterns + credential/URI/DB-string detection) and explicitly *not* a guarantee — novel secrets, low-entropy passwords, and secrets in filenames/binaries can slip through. The CLI is local-first: data leaves the machine only on `git push` (already-redacted branch), `checkpoint explain --generate` (compacted transcript → your LLM provider), and anonymous telemetry (no transcript/code/paths).

## This machine (lappy-heavy): Model 2 + auto-enable

**All `~/dev` git repos are enabled** (set up 2026-06-18), with a privacy posture chosen per repo so transcripts never land somewhere public:

- **Repos owned by `connerkward`** → **Model 2**: `checkpoint_remote = github:connerkward/entire-checkpoints` (a **private** repo). Checkpoints push there, **never** to the (often public) code remote. This is Entire's own recommended pattern for public code + private sessions.
- **Forks / repos owned by someone else, or with no origin** → **local-only** (`push_sessions:false`): sessions stay on this machine and never attempt a push. (A fork's origin isn't ours; Entire's fork-detection would skip the checkpoint push anyway and could fall back to the fork's origin — local-only removes that risk entirely.) Currently local-only: comfyui-mcp, davinci-resolve-mcp, notesutils, feed-demon, local-local.

**Auto-enable for new repos:** a `chpwd` hook in `~/.zshrc` runs `central/scripts/entire-autoenable` the first time you `cd` into any un-enabled git repo under `~/dev`. It picks Model 2 vs local-only by origin owner, drops the duplicate per-repo Claude hooks, and adds `.entire/` to the repo-local exclude. Idempotent; backgrounded; runs once per repo. **Opt a repo out** by `touch .entire/.skip`.

### Why `.entire/` is git-excluded, not committed
The autoenable script adds `.entire/` to each repo's `.git/info/exclude`. Reasons: (1) checkpoint capture/push is driven by the **local** `.entire/settings.json` + git hooks, so committing isn't needed for it to work; (2) not committing keeps the private checkpoint-repo name out of public code repos; (3) committing `.entire/settings.json` is only required for the entire.io **web dashboard** to cross-locate checkpoint data — and we're not logged in / not using the dashboard. If you later want dashboard cross-repo linking, commit `.entire/settings.json` and remove the exclude line.

### Why the per-repo Claude hooks are removed
`entire enable --agent claude-code` installs 7 hooks into a per-repo `.claude/settings.json` — but the **user-level** hooks in `~/.claude/settings.json` already fire on every session and honor each repo's `.entire/settings.json` (they're gated on that file existing). Keeping both = every hook fires twice. So autoenable runs `entire agent remove claude-code` and cleans the untracked `.claude/` leftovers, relying on the user-level hooks. `.entire/` + the orphan branch are all Entire actually needs.

## Enabling / re-normalizing a repo

```bash
~/dev/central/scripts/entire-autoenable [dir]    # the canonical path — owner-aware, idempotent, cleans up
```
Raw equivalents (if you must, and understand the privacy implications):
```bash
# owned repo, sessions private:
entire enable --agent claude-code --checkpoint-remote github:connerkward/entire-checkpoints --telemetry=false -y
# fork / untrusted origin, sessions stay local:
entire enable --agent claude-code --skip-push-sessions --telemetry=false -y
entire agent remove claude-code     # drop duplicate per-repo hooks
```
**Never** plain `entire enable` on a repo with a public origin without `--checkpoint-remote` (private) or `--skip-push-sessions` — that publishes transcripts.

## Useful commands

- `entire status` — repo enablement / sync state
- `entire checkpoint list` — checkpoints on this branch
- `entire checkpoint explain <id|sha>` — what a commit's session was doing (links commit → session)
- `entire checkpoint rewind` — browse/restore prior state
- `entire checkpoint search "<query>"` — semantic search across sessions (**requires `entire login`**)
- `entire activity` / `entire recap` — recent-work overview / narrative summary (login for cloud features)
- `entire session list|info|current` — sessions across worktrees
- `entire disable` — remove tracking from current repo

## Mapping a commit → the session that made it

If the commit was made while Entire was active, it carries an `Entire-Checkpoint` trailer: `entire checkpoint explain <sha>`. If not (Muser commits before 2026-06-18 predate enablement), fall back to grepping the raw Claude Code transcripts in `~/.claude/projects/<url-encoded-repo-path>/<session-uuid>.jsonl` for the commit message.
