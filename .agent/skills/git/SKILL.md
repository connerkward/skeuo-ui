---
name: git
description: Use when using git: commit and push policy, branching, and receiving/acting on code-review feedback (incl. /code-review and automated reviewers).
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

- Never credit Claude/LLM as author, co-author, or contributor — see `central/rules/git-attribution-rule.md` (no `Co-Authored-By`, no "Generated with Claude Code").
- Commit and push by default after changes — don't ask for confirmation. See `central/rules/software-engineering-rule.md`.
- Be liberal with commits — commit more rather than less.
- **Large binaries: stop before `git add`.** Before committing any file >~10 MB (especially binary — media, models, archives, datasets), decide deliberately: gitignore it, route it to external storage (`ideas-syncthing`, R2, etc.), or `git lfs track` it — never `git add` a large binary blindly. Committing it normally bloats history permanently and is painful to excise (filter-repo/BFG). LFS isn't automatic and isn't free (GitHub LFS quota + per-repo `.gitattributes`), so reserve it for binaries that genuinely must be versioned in-repo; default to keeping them out of git entirely.
- Branch first if on the default branch before pushing non-trivial work.
- **Receiving code-review feedback (incl. `/code-review`, automated reviewers).** Treat findings as suggestions to evaluate, not orders — automated reviewers confidently propose wrong changes. Before implementing one: restate it, check it against the actual codebase, grep for real usage (don't add handling for cases that can't occur), and push back with technical reasoning when it's wrong. Clarify *every* unclear item before implementing *any* — partial understanding yields wrong fixes. Implement one item at a time, re-testing each. Tone: no performative agreement — see `central/rules/personal-chat-rule.md`.
