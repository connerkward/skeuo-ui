# Operational security — running code, destructive commands, CI/CD, least privilege

Security of what you *do*, not just what you write. Especially relevant for an agent that runs
shell commands and executes code.

## Running untrusted / third-party code

- Treat cloned repos, downloaded scripts, and generated code as **untrusted until reviewed**.
  Read before you run — especially `Makefile`, `package.json` scripts, `setup.py`, git hooks,
  `.envrc`, devcontainer `postCreate`.
- Run untrusted code in a **sandbox**: a container, a throwaway VM, or macOS Seatbelt
  (`sandbox-exec`; ToB `seatbelt-sandboxer` generates minimal profiles). Limit network and
  filesystem to what's needed.
- Never run untrusted code with elevated privileges or with real secrets in the environment.

## Destructive / irreversible commands

Per the reversibility principle and the media-rm and machine-config rules:

- **Confirm before irreversible, outward-facing, or system-level actions.** `rm -rf`, force
  pushes, history rewrites, dropping DBs/tables, `kubectl delete`, terraform `destroy`,
  disabling firewalls, prod deploys, sending/posting externally.
- **Scope kills and deletes** — never `pkill -f <substring>` (hits sibling sessions; see
  web-dev-rule) or `rm` on a glob you didn't enumerate. Target a pid/port/path you own.
- **Media → `trash`, not `rm`** (media-rm-rule). **System config changes → document them**
  (machine-config-rule), with a reversal recipe.
- Prefer dry-run flags first (`--dry-run`, `terraform plan`, `git push --dry-run`).

## Least privilege (tokens, keys, perms)

- Scope every credential to the minimum: read-only when you only read; a single repo/bucket,
  not org-wide; short expiry; separate tokens per purpose so one leak is contained.
- DB users: per-service, only the needed grants — not a shared superuser.
- File/dir perms: not `0777`; secrets files `0600`. Containers: non-root user, drop
  capabilities, read-only root FS where possible.
- Rotate on exposure; have a revocation path (ties to [web.md](web.md#auth--jwt) lifecycle).

## CI/CD & GitHub Actions

CI runs with access to secrets and the ability to publish — a prime target.

- **Pin actions to a full commit SHA**, not a moving tag (`@v4` can be repointed).
  `uses: actions/checkout@<40-char-sha>`.
- **Least-privilege `GITHUB_TOKEN`:** set top-level `permissions:` to `read-all` (or less) and
  grant write per-job only where needed.
- **`pull_request_target` / `workflow_run` + checkout of PR head = RCE on your secrets.** Don't
  build/run untrusted PR code in a context that has secrets. Treat fork PRs as untrusted.
- **Never interpolate untrusted context into a `run:` block** —
  `run: echo "${{ github.event.issue.title }}"` is shell injection. Pass via `env:` and quote,
  or use an action input.
- Don't echo secrets; use masked secrets; avoid `pull_request` triggers exposing secrets to
  forks. For a full pass, use ToB `agentic-actions-auditor`.

## Checklist

- [ ] Untrusted code read before running; sandboxed; no secrets/privilege in its env.
- [ ] Irreversible/system/outward actions confirmed; dry-run first; kills/deletes scoped.
- [ ] Credentials least-privileged, short-lived, per-purpose; revocation path exists.
- [ ] CI actions SHA-pinned; `GITHUB_TOKEN` least-privilege; no untrusted context in `run:`;
      fork PRs treated as untrusted.
