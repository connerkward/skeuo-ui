# Incidents

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
