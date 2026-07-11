# Incidents

## 2026-07-11 — Unscoped git commits in the shared checkout sweep sibling agents' live WIP

**Symptom:** Two concurrent agent sessions in the shared checkout ran `git commit`
after unscoped staging, sweeping other agents' in-flight uncommitted work into
unrelated commits. Commit 2f3a929c (twoimg experiment) absorbed the
director-switch agent's 6 staged files. Commit 4535f8f3 (first attempt) swept ~40
files of extract12/orchestrate12/knob_angle/regions.json WIP before the damage was
caught and reversed via `git reset -- <paths>` + re-staging.

**Root cause (traced, not assumed):** `git add`/`git commit` without explicit
pathspec in a multi-agent shared checkout; staging area is shared global state.
Each agent believed it was committing only its own files, but unscoped patterns
(`git add .`, commit with a dirty index after partial staging) swept all
uncommitted changes from all agents. The shared checkout enforced no friction
between agents' staging operations.

**Impact:** No data lost either time — both were caught and reversed before push
— but each recovery cost careful diffing (`git diff --name-only --cached` / `git
diff --name-only HEAD` cross-checked against the intended change set), and a sweep
that included a mid-edit file (e.g., a regions.json JSON parse in progress) could
have committed broken state to main. The multi-agent pattern is frequent and
likely to repeat.

**Guardrails added:** Standing instruction (already in agent briefs) that **every
commit in the shared checkout MUST use explicit pathspecs**: `git add <file1>
<file2> … -- <pattern>` scoped to intended files, then `git commit -- <files>`
(never `git commit -A` or unscoped). This removes global-state aliasing. **Repo
reference:** `.claude/rules/` carries the shared-checkout discipline
(`web-dev-rule`, `git-worktree-rule`, `git-worktree-rule` §"Shared-state
hygiene").

**Candidates for future hardening (out of scope, flagged for human decision):** (1)
A pre-commit hook that warns when a commit touches more than N files or files
outside a declared scope — catches careless staging. (2) Per-agent worktrees for
any multi-file task — eliminates global staging area aliasing entirely, but adds
per-worktree `node_modules` / env overhead.

**Changed as a result:** This incident entry documents the recurring class; the
standing instruction (scoped pathspecs) is already wired into agent briefs and
rule docs, no code change needed.

## 2026-07-10 — `entire` pre-push hook wedged, forcing repeated `git push --no-verify`

**Symptom:** Multiple agent sessions working this repo hit a hung `git push` and had
to fall back to `--no-verify` to get unblocked. Every successful push also printed:

> Checkpoints were pushed to a separate checkpoint remote, but .entire/settings.json
> does not contain checkpoint_remote in the latest commit. entire.io will not be able
> to discover these checkpoints until checkpoint_remote is committed and pushed in
> .entire/settings.json.

**Root cause (traced, not assumed):** the checkpoint remote itself
(`github:connerkward/entire-checkpoints`, a private repo) is correctly configured and
reachable — `git ls-remote` against it returns instantly. The actual hang is in
`git`'s HTTPS auth path: this repo has **no `credential.helper` configured** at the
user/system level except macOS's Xcode-provided `osxkeychain` default. Tracing a real
`git fetch` against the checkpoint remote (`GIT_CURL_VERBOSE=1`) showed a reproducible
~15–20s stall between the server's initial `401` and the retried authenticated
request — the `osxkeychain` helper resolving credentials. In an interactive shell
with an unlocked keychain this eventually resolves; in a **headless/background agent
shell with no one to satisfy a Keychain prompt, it can hang indefinitely.** The old
`entire hooks git pre-push` invocation had no timeout around this step, so a stuck
credential lookup wedged the entire `git push` — that's what several agents hit today.

The "checkpoint_remote not in the latest commit" warning is a **separate, expected,
non-bug**: this machine deliberately keeps `.entire/settings.json` untracked
(`.git/info/exclude`) across all repos, including this one — see the `entire` skill's
"Why `.entire/` is git-excluded, not committed." Committing it here would put the
private checkpoint-repo name into `skeuo-ui`'s (public) history for a feature (the
entire.io web dashboard) this account doesn't use. Left as-is on purpose; the warning
is cosmetic.

**Guardrail added:** `.git/hooks/pre-push` (machine-local, not git-tracked) now wraps
`entire hooks git pre-push "$1"` in a bounded `timeout 25` so a stuck checkpoint-sync
step can no longer block the user's actual push. Falls back to running unwrapped if
neither `timeout` nor `gtimeout` is on `PATH`. `.git/hooks/` isn't version-controlled,
so this fix is per-checkout; it does not (yet) propagate to fresh clones/worktrees or
other repos on the fleet.

**Changed as a result:** `/Users/conner/dev/skeuo-ui/.git/hooks/pre-push` (this
commit's companion doc; the hook file itself is untracked by git by design).

**Siblings / follow-up (not done in this pass, flagged for a human decision):** the
same unbounded hang can occur in every other Model-2 repo on this machine, since
`entire enable` installs the same un-timed hook everywhere. The generalizable fix
would be to bake the `timeout`-wrapped hook template into
`~/dev/central/scripts/entire-autoenable` so it's applied to every repo on next
(idempotent) run — out of scope for this task, which was scoped to `skeuo-ui` only.
