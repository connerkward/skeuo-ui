#!/usr/bin/env python3
"""driftbisect2 — extraction-commit bisect readout.

Fixes PAINT at the CURRENT committed generation (paint.png/mask.png as they exist
on origin/main today) and swaps ONLY the extractor: 794da20e's extract12.py (the
version whose output produced the low-drift baseline numbers in roster_audit.json)
vs origin/main's extract12.py (today's extractor, whose output produced the live
high-drift numbers). Same paint, same mask, same template, same drift_table() code
(imported from twoimg/roster_audit.py, not reimplemented) -> any difference between
the old-extractor and current-extractor readings on the SAME paint is attributable
ONLY to the extraction algorithm.

This is the substitute for the originally-specified "old paint x current extractor"
cell, which turned out to be unrecoverable (see README.md in this dir for the full
recovery-attempt log: every templated-passing skin's original 794da20e-seed paint.png
was gitignored and silently overwritten by a later reroll before ever being committed
or backed up to Drive -- confirmed by seed mismatch across ALL SIX templated-passing
skins between 794da20e and the first paint-committing commit 39d76200).
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "twoimg"))
from roster_audit import drift_table  # imported, not reimplemented (verify-outputs-rule)

HERE = os.path.dirname(os.path.abspath(__file__))
SKINS = ["fallout-pipboy", "steam-porthole", "fa-pod"]

# (a) old paint x old extractor -- from roster_audit.json's historical_oldest (already computed,
#     796da20e regions.json x 794da20e's own extract12.py, on the ORIGINAL seed's own paint dims)
# (b) new paint x current extractor -- from roster_audit.json's live (already computed)
AUDIT = json.load(open(os.path.join(HERE, "..", "twoimg", "roster_audit.json")))
hist_by_id = {h["id"]: h for h in AUDIT["historical_oldest"]}
live_by_id = {l["id"]: l for l in AUDIT["live"]}


def load(path):
    return json.load(open(path))


def measure(run_dir):
    regs_doc = load(os.path.join(run_dir, "regions.json"))
    res = load(os.path.join(run_dir, "results.json"))
    template = regs_doc.get("template") or res.get("template") or {}
    regs = regs_doc.get("regions", {})
    from PIL import Image
    W, H = Image.open(os.path.join(run_dir, "paint.png")).size
    dt = drift_table(template, regs, W, H)
    vals = {k: v[0] for k, v in dt.items()}
    mean = sum(vals.values()) / len(vals) if vals else None
    worst = max(vals.items(), key=lambda kv: kv[1]) if vals else (None, None)
    # fromTemplate fallback = the extractor couldn't cut/detect that control at all and fell
    # back to the AUTHORED template position verbatim -> trivially 0 drift (not a real
    # measurement). Flag + report a fallback-excluded mean alongside the raw one so a fallback
    # doesn't artificially deflate an extractor's apparent drift.
    fallback = [k for k, r in regs.items() if r.get("fromTemplate")]
    vals_excl = {k: v for k, v in vals.items() if k not in fallback}
    mean_excl = sum(vals_excl.values()) / len(vals_excl) if vals_excl else mean
    return {"mean_drift_px": round(mean, 1) if mean is not None else None,
            "n": len(vals), "per_control_px": {k: round(v, 1) for k, v in vals.items()},
            "worst_control": worst[0], "worst_px": round(worst[1], 1) if worst[1] is not None else None,
            "dims": [W, H], "fallback_controls": fallback,
            "mean_drift_px_excl_fallback": round(mean_excl, 1) if vals_excl else None}


out = {"note": __doc__, "skins": {}}
hdr_a = "(a) old paint x old extr"
hdr_c = "(c') new paint x OLD extr"
hdr_b = "(b) new paint x CURRENT extr"
print(f"{'skin':16} {hdr_a:>26} {hdr_c:>28} {hdr_b:>30}  verdict")
for sid in SKINS:
    a = hist_by_id.get(sid, {})
    b = live_by_id.get(sid, {})
    c = measure(os.path.join(HERE, f"assets-{sid}-old"))
    d = measure(os.path.join(HERE, f"assets-{sid}-cur"))  # sanity: should match (b) closely
    a_mean = a.get("mean_drift_px")
    b_mean = b.get("mean_drift_px")
    # use the fallback-excluded mean for the OLD extractor so a detection-miss (which trivially
    # reads 0 drift by falling back to the template) can't artificially deflate its apparent
    # accuracy and bias the verdict toward "detector-driven"
    c_mean = c["mean_drift_px_excl_fallback"]
    d_mean = d["mean_drift_px_excl_fallback"]
    # verdict: does swapping ONLY the extractor (c vs d, same paint) reproduce the a->b jump?
    swap_delta = round(d_mean - c_mean, 1) if (c_mean is not None and d_mean is not None) else None
    audit_delta = round(b_mean - a_mean, 1) if (a_mean is not None and b_mean is not None) else None
    if swap_delta is not None and abs(swap_delta) > 150 and swap_delta > 0:
        verdict = "DETECTOR-DRIVEN (old extractor reads low on today's paint; current extractor reads high on the SAME paint)"
    elif swap_delta is not None and abs(swap_delta) <= 150:
        verdict = "PAINT-DRIVEN (extractor swap on identical paint changes drift <150px noise floor; both read high)"
    else:
        verdict = "AMBIGUOUS"
    print(f"{sid:16} {a_mean!s:>26} {c_mean!s:>28} {b_mean!s:>30}  {verdict}  (fallback-excl means; swap_delta={swap_delta})")
    out["skins"][sid] = {
        "a_old_paint_old_extractor__from_roster_audit_historical": a,
        "c_new_paint_OLD_extractor__NEW_this_run": c,
        "d_new_paint_current_extractor__sanity_replication_of_live": d,
        "b_new_paint_current_extractor__from_roster_audit_live": b,
        "swap_delta_px__d_minus_c__extractor_only": swap_delta,
        "audit_delta_px__b_minus_a__paint_and_extractor_both_changed": audit_delta,
        "live_vs_replication_agreement_px": round(d_mean - b_mean, 1) if (d_mean is not None and b_mean is not None) else None,
        "verdict": verdict,
    }

json.dump(out, open(os.path.join(HERE, "results.json"), "w"), indent=2)
print("\n-> results.json written")
