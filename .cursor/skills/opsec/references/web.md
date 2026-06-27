# Web app vulnerabilities

HTTP request handling, rendering, and auth. Defenses + the concrete bypass payloads attackers
use. Apply the relevant section's defaults whenever you touch that surface.

## Access control (IDOR, privilege escalation, mass assignment)

The #1 source of high-severity web bugs — invisible to scanners; you must reason about *who
owns what*. Verify ownership **at the data layer**, on every read and write, not at the route.

- **IDOR / horizontal:** `/orders/1234` must check 1234 belongs to the requester. Return
  **404, not 403**, for unauthorized access (no enumeration).
- **Vertical / privesc:** never trust a client-supplied role; validate role transitions
  server-side; the actor must be authorized to grant the target role.
- **Mass assignment:** whitelist writable fields — `User.update(pick(req.body, ['name','email']))`,
  never `User.update(req.body)` (attacker sends `{role:"admin"}`). Applies to every ORM.
- **Nested resources:** check parent ownership too (own the comment's parent post).
- **Account lifecycle:** on org-removal/deletion, revoke all sessions + API keys immediately;
  short-lived tokens + revocation list make it effective in minutes.
- Prefer non-guessable ids (UUIDv4/ULID) — defense in depth, **not** a substitute for the check.

```
resource = db.find(id)
if resource is null: return 404
if resource.ownerId != user.id and not user.hasOrgAccess(resource.orgId): return 404
```

## XSS

Every user-influenced value must be safe in its render context. Default to framework
auto-escaping; treat every escape hatch (`innerHTML`, `v-html`, `dangerouslySetInnerHTML`,
`document.write`, `eval`) as a finding when fed user data.

- Sources incl. the overlooked: URL fragment, headers shown in UI, third-party API data,
  `postMessage`, storage, error messages, **SVG uploads (run JS)**, Markdown allowing HTML.
- Sanitize rich text with **DOMPurify** (allowlist), never a regex.
- **CSP:** `default-src 'self'; script-src 'self'` (nonces/hashes for inline; no
  `unsafe-inline`/`unsafe-eval`); `frame-ancestors 'none'`; `base-uri 'self'`. Plus
  `X-Content-Type-Options: nosniff`.

## CSRF

Every **state-changing** endpoint, including pre-auth (login, signup, reset, verify, OAuth
callback).

- **CSRF token:** random, session-tied, validated on every state-changer, regenerated on login.
  Missing token ⇒ reject. Prefer header (`X-CSRF-Token`) over URL param.
- **SameSite=Strict/Lax** + `Secure` + `HttpOnly` cookies.
- JSON content-type does **not** stop CSRF — also check Origin/Referer. Never state-change on GET.

## Open redirect

Prefer relative paths only (reject `//` and absolute URLs) or an indirect map; else allowlist
the host after Punycode normalization.

| Bypass | Example |
|---|---|
| `@` userinfo | `https://legit.com@evil.com` |
| Subdomain | `https://legit.com.evil.com` |
| Protocol payload | `javascript:` / `data:text/html,...` |
| Double-encode | `%252f%252fevil.com` → `//evil.com` |
| Backslash / null / tab | `legit.com\@evil.com`, `legit.com%00.evil.com`, `legit.com%09.evil.com` |
| Protocol-relative / fragment | `//evil.com`, `https://legit.com#@evil.com` |
| IDN homograph | `legіt.com` (Cyrillic) — convert to Punycode before validating |

## SQL injection

**Parameterized queries / prepared statements** — never concatenate. ORMs parameterize, but
raw escape hatches (`.raw()`, `queryRawUnsafe`, `find_by_sql`) reintroduce it. Can't
parameterize → **allowlist**: table/column names, `ORDER BY`, sort dir, `LIMIT`/`OFFSET` (cast
int). `LIKE` → also escape `%`/`_`. Least-privilege DB user; never return raw SQL errors.

## XXE

Disable DTDs + external entities. Watch non-obvious XML: **DOCX/XLSX/PPTX (zipped XML), SVG,
SAML, PDF-XFA**, JSON→XML.
- Python: `defusedxml`, or `etree.XMLParser(resolve_entities=False, no_network=True)`.
- Java: `disallow-doctype-decl=true` + disable external general/parameter entities.
- .NET: `DtdProcessing.Prohibit; XmlResolver=null`. Node: parser with DTD off.

## Path traversal

Best: don't put input in paths — use an indirect map. Else canonicalize and confirm
containment (resolves symlinks):
```python
base = os.path.abspath(os.path.realpath(base_dir))
target = os.path.abspath(os.path.realpath(os.path.join(base, user_path)))
if os.path.commonpath([base, target]) != base: raise ValueError()
```
Reject `..`/absolute indicators; allowlist chars; test encoded variants (`%2e%2e%2f`, double).
Archive extraction → same check (zip-slip).

## SSRF

Server fetches a user-influenced URL (webhooks, previews, import-from-URL, PDF/HTML render).
Critical when it reaches cloud metadata.

- **Allowlist** destination domains where possible; **scheme** http/https only.
- **Resolve DNS, validate the IP** is not private/internal/link-local; **block metadata**
  (`169.254.169.254`, `metadata.google.internal`). **Pin the resolved IP** for the request
  (defeats DNS rebinding). Disable/validate redirects. Timeout + size cap.

| Bypass | Example |
|---|---|
| Decimal/octal/hex/short IP | `2130706433`, `0177.0.0.1`, `0x7f000001`, `127.1` |
| IPv6 | `[::1]`, `[::]`, `[::ffff:127.0.0.1]` |
| Parser confusion / redirect | `http://attacker.com#@internal`; external → 302 → internal |
| DNS rebinding / CNAME | resolves external then internal |

## File upload

Layer all three: **extension allowlist** (last extension) + **magic-byte match** + **content
re-parse** (decode images, reject polyglots); plus server-side **size** limits.

| Attack | Prevent |
|---|---|
| `shell.php.jpg` / `shell.jpg.php` / `%00` | Allowlist; single extension; reject null |
| MIME spoof / magic-byte prepend | Validate bytes; parse whole file as its type |
| SVG with JS / polyglot | Sanitize SVG or disallow; strict re-parse |
| XXE via DOCX/XLSX / zip-slip | Disable external entities; path-check extraction |
| Filename injection (`; rm -rf`) | Discard original name; random UUID |

Magic bytes: JPEG `FF D8 FF` · PNG `89 50 4E 47` · PDF `25 50 44 46` · ZIP/DOCX `50 4B 03 04`.
Store: random name, **outside webroot** (or separate origin), serve with
`Content-Disposition: attachment` + `nosniff`, non-executable perms.

## Auth & JWT

- **Passwords:** Argon2id/bcrypt/scrypt (never fast hashes). Min 8 (12+ rec), high max, no
  forced composition; check breach lists. Rate-limit/back-off per account + IP.
- **Sessions:** `HttpOnly; Secure; SameSite`; **regenerate id on login** + privilege change;
  idle + absolute timeout.
- **JWT footguns:** reject `alg:none`; **pin the expected algorithm on verify** (never read it
  from the token — RS256→HS256 confusion); 256-bit random secret (env, per security-rule);
  always set+validate `exp` (short ~15min); store in HttpOnly cookie, **not localStorage**; add
  `jti` + revocation. `jwt.verify(t, secret, { algorithms:['HS256'] })`.

## API (GraphQL, mass assignment)

- **Mass assignment:** allowlist fields (see access control).
- **GraphQL:** disable introspection in prod; enforce **depth** + **cost** limits;
  **limit operations/request** (anti batched brute-force on login/OTP); **authorize per
  resolver/field** (nested fields can leak another user's data — IDOR via GraphQL); generic
  errors in prod.

## Security headers (all responses)

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
Content-Security-Policy: <see XSS>
X-Content-Type-Options: nosniff
X-Frame-Options: DENY            # or CSP frame-ancestors
Referrer-Policy: strict-origin-when-cross-origin
Cache-Control: no-store          # authenticated/sensitive responses
```

## Checklist

- [ ] Ownership checked at data layer on read+write; 404 not 403; no mass assignment.
- [ ] User data auto-escaped; no innerHTML/v-html on it; DOMPurify for rich text; CSP set.
- [ ] CSRF token on every state-changer (incl. pre-auth); SameSite+Secure+HttpOnly.
- [ ] Parameterized SQL; XML external entities off; paths canonicalized + contained.
- [ ] SSRF: scheme/IP validated, metadata blocked, IP pinned, redirects controlled.
- [ ] Uploads: extension+magic+content validated, random name, outside webroot.
- [ ] Passwords slow-hashed; sessions regenerated on login; JWT alg pinned, `exp` set, in cookie.
- [ ] GraphQL depth/cost/op limits + per-resolver authz; security headers global.
