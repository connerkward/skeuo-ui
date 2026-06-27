---
name: linear
description: Mechanics and policy for Linear issue operations via MCP (find/claim/report/close). Use when doing Linear work.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Linear (issue operations)

**Workspace:** Personal teams.

**Policy:** Lifecycle Backlog → Todo → In Progress → Done. Do not mark Done without testing and an Agent Test Report comment. Add agent-tested; add human-requested when confidence is low or human review needed.

**Prereqs:** Linear MCP available. Prefer `claude.ai Linear` (cloud connector) tools; fall back to local `linear` MCP tools on auth errors. Use list_issues, save_issue, save_comment (or client’s tool names).

**Find:** `list_issues(state: "Todo", label: "machine:<this-machine>")`; fallback `label: "agent"`.
**Claim:** `save_issue(id, state: "In Progress")`; `save_comment(issueId, body: "Picked up by agent on <machine> at <ISO-8601>")`.
**Close:** Test first. Comment with Agent Test Report (what, how, confidence, human review yes/no). Then `save_issue(state: "Done", labels: ["agent-tested"])`; add human-requested if low confidence. When adding human-requested, end the comment with: `> ⚠️ human-requested — please add \`human-tested\` label after you verify.`
**Human review:** When a human verifies a `human-requested` issue, `save_issue(labels: ["human-tested"])`. This closes the loop — human-requested without human-tested means unverified.
**Blocked:** `save_comment` reason; `save_issue(state: "Backlog")`.
**Completed projects:** Do not modify projects in Done/Completed state unless the user explicitly asks to update that specific project.

**Labels:** machine:desky|lappy|lappyheavy; tool:claude-code|cursor|antigravity|copilot|cline; agent-tested, agent-executed, human-requested, agent-requested, human-tested.

**Description format:** Standard markdown with real newlines (never escaped `\n`). `##` for sections, `-` for bullets, `[]` for checklists. Keep concise. Agent test reports go in a comment via `save_comment`, not in the description — use format: `## Agent Test Report\n- What:\n- How:\n- Confidence:\n- Human review needed:`
