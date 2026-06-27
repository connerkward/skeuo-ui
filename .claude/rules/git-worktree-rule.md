---
name: "git-worktree-rule"
id: "git-worktree-01"
description: "Assume multiple agents share every local repo: don't branch-in-place or switch branches in the shared checkout — isolate non-trivial work in a git worktree, keep the shared checkout on main."
globs: ["**/*"]
applyTo: ["**/*"]
alwaysApply: false
priority: "high"
human-reviewed-at: 2026-06-16
human-reviewed-by: connerward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---
# Multi-agent git — assume a shared checkout; isolate with worktrees, not in-place branches

**Always assume more than one agent is working in the same local repo at the
same time.** This is the default, not the exception — a single working directory
has exactly **one branch checked out** and **one set of files**, so anything that
changes that shared state reaches under every other agent in the checkout. The
proof is concrete: two agents committed to the same `comfyui-pipeline` branch in
one shared `skeuo-ui` checkout, interleaved, each unaware of the other (2026-06-16).

## The policy

1. **Don't create a branch and work in the shared checkout, and don't `git
   checkout` / switch its branch.** Switching the shared checkout's branch yanks
   the tree out from under whoever else is editing it. Keep the shared checkout
   on **`main`** as a stable common base.
2. **Isolate real work in a git worktree** — its own directory *and* its own
   branch, so edits, HMR, dev servers, and branch state never collide:
   ```bash
   git worktree add ../<repo>-<topic> -b <topic-branch>   # new dir + new branch
   # work there; commit + push from there
   git worktree remove ../<repo>-<topic>                  # when done
   ```
   The branch lives *with* the worktree — that is the point. "Use worktrees, not
   branches" means: don't branch-in-place; spin the branch up inside its own
   worktree.
3. **Restraint still applies — don't reflexively spin up a worktree for a
   one-line fix.** Worktrees cost a directory, per-tree `node_modules`/deps, and
   cleanup. For a trivial edit where you're confident no one else is touching the
   repo, working in place is fine. Reach for a worktree when the work is
   non-trivial OR concurrent collision is plausible — *"if truly necessary, if you
   really must."* See [[restraint-rule]].

## Shared-state hygiene (when you do touch the shared checkout)

- **Commit + push your own work promptly** — origin is the safety net. A branch
  someone else switches away from can't lose committed-and-pushed work.
- **`git status` before any branch/merge/reset op.** Unexpected uncommitted
  changes are probably **another agent's live WIP** — never clobber them. (Here:
  a stray `.gitignore` edit was another agent's; it was left untouched.)
- **Scope `git add` to your own files**, never `git add -A` / `.` blindly — it
  sweeps another agent's WIP into your commit.
- **Avoid repo-wide destructive ops** that hit others' uncommitted work:
  `git reset --hard`, `git checkout -- .`, `git stash` (stashes *everyone's*
  changes), `git clean -fd`, and force-pushing a shared branch.
- **Merge without a checkout switch when you can.** If `main` fast-forwards into
  your branch, update the ref instead of switching the shared tree:
  `git branch -f main <branch> && git push origin main` — leaves the working tree
  and its dirty state untouched.

## Relation to other rules

- [[web-dev-rule]] — the web-specific case (per-worktree dev server port + Playwright
  profile isolation); this rule is the general git stance behind it.
- [[parallel-by-default-rule]] — when fanning out agents that mutate files, give
  each `isolation: "worktree"`.
- `git` skill — commit/push/branch policy (commit promptly, branch first off the
  default branch); this rule refines *where* that branch should live (a worktree).
