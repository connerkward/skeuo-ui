---
name: opsec
description: Security for ALL dev and agent actions, not just web. Use WHILE writing/modifying code (any language), running shell commands, executing or reviewing untrusted code, installing/updating dependencies, configuring infra or CI/CD, handling tokens/permissions — and on-demand when asked to scan / audit / security-review. Covers injection (shell/SQL/code), deserialization, crypto misuse, race/TOCTOU, supply-chain & dependency risk, operational safety (destructive commands, sandboxing, least privilege, CI/GitHub Actions), insecure defaults & config cliffs, privilege escalation, data/PII leakage, plus the full web vuln catalog (IDOR, XSS, CSRF, SSRF, XXE, path traversal, upload, JWT). Bug-hunter's perspective. Secrets storage itself is governed by security-rule.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# opsec — security for every action

Approach all work — code, commands, config, dependencies — from a **bug hunter's /
attacker's perspective**: assume hostile input, untrusted code, and that every control will be
probed. Make things **as secure as possible without breaking functionality**. Dual-mode:
guides you *while you act*, and runs an audit workflow *on request*.

> **Naming note:** despite the `opsec` name (usually operational security), this is the
> all-purpose security skill — application + operational + supply-chain. It triggers on any
> security-relevant action, not only process/secrecy discipline.

## When to use

- **Acting** on anything security-relevant: writing/editing code in any language; building
  shell commands or running tools; executing or reviewing third-party/untrusted code; adding
  or upgrading dependencies; configuring infra, containers, or CI/CD; handling tokens, keys,
  permissions, or file paths. Apply the matching section's defaults by default.
- **Auditing** on request — "scan / audit / security-review / find vulns in" code, a PR, a
  config, a pipeline. Run the [Audit workflow](#audit-workflow).

## When NOT to use

- **Secrets storage/transport** (where keys/passwords may live, never logging/committing
  plaintext) → governed by always-on `central/rules/security-rule.md`. This skill defers to
  it; see [Secrets](#secrets-defers-to-security-rule).
- **Deep specialized audits** — smart contracts, deep memory-safety, crypto constant-time,
  fuzzing campaigns, malware/YARA. Out of scope; use the Trail of Bits marketplace
  (`/plugin marketplace add trailofbits/skills`) when a project genuinely needs them.
- **Pure cosmetic/docs/refactor** with no security-relevant surface.

## Core principles

- **Defense in depth** — never one control.
- **Fail closed** — on error, deny / abort; don't fall open to a permissive default.
- **Least privilege** — minimum scope for tokens, DB users, file perms, CI permissions.
- **Validate server-/trust-side** — never trust client, caller, or fetched data.
- **Encode/quote at the sink** — context-correct for SQL, shell, HTML/JS/URL, paths.
- **Reversibility** — prefer reversible actions; for destructive/irreversible ones, confirm.

## How to apply (act-time)

When an action hits a surface below, open the matching reference and apply its defaults —
don't wait to be asked. Each is self-contained: defenses, concrete bypass payloads, checklist.

| Surface you're touching | Reference |
|---|---|
| Any web request handling — resource access/roles, rendering user data, redirects, SQL, XML, paths, URL-fetching, uploads, auth/JWT, GraphQL, headers | [web.md](references/web.md) |
| Non-web code — shell/code injection, deserialization, crypto, race/TOCTOU, memory | [code-security.md](references/code-security.md) |
| Adding/upgrading dependencies — vetting, lockfiles, install scripts, typosquatting | [supply-chain.md](references/supply-chain.md) |
| Running commands/code, destructive ops, sandboxing, least-privilege tokens, CI/CD & GitHub Actions | [operational.md](references/operational.md) |
| Config/env handling, framework defaults, fail-open patterns | [insecure-defaults.md](references/insecure-defaults.md) |
| Any privilege boundary; anything written to logs/errors/responses/telemetry; PII | [escalation-and-leaks.md](references/escalation-and-leaks.md) |

## Audit workflow

When asked to review, do **not** just grep and dump matches. For every candidate finding:

1. **Discover** — language, framework, runtime, conventions. Map the security surface: input
   sources, sinks (shell/SQL/code-exec/file/network), trust boundaries, auth/authz points,
   dependencies, config, CI/CD.
2. **Search** — per surface, scan for the patterns in the relevant reference. Focus on
   production-reachable code, not test fixtures / examples / docs.
3. **Verify (trace the path)** — confirm input is actually attacker-controllable and reaches
   the sink. Trace the bad value *backward* to its origin. A match is not a finding.
4. **Confirm impact** — what does exploitation get? Reachable in production config?
5. **Report with evidence** — file:line, the pattern, how it's reached, an exploitation
   sketch, the fix, and a [severity](#severity).

Default to verifying before reporting. False positives waste the user's time.

A real risk isn't dismissed because it's "documented", "behind auth", "validated
client-side", "a dev-only default", or "we'll fix it later" — none of those are controls. When
weighing one, assume an attacker who controls input/config, a developer who copy-pastes the
first example, and one who swaps a key/arg without noticing the error.

## Severity

| Severity | Criteria |
|---|---|
| Critical | Default/obvious usage is exploitable; unauthenticated impact (RCE, auth bypass, full data read, supply-chain compromise). |
| High | Easy misconfig or common pattern breaks security (IDOR, stored XSS, SSRF-to-metadata, command injection). |
| Medium | Requires a precondition or unusual config. |
| Low | Requires deliberate misuse or has limited impact. |

## Secrets (defers to security-rule)

Where secrets may be stored, and never logging/committing them in plaintext, is owned by the
always-on `central/rules/security-rule.md`. **Do not restate or contradict it.** This skill
adds only the *usage* angles the rule doesn't: secrets must never reach client-side code
(JS bundles/source maps, `localStorage`, SSR hydration, `NEXT_PUBLIC_*`/`VITE_*`), token
**scope/least-privilege** (see operational.md), and not leaking them via logs/errors (see
escalation-and-leaks.md).

## Sources

Synthesized from two external skill projects, reorganized under Trail of Bits' skill-authoring
standard (when-to-use / when-not / rationalizations-to-reject / progressive disclosure):

- **VibeSec-Skill** by BehiSec — web vuln catalog + bypass payloads. Apache-2.0.
  https://github.com/BehiSecc/VibeSec-Skill
- **Trail of Bits Skills** — non-web coverage drawn from `insecure-defaults`, `sharp-edges`,
  `supply-chain-risk-auditor`, `agentic-actions-auditor`, `seatbelt-sandboxer`; plus the
  audit discipline and adversary model. CC-BY-SA-4.0. https://github.com/trailofbits/skills
