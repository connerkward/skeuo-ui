#!/usr/bin/env python3
"""Sanitize a central skill for public release.

Usage: python3 sanitize.py <central-skill-dir> --out <staging-dir> [--allow PATTERN ...]

Copies the skill to a staging dir, AUTO-REPLACES unambiguous personal data, then SCANS for
residual private patterns. Prints a unified diff and a leak report. Exits NON-ZERO if any
flagged pattern survives — that failure blocks publish (resolve by editing central, or pass
--allow for a vetted false-positive). The public-facing GitHub identity 'connerkward' is
intentionally kept. Never push the central copy directly; push the approved staging dir.
"""
import argparse, os, re, shutil, subprocess, sys

# (regex, replacement) — deterministic, safe to auto-apply.
AUTO = [
    (r'/Users/conner\b', '~'),
    (r'\bconner\.k\.ward@gmail\.com\b', 'you@example.com'),
    (r'\blappy-heavy\.tilapia-micro\.ts\.net\b', 'your-host'),
    (r'\btilapia-micro\.ts\.net\b', 'your-tailnet.ts.net'),
    (r'\blappy-heavy\b', 'your-mac'),
    (r'\b(lappy|desky|mogo)\b', 'your-machine'),
    (r'\b192\.168\.8\.\d{1,3}\b', '192.168.x.x'),
    (r'\b192\.168\.8\.x\b', '192.168.x.x'),
    # NOTE: internal [[wiki-links]] are handled by scrub_wikilinks(), not here — a ref to a
    # PUBLISHED sibling becomes a real GitHub link; a ref to a non-public skill is left
    # bracketed so the FLAG scan below blocks publish (no silently-dangling references).
]

# Patterns that, if present AFTER auto-replace, BLOCK publish (human must resolve).
# Conservative: these are strong signals of a private leak, not common English.
FLAG = [
    # any [[wiki-link]] surviving scrub_wikilinks() points at a NON-public skill — block.
    (r'\[\[[A-Za-z0-9][A-Za-z0-9_-]*\]\]',  'reference to a non-public skill/rule (publish that skill first, or rewrite the line in central to not name it)'),
    (r'\bckward\b',                         'internal user handle'),
    (r'~/dev/central\b',                    'private central repo path'),
    (r'\bcentral/(rules|skills|scripts)/[A-Za-z0-9._/-]+', 'private central repo internal path'),
    (r'\bideas-syncthing\b',                'private corpus name'),
    (r'\b(skeuo|feedsieve|feed-demon|war-room|portfolio-2026)\b', 'private project name'),
    (r'\.ts\.net\b',                        'tailnet hostname'),
    # value must look like a real key (>=16 key-chars), not a placeholder like ...,<x>,$VAR,your_key
    (r'\b[A-Za-z0-9_]*(SECRET|TOKEN|PASSWORD|API_KEY|PRIVATE_KEY)[A-Za-z0-9_]*\s*=\s*["\']?[A-Za-z0-9+/_-]{16,}', 'inline secret assignment'),
    # realistic credential lengths + word boundary (avoids e.g. "task-oriented" tripping sk-)
    (r'\b(AKIA[A-Z0-9]{12,}|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})\b', 'credential-shaped string'),
]

# Files/dirs never copied to the public staging dir.
EXCLUDE_NAMES = {'.git', '.DS_Store', '__pycache__', '.serve-url', 'TODO.md', '.studio-out'}
TEXT_EXT = {'.md', '.py', '.sh', '.js', '.ts', '.json', '.txt', '.swift', '.html', '.css', '.yml', '.yaml', '.toml'}

def is_text(p): return os.path.splitext(p)[1].lower() in TEXT_EXT

def load_published_map():
    """Parse references/name-map.md → {internal_skill_name: public_repo}. Single source of
    truth for which skills are public. First backtick token of col-0 = internal name; first
    of col-1 = repo. Skills absent from the table (e.g. screencast) are treated as private."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'references', 'name-map.md')
    m = {}
    try:
        lines = open(path, encoding='utf-8').read().splitlines()
    except OSError:
        return m  # no map → every [[link]] will block; fail safe, not silent
    for line in lines:
        if line.startswith('## '):            # table ends at the first prose section
            if m: break
            continue
        if not line.lstrip().startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 2:
            continue
        i_tok = re.search(r'`([^`]+)`', cells[0])
        r_tok = re.search(r'`([^`]+)`', cells[1])
        if i_tok and r_tok:
            m[i_tok.group(1)] = r_tok.group(1)
    return m

def scrub_wikilinks(text, published):
    """[[X]] → [X](repo url) when X is a published sibling; otherwise leave [[X]] intact so
    the FLAG scan blocks publish. Prevents the silently-dangling-reference bug."""
    def repl(mo):
        name = mo.group(1)
        repo = published.get(name)
        return f'[{name}](https://github.com/connerkward/{repo})' if repo else mo.group(0)
    return re.sub(r'\[\[([A-Za-z0-9][A-Za-z0-9_-]*)\]\]', repl, text)

def copy_skill(src, out):
    if os.path.exists(out): shutil.rmtree(out)
    def ig(_d, names): return [n for n in names if n in EXCLUDE_NAMES]
    shutil.copytree(src, out, ignore=ig)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('skill_dir'); ap.add_argument('--out', required=True)
    ap.add_argument('--allow', action='append', default=[], help='regex of vetted false-positives to ignore in the leak scan')
    a = ap.parse_args()
    src = os.path.abspath(a.skill_dir.rstrip('/'))
    if not os.path.isdir(src): sys.exit(f"not a dir: {src}")
    copy_skill(src, a.out)
    published = load_published_map()

    # auto-replace pass
    changed = 0
    for root, _d, files in os.walk(a.out):
        for fn in files:
            p = os.path.join(root, fn)
            if not is_text(p): continue
            try: t = open(p, encoding='utf-8').read()
            except (UnicodeDecodeError, IsADirectoryError): continue
            orig = t
            for rx, rep in AUTO: t = re.sub(rx, rep, t)
            t = scrub_wikilinks(t, published)   # published sibling refs → links; private refs left to FLAG
            if t != orig:
                open(p, 'w', encoding='utf-8').write(t); changed += 1

    # residual leak scan
    allow = [re.compile(x) for x in a.allow]
    leaks = []
    for root, _d, files in os.walk(a.out):
        for fn in files:
            p = os.path.join(root, fn)
            if not is_text(p): continue
            try: lines = open(p, encoding='utf-8').read().splitlines()
            except (UnicodeDecodeError, IsADirectoryError): continue
            for i, line in enumerate(lines, 1):
                for rx, why in FLAG:
                    for m in re.finditer(rx, line):
                        if any(al.search(m.group(0)) for al in allow): continue
                        rel = os.path.relpath(p, a.out)
                        leaks.append((rel, i, why, m.group(0)[:80]))

    # diff (best-effort, requires the source on disk)
    print(f"=== sanitize: {os.path.basename(src)} -> {a.out} ({changed} files auto-scrubbed) ===")
    d = subprocess.run(['diff', '-ru', '--exclude=.git', src, a.out],
                       capture_output=True, text=True)
    if d.stdout.strip():
        print("\n--- DIFF (private -> scrubbed): review before approving ---")
        print(d.stdout[:8000] + ('\n…(diff truncated)…' if len(d.stdout) > 8000 else ''))

    if leaks:
        print(f"\n!!! {len(leaks)} RESIDUAL LEAK(S) — PUBLISH BLOCKED. Fix in central or --allow a vetted FP:")
        for rel, ln, why, snip in leaks:
            print(f"   {rel}:{ln}  [{why}]  {snip!r}")
        sys.exit(1)
    print("\nLeak scan CLEAN. Staging dir ready for human review + push:", a.out)

if __name__ == '__main__':
    main()
