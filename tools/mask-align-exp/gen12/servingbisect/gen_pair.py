#!/usr/bin/env python3
"""servingbisect/gen_pair.py — serving-path bisect: fal vs Vertex, SAME production prompt.

Isolates the fal->Vertex serving switch (PAINT_VERTEX flipped ON 2026-07-10, ../genskin.py:35)
as a drift suspect, per the drift-clause bisect's follow-up chain
(docs/experiments/2026-07-11-drift-clause-bisect.md): the clause bisect (218224f7) exonerated
the bold-silhouette clause; the extraction-commit bisect (892bf045, driftbisect2/README.md)
proved drift is PAINT-driven, not detector-driven. Remaining suspects: (a) the fal->Vertex
serving switch, (b) seed ranges, (c) accumulated prompt additions in aggregate. This tests (a)
directly: same production prompt, same 2 themes (the true regressors), same 2 seeds each,
generated via BOTH serving paths.

Does NOT edit ../genskin.py. Imports it read-only (importlib, same pattern as driftbisect/
driftbisect2 use for extract12.py) and drives its REAL main() — the exact current production
prompt-assembly code (the ~150-line block in main()) runs completely unmodified for BOTH
paths — by runtime-monkeypatching two module attributes for the duration of THIS process only
(never written to genskin.py's file on disk, never touching the shared checkout's module):
  * genskin.HERE         -> this dir, so main()'s OUT=(HERE, f"assets-{sid}") lands under
                             servingbisect/, never the shared assets-<theme>/ dirs.
  * genskin.PAINT_VERTEX -> True for the vertex arm, False for the fal arm. main() reads this
                             module-global at CALL time (not bind time), so toggling it right
                             before each main() call routes that one generation down
                             edit_vertex() [direct Vertex AI] or edit()+upload() [fal's wrapper,
                             MODEL = fal-ai/gemini-3-pro-image-preview/edit — the pre-switch
                             path] with everything else (prompt, blueprint, seed) identical.

Same seed -> same pick_blueprint_arm(seed) draw (deterministic off the seed alone) -> both
paths get the same solid/outline blueprint-conditioning arm for a given (theme, seed), so
serving-path is the only thing varying within each seed pair.

Two themes (fallout-pipboy, steam-porthole — the true regressors per the roster audit), two
seeds each (current production seed + one more), both paths => 8 gens.
SEQUENTIAL, never parallel — the Vertex 429-quota lesson baked into genskin.py's own
edit_vertex() retry comment (a burst of concurrent Vertex calls burned a whole orchestrate12
roll to RESOURCE_EXHAUSTED on 2026-07-11 with zero real generations).

Usage: python3 gen_pair.py                                    # all 8 jobs
       python3 gen_pair.py --only fallout-pipboy:571:vertex    # single job (retry helper)
"""
import os, sys, json, time, importlib.util, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)

_spec = importlib.util.spec_from_file_location("genskin", os.path.join(GEN12, "genskin.py"))
genskin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(genskin)
# runtime-only override (this process's imported module object) — genskin.py on disk is untouched.
genskin.HERE = HERE

THEMES = {
    "fallout-pipboy": [571, 671],   # 571 = current production seed (assets-fallout-pipboy/results.json)
    "steam-porthole": [623, 723],   # 623 = current production seed (assets-steam-porthole/results.json)
}
PATHS = ["vertex", "fal"]


def job_id(theme, seed, path):
    return f"{theme}-{path}-{seed}"


def run_job(theme, seed, path):
    sid = job_id(theme, seed, path)
    out_dir = os.path.join(HERE, f"assets-{sid}")
    if os.path.exists(os.path.join(out_dir, "paint.png")):
        print(f"[skip] {sid} already generated (paint.png exists)", flush=True)
        return
    base_spec = json.load(open(os.path.join(GEN12, "theme_specs", f"{theme}.json")))
    spec = dict(base_spec)
    spec["id"] = sid
    spec["seed"] = seed
    tmp_spec = os.path.join(HERE, f"_spec-{sid}.json")
    json.dump(spec, open(tmp_spec, "w"), indent=1)

    genskin.PAINT_VERTEX = (path == "vertex")
    sys.argv = ["genskin.py", tmp_spec]
    t0 = time.time()
    genskin.main()
    dt = time.time() - t0
    # record the serving path explicitly (genskin.py's own `model` field is always the fal MODEL
    # constant regardless of path — cosmetic mainline quirk, not something this bisect should
    # rely on to know which path ran; stamp it ourselves).
    res_path = os.path.join(out_dir, "results.json")
    res = json.load(open(res_path))
    res["serving_path"] = path
    res["theme"] = theme
    res["gen_seconds"] = round(dt, 1)
    json.dump(res, open(res_path, "w"), indent=1)
    print(f"[gen_pair] {sid} done in {dt:.0f}s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="theme:seed:path — run a single job instead of all 8")
    args = ap.parse_args()

    if args.only:
        theme, seed, path = args.only.split(":")
        jobs = [(theme, int(seed), path)]
    else:
        jobs = [(theme, seed, path) for theme, seeds in THEMES.items()
                 for seed in seeds for path in PATHS]

    t_start = time.time()
    for i, (theme, seed, path) in enumerate(jobs, 1):
        print(f"=== job {i}/{len(jobs)}: {theme} seed={seed} path={path} "
              f"[elapsed {time.time()-t_start:.0f}s] ===", flush=True)
        run_job(theme, seed, path)
    print(f"ALL {len(jobs)} JOBS DONE in {time.time()-t_start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
