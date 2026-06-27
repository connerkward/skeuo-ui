import os
import sys
import shutil
import glob
import re
from pathlib import Path

# Derive central root from this file's location: <BASE_DIR>/skills/universal-rule-skill-export/export_config.py
BASE_DIR = str(Path(__file__).resolve().parent.parent.parent)
SOURCE_RULES = os.path.join(BASE_DIR, "rules")
SOURCE_SKILLS = os.path.join(BASE_DIR, "skills")

DEST_AGENT_RULES = os.path.join(BASE_DIR, ".agent/rules")
DEST_AGENT_SKILLS = os.path.join(BASE_DIR, ".agent/skills")

DEST_CLAUDE_RULES = os.path.join(BASE_DIR, ".claude/rules")
DEST_CLAUDE_SKILLS = os.path.join(BASE_DIR, ".claude/skills")

DEST_CURSOR_RULES = os.path.join(BASE_DIR, ".cursor/rules")
DEST_CURSOR_SKILLS = os.path.join(BASE_DIR, ".cursor/skills")

DEST_QWEN_RULES = os.path.join(BASE_DIR, ".qwen/rules")
DEST_QWEN_SKILLS = os.path.join(BASE_DIR, ".qwen/skills")
DEST_QWEN_INDEX = os.path.join(BASE_DIR, ".qwen/QWEN.md")

DEST_OPENCODE_RULES = os.path.join(BASE_DIR, ".opencode/rules")
DEST_OPENCODE_SKILLS = os.path.join(BASE_DIR, ".opencode/skills")
DEST_OPENCODE_BUNDLE = os.path.join(BASE_DIR, ".opencode/AGENTS.md")

SKILL_DESTS = [
    DEST_AGENT_SKILLS,
    DEST_CLAUDE_SKILLS,
    DEST_CURSOR_SKILLS,
    DEST_QWEN_SKILLS,
    DEST_OPENCODE_SKILLS,
]

RULE_DESTS = [
    DEST_AGENT_RULES,
    DEST_CLAUDE_RULES,
    DEST_CURSOR_RULES,
    DEST_QWEN_RULES,
    DEST_OPENCODE_RULES,
]

GENERATED_INDEX_FILES = [DEST_QWEN_INDEX, DEST_OPENCODE_BUNDLE]


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def read_file(path):
    with open(path, 'r') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w') as f:
        f.write(content)

def parse_frontmatter(content):
    match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
    if match:
        return match.group(1), content[match.end():]
    return "", content

def update_frontmatter_for_agent(frontmatter, content):
    if "trigger:" not in frontmatter:
        frontmatter += "\ntrigger: always_on"
    return f"---\n{frontmatter}\n---{content}"

# Heavy runtime assets stay only in the source central/skills/ (which the live ~/.claude
# symlink reads); the per-tool generated copies need only the text/instructions, so media,
# compiled binaries, and caches are excluded to keep the exported trees lean.
SKILL_IGNORE_GLOBS = [
    "*.gif", "*.mp4", "*.mov", "*.webm", "*.png", "*.jpg", "*.jpeg", "*.wav",
    ".git", "__pycache__", "*.pyc", ".studio-out", ".DS_Store",
    "say-notify-overlayd", "sck-record",  # compiled swift binaries (gitignored at source)
]
SKILL_COPY_IGNORE = shutil.ignore_patterns(*SKILL_IGNORE_GLOBS)

def _skill_ignored(rel_path):
    import fnmatch
    return any(fnmatch.fnmatch(part, g) for part in rel_path.split(os.sep) for g in SKILL_IGNORE_GLOBS)

def export_skills():
    print("Exporting Skills...")
    skills = [d for d in os.listdir(SOURCE_SKILLS) if os.path.isdir(os.path.join(SOURCE_SKILLS, d))]

    for skill in skills:
        src_skill_dir = os.path.join(SOURCE_SKILLS, skill)

        for dest_root in SKILL_DESTS:
            dest_path = os.path.join(dest_root, skill)
            if os.path.exists(dest_path):
                shutil.rmtree(dest_path)
            shutil.copytree(src_skill_dir, dest_path, ignore=SKILL_COPY_IGNORE)

        print(f"  Synced skill: {skill}")

def build_rule_outputs():
    """Pure: return {abs_path: expected_content} for every generated rule file + index.
    Single source of truth used by BOTH export (writes them) and check (compares them)."""
    rule_files = sorted(glob.glob(os.path.join(SOURCE_RULES, "*.md")))
    out = {}
    qwen_imports = []
    bundle_sections = []  # (rule_name, body) for AGENTS.md

    for rule_path in rule_files:
        filename = os.path.basename(rule_path)
        name_no_ext = os.path.splitext(filename)[0]
        folder_name = name_no_ext.replace("-rule", "")
        content = read_file(rule_path)
        fm, body = parse_frontmatter(content)
        destination_filename = filename if filename.endswith("-rule.md") else f"{name_no_ext}-rule.md"

        out[os.path.join(DEST_AGENT_RULES, folder_name, "RULE.md")] = update_frontmatter_for_agent(fm, body)
        out[os.path.join(DEST_CLAUDE_RULES, destination_filename)] = content
        out[os.path.join(DEST_CURSOR_RULES, f"{folder_name}.mdc")] = content
        out[os.path.join(DEST_QWEN_RULES, destination_filename)] = content
        out[os.path.join(DEST_OPENCODE_RULES, destination_filename)] = content

        qwen_imports.append(destination_filename)
        bundle_sections.append((folder_name, body.strip()))

    qwen_lines = ["# Central Rules (auto-generated)", ""] + [f"@rules/{n}" for n in qwen_imports]
    out[DEST_QWEN_INDEX] = "\n".join(qwen_lines) + "\n"
    out[DEST_OPENCODE_BUNDLE] = _build_bundle("Central Rules", bundle_sections)
    return out


def export_rules():
    print("Exporting Rules...")
    outputs = build_rule_outputs()
    for path, content in outputs.items():
        ensure_dir(os.path.dirname(path))
        write_file(path, content)
    print(f"  Wrote {len(outputs)} rule files across 5 targets")


def _build_bundle(title, sections):
    out = [f"# {title} (auto-generated from central/rules)", ""]
    for name, body in sections:
        out.append(f"## {name}")
        out.append("")
        out.append(body)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def clear_dir(path):
    if not os.path.isdir(path):
        return
    for name in os.listdir(path):
        p = os.path.join(path, name)
        if os.path.isdir(p):
            shutil.rmtree(p)
        else:
            os.remove(p)

def _tree_diffs(src, dst):
    """Content-based recursive diff (mtime-immune, unlike filecmp). Returns list of drift strings."""
    diffs = []
    if not os.path.exists(dst):
        return [f"{dst} (missing export dir)"]
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if not _skill_ignored(d)]   # prune ignored dirs
        rel = os.path.relpath(root, src)
        for f in files:
            relf = os.path.normpath(os.path.join(rel, f))
            if _skill_ignored(relf):   # excluded from exports by design — not drift
                continue
            sp, dp = os.path.join(root, f), os.path.join(dst, rel, f)
            if not os.path.exists(dp):
                diffs.append(f"{dp} (missing)")
            elif open(sp, "rb").read() != open(dp, "rb").read():
                diffs.append(f"{dp} (differs from source)")
    for root, dirs, files in os.walk(dst):
        dirs[:] = [d for d in dirs if not _skill_ignored(d)]
        rel = os.path.relpath(root, dst)
        for f in files:
            if _skill_ignored(os.path.normpath(os.path.join(rel, f))):
                continue
            if not os.path.exists(os.path.join(src, rel, f)):
                diffs.append(f"{os.path.join(root, f)} (extra — not in source)")
    return diffs


def check_fresh():
    """Return drift list: exported files that diverge from a fresh build of central source.
    Catches the silent-drift bug — someone edited an export instead of the central source."""
    drift = []
    # skills: each export must be a byte-identical copy of its source tree
    skills = [d for d in os.listdir(SOURCE_SKILLS) if os.path.isdir(os.path.join(SOURCE_SKILLS, d))]
    for skill in skills:
        src = os.path.join(SOURCE_SKILLS, skill)
        for dest_root in SKILL_DESTS:
            drift += _tree_diffs(src, os.path.join(dest_root, skill))
    # rules + generated indexes: compare on-disk against the pure builder
    for path, expected in build_rule_outputs().items():
        if not os.path.exists(path):
            drift.append(f"{path} (missing)")
        elif read_file(path) != expected:
            drift.append(f"{path} (stale — differs from source build)")
    return drift


def export():
    for d in RULE_DESTS + SKILL_DESTS:
        ensure_dir(d)
        clear_dir(d)
    for idx in GENERATED_INDEX_FILES:
        if os.path.exists(idx):
            os.remove(idx)
    export_skills()
    export_rules()
    print("Export Complete.")


def main():
    if "--check" in sys.argv:
        drift = check_fresh()
        if drift:
            print(f"STALE: {len(drift)} exported file(s) diverge from central source:")
            for d in drift[:50]:
                print(f"  - {d}")
            if len(drift) > 50:
                print(f"  … and {len(drift) - 50} more")
            print("Fix: edit the SOURCE in central/{rules,skills}/, then re-run the export "
                  "(never edit an exported copy directly).")
            sys.exit(1)
        print("FRESH: all exports match central source.")
        sys.exit(0)
    export()


if __name__ == "__main__":
    main()
