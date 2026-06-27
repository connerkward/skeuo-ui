# Privilege escalation & data / info leakage

Two cross-cutting failure modes: a lower-privileged actor gaining higher privilege, and
sensitive data escaping through an unintended channel.

## Privilege escalation

Any boundary between privilege levels is a target. Re-check authorization at the boundary —
never infer it from a prior step.

- **App-level (web):** vertical/horizontal access, mass assignment of `role`/`isAdmin`,
  IDOR — see [web.md](web.md#access-control-idor-privilege-escalation-mass-assignment). The recurring root cause: trusting a
  client-supplied role/id instead of re-deriving it server-side.
- **Token/scope creep:** a token minted for one purpose reused for a broader one; a refresh
  flow that returns a wider scope than requested; an OAuth scope upgrade without re-consent.
  Scope tokens narrowly and verify scope at each use ([operational.md](operational.md)).
- **OS/process:** `sudo` rules wider than needed, **setuid/setgid** binaries, world-writable
  files in a privileged `PATH`, services running as root, `docker.sock` exposed to a container
  (= host root), writable cron/systemd units. Run as non-root; drop capabilities.
- **Insecure inheritance:** child processes inheriting the parent's secrets via environment,
  or a sandbox that leaks env/fs. Strip the environment you pass to untrusted children.
- **Path/library hijack:** untrusted dir early in `PATH`, `LD_PRELOAD`/`LD_LIBRARY_PATH`,
  DLL planting, writable plugin dirs. Use absolute paths for security-critical binaries.

## Data / info leakage

Audit everything written to a channel an attacker can read: responses, logs, error messages,
stack traces, telemetry/analytics, crash reports, URLs, client-side state, caches.

- **Secrets in logs/errors** — never log tokens, passwords, keys, full PANs/SSNs, session ids,
  Authorization headers. Redact before logging. (Storage governed by `security-rule`; this is
  the *don't-emit-them* angle.)
- **Verbose errors in production** — no stack traces, SQL errors, internal paths, framework
  versions, or debug pages to users. Generic message out, detail to the server log.
- **Over-fetching / over-returning** — APIs returning whole records (password hashes, internal
  flags, other users' fields). Return a DTO with explicit fields, not the raw model.
- **PII handling** — collect the minimum; mask on display (`***-**-1234`); don't put PII or
  secrets in URLs (logged everywhere) or in client-visible state.
- **Side channels** — different responses/timings for "user exists" vs not (enumeration; see
  the 404-not-403 rule in [web.md](web.md#access-control-idor-privilege-escalation-mass-assignment)); constant-time secret
  compares ([code-security.md](code-security.md)).
- **Client-exposed secrets** — JS bundles/source maps, `localStorage`, SSR hydration,
  `NEXT_PUBLIC_*`/`REACT_APP_*`/`VITE_*` are public; keep secrets server-side.
- **Caching/CDN** — `Cache-Control: no-store` for authenticated/sensitive responses so a
  shared cache doesn't serve one user's data to another.

## Checklist

- [ ] Authorization re-checked at every privilege boundary, server-side; no trusted client role/id.
- [ ] Tokens scoped narrowly; scope verified at use; no scope creep on refresh.
- [ ] No root/over-privileged processes; setuid/PATH/`LD_*`/socket-exposure reviewed.
- [ ] Secrets/PII never logged; redacted before emit.
- [ ] Production errors generic; no stack traces/internal detail to users.
- [ ] APIs return explicit DTO fields, not raw records; PII minimized/masked; not in URLs.
- [ ] Enumeration/timing side-channels closed; sensitive responses `no-store`.
