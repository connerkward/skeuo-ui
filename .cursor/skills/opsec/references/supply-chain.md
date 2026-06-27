# Supply chain & dependencies

Most code in a project is third-party. A malicious or compromised dependency runs with your
app's full privileges — and often at *install* time, before any of your code runs.

## Before adding a dependency

- **Need it at all?** A 3-line utility isn't worth a dependency + its transitive tree. "Best
  part is no part." Prefer the standard library.
- **Vet the package**, not just the name: real download counts, maintained (recent commits,
  responsive issues), repo matches the registry, sane number of maintainers, reasonable
  transitive footprint. Beware brand-new packages and sudden maintainer changes.
- **Typosquatting / confusion** — confirm the exact name and ecosystem. `python3-dateutil`
  vs `dateutil`, `crossenv` vs `cross-env`, scoped vs unscoped. **Dependency confusion:** an
  internal package name published to a public registry can shadow the private one — pin the
  registry/scope for internal packages.
- **Install-time execution is the main threat.** npm `preinstall`/`postinstall` scripts and
  PyPI `setup.py` run arbitrary code on `npm install` / `pip install`. For untrusted installs
  consider `npm install --ignore-scripts`. Review lifecycle scripts of anything new.

## Pinning & integrity

- **Commit the lockfile** (`package-lock.json`, `poetry.lock`, `uv.lock`, `Cargo.lock`,
  `go.sum`) and install from it (`npm ci`, `pip install -r` with hashes, `uv sync --frozen`).
- Pin exact versions for apps; lockfile carries integrity hashes — don't bypass them.
- In CI, use `--frozen`/`ci` modes so a drifted lockfile fails the build instead of silently
  resolving new versions.

## Ongoing

- **Audit installed deps:** `npm audit`, `pip-audit`, `cargo audit`, `osv-scanner`,
  `govulncheck`. Wire one into CI.
- **Automated update PRs** (Dependabot/Renovate) — but review them; a malicious version can
  arrive via an "update."
- **Don't `curl … | sh`** untrusted install scripts. Download, read, then run.
- For a deep dependency-risk audit, use ToB `supply-chain-risk-auditor`.

## Checklist

- [ ] New dep is actually needed (no stdlib equivalent).
- [ ] Name verified (no typosquat / dependency-confusion); package vetted (maintenance, source).
- [ ] Install/lifecycle scripts reviewed; `--ignore-scripts` for untrusted installs.
- [ ] Lockfile committed; CI installs frozen/from-lock with integrity hashes.
- [ ] Vuln scanner in CI; update PRs reviewed, not auto-merged blind.
- [ ] No piping remote scripts straight into a shell.
