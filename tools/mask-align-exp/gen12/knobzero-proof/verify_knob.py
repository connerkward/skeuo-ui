#!/usr/bin/env python3
"""verify_knob.py — the deterministic, non-circular render-side half of the knob-zero closed
loop. Breaks the circularity the user caught (2026-07-11, second overrule): the PRIOR verifier
re-ran the SAME gradient-magnitude peak detector on both the extraction-time measurement (which
sets knob_zero_deg, i.e. how far the cap gets counter-rotated) and the render-time "check" -- so
a systematic edge-vs-centroid bias present in both cancelled out and the loop reported <=1deg
error while a human eye saw the mark visibly off 12 o'clock (verify-rule Sec.2, circular
validation).

This version measures the render TWICE, from two physically DIFFERENT signals:
  1. PRIMARY (matches the pipeline): knob_angle.detect_from_render_crop -- gradient-magnitude
     run-centroid, the same method (now fixed) that extract12.py uses at extraction time.
  2. INDEPENDENT (the actual break in circularity): knob_angle.detect_texture_from_render_crop
     -- local-standard-deviation ("texture disruption") run-centroid. A carved notch's outline
     disrupts the otherwise smooth radially-symmetric conic-brushed texture, so its angular bin
     has much higher local pixel-value variance than a bin sampling only smooth material. This
     is a different physical channel (intensity VARIANCE, not gradient magnitude) computed by
     different code, so it does not share the gradient detector's edge-bias or any of its
     specific failure modes. Two independently-computed signals agreeing is real evidence; one
     detector agreeing with itself is not. (An earlier attempt used mean inverted luminance --
     "a notch is a dark depression" -- but was empirically too weak on real render crops; see
     knob_angle.py's docstring for the measured numbers that ruled it out.)

Also runs a third, purely-structural check independent of BOTH centroid computations:
run_straddles() on the gradient detector's own contiguous anomalous run -- does the run of bins
that were flagged as anomalous actually CONTAIN 0deg (12 o'clock), not just does its weighted
mean land near 0. A run whose centroid happens to average near the target while not actually
covering it would be a red flag this catches that a bare "|angle|<=3" check would miss.

ACCEPTANCE BAR: <=3deg render error, measured by the INDEPENDENT (luminance-dip) signal -- not
the gradient signal the pipeline itself uses to set knob_zero_deg. Reports both signals plus
their mutual agreement so a human can see whether they corroborate or diverge.

Usage: python3 verify_knob.py <player_base_url> [skin_id ...]
  e.g. python3 verify_knob.py http://localhost:54350 steam-porthole ps1-crunchy ...
  (defaults to the 6-skin knob-zero batch when no skin ids given)
Requires: node + playwright resolvable from gen12/ (root repo node_modules), the target skins'
player.html already rebuilt from the current regions.json (run build_player.py first).
"""
import os, sys, json, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
sys.path.insert(0, GEN12)
from knob_angle import detect_from_render_crop, detect_texture_from_render_crop, angular_error, run_straddles

DEFAULT_SKINS = ["steam-porthole", "ps1-crunchy", "myst-arcanum", "fallout-vault", "fa-pod", "n64-cutscene"]
BAR_DEG = 3.0


def render_crops(base_url, sid):
    url = f"{base_url}/assets-{sid}/player.html"
    r = subprocess.run(["node", os.path.join(HERE, "render_knob.mjs"), url, HERE, sid],
                        capture_output=True, text=True, cwd=GEN12, timeout=60)
    if r.returncode != 0:
        print(f"[render] {sid} FAILED: {r.stderr[-2000:]}", file=sys.stderr)
        return False
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        out = {"raw": r.stdout}
    if out.get("error"):
        print(f"[render] {sid} error: {out['error']}", file=sys.stderr)
        return False
    return True


def measure(sid):
    init_png = os.path.join(HERE, f"{sid}-live-init.png")
    if not os.path.exists(init_png):
        return {"sid": sid, "error": "no-render"}
    g_angle, g_info, g_geo, g_run = detect_from_render_crop(init_png)
    d_angle, d_info, d_run = detect_texture_from_render_crop(init_png)
    g_err = angular_error(g_angle, 0.0)
    d_err = angular_error(d_angle, 0.0)
    straddle = run_straddles(g_run[0], g_run[1], 0.0) if g_run else None
    agree = angular_error(g_angle, d_angle) if (g_angle is not None and d_angle is not None) else None
    verdict = "PASS" if (d_err is not None and d_err <= BAR_DEG) else ("NO-SIGNAL" if d_err is None else "FAIL")
    return {
        "sid": sid,
        "gradient_deg": None if g_angle is None else round(g_angle, 2),
        "gradient_err_deg": None if g_err is None else round(g_err, 2),
        "gradient_info": g_info,
        "gradient_run_straddles_0deg": straddle,
        "independent_texture_disruption_deg": None if d_angle is None else round(d_angle, 2),
        "independent_err_deg": None if d_err is None else round(d_err, 2),
        "independent_info": d_info,
        "signals_agree_deg": None if agree is None else round(agree, 2),
        "verdict": verdict,
    }


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    base_url = args[0].rstrip("/")
    skins = args[1:] if len(args) > 1 else DEFAULT_SKINS
    results = []
    for sid in skins:
        print(f"=== {sid} ===")
        ok = render_crops(base_url, sid)
        if not ok:
            results.append({"sid": sid, "error": "render-failed"})
            continue
        m = measure(sid)
        results.append(m)
        print(json.dumps(m, indent=2))
    out_path = os.path.join(HERE, "verify_results.json")
    json.dump({"bar_deg": BAR_DEG, "signal": "independent = texture-disruption (local-std) run centroid (knob_angle.detect_texture_from_render_crop); gradient = primary pipeline signal, shown for comparison only, NOT the pass bar", "results": results},
              open(out_path, "w"), indent=2)
    print(f"\nwrote {out_path}")
    n_pass = sum(1 for r in results if r.get("verdict") == "PASS")
    print(f"{n_pass}/{len(results)} PASS (independent signal, <= {BAR_DEG} deg)")


if __name__ == "__main__":
    main()
