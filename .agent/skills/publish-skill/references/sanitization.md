# Sanitization — what gets scrubbed before a skill goes public

`scripts/sanitize.py` enforces this. Auto-replaced items are fixed silently; flagged items
**block publish** until resolved (edit central, or `--allow <regex>` for a vetted
false-positive). Always review the printed diff before approving — the human gate is the
last line of defense, not the regex.

## Auto-replaced (deterministic, safe)

| Private | Replacement |
|---|---|
| `/Users/conner` | `~` |
| `conner.k.ward@gmail.com` | `you@example.com` |
| `lappy-heavy`, `lappy`, `desky`, `mogo` | `your-mac` / `your-machine` |
| `lappy-heavy.tilapia-micro.ts.net`, `tilapia-micro.ts.net` | generic host / tailnet |
| `192.168.8.x` LAN IPs | `192.168.x.x` |

## Flagged → blocks publish (human must resolve)

- `ckward` (internal handle — note `connerkward`, the public GitHub identity, is **kept**)
- `~/dev/central` and private repo paths
- Private corpus/project names: `ideas-syncthing`, `skeuo`, `feedsieve`, `feed-demon`,
  `war-room`, `portfolio-2026`
- `[[wiki-links]]` to a **non-public** skill/rule — block. (A link to a *published* sibling
  is auto-rewritten to its real `github.com/connerkward/<repo>` URL via the name-map and does
  NOT block; only refs to skills absent from `references/name-map.md` — e.g. `screencast`,
  `publish-skill`, `writing-as-conner` — survive as `[[name]]` and trip this flag. Resolve by
  rewriting the line in central to not name the private skill, or publish that skill first.)
- `.ts.net` tailnet hostnames
- Inline secret assignments (`*_TOKEN=`, `*_API_KEY=`, …) and credential-shaped strings
  (`ghp_…`, `sk-…`, `AKIA…`). Per security-rule this is an absolute stop.

## Also do by hand (judgment, not regex)

- **Strip internal cross-refs to other private skills** unless that skill is also public.
- **Drop internal scratch** (`TODO.md`, `.serve-url`) — excluded by the copier already.
- **Generalize machine-specific instructions** (LaunchAgent labels, per-host wiring) into
  portable setup steps; the private specifics live in the `machines` skill, not the public repo.
- **Re-read the README and SKILL.md as a stranger** — would anything here identify the
  author's machine, projects, or accounts beyond the intended `connerkward` GitHub identity?

## False positives

If the scan flags something genuinely safe (e.g. the word "central" used generically),
pass `--allow '<regex>'`. Prefer fixing the source over allow-listing — an allow that's too
broad defeats the scan.
