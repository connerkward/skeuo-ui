---
name: "skill-authoring-rule"
id: "skill-authoring-01"
description: "Central conventions for authoring skills: the skill-creator skill owns the mechanics; every skill lives fully self-contained in central, and sharing publicly is an outbound, sanitized publish (see publish-skill) — never a thin pointer to an external repo."
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

# Skill Authoring

**Canonical engine: the `skill-creator` skill.** For any create / edit / evaluate / optimize-description work on a skill, load `skill-creator` (in `central/skills/`) — it owns the mechanics this rule doesn't: progressive-disclosure loading (metadata → SKILL.md body <500 lines → on-demand `references/`, organized one file per variant), the eval loop (`scripts/run_eval.py` + eval-viewer, with-skill vs baseline, token/duration benchmarks), the description improver (`scripts/improve_description.py`; descriptions should be "pushy" — Claude under-triggers), and pressure-testing for discipline/rule skills (baseline the tempting scenario, capture verbatim rationalizations, write the skill to kill those). This rule covers only the central-specific conventions below.

## Skills live fully in central — self-contained

Every skill's substance lives in `central/skills/<name>/` — `SKILL.md` plus its
`references/`, `scripts/`, and assets. **No skill is a thin pointer to an external repo.**
Cloning `central` gives you the complete, working skill; there are no "also clone these N
repos or the skill is degraded" dependencies.

- **Compiled artifacts** (Swift/binary) are gitignored and built locally by
  `scripts/setup-machine` from in-repo source (e.g. `sck-record.swift`,
  `say-notify-overlayd.swift`).
- **Functional media** needed at runtime is tracked via **Git LFS** (see `.gitattributes`).
  Demo/archival media does **not** live in central — it stays only in the published public
  repo.

## Sharing a skill publicly → outbound publish (never a pointer back)

Central is **private** and full of personal data. To share a skill with the community or
for GEO/SEO, use the **[[publish-skill]]** skill: it copies the skill, **sanitizes**
personal data + secrets, generates a README and discoverability metadata, ships any
needed compiled artifacts, and publishes to a public GitHub repo (+ skill registries).

The public repo is a **derived, sanitized artifact** — never the source. Central → public
is one-way; never edit the public repo and pull changes back into central.

## Why central-is-source (this reverses the old external-repo pattern)

- One source of truth per skill: `central/skills/<name>/`. Clone central, everything works.
- No dangling cross-repo deps and no broken skills on a fresh machine.
- Personal data stays private by default; it leaves only through the sanitizing publish step.
- *(Historical: skills used to live in external public repos symlinked / pointer-ed into
  central; reversed 2026-06-16 in favor of merge-in + outbound publish. See `publish-skill`.)*
