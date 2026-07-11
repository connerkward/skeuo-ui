#!/usr/bin/env python3
"""score_bisect — compute the SAME drift metric roster_audit.py uses (per-control distance
between the authored template centre and extract12's detected device centre), over the 12
drift-clause-bisect generations, grouped by (theme, seed, arm).

Imports drift_table() from ../twoimg/roster_audit.py (read-only import, not duplicated) so
this experiment's numbers are directly comparable to the roster audit's own — same metric,
same code, different inputs. Does not edit roster_audit.py.

Usage: python3 score_bisect.py   (no args) -> writes bisect_scores.json
"""
import os, sys, json, importlib.util
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)

_spec = importlib.util.spec_from_file_location("roster_audit", os.path.join(GEN12, "twoimg", "roster_audit.py"))
roster_audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(roster_audit)
drift_table = roster_audit.drift_table

from run_manifest import THEMES, ARMS

NOISE_FLOOR_PX = 150  # per docs/design/2026-07-11-think-about-notes.md §3: two skins moved
                        # -82/-99px under an IDENTICAL pipeline with no prompt change — a
                        # regression/improvement below ~100-150px is not distinguishable from
                        # run-to-run variance. We use the conservative (higher) end, 150px, as
                        # the "clears the floor" bar per the note's decision rule.


def score_one(sid, seed, arm):
    d = os.path.join(HERE, f"assets-bisect-{sid}-{arm.lower()}-{seed}")
    rj, resj = os.path.join(d, "regions.json"), os.path.join(d, "results.json")
    if not (os.path.exists(rj) and os.path.exists(resj)):
        return {"id": sid, "seed": seed, "arm": arm, "error": "missing regions.json/results.json"}
    regions = json.load(open(rj)); results = json.load(open(resj))
    template = regions.get("template") or results.get("template") or {}
    regs = regions.get("regions", {})
    paint = Image.open(os.path.join(d, "paint.png")).convert("RGB")
    W, H = paint.size
    dt = drift_table(template, regs, W, H)
    drift_px_vals = {k: v[0] for k, v in dt.items()}
    mean_drift = float(np.mean(list(drift_px_vals.values()))) if drift_px_vals else None
    max_ctrl = max(drift_px_vals.items(), key=lambda kv: kv[1]) if drift_px_vals else (None, None)
    gate = regions.get("gate", {})
    return {
        "id": sid, "seed": seed, "arm": arm, "dims": [W, H], "n_controls": len(dt),
        "mean_drift_px": round(mean_drift, 1) if mean_drift is not None else None,
        "max_drift_control": max_ctrl[0],
        "max_drift_px": round(max_ctrl[1], 1) if max_ctrl[1] is not None else None,
        "per_control_drift_px": {k: round(v[0], 1) for k, v in dt.items()},
        "gate_pass": gate.get("PASS"), "gate_reasons": gate.get("reasons"),
        "leak": results.get("leak"),
    }


def main():
    runs = []
    for sid, (spec_path, seeds) in THEMES.items():
        for seed in seeds:
            for arm in ARMS:
                runs.append(score_one(sid, seed, arm))

    # per-arm aggregate (mean of per-gen mean_drift_px, across all 4 gens/arm)
    by_arm = {}
    for arm in ARMS:
        vals = [r["mean_drift_px"] for r in runs if r["arm"] == arm and r.get("mean_drift_px") is not None]
        by_arm[arm] = {
            "n": len(vals), "mean_of_means_px": round(float(np.mean(vals)), 1) if vals else None,
            "values": vals,
        }
    # per-theme, per-arm (mean across the 2 seeds)
    by_theme_arm = {}
    for sid in THEMES:
        by_theme_arm[sid] = {}
        for arm in ARMS:
            vals = [r["mean_drift_px"] for r in runs if r["id"] == sid and r["arm"] == arm and r.get("mean_drift_px") is not None]
            by_theme_arm[sid][arm] = round(float(np.mean(vals)), 1) if vals else None

    # decision-rule deltas vs A (baseline), per theme — does B or C clear the noise floor?
    deltas = {}
    for sid in THEMES:
        base = by_theme_arm[sid].get("A")
        deltas[sid] = {}
        for arm in ("B", "C"):
            v = by_theme_arm[sid].get(arm)
            if base is None or v is None:
                deltas[sid][arm] = None
                continue
            deltas[sid][arm] = round(base - v, 1)   # positive = arm reduced drift vs A

    clears_floor = {}
    for arm in ("B", "C"):
        both_clear = all(
            (deltas[sid].get(arm) is not None and deltas[sid][arm] > NOISE_FLOOR_PX)
            for sid in THEMES
        )
        any_clear = any(
            (deltas[sid].get(arm) is not None and deltas[sid][arm] > NOISE_FLOOR_PX)
            for sid in THEMES
        )
        clears_floor[arm] = {"both_themes": both_clear, "any_theme": any_clear,
                              "per_theme_delta_px": {sid: deltas[sid].get(arm) for sid in THEMES}}

    out = {
        "note": ("mean_drift_px per gen = mean over controls of |authored-template-centre - "
                 "extract12-detected-device-centre| in px, IDENTICAL metric/code to "
                 "twoimg/roster_audit.py's drift_table(). noise_floor_px is the conservative "
                 "150px bar from docs/design/2026-07-11-think-about-notes.md §3 (two skins "
                 "moved -82/-99px under an unchanged pipeline with no prompt change -- a "
                 "regression/improvement below ~150px is not distinguishable from run-to-run "
                 "variance)."),
        "noise_floor_px": NOISE_FLOOR_PX,
        "runs": runs,
        "by_arm": by_arm,
        "by_theme_arm": by_theme_arm,
        "delta_vs_A_px": deltas,
        "clears_noise_floor": clears_floor,
    }
    json.dump(out, open(os.path.join(HERE, "bisect_scores.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
