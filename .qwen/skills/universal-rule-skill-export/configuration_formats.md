# Agent Configuration Formats

This document outlines the configuration formats for **Antigravity** (`.agent`), **Claude** (`.claude`), **Cursor** (`.cursor`), **Qwen Code** (`.qwen`), and **OpenCode** (`.opencode`).

Each system handles **Rules** and **Skills** differently. Some auto-load from a rules directory; others require a bundled index file or manual opt-in via the tool's config file.

---

## 1. Antigravity (`.agent`)

Antigravity appears to use a directory-centric approach for rules and a shared format for skills.

### Directory Structure
```
.agent/
├── rules/
│   └── [rule-name]/       # Rules are directories
│       └── RULE.md        # The actual rule content
├── skills/
│   └── [skill-name]/
│       └── SKILL.md       # Skill definition
└── workflows/             # Workflow definitions
```

### Rule Format (`RULE.md`)
Rules are defined in `RULE.md` files within a subdirectory named after the rule category or name.

**Frontmatter:**
```yaml
---
trigger: always_on      # When the rule is active
description: "..."      # Brief description
globs: ["**/*"]         # File patterns to match
---
```

### Skill Format (`SKILL.md`)
Skills are defined in `SKILL.md` files within a subdirectory. This format appears to be the "source of truth" extended to other agents.

**Frontmatter:**
```yaml
---
name: [skill-name]
description: "..."
---
```

---

## 2. Claude (`.claude`)

Claude uses a flat-file structure for rules and supports a local settings file.

### Directory Structure
```
.claude/
├── rules/
│   └── [rule-name]-rule.md  # Rules are flat Markdown files
├── skills/
│   └── [skill-name]/        # Mirrored from .agent
│       └── SKILL.md
└── settings.local.json      # Local configuration (permissions, etc.)
```

### Rule Format (`*-rule.md`)
Rules are standalone Markdown files. The frontmatter includes detailed metadata, likely following the Model Context Protocol (MCP) or similar standard.

**Frontmatter:**
```yaml
---
name: "software-engineering-rule"
id: "se-rule-01"
description: "..."
globs: ["**/*"]
applyTo: ["**/*"]
alwaysApply: true
priority: "high"
human-reviewed-at: YYYY-MM-DD
human-reviewed-by: [username]
---
```

---

## 3. Cursor (`.cursor`)

Cursor follows a similar structure to Claude but utilizes the `.mdc` extension for rules.

### Directory Structure
```
.cursor/
├── rules/
│   └── [rule-name].mdc      # Rules use .mdc extension
├── skills/
│   └── [skill-name]/        # Mirrored from .agent
│       └── SKILL.md
```

### Rule Format (`*.mdc`)
`.mdc` (Markdown Configuration?) files appear to be functionally identical to the `.md` rules used by Claude in this environment, sharing the same detailed frontmatter.

**Frontmatter:**
```yaml
---
name: "software-engineering-rule"
id: "se-rule-01"
description: "..."
globs: ["**/*"]
applyTo: ["**/*"]
alwaysApply: true
priority: "high"
---
```

---

## 4. Qwen Code (`.qwen`)

Qwen Code uses `QWEN.md` as its primary context/memory file (analogous to `CLAUDE.md`). It searches hierarchically: global `~/.qwen/QWEN.md`, then project root and ancestors up to `.git`. There is **no convention for auto-loading a rules directory** — rule files become active only when explicitly imported from a `QWEN.md` via the `@path/to/file.md` syntax.

### Directory Structure
```
.qwen/
├── QWEN.md                    # Generated index; @-imports every rule file below
├── rules/
│   └── [rule-name]-rule.md    # Flat Markdown, same convention as .claude
└── skills/
    └── [skill-name]/          # Mirrored from source
        └── SKILL.md
```

### Generated `QWEN.md`
The export writes a `.qwen/QWEN.md` that contains one `@rules/<filename>` line per rule. This is what makes the rules effective for Qwen Code — without it, files in `.qwen/rules/` are inert.

```markdown
# Central Rules (auto-generated)

@rules/security-rule.md
@rules/software-engineering-rule.md
...
```

### Skill Format (`SKILL.md`)
Identical to Claude/Cursor: `.qwen/skills/<name>/SKILL.md` with standard `name`/`description` frontmatter.

---

## 5. OpenCode (`.opencode`)

OpenCode natively auto-loads `.opencode/skills/` and an `AGENTS.md` at project root. It does NOT auto-load a `.opencode/rules/` directory. The export writes individual rule files and a bundled `.opencode/AGENTS.md` that the user opts into via `opencode.json` or by promoting it to root.

### Directory Structure
```
.opencode/
├── AGENTS.md                  # Generated bundle; ready to import or promote to root
├── rules/
│   └── [rule-name]-rule.md    # Flat Markdown copies
└── skills/
    └── [skill-name]/          # Native auto-load
        └── SKILL.md
```

### How to activate rules
Either add to `opencode.json`:
```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [".opencode/AGENTS.md"]
}
```

Or copy/symlink `.opencode/AGENTS.md` to the project root as `AGENTS.md` (OpenCode auto-loads project-root `AGENTS.md`). The export deliberately does NOT write directly to root `AGENTS.md` to avoid clobbering user-managed content.

### Skill Format (`SKILL.md`)
Identical to Claude/Cursor. OpenCode walks `.opencode/skills/` natively and surfaces each as a slash-available skill.

---

## Summary Comparison

| Feature | Antigravity | Claude | Cursor | Qwen Code | OpenCode |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Rule Structure** | `rules/[name]/RULE.md` | `rules/[name]-rule.md` | `rules/[name].mdc` | `rules/[name]-rule.md` + `QWEN.md` index | `rules/[name]-rule.md` + `AGENTS.md` bundle |
| **Rule Extension** | `.md` | `.md` | `.mdc` | `.md` | `.md` |
| **Auto-loads rules dir?** | Yes | Yes | Yes | **No** (`@`-import via `QWEN.md`) | **No** (manual `instructions:` / root `AGENTS.md`) |
| **Skill Format** | `skills/[name]/SKILL.md` | Same | Same | Same | Same (native) |
| **Skill auto-discovery?** | Yes | Yes | Yes | Yes | Yes |
