#!/usr/bin/env python3
"""roster_audit — $0 template-adherence audit over the EXISTING gen12 roster (Task 2,
2026-07-10). No new generations. Answers the user's complaint ("paint step is just not
following the template at all anymore, even in the controls — all the controls had colour
contamination") from data already on disk plus git history — read-only against
../assets-*/ (mainline gen12 roster), writes only inside twoimg/.

What it computes, per skin:
  - per-control DRIFT (px) = distance between the authored template centre (results.json's
    `template`, fractional, baked at generation time) and the DETECTED device centre
    (regions.json's `regions.<name>.device` bbox centre, extract12's own snapped/drift-
    corrected estimate) on the skin's real paint.png pixel grid.
  - per-control CONTAMINATION % = the exact perimeter-band hue-distance bleed-ring metric
    from score_twoimg.py (bleed_ring_pct), reused verbatim so this skin-level number is
    directly comparable to the twoimg experiment's own numbers, not a bespoke reinvention.

Scope: the 13 skins that auto-PASS extract12's gate today, filtered to the ones the drift
metric is even meaningful for — TEMPLATED mode only (a templateless skin has no authored
`template` to drift against). Reports the actual mode breakdown plainly rather than
assuming the user's "13" figure was all-templated.

Historical comparison ($0, git-history only): for each templated-passing skin, diff the
OLDEST commit that touched its regions.json (794da20e, the original 14-skin batch) against
the CURRENT committed state, on the fraction-drift metric only (contamination needs the
historical paint.png pixels; out of scope for this $0 pass — see docstring note in the
output).

Usage: python3 roster_audit.py   (no args) -> writes twoimg/roster_audit.json
"""
import os, sys, json, subprocess, colorsys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))  # .../skeuo-ui

OLDEST_COMMIT = "794da20e"  # first 14-skin themed batch — common ancestor for all 6 below

# From a live gate sweep (2026-07-10) over every assets-* under gen12/ (excluding _biref/_pbr
# sidecars): 15 skins total, 13 PASS, 2 FAIL (fa-sky: emptiness; ps1-wild: region-misplaced +
# emptiness + state-align). Of the 13 PASSING, only 6 are TEMPLATED mode — the other 7 are
# templateless (freeform) and have no authored `template` to drift against, so the
# adherence-audit set is the intersection, not all 13.
ALL_SKINS_GATE = {
    "claymation": ("templateless", True), "diablo-gothic": ("templateless", True),
    "fa-pod": ("templated", True), "fa-sky": ("templateless", False),
    "fallout-pipboy": ("templated", True), "fallout-vault": ("templateless", True),
    "myst-arcanum": ("templateless", True), "n64-cutscene": ("templateless", True),
    "n64-prerender-character": ("templateless", True), "ps1-crunchy": ("templated", True),
    "ps1-wild": ("templateless", False), "steam-porthole": ("templated", True),
    "wc-goldshield": ("templated", True), "wmp-quicksilver": ("templated", True),
    "wmp-vario": ("templateless", True),
}
TEMPLATED_PASSING = sorted(k for k, (m, p) in ALL_SKINS_GATE.items() if m == "templated" and p)

BAND_FRAC, HUE_TOL, SAT_FLOOR, VAL_FLOOR = 0.14, 16, 60, 70  # identical to score_twoimg.py


def bleed_ring_pct(paint_hsv, bbox, key_rgb, W, H):
    """Verbatim copy of score_twoimg.py's metric (not re-derived) so numbers are comparable."""
    x, y, w, h = bbox
    mx, my = w * BAND_FRAC, h * BAND_FRAC
    ox0, oy0 = max(0.0, x - mx), max(0.0, y - my)
    ox1, oy1 = min(1.0, x + w + mx), min(1.0, y + h + my)
    X0, Y0, X1, Y1 = int(ox0 * W), int(oy0 * H), int(ox1 * W), int(oy1 * H)
    if X1 <= X0 or Y1 <= Y0: return 0.0
    win = paint_hsv[Y0:Y1, X0:X1]
    ix0, iy0 = int((x - ox0) * W) if x >= ox0 else 0, int((y - oy0) * H) if y >= oy0 else 0
    ix1, iy1 = int((x + w - ox0) * W), int((y + h - oy0) * H)
    interior = np.zeros(win.shape[:2], dtype=bool)
    interior[max(0, iy0):max(0, iy1), max(0, ix0):max(0, ix1)] = True
    band = ~interior
    kh = int(colorsys.rgb_to_hsv(*[v / 255 for v in key_rgb])[0] * 255)
    hd = np.minimum(np.abs(win[..., 0].astype(int) - kh), 255 - np.abs(win[..., 0].astype(int) - kh))
    hit = band & (hd < HUE_TOL) & (win[..., 1] > SAT_FLOOR) & (win[..., 2] > VAL_FLOOR)
    n_band = int(band.sum())
    return 100.0 * int(hit.sum()) / n_band if n_band else 0.0


def drift_table(template, regs, W, H):
    """{control: (drift_px, dx_px, dy_px)} from template centre vs detected device centre."""
    out = {}
    for k, t in template.items():
        dev = (regs.get(k) or {}).get("device")
        if not dev:
            continue
        cx, cy = dev[0] + dev[2] / 2, dev[1] + dev[3] / 2
        dxp, dyp = (cx - t[0]) * W, (cy - t[1]) * H
        out[k] = (float((dxp ** 2 + dyp ** 2) ** 0.5), float(dxp), float(dyp))
    return out


def audit_live(sid):
    d = os.path.join(GEN12, f"assets-{sid}")
    regions = json.load(open(os.path.join(d, "regions.json")))
    results = json.load(open(os.path.join(d, "results.json")))
    template = regions.get("template") or results.get("template") or {}
    regs = regions.get("regions", {})
    paint = Image.open(os.path.join(d, "paint.png")).convert("RGB")
    W, H = paint.size
    paint_hsv = np.asarray(paint.convert("HSV")).astype(int)
    KEYS = {k: tuple(v) for k, v in (results.get("keys") or {}).items()}

    dt = drift_table(template, regs, W, H)
    contam = {}
    for name, key in KEYS.items():
        bbox = (regs.get(name) or {}).get("device")
        if not bbox:
            continue
        contam[name] = round(bleed_ring_pct(paint_hsv, bbox, key, W, H), 4)

    drift_px_vals = {k: v[0] for k, v in dt.items()}
    mean_drift = float(np.mean(list(drift_px_vals.values()))) if drift_px_vals else None
    max_ctrl = max(drift_px_vals.items(), key=lambda kv: kv[1]) if drift_px_vals else (None, None)
    mean_contam = float(np.mean(list(contam.values()))) if contam else None
    max_contam_ctrl = max(contam.items(), key=lambda kv: kv[1]) if contam else (None, None)

    return {
        "id": sid, "dims": [W, H], "n_controls": len(dt),
        "mean_drift_px": round(mean_drift, 1) if mean_drift is not None else None,
        "max_drift_control": max_ctrl[0], "max_drift_px": round(max_ctrl[1], 1) if max_ctrl[1] is not None else None,
        "mean_contam_pct": round(mean_contam, 3) if mean_contam is not None else None,
        "max_contam_control": max_contam_ctrl[0],
        "max_contam_pct": round(max_contam_ctrl[1], 3) if max_contam_ctrl[1] is not None else None,
        "gate_pass": regions.get("gate", {}).get("PASS"),
        "per_control_drift_px": {k: round(v[0], 1) for k, v in dt.items()},
        "per_control_contam_pct": contam,
    }


def git_show_json(commit, relpath):
    p = subprocess.run(["git", "-C", REPO, "show", f"{commit}:{relpath}"], capture_output=True, text=True)
    if p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return None


def audit_historical(sid):
    rel_regions = f"tools/mask-align-exp/gen12/assets-{sid}/regions.json"
    rel_results = f"tools/mask-align-exp/gen12/assets-{sid}/results.json"
    regions = git_show_json(OLDEST_COMMIT, rel_regions)
    results = git_show_json(OLDEST_COMMIT, rel_results)
    if not regions or not results:
        return {"id": sid, "commit": OLDEST_COMMIT, "error": "not present at this commit"}
    template = regions.get("template") or results.get("template") or {}
    regs = regions.get("regions", {})
    dims = results.get("dims")  # [jointW, H] — paint.png is the LEFT half
    if not dims:
        return {"id": sid, "commit": OLDEST_COMMIT, "error": "no dims in historical results.json"}
    W, H = dims[0] // 2, dims[1]
    dt = drift_table(template, regs, W, H)
    drift_px_vals = {k: v[0] for k, v in dt.items()}
    mean_drift = float(np.mean(list(drift_px_vals.values()))) if drift_px_vals else None
    max_ctrl = max(drift_px_vals.items(), key=lambda kv: kv[1]) if drift_px_vals else (None, None)
    return {
        "id": sid, "commit": OLDEST_COMMIT, "seed": results.get("seed"), "dims": [W, H],
        "mean_drift_px": round(mean_drift, 1) if mean_drift is not None else None,
        "max_drift_control": max_ctrl[0], "max_drift_px": round(max_ctrl[1], 1) if max_ctrl[1] is not None else None,
        "per_control_drift_px": {k: round(v[0], 1) for k, v in dt.items()},
    }


def main():
    live = [audit_live(sid) for sid in TEMPLATED_PASSING]
    hist = [audit_historical(sid) for sid in TEMPLATED_PASSING]
    # pair live current-seed with historical for a plain degraded/improved/flat call
    deltas = []
    for L, H_ in zip(live, hist):
        if H_.get("mean_drift_px") is None or L.get("mean_drift_px") is None:
            continue
        deltas.append({"id": L["id"], "old_seed": H_.get("seed"), "old_mean_drift_px": H_["mean_drift_px"],
                        "new_mean_drift_px": L["mean_drift_px"],
                        "delta_px": round(L["mean_drift_px"] - H_["mean_drift_px"], 1)})

    out = {
        "note": ("$0 audit from EXISTING regions.json/results.json/paint.png + git history — "
                  "no new generations. mean_drift_px is the mean distance (px, on the skin's own "
                  "paint.png pixel grid) between each control's AUTHORED template centre and its "
                  "DETECTED device centre; mean_contam_pct is the twoimg experiment's own "
                  "perimeter-band hue-bleed metric (score_twoimg.bleed_ring_pct), reused verbatim, "
                  "measuring guide-colour residue around each control's own bbox."),
        "gate_sweep_15_skins": {k: {"mode": m, "pass": p} for k, (m, p) in ALL_SKINS_GATE.items()},
        "n_pass": sum(1 for _, p in ALL_SKINS_GATE.values() if p),
        "n_templated_passing": len(TEMPLATED_PASSING),
        "templated_passing_ids": TEMPLATED_PASSING,
        "live": live,
        "historical_oldest": hist,
        "oldest_vs_current_delta": deltas,
    }
    json.dump(out, open(os.path.join(HERE, "roster_audit.json"), "w"), indent=1)
    print(f"-> roster_audit.json  ({len(live)} templated-passing skins audited)")
    for L in live:
        print(f"  {L['id']:16} mean_drift={L['mean_drift_px']:>6.1f}px  max_drift={L['max_drift_control']}"
              f"({L['max_drift_px']}px)  mean_contam={L['mean_contam_pct']}%  worst_contam="
              f"{L['max_contam_control']}({L['max_contam_pct']}%)")
    for d in deltas:
        print(f"  [history] {d['id']:16} seed {d['old_seed']}->current  drift {d['old_mean_drift_px']}px -> "
              f"{d['new_mean_drift_px']}px  (delta {d['delta_px']:+.1f}px)")


if __name__ == "__main__":
    main()
