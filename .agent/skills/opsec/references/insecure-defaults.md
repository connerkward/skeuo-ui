# Insecure defaults & config cliffs

Apps that run **insecurely when configuration is missing**. The distinction that matters:

- **Fail-open (CRITICAL):** `SECRET = env.get('KEY') or 'default'` → app runs with a weak,
  known value.
- **Fail-secure (SAFE):** `SECRET = env['KEY']` → app crashes if missing. Crashing is correct.

When you write config handling, **fail closed**: require the value, don't substitute a
permissive fallback. When you audit, trace whether the app runs with the default or refuses
to start.

## Patterns to flag

- **Fallback secrets/credentials:** `getenv(X) or "..."`, `process.env.X || "..."`,
  `ENV.fetch(X){ "..." }` for anything security-relevant (signing keys, DB creds, admin pw).
- **Fail-open switches:** `AUTH_REQUIRED = env.get("X", "false")`, `verify_ssl=False` default,
  `DEBUG=true`, permissive CORS `*`, `0.0.0.0` bind with no auth.
- **Dangerous defaults in your own APIs** (sharp-edges): a constructor param with a good
  default that still *accepts* an insecure value (`hashAlgo='sha256'` but accepts `'md5'`;
  `otpLifetime=120` but accepts `0`). Defaulting isn't validating — reject bad values.
- **Magic/edge values:** what does `timeout=0` mean — infinite or immediate? `max_attempts=0`?
  empty string bypassing a check? `-1` = "never expire"? Define and validate them.
- **Config cliffs:** one silent typo flips security. `verify_ssl: fasle` parsed as truthy;
  dangerous combos accepted silently (`auth_required: true` + `bypass_auth_for_health: true`
  + `health_path: "/"`). Validate config; reject unknown keys and dangerous combinations.
- **Weak crypto defaults:** MD5/SHA1/DES/RC4/ECB in a security context (skip checksums/non-security hashing).

## When NOT to flag

- Test fixtures (`test/`, `spec/`, `__tests__/`), `.example`/`.sample`/`.template` files,
  docs, and dev-only tooling explicitly scoped to local dev.
- **Fail-secure** crash-on-missing behavior — that's the correct pattern.

## Defense

- Require security-critical config (fail closed); validate values, not just defaults.
- Validate the whole config at startup: reject unknown keys, type-check, reject dangerous
  combinations; log the effective security-relevant settings.
- Secrets themselves: stored per `central/rules/security-rule.md` (env, never committed).

## Checklist

- [ ] No fail-open fallback for secrets/auth/TLS; missing critical config crashes (fail closed).
- [ ] Your APIs validate accepted values, not just provide a good default.
- [ ] Edge values (0/""/null/-1) have defined, validated semantics.
- [ ] Config validated at startup; unknown keys and dangerous combos rejected.
- [ ] No weak crypto defaults in security contexts.
