---
name: "central-authoring-rule"
id: "central-authoring-01"
description: "Add/edit a rule or skill means CENTRAL: author in central/rules or central/skills (single source of truth, symlinked/exported everywhere), never a per-tool .claude/.cursor copy."
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

# "Add a rule / add a skill" means CENTRAL

When the user says "add a rule", "add a skill", "make a rule/skill", "edit the X rule/skill", "update a rule", or any similar phrasing, the target is **`central`** — `~/dev/central/rules/*.md` for rules, `~/dev/central/skills/<name>/` for skills. Central is the single source of truth; it is symlinked into `~/.claude/` (and exported to `.agent/.cursor/.qwen/.opencode`), so a central edit is what propagates everywhere.

**Default here, don't ask.** Unless the user explicitly says otherwise ("just for this project", "a project-local rule", "a Claude-specific hook"), assume central.

- **Do NOT** create or edit a Claude-specific / machine-local copy: not `~/.claude/rules/`, not `~/.claude/skills/`, not a project's generated `.claude/`, `.cursor/`, `.qwen/`, `.opencode/`. Those are auto-generated from central and edits there get clobbered on the next export.
- **After editing** `central/rules/` or `central/skills/`, run the export (`python3 ~/dev/central/skills/universal-rule-skill-export/export_config.py`) and commit the source edit + regenerated exports together, then push. See [[universal-rule-skill-export]].
- For the mechanics of *authoring* a skill (progressive disclosure, eval loop, self-contained-in-central + outbound publishing via [[publish-skill]]), use [[skill-authoring-rule]] and the `skill-creator` skill. This rule only fixes the **location/default**: central, not a per-tool copy.

**Exception:** harness behaviors that genuinely can't live in central — e.g. a `UserPromptSubmit`/`PostToolUse` **hook**, which must be registered in machine-local `~/.claude/settings.json` (`~/.claude/hooks/` and `settings.json` are not symlinked). Even then, put the hook's *logic* in a central script and keep only the one-line registration machine-local. See `update-config` for hook mechanics.
