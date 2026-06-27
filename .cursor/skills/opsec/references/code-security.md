# Code security (any language) — injection, deserialization, crypto, TOCTOU, memory

Non-web code bugs. For the HTTP-specific cases (SQLi, XXE, path traversal in request handling)
see [web.md](web.md); this file covers the language/runtime-level surfaces.

## Command / shell injection

Passing user/untrusted data into a shell is the highest-impact non-web bug (→ RCE).

- **Never build a shell string from input.** Pass argument **arrays** to an exec API that
  bypasses the shell.
```python
# VULNERABLE
os.system("convert " + filename + " out.png")
subprocess.run(f"git log {ref}", shell=True)
# SECURE — arg list, no shell
subprocess.run(["convert", filename, "out.png"])        # shell=False (default)
subprocess.run(["git", "log", ref])
```
```js
exec(`convert ${file} out.png`)                 // VULNERABLE
execFile("convert", [file, "out.png"])          // SECURE
```
- If a shell is truly unavoidable, allowlist the input and use the language's quoting
  (`shlex.quote`, not hand-rolled). Argument injection still applies — a value starting with
  `-` can become a flag; use `--` to terminate options.
- Watch indirect sinks: `Runtime.exec`, `system`, backticks, `popen`, `eval`-of-shell,
  template/`Makefile`/CI command interpolation.

## Code injection / dynamic eval

`eval`, `exec`, `Function()`, `pickle`, `yaml.load`, template engines with code, SSTI,
`require()`/import of a computed path. **Don't eval untrusted data.** Use a data parser
(`json.loads`), a safe loader (`yaml.safe_load`), or a sandboxed expression evaluator with an
allowlist. Server-side template injection: never put user input into the template *source*,
only into the data context.

## Insecure deserialization

Deserializing attacker-controlled bytes with a format that can instantiate arbitrary types is
RCE. Avoid: Python `pickle`/`marshal`/`shelve`, PyYAML `yaml.load`, Java native
`ObjectInputStream`, Ruby `Marshal.load`, PHP `unserialize`, .NET `BinaryFormatter`/
`NetDataContractSerializer`. **Prefer data-only formats (JSON) with a schema.** If a rich
format is required, use allow-listed types / safe modes and sign the payload.

## Cryptography misuse

Don't roll your own. Use a vetted high-level library (libsodium/NaCl, `cryptography`, Tink).

- **Don't choose primitives you don't need to.** Avoid APIs that let you pick `alg`/mode
  (footgun — see JWT `alg:none`, [web.md](web.md#auth--jwt)).
- ECB mode, static/zero IV/nonce, nonce reuse → broken. Use authenticated encryption
  (AES-GCM, ChaCha20-Poly1305) with a unique nonce per message.
- Randomness: CSPRNG only (`secrets`, `crypto.randomBytes`, `/dev/urandom`) — never
  `random`/`Math.random()`/`rand()` for tokens, keys, IVs, salts.
- Comparisons of secrets/MACs/tokens must be **constant-time** (`hmac.compare_digest`,
  `crypto.timingSafeEqual`), not `==`.
- Passwords → Argon2id/bcrypt/scrypt ([web.md](web.md#auth--jwt)); never a plain/fast hash.
- For deep timing-side-channel work, use ToB `constant-time-analysis`.

## Race conditions / TOCTOU

Time-of-check-to-time-of-use: a value is validated, then used after it can change.

- **File TOCTOU:** `if os.access(p): open(p)` — the path can be swapped (symlink) in between.
  Open first, then check the *fd* (`os.fstat`), use `O_NOFOLLOW`/`O_EXCL`.
- **Temp files:** never predictable names in a shared dir; use `mkstemp`/`NamedTemporaryFile`
  (atomic, 0600), never `tempnam`/manual `/tmp/foo$$`.
- **App-level:** check-then-act on balances/quotas/uniqueness without a lock or atomic op →
  double-spend / duplicate. Use DB transactions, `SELECT ... FOR UPDATE`, unique constraints,
  or atomic compare-and-set.

## Memory safety (C/C++/unsafe)

Brief — for real depth use ToB `c-review`. Defaults: bounds-check all indexing; prefer
`snprintf`/`strlcpy` over `strcpy`/`sprintf`/`gets`; check every allocation and integer math
for overflow before sizing a buffer; no use-after-free / double-free (RAII / smart pointers);
initialize before use. In Rust, audit every `unsafe` block for the invariant it's upholding.

## Checklist

- [ ] No shell string built from input; arg-array exec; `--` to stop option parsing.
- [ ] No `eval`/dynamic-code on untrusted data; safe loaders (`yaml.safe_load`, `json`).
- [ ] No unsafe deserializer on untrusted bytes; data-only formats with schema.
- [ ] Vetted crypto lib; AEAD; CSPRNG; unique nonces; constant-time secret compare.
- [ ] TOCTOU closed: operate on fds, atomic temp files, locks/atomic ops for check-then-act.
