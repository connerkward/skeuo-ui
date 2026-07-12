#!/usr/bin/env python3
"""prompt_provenance — inline citation markers for gen12's model-facing prompts, + the
strip/regen tooling. USER DIRECTIVE (2026-07-11): every prompt clause sent to an image or
VLM model in this pipeline exists because of a concrete experiment, a human review round, a
decision, or a fix commit — and that WHY rots the moment nobody records it (the fix lands,
the reason doesn't). This is the gen12-local analogue of central's `provenance` skill
(HTML-comment markers in rule SOURCE, stripped at export so injection stays lean) — same
"record the why in source, strip it before it reaches the consumer" shape, adapted because
these consumers are string literals inside Python (not Markdown), so the marker is an inline
token instead of an HTML comment.

THE CONVENTION
  * SOURCE (genskin.py / observe12.py / director_review.py) carries citations INLINE, as
    ⟦cite:ref[;ref...]⟧ markers appended directly inside the existing prompt string literals
    — no restructuring of the (considerable) conditional prompt-assembly logic those files
    already have. Each <ref> is one of:
      - a repo-relative path      docs/experiments/2026-07-11-jsonspec-paint.md
      - a commit                  sha:8abf3e8a
      - genuinely unrecoverable   unknown   (flagged, never invented — the
                                              verify-outputs-rule discipline: don't
                                              fabricate a source)
  * strip_cites() removes every marker before anything reaches an API — this is the ONLY
    function on the hot path. genskin.py strips immediately after assembling the prompt
    (before the Vertex/fal call AND before the prompt is persisted to results.json);
    observe12.py / director_review.py strip right after their prompt assignments.
  * regenerate_doc() (run this file directly: `python3 prompt_provenance.py`) rebuilds
    PROMPT-PROVENANCE.md — the assembled prompts with citations rendered as visible links,
    the human-readable "why does the prompt say X" reference. One command.

MARKER CHARACTER: ⟦ ⟧ (U+27E6/U+27E7, MATHEMATICAL WHITE SQUARE BRACKET) — chosen over ASCII
[]/()/{} because those appear constantly in the prompts' own text (JSON blocks, plain
punctuation); ⟦⟧ never collides and is trivial to grep for when auditing coverage.

COVERAGE IS NOT MANDATORY, VISIBILITY IS. Retrofitting a citation onto literally every clause
is not the goal (restraint) — `warn_uncited()` makes a NEW clause added without a cite LOUD
(a stderr warning during doc regen), not blocked.

BYTE-IDENTICAL GUARANTEE: markers are pure additive insertions into string literals, and
strip_cites removes exactly its own marker characters — verified 2026-07-12 against a
pre-annotation baseline across 11 genskin flag configs (both states of PROMPT_JSON_SPEC,
KNOB_POINTER_UP, SEEK_CLAUSE_LITE; solid/outline/twoimg conditioning; templateless; baked
ticks) + static joined-constant proofs for observe12/director_review. See TODO.md entry.
"""
import os
import re
import ast
import sys
import json
import types
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))  # gen12 -> mask-align-exp -> tools -> root
DOC_PATH = os.path.join(HERE, "PROMPT-PROVENANCE.md")

CITE_RE = re.compile(r"⟦cite:([^⟧]*)⟧")


def strip_cites(text):
    """Remove every ⟦cite:...⟧ marker. Markers are pure ADDITIVE insertions into the source
    string literals, so removing exactly their own characters restores the marker-free prompt
    byte-for-byte — no whitespace cleanup pass, no risk of eating adjacent text."""
    return CITE_RE.sub("", text)


def warn_uncited(text, label, min_len=90):
    """Loudly (stderr) flag long prose lines with no citation anywhere on them — not blocking,
    just visible. Short/structural lines are ignored to keep signal-to-noise usable."""
    warned = 0
    for line in text.split("\n"):
        if len(strip_cites(line).strip()) < min_len or CITE_RE.search(line):
            continue
        print(f"[prompt_provenance] WARN uncited clause in {label}: "
              f"{strip_cites(line).strip()[:90]}...", file=sys.stderr)
        warned += 1
    return warned


def _commit_subject(sha):
    try:
        out = subprocess.check_output(["git", "log", "-1", "--format=%h %s", sha],
                                       cwd=REPO_ROOT, stderr=subprocess.DEVNULL)
        return out.decode().strip()
    except Exception:
        return f"{sha} — not found in this checkout"


def render_ref(ref):
    """One citation ref -> a markdown fragment; file links relative to this doc's own dir."""
    if ref == "unknown":
        return "*provenance unknown — flagged, not invented*"
    if ref.startswith("sha:"):
        return f"commit `{_commit_subject(ref[4:])}`"
    abs_target = os.path.join(REPO_ROOT, ref)
    rel = os.path.relpath(abs_target, HERE)
    exists = "" if os.path.exists(abs_target) else " ⚠missing"
    return f"[`{ref}`]({rel}){exists}"


def annotate_markdown(text):
    """Render TEXT with each ⟦cite:...⟧ marker replaced by a visible inline citation."""
    def _sub(m):
        refs = [r.strip() for r in m.group(1).split(";") if r.strip()]
        return "  ⟨cite: " + "; ".join(render_ref(r) for r in refs) + "⟩"
    return CITE_RE.sub(_sub, text)


# --------------------------------------------------------------------- genskin.py doc sections
# genskin.py is run for-real via --blueprint-only (no network spend — genskin's own
# short-circuit returns BEFORE any edit()/edit_vertex() call), by exec-ing a FLAG-PATCHED copy
# of its source as a fresh module. Source-patching (not setattr-after-import) because several
# derived values (SEEK_SLOT_BULLET, _POINTER_UP_CLAUSE) are computed at import time from the
# flags. __file__ is pointed at a /tmp scratch dir so genskin's HERE-derived output
# (assets-<id>/results.json + blueprint.png) can NEVER clobber the real assets dirs.
GENSKIN_PATH = os.path.join(HERE, "genskin.py")
SCRATCH_OUT = "/tmp/prompt-provenance-out"
GENSKIN_MATRIX = [
    # (doc section label, theme spec, flag overrides (source-patched), spec-field overrides)
    ("templated / solid conditioning / prose (production default)", "fa-pod.json",
     {"BLUEPRINT_ARM_WEIGHTS": [("solid", 1.0)]}, {}),
    ("templated / outline conditioning / prose (trial arm)", "fa-pod.json",
     {"BLUEPRINT_ARM_WEIGHTS": [("outline", 1.0)]}, {}),
    ("templated / twoimg conditioning (flag-gated mode, falsified, default OFF)", "fa-pod.json",
     {}, {"conditioning": "twoimg"}),
    ("templated / solid / PROMPT_JSON_SPEC=True (flag-gated encoding, default OFF)", "fa-pod.json",
     {"BLUEPRINT_ARM_WEIGHTS": [("solid", 1.0)], "PROMPT_JSON_SPEC": True}, {}),
    ("templateless / prose", "claymation.json", {}, {}),
]


def load_genskin_with_flags(flag_overrides):
    src = open(GENSKIN_PATH).read()
    for k, v in flag_overrides.items():
        pat = rf"^{k} = .*$"
        n = len(re.findall(pat, src, flags=re.M))
        assert n == 1, f"flag {k}: expected exactly 1 assignment, found {n}"
        src = re.sub(pat, f"{k} = {v!r}", src, count=1, flags=re.M)
    os.makedirs(SCRATCH_OUT, exist_ok=True)
    mod = types.ModuleType("genskin_provenance")
    mod.__dict__["__file__"] = os.path.join(SCRATCH_OUT, "genskin.py")
    exec(compile(src, GENSKIN_PATH, "exec"), mod.__dict__)
    assert mod.HERE == SCRATCH_OUT, mod.HERE
    return mod


def build_genskin_sections():
    sections = []
    for label, spec_file, flag_overrides, spec_overrides in GENSKIN_MATRIX:
        spec = json.load(open(os.path.join(HERE, "theme_specs", spec_file)))
        spec.update(spec_overrides)
        mod = load_genskin_with_flags(flag_overrides)
        tmp_spec = os.path.join(SCRATCH_OUT, f"provenance-spec-{spec['id']}.json")
        json.dump(spec, open(tmp_spec, "w"))
        old_argv = sys.argv
        sys.argv = ["genskin.py", tmp_spec, "--blueprint-only"]
        try:
            mod.main()
            res = json.load(open(os.path.join(SCRATCH_OUT, f"assets-{spec['id']}", "results.json")))
            annotated = res.get("prompt_annotated", "(genskin did not emit prompt_annotated)")
        finally:
            sys.argv = old_argv
            os.remove(tmp_spec)
        sections.append((f"genskin.py — {label}", annotated))
    return sections


# --------------------------------------------------- observe12.py / director_review.py sections
# Both are top-level SCRIPTS (argv/network/browser side effects at import time) — unsafe to
# import for doc-gen. Extract the annotated prompt-literal text statically via ast: the joined
# string CONSTANTS of the named assignment's expression (f-string interpolations are
# runtime-varying holes, simply absent from the joined text — the clauses and their citations
# all live in the constants). Where a name is assigned more than once (the runtime
# `X = strip_cites(X)` re-assignment), the assignment with the LONGEST joined constants is the
# annotated literal.
def _joined_constants(py_path, target):
    tree = ast.parse(open(py_path).read())
    best = ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
           and isinstance(node.targets[0], ast.Name) and node.targets[0].id == target:
            consts = "".join(n.value for n in ast.walk(node.value)
                              if isinstance(n, ast.Constant) and isinstance(n.value, str))
            if len(consts) > len(best):
                best = consts
    return best or None


STATIC_SECTIONS = [
    ("observe12.py — VLM defect-check prompt (string-constant text; runtime interpolations omitted)",
     "observe12.py", "prompt"),
    ("director_review.py — director persona SYSTEM_PROMPT", "director_review.py", "SYSTEM_PROMPT"),
    ("director_review.py — director USER_PROMPT (string-constant text; runtime interpolations omitted)",
     "director_review.py", "USER_PROMPT"),
    # flag-gated genskin clause VARIANTS that don't appear in the default assemblies above
    ("genskin.py — SEEK_CLAUSE_LITE=True device bullet (flag-gated variant, default OFF)",
     "genskin.py", "_SEEK_SLOT_BULLET_LITE"),
    ("genskin.py — SEEK_CLAUSE_LITE=True strip bullet (flag-gated variant, default OFF)",
     "genskin.py", "_SEEK_STRIP_BULLET_LITE"),
]


def build_static_sections():
    out = []
    for label, fname, target in STATIC_SECTIONS:
        txt = _joined_constants(os.path.join(HERE, fname), target)
        if txt:
            out.append((label, txt))
        else:
            print(f"[prompt_provenance] WARN: {target} not found in {fname}", file=sys.stderr)
    return out


def regenerate_doc():
    sections = build_genskin_sections() + build_static_sections()
    total_cites = 0
    total_warned = 0
    lines = [
        "# Prompt Provenance — why each clause is the way it is\n",
        "GENERATED by [`prompt_provenance.py`](./prompt_provenance.py) — run",
        "`python3 prompt_provenance.py` to refresh. Do not hand-edit; edit the `⟦cite:...⟧`",
        "markers in [`genskin.py`](./genskin.py) / [`observe12.py`](./observe12.py) /",
        "[`director_review.py`](./director_review.py) source and regenerate.\n",
        "Every marker in SOURCE is removed by `strip_cites()` before the prompt reaches any",
        "model/API (verified byte-identical against a pre-annotation baseline across all flag",
        "states — see TODO.md). This document is where the citations become visible: each",
        "`⟨cite: ...⟩` names the experiment / human-review round / decision / commit that",
        "clause exists because of. Note: the `KNOB_POINTER_UP` pointer-up clause was FALSIFIED",
        "(paint-at-convention lost to detect-and-counter-rotate, flag stays OFF) — its cite",
        "rides the `_POINTER_UP_CLAUSE` literal in genskin.py source, empty by default.\n",
    ]
    for title, annotated in sections:
        lines.append(f"\n## {title}\n")
        total_cites += len(CITE_RE.findall(annotated))
        total_warned += warn_uncited(annotated, title)
        lines.append("```text")
        lines.append(annotate_markdown(annotated).replace("```", "'''"))
        lines.append("```")
    lines.append(f"\n---\n*{total_cites} citation markers across {len(sections)} sections; "
                  f"{total_warned} long uncited clause(s) flagged to stderr during generation "
                  f"(warn-only by design — see prompt_provenance.py docstring).*")
    open(DOC_PATH, "w").write("\n".join(lines) + "\n")
    print(f"[prompt_provenance] wrote {DOC_PATH} ({len(sections)} sections, "
          f"{total_cites} cites, {total_warned} uncited warnings)")


if __name__ == "__main__":
    regenerate_doc()
