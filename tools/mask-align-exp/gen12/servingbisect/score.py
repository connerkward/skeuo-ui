#!/usr/bin/env python3
"""servingbisect/score.py — serving-path bisect readout.

Same production prompt, same theme, same seed -> only the SERVING PATH varies (Vertex direct
vs fal's wrapper). Imports drift_table() from twoimg/roster_audit.py (not reimplemented, per
verify-outputs-rule) so the metric is byte-identical to the live roster audit and the two prior
bisects in this chain. Same-seed cross-path comparison is the key readout: if fal-served paints
drift meaningfully less than Vertex-served paints at the SAME seed/prompt, the serving path is
the driver; if the two are within noise, the driver is elsewhere (seed range / aggregate prompt
churn).

Noise floor: 150px, carried forward from the drift-clause bisect (docs/experiments/
2026-07-11-drift-clause-bisect.md) — established from that bisect's own Arm A/B/C run-to-run
variance at fixed prompt. n=2 seeds/theme/path: directional evidence, not significance.
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "twoimg"))
from roster_audit import drift_table  # imported, not reimplemented

HERE = os.path.dirname(os.path.abspath(__file__))
NOISE_FLOOR_PX = 150

THEMES = {
    "fallout-pipboy": [571, 671],
    "steam-porthole": [623, 723],
}
PATHS = ["vertex", "fal"]


def measure(run_dir):
    regs_p = os.path.join(run_dir, "regions.json")
    res_p = os.path.join(run_dir, "results.json")
    if not (os.path.exists(regs_p) and os.path.exists(res_p)):
        return {"error": "missing regions.json/results.json"}
    regs_doc = json.load(open(regs_p))
    res = json.load(open(res_p))
    template = regs_doc.get("template") or res.get("template") or {}
    regs = regs_doc.get("regions", {})
    from PIL import Image
    W, H = Image.open(os.path.join(run_dir, "paint.png")).size
    dt = drift_table(template, regs, W, H)
    vals = {k: v[0] for k, v in dt.items()}
    fallback = [k for k, r in regs.items() if r.get("fromTemplate")]
    vals_excl = {k: v for k, v in vals.items() if k not in fallback}
    mean = sum(vals.values()) / len(vals) if vals else None
    mean_excl = sum(vals_excl.values()) / len(vals_excl) if vals_excl else mean
    worst = max(vals.items(), key=lambda kv: kv[1]) if vals else (None, None)
    gate = regs_doc.get("gate", {})
    return {
        "mean_drift_px": round(mean, 1) if mean is not None else None,
        "mean_drift_px_excl_fallback": round(mean_excl, 1) if mean_excl is not None else None,
        "n_controls": len(vals),
        "fallback_controls": fallback,
        "worst_control": worst[0],
        "worst_px": round(worst[1], 1) if worst[1] is not None else None,
        "per_control_px": {k: round(v, 1) for k, v in vals.items()},
        "gate_pass": gate.get("PASS"),
        "gate_reasons": gate.get("reasons", []),
        "serving_path": res.get("serving_path"),
        "seed": res.get("seed"),
        "gen_seconds": res.get("gen_seconds"),
        "blueprint_conditioning": res.get("blueprint_conditioning"),
        "dims": [W, H],
    }


def main():
    out = {"note": __doc__, "noise_floor_px": NOISE_FLOOR_PX, "runs": {}}
    print(f"{'theme':16} {'seed':>6}  {'vertex px':>12}  {'fal px':>12}  {'Δ (vertex-fal)':>16}  verdict")
    pooled = {"vertex": [], "fal": []}
    for theme, seeds in THEMES.items():
        for seed in seeds:
            row = {}
            for path in PATHS:
                sid = f"{theme}-{path}-{seed}"
                run_dir = os.path.join(HERE, f"assets-{sid}")
                m = measure(run_dir)
                row[path] = m
                out["runs"][sid] = m
                if m.get("mean_drift_px_excl_fallback") is not None:
                    pooled[path].append(m["mean_drift_px_excl_fallback"])
            v = row["vertex"].get("mean_drift_px_excl_fallback")
            f = row["fal"].get("mean_drift_px_excl_fallback")
            delta = round(v - f, 1) if (v is not None and f is not None) else None
            if delta is None:
                verdict = "INCOMPLETE"
            elif abs(delta) <= NOISE_FLOOR_PX:
                verdict = "WITHIN NOISE FLOOR (serving path not the driver at this seed)"
            elif delta > NOISE_FLOOR_PX:
                verdict = "VERTEX DRIFTS MORE (serving-path suspect supported)"
            else:
                verdict = "FAL DRIFTS MORE (unexpected direction)"
            print(f"{theme:16} {seed:>6}  {v!s:>12}  {f!s:>12}  {delta!s:>16}  {verdict}")
            out["runs"][f"{theme}-{seed}-verdict"] = verdict

    pooled_summary = {}
    for path in PATHS:
        vals = pooled[path]
        pooled_summary[path] = {
            "n": len(vals),
            "mean_px": round(sum(vals) / len(vals), 1) if vals else None,
            "vals": vals,
        }
    pooled_delta = None
    if pooled_summary["vertex"]["mean_px"] is not None and pooled_summary["fal"]["mean_px"] is not None:
        pooled_delta = round(pooled_summary["vertex"]["mean_px"] - pooled_summary["fal"]["mean_px"], 1)
    out["pooled"] = {**pooled_summary, "pooled_delta_vertex_minus_fal_px": pooled_delta}
    print(f"\npooled (n={pooled_summary['vertex']['n']}/{pooled_summary['fal']['n']}): "
          f"vertex={pooled_summary['vertex']['mean_px']}px  fal={pooled_summary['fal']['mean_px']}px  "
          f"Δ={pooled_delta}px  (noise floor {NOISE_FLOOR_PX}px)")

    json.dump(out, open(os.path.join(HERE, "results.json"), "w"), indent=2)
    print("\n-> results.json written")


if __name__ == "__main__":
    main()
