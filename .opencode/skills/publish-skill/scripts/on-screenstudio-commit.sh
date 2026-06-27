#!/usr/bin/env bash
# on-screenstudio-commit.sh — central script invoked by a machine-local PostToolUse(Bash) hook.
#
# Purpose: when the most recent commit in ~/dev/central touched skills/screenstudio-alt/,
# emit a JSON `additionalContext` directive telling the active Claude Code agent to run the
# publish-skill sanitize + security pass and publish to the public screenstudio-alt repo.
# Otherwise print NOTHING and exit 0 (silent for every non-screenstudio commit).
#
# It does NOT publish. The sanitization/security/sanitize pass needs the AGENT's judgment —
# auto-publishing via shell would risk leaking personal data/secrets. This only TRIGGERS the
# pass by injecting the directive; the agent performs it (human-gated, per publish-skill).
#
# Invoked by the hook on EVERY Bash call, but it only does real work when the Bash command was
# a git commit/push in central AND HEAD touches screenstudio-alt — so it is cheap and silent
# the rest of the time. The hook passes the Bash command on stdin (the PostToolUse JSON payload).

set -euo pipefail

CENTRAL="$HOME/dev/central"
SKILL_PATH="skills/screenstudio-alt/"
PUBLIC_REPO="connerkward/screenstudio-alternative-skill"   # verified live on GitHub 2026-06-18

# Read the hook payload from stdin (PostToolUse JSON). Cheap pre-filter: only proceed when the
# Bash command looks like a git commit (or merge/rebase that can move HEAD) in central. If we
# can't parse it, fall through to the diff-tree check anyway (correctness over the optimization).
payload="$(cat 2>/dev/null || true)"
if [ -n "$payload" ] && command -v jq >/dev/null 2>&1; then
  cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"
  # Only a git commit/merge/rebase/pull can change what HEAD points at. Anything else → skip.
  if [ -n "$cmd" ] && ! printf '%s' "$cmd" | grep -Eqi 'git\b.*(commit|merge|rebase|pull|cherry-pick|revert|reset)'; then
    exit 0
  fi
fi

# Must be a real git repo.
git -C "$CENTRAL" rev-parse --git-dir >/dev/null 2>&1 || exit 0

# Did the most recent commit (HEAD) touch the screenstudio-alt skill?
if ! git -C "$CENTRAL" diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null \
     | grep -q "^${SKILL_PATH}"; then
  exit 0   # non-screenstudio commit → silent
fi

sha="$(git -C "$CENTRAL" rev-parse --short HEAD 2>/dev/null || echo HEAD)"
subject="$(git -C "$CENTRAL" log -1 --format=%s HEAD 2>/dev/null || true)"

directive="AUTOMATION TRIGGER — screenstudio-alt was just changed in central (commit ${sha}: \"${subject}\").

ACTION REQUIRED before this work is considered shipped: run the publish-skill SANITIZE + SECURITY pass on the screenstudio-alt skill, then publish to the public repo ${PUBLIC_REPO}.

Do this with YOUR judgment — do NOT auto-publish blindly; the sanitization pass is what prevents leaking personal data/secrets, and it is human-gated:
1. Load the publish-skill skill (read ~/dev/central/skills/publish-skill/SKILL.md).
2. Run: python3 ~/dev/central/skills/publish-skill/scripts/sanitize.py ~/dev/central/skills/screenstudio-alt --out /tmp/publish-screenstudio-alt
   This scrubs personal data/paths/secrets and runs the residual-leak scan (it exits non-zero and BLOCKS if anything leaks).
3. Show the human the private->scrubbed diff + leak report and get approval (HARD GATE — nothing leaves the machine until the scan is clean AND the human approves).
4. After approval, build/attach working artifacts, refresh README + GEO/SEO metadata, and push the approved staging dir to ${PUBLIC_REPO} (the central copy is never pushed directly).
5. A real publish/major update triggers a crosspost announcement (human-gated preview).

This was auto-triggered by the on-screenstudio-commit PostToolUse hook. If you (or the human) have already completed this publish for commit ${sha}, you may skip it."

# Emit as PostToolUse additionalContext so it reaches the model on the next turn.
# Use jq to JSON-encode safely (the directive contains quotes/newlines).
if command -v jq >/dev/null 2>&1; then
  jq -n --arg ctx "$directive" \
    '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}'
else
  # Fallback: hand-escape (jq should always be present on this machine, but degrade gracefully).
  esc="$(printf '%s' "$directive" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')"
  printf '{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": %s}}\n' "$esc"
fi

exit 0
