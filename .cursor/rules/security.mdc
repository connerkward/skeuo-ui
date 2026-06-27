---
name: "security-rule"
id: "sec-rule-01"
description: "Global security law."
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
# Invariants (Always True)
- Do not leak keys, passwords env files, especially in commit or logs
- Do not use raw text passwords in terminal or places where it could be captured by logs.
- NEVER store keys, passwords, or secrets in plaintext anywhere except `.env` files, and only if those `.env` files are not git-tracked (must be in `.gitignore`).

# Scope
These are the always-on secrets-hygiene invariants. They are the floor, not the whole of security. For broader security guidance across ALL actions — secure coding (any language: injection, deserialization, crypto, race/TOCTOU, memory), dependency/supply-chain risk, operational safety (running untrusted code, destructive commands, CI/CD, least privilege), insecure defaults, privilege escalation, data/PII leakage, and the full web vuln catalog — the `opsec` skill triggers on the relevant action and defers to this rule on anything touching secrets storage. This rule wins on any conflict.
