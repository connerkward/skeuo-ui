---
name: universal-rule-skill-export
description: Source-of-truth sync for central rules/skills. Use when (a) editing files in central/rules or central/skills (re-run export to update .agent/.claude/.cursor/.qwen/.opencode copies), or (b) setting up a NEW repo that should pick up central's rules/skills (attach central via copy-central-rules-skills).
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Universal Rule/Skill Export

Central is the single source of truth for rules and skills. (MCP servers have a parallel source of truth in `~/.claude.json` — see `central/skills/mcp/SKILL.md`.)

## Fresh machine? Start here

```bash
git clone https://github.com/connerkward/central ~/dev/central
~/dev/central/scripts/setup-machine
source ~/.zshrc
```

`setup-machine` is idempotent: it wires the `~/.claude/`, `~/.qwen/`, `~/.config/opencode/` symlinks at central, installs the `copy-central-rules-skills` and `sync-mcp-servers` aliases, and runs the MCP sync if `~/.claude.json` exists. From that point on, every tool reads from central directly — see "Global wiring on this machine" below.

---

This skill owns two distinct workflows:

| Workflow | When | Tool |
|----------|------|------|
| **A — Update central's own exports** | After editing `central/rules/` or `central/skills/` | `export_config.py` |
| **B — Attach central to a different repo** | New repo, fresh clone, or any repo that should follow central | `copy-central-rules-skills` |

If you're not sure which one applies: editing inside central → A. Anywhere else → B.

There's also a **third pattern — global symlinks** — for the user's own machine: see "Global wiring on this machine" below. That's how rules/skills get into Claude/Qwen/OpenCode globally without re-running anything when central edits land.

## Source of truth

ONLY edit these. Everything else regenerates from them:
- Rules: `central/rules/*.md`
- Skills: `central/skills/<name>/`

Auto-generated, never edit directly:
- `central/.agent/`, `central/.claude/`, `central/.cursor/`, `central/.qwen/`, `central/.opencode/` (re-run workflow A)
- Any other repo's `.agent/`, `.claude/`, `.cursor/`, `.qwen/`, `.opencode/` (re-run workflow B from inside that repo)

Not exported (intentionally): top-level non-directory files in `skills/` (e.g. `PROVENANCE.md`) are NOT copied to the destinations — `export_config.py`'s `export_skills()` only walks skill *subdirectories* (`os.path.isdir`). So `PROVENANCE.md` correctly never appears in `.claude/skills/`, `.cursor/skills/`, etc.

---

## Workflow A — Update central's exports

Run after any edit to `central/rules/` or `central/skills/`:

```bash
python3 ~/dev/central/skills/universal-rule-skill-export/export_config.py
```

Regenerates all five destinations from the sources. Commit the source edit AND the regenerated exports together.

---

## Workflow B — Attach central to a new repo

This is the **canonical new-repo setup step.** Run it once per new repo (and re-run anytime you want that repo to pick up central updates).

```bash
# from inside the new repo
copy-central-rules-skills
```

If the alias is missing (`command not found`), the machine hasn't been bootstrapped — run `~/dev/central/scripts/setup-machine` first, then `source ~/.zshrc`. Or invoke the script directly:

```bash
python3 ~/dev/central/scripts/copy-central-rules-skills --target .
```

What it does:
- Mirrors central's rules and skills into the target repo as `.agent/`, `.claude/`, `.cursor/`, `.qwen/`, AND `.opencode/` versions
- Stamps each file's frontmatter with central's current git hash + timestamp so the repo records exactly which version it synced
- Full mirror (clears destinations first), so deleted central rules disappear from the target
- Generates index/bundle files for tools that don't auto-load a rules directory

### When to run B

- Immediately after `git init` or `git clone` of a new repo
- Anytime central has shipped updates and you want this repo to catch up
- After switching branches if the target previously had stale exports

### What you get

After running B in `<repo>/`:
```
# Native auto-loaders
<repo>/.cursor/rules/<rule>.mdc                    # Cursor: native auto-load
<repo>/.cursor/skills/<skill>/SKILL.md
<repo>/.claude/rules/<rule>-rule.md                # Claude Code: per-repo, layered on ~/.claude/
<repo>/.claude/skills/<skill>/SKILL.md
<repo>/.agent/rules/<rule>/RULE.md                 # Antigravity / generic
<repo>/.agent/skills/<skill>/SKILL.md

# Index/bundle required for these (no native rules-dir auto-load)
<repo>/.qwen/rules/<rule>-rule.md
<repo>/.qwen/skills/<skill>/SKILL.md
<repo>/.qwen/QWEN.md                               # generated: @-imports every rule
<repo>/.opencode/rules/<rule>-rule.md
<repo>/.opencode/skills/<skill>/SKILL.md           # OpenCode reads .opencode/skills/ natively
<repo>/.opencode/AGENTS.md                         # generated: bundled rules
```

### How each tool actually picks them up

| Tool | Rules | Skills |
|------|-------|--------|
| Cursor | Auto-loads `.cursor/rules/*.mdc` | Reads `.cursor/skills/` |
| Claude Code | Auto-loads `.claude/rules/*-rule.md` (per-repo) + global `~/.claude/rules` | Auto-loads `.claude/skills/` |
| Antigravity | Reads `.agent/rules/*/RULE.md` (frontmatter `trigger: always_on`) | Reads `.agent/skills/` |
| Qwen Code | Reads `.qwen/QWEN.md` (project root → ancestors up to `.git`); that file `@`-imports every rule | Reads `.qwen/skills/` natively |
| OpenCode | **Manual opt-in.** Add `instructions: [".opencode/AGENTS.md"]` to `opencode.json`, or copy/symlink `.opencode/AGENTS.md` to project root as `AGENTS.md` | Auto-loads `.opencode/skills/` (native) |

### Should you commit the synced files?

- **Solo repo, just for you:** add `.agent/`, `.claude/rules/`, `.claude/skills/`, `.cursor/`, `.qwen/`, `.opencode/` to `.gitignore` — you can re-attach anytime, no need to track copies.
- **Shared repo with collaborators:** commit them so collaborators get central's rules without needing their own central. They'll be stamped with the central git hash so it's clear which version shipped.

---

## Global wiring on this machine

Workflows A and B handle in-central previews and per-repo copies. For the user's own daily-driver tools (Claude Code, Qwen Code, OpenCode), rules and skills are wired **globally via symlinks** straight to central's source — no export run needed, edits show up on the next launch.

`scripts/setup-machine` is idempotent and establishes:

```
~/.claude/rules            -> ~/dev/central/rules               (source)
~/.claude/skills           -> ~/dev/central/skills              (source)
~/.qwen/QWEN.md            -> ~/dev/central/.qwen/QWEN.md       (generated index)
~/.qwen/rules              -> ~/dev/central/rules               (source; @-import targets resolve here)
~/.qwen/skills             -> ~/dev/central/skills              (source)
~/.config/opencode/skills  -> ~/dev/central/skills              (source)
~/.cursor/skills           -> ~/dev/central/skills              (source; Cursor auto-loads this)
```

**Cursor rules are per-repo only.** Cursor has no global rules directory (its global "User Rules" are plain text in the settings DB, not a filesystem path it auto-loads), and it does NOT read `.cursor/rules` from ancestor directories — only the project root + nested subdirs. So central rules reach a Cursor project only via workflow B (`copy-central-rules-skills`) in that repo. Skills, by contrast, ARE global (the `~/.cursor/skills` symlink above + Cursor's `~/.claude/skills` compat path).

For OpenCode rules, `~/.config/opencode/opencode.json` `instructions:` is set to a glob:
```json
{"instructions": ["/Users/conner/dev/central/rules/*-rule.md"]}
```
so new rules auto-appear without editing the config.

MCP servers stay synced via `sync-mcp-servers` (Claude Code as source of truth → Cursor / Qwen / OpenCode). `setup-machine` runs this too. Full MCP details, including `npx` vs global-install trade-offs and the cross-tool config-shape table, live in `central/skills/mcp/SKILL.md`.

### Workflow A still matters (but less than it did)

After **content edits** to an existing rule or skill: nothing to do. The symlinks point at central's source, so all three tools see the new content on next launch.

After **adding/removing/renaming** a rule file: re-run workflow A. The Qwen `QWEN.md` index hard-codes the list of `@rules/<filename>` imports, so it needs regen when the set of rule filenames changes. Skills and rule content are unaffected — those resolve through symlinks at read time.

---

## Why two workflows, one skill

Both are "central → destination" syncs. Workflow A's destination is central itself (the in-repo previews); workflow B's destination is any other repo. Same source, same intent, so they live in one skill.
