#!/usr/bin/env python3
"""knobup/run_experiment.py — KNOB_POINTER_UP compliance experiment (2026-07-11).

Tests the user's inverted-architecture insight (verbatim): "maybe instead of all this bullshit
[detect-and-counter-rotate] you can just specify in prompt that the tick on knob face should
point upwards 0 degrees?" — paint the pointer AT the zero-degree convention instead of detecting
and correcting after.

2 themes (steam-porthole = templated/single-mark; myst-arcanum = templateless/MULTI-mark
ambiguity case — its stone-and-brass arcane engraving gives the radial-anomaly detector more
than one candidate mark to lock onto) x 4 seeds each, KNOB_POINTER_UP clause ON for all 8.

Full pipeline per gen — genskin -> extract12 pass1 -> biref12 -> extract12 pass2, the SAME chain
orchestrate12.py runs for one roll — monkeypatching genskin.HERE to write into knobup/ instead of
gen12/assets-<id>/ (never touches/collides with the live production roster; same isolation
pattern as jsonspec/genskin_jsonspec.py) and genskin.KNOB_POINTER_UP / _POINTER_UP_CLAUSE
in-memory only — the committed genskin.py file stays default OFF (see its KNOB_POINTER_UP
comment); this script never edits it.

Compliance metric: fraction of the 8 gens' detected regions.regions.vol.knob_zero_deg within
+-10deg of 0 (up), read via knob_angle.angular_error — the SAME shared detector extract12.py's
mainline pipeline already writes to every skin's regions.json (verify-outputs-rule: the verifier
is independent of the generation clause it's checking — it was written BEFORE this experiment,
for a different purpose, and doesn't know KNOB_POINTER_UP exists).

Compared against the historical (pre-fix, clause OFF) distribution supplied by the task —
the 6 mainline templated skins' knob_zero_deg at the time detect-and-counter-rotate was the
only mechanism: 85.6, 144, 95, 355, 4, 359 degrees.

Cost: 8 x ~$0.24-0.30 (Vertex 4K image edit, PAINT_VERTEX=True) ~= $2. extract12/biref12 are $0
(BIREF_LOCAL, MPS).

Usage: python3 run_experiment.py
Writes knobup/assets-knobup-<theme>-<seed>/ (full pipeline output per gen, incl. regions.json)
and knobup/results.json (the compliance table consumed by build_results_page.py).
"""
import os, sys, json, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
sys.path.insert(0, GEN12)
import genskin as G  # noqa: E402  (proven builder — imported, never edited on disk)
from knob_angle import angular_error  # noqa: E402  (the shared, independent verifier)

THEME_SPECS = os.path.join(GEN12, "theme_specs")
THEMES = ["steam-porthole", "myst-arcanum"]
SEEDS = [101, 202, 303, 404]  # distinct from the mainline seeds (623 / 649) — no collision risk

POINTER_UP_CLAUSE = ", its pointer notch aiming straight up"


def load_spec(theme):
    return json.load(open(os.path.join(THEME_SPECS, f"{theme}.json")))


def run_gen(theme, seed):
    """Runs genskin.py's OWN main() end-to-end with KNOB_POINTER_UP forced ON, in-memory only
    (module attributes swapped back after the call — the file on disk is never touched), then
    the extract->biref->extract chain via subprocess (each takes its own <assets-dir> argv, so
    location is independent of genskin's HERE monkeypatch)."""
    spec = dict(load_spec(theme))
    sid = f"knobup-{theme}-{seed}"
    spec["id"] = sid
    spec["seed"] = seed
    tmp_spec = os.path.join(HERE, f".tmp-spec-{sid}.json")
    json.dump(spec, open(tmp_spec, "w"))

    orig_here = G.HERE
    orig_flag = G.KNOB_POINTER_UP
    orig_clause = G._POINTER_UP_CLAUSE
    orig_argv = sys.argv
    G.HERE = HERE                          # -> writes to knobup/assets-<sid>/, not gen12/
    G.KNOB_POINTER_UP = True
    G._POINTER_UP_CLAUSE = POINTER_UP_CLAUSE
    try:
        sys.argv = ["genskin.py", tmp_spec]
        G.main()
    finally:
        G.HERE, G.KNOB_POINTER_UP, G._POINTER_UP_CLAUSE, sys.argv = (
            orig_here, orig_flag, orig_clause, orig_argv)
        os.remove(tmp_spec)

    assets_dir = os.path.join(HERE, f"assets-{sid}")
    # pass1 (pre-biref) -> biref -> pass2 (picks up the matte + writes knob_zero_deg)
    subprocess.run(["python3", "extract12.py", assets_dir], cwd=GEN12, check=False)
    subprocess.run(["python3", "biref12.py", assets_dir], cwd=GEN12, check=False)
    subprocess.run(["python3", "extract12.py", assets_dir], cwd=GEN12, check=False)
    return assets_dir


def main():
    rows = []
    for theme in THEMES:
        for seed in SEEDS:
            print(f"\n########## {theme} seed={seed} ##########", flush=True)
            assets_dir = run_gen(theme, seed)
            zdeg = None
            try:
                regs = json.load(open(os.path.join(assets_dir, "regions.json")))["regions"]
                zdeg = regs.get("vol", {}).get("knob_zero_deg")
            except Exception as e:
                print(f"  !! regions.json read failed: {e}")
            err = angular_error(zdeg) if zdeg is not None else None
            compliant = bool(err is not None and err <= 10.0)
            rows.append({"theme": theme, "seed": seed, "id": f"knobup-{theme}-{seed}",
                         "assets_dir": os.path.relpath(assets_dir, HERE),
                         "knob_zero_deg": zdeg, "abs_error_from_up": err,
                         "compliant_10deg": compliant})
            print(f"  -> knob_zero_deg={zdeg} err={err} compliant={compliant}", flush=True)
            json.dump(rows, open(os.path.join(HERE, "results.json"), "w"), indent=2)  # save as we go
            time.sleep(12)  # Vertex per-minute quota (jsonspec/run_batch.py precedent)

    n_compliant = sum(r["compliant_10deg"] for r in rows)
    print(f"\n=== {n_compliant}/{len(rows)} compliant (+-10deg of up) ===")


if __name__ == "__main__":
    main()
