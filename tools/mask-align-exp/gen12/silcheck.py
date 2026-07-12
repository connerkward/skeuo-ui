#!/usr/bin/env python3
"""silcheck — deterministic silhouette-match check for baked icon buttons (gen12).

Built per the verification-recalibration lane's finding: VLMs scored 0% recall on
silhouette-mismatch defects (fa-sky/myst-arcanum/steam-porthole/wmp-quicksilver, human
review round1, review-2026-07-11-round1.json) -- a genuine shape-judgment blindness a VLM
cannot see reliably. The fix is geometric, not another model call.

WHAT IT CATCHES (regardless of upstream cause -- misassigned blob, snap-to-paint drift, or
a genuinely degenerate/fragmented mask blob): does the button's OWN painted silhouette sit
INSIDE and FILL the `device` bbox that build_player.py's press-overlay positioning uses? If
the silhouette is off-center, spills outside the box, or barely fills it, the press
depression drawn in the player will visibly not match the button -- the defect class named
in the human review.

GATING METHOD + two NON-gating diagnostics (see CALIBRATION NOTES at the bottom for the full
trail -- what was tried, what was dropped, and why):

  METHOD A ("maskKey", GATES THE VERDICT) -- verbatim port of build_player.py's ink-
    silhouette extraction (lines ~414-433). Crops mask.png around the button's `maskDevice`
    bbox (10% pad), colour-keys against `keys[<button>]` (squared-dist < 7000 -- same
    constant), and compares the resulting silhouette's tight bbox/centroid to `device`.
    Ground truth for "does the press overlay's own build path actually find a coherent,
    well-placed blob." Catches: coverage collapse (no matching-colour blob at all -- a
    fragmented/degenerate mask region) and gross misassignment. Zero false positives across
    the full 15-skin roster except one genuine finding (fa-pod/prev, see notes below). MISS:
    this is anchored to `maskDevice`, which is the SAME upstream detection `device` is snap-
    corrected from -- if the true painted button sits further from BOTH maskDevice and device
    than snap_to_paint's capped x-shift reaches, this method still finds a self-consistent
    "blob near where it expected one" and passes (the verify-outputs-rule circularity trap:
    validating a detector's box against that same detector's own upstream signal).

  DIAGNOSTIC, non-gating -- "paintVividnessAdvisory": ported from extract12.py's OWN paint-
    based icon-detection heuristic (`snap_to_paint`, `sel = (mx - mn) > 60`, i.e. per-pixel
    colour-saturation vividness vs the surrounding material), extended to a full 2-D bbox/
    centroid/area, run independent of mask.png. PROTOTYPED AS A GATING SIGNAL AND DROPPED:
    it catches myst-arcanum's degenerate icon content (area_ratio 0.06-0.21 vs every healthy
    button's >=0.44) but the colour-saturation premise only holds for vivid/glossy icon
    styles -- on monochrome/engraved styles (diablo-gothic, fallout-pipboy, ps1-crunchy) it
    measured near-zero "vividness" on EVERY button, healthy or not, and would have failed
    those 3 entire unnamed skins outright. A signal that can't discriminate icon-from-
    material on a whole class of art style is worse than not having it (restraint-rule).
    Computed and recorded per button for human triage, never used to gate.

  DIAGNOSTIC, non-gating -- "circleFitAdvisory": ported from extract12.py's `circle_fit`
    (gradient-magnitude ring search, used there for knob sockets) as a 3rd, independent
    signal for round buttons. It DOES measure the one real defect Method A misses (fa-sky/
    playpause, confirmed by direct visual inspection -- see CALIBRATION NOTES) but produces
    comparable-magnitude noise on genuinely healthy buttons with a concentric two-tone bezel
    (outer chrome ring + inner glass disc -- the search can lock onto either ring; verified
    false-positive: fa-pod/queue measured the SAME offset magnitude as fa-sky's real defect).
    Reported per-button for human triage; deliberately NOT part of the verdict.

Metrics per button, in <assets-dir>/observe/silcheck.json (top-level fields are the
originally-specced {iou, offset_px, area_ratio, verdict}, all from the gating Method A; the
two diagnostics are nested alongside for anyone doing deeper triage):
  iou          -- IoU(silhouette tight bbox, device bbox), Method A.
  offset_px    -- centroid(silhouette) to centroid(device bbox), paint.png pixels, Method A.
  area_ratio   -- silhouette filled-pixel area (image-fraction units) / device bbox area,
                  Method A. Low => sliver/fragment even if roughly centered.
  coverage     -- filled-pixel fraction of the padded crop, Method A.
  verdict      -- PASS / FAIL / MISSING / NO-SILHOUETTE, from Method A alone.
  paintVividnessAdvisory -- non-gating diagnostic {iou, offset_px, area_ratio, coverage, verdict}.
  circleFitAdvisory      -- non-gating diagnostic {offset_px, offset_frac_diag, score}.

Usage:  python3 silcheck.py <assets-dir>              # one skin, prints + writes json
        python3 silcheck.py --all                     # every assets-* dir in cwd, + summary
        python3 silcheck.py --calibrate                # --all + compare vs human review labels
"""
import os, sys, json, glob
import numpy as np
from PIL import Image

# ---- Method A (maskKey) constants -- IDENTICAL to build_player.py's ink-silhouette path ----
PAD_A = 0.10                  # build_player.py's ink-crop pad
KEY_DIST2 = 7000              # build_player.py's colour-key squared-dist threshold
COV_FLOOR_A = 0.02            # build_player.py's "no blob found -> rounded-rect fallback" floor
IOU_FAIL_A = 0.30
OFFSET_FRAC_FAIL_A = 0.35
AREA_RATIO_FAIL_A = 0.05

# ---- Method B (paintVividness) constants -- ported from extract12.py's snap_to_paint ----
PAD_B = 0.10
VIVID_THRESH = 60             # extract12.py: `sel = (mx - mn) > 60`
VIVID_DISTRUST = 0.55         # extract12.py: `if sel.mean() > 0.55: return b` (no icon to snap)
AREA_RATIO_FAIL_B = 0.30      # calibrated: myst-arcanum's degenerate buttons measured
                               # 0.056-0.211; every healthy unnamed-skin button measured
                               # >=0.44 (15-skin sweep, 2026-07-12) -- wide margin either side.

# ---- Method C (circleFitAdvisory) constants -- ported from extract12.py's circle_fit ----
CIRCLEFIT_RNG = 0.3           # dx,dy search range as a fraction of r0
CIRCLEFIT_RLO, CIRCLEFIT_RHI = 0.85, 1.15


def _iou(a, b):
    ax0, ay0, ax1, ay1 = a[0], a[1], a[0] + a[2], a[1] + a[3]
    bx0, by0, bx1, by1 = b[0], b[1], b[0] + b[2], b[1] + b[3]
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def method_a_mask_key(mask, MW, MH, PW, PH, db, mb, key):
    """Port of build_player.py's ink-silhouette extraction (lines ~414-433), read-only."""
    crop = [mb[0] - mb[2] * PAD_A, mb[1] - mb[3] * PAD_A, mb[2] * (1 + 2 * PAD_A), mb[3] * (1 + 2 * PAD_A)]
    cx0 = max(0, int(round(crop[0] * MW))); cy0 = max(0, int(round(crop[1] * MH)))
    cx1 = min(MW, int(round((crop[0] + crop[2]) * MW))); cy1 = min(MH, int(round((crop[1] + crop[3]) * MH)))
    if cx1 <= cx0 or cy1 <= cy0:
        return {"verdict": "NO-SILHOUETTE", "reason": "empty-crop", "coverage": 0.0,
                "iou": 0.0, "offset_px": None, "area_ratio": 0.0}
    sub = mask[cy0:cy1, cx0:cx1].astype(int)
    d0 = sub[:, :, 0] - key[0]; d1 = sub[:, :, 1] - key[1]; d2 = sub[:, :, 2] - key[2]
    sel = (d0 * d0 + d1 * d1 + d2 * d2) < KEY_DIST2
    cw, ch = cx1 - cx0, cy1 - cy0
    cov = int(sel.sum())
    coverage = cov / max(1, cw * ch)
    if coverage < COV_FLOOR_A:
        return {"verdict": "NO-SILHOUETTE", "reason": "no-blob-near-key-colour", "coverage": round(coverage, 4),
                "iou": 0.0, "offset_px": None, "area_ratio": 0.0}
    ys, xs = np.where(sel)
    sx0n = (cx0 + xs.min()) / MW; sx1n = (cx0 + xs.max() + 1) / MW
    sy0n = (cy0 + ys.min()) / MH; sy1n = (cy0 + ys.max() + 1) / MH
    sbbox = [sx0n, sy0n, sx1n - sx0n, sy1n - sy0n]
    cxn = (cx0 + xs.mean()) / MW; cyn = (cy0 + ys.mean()) / MH
    dcx, dcy = db[0] + db[2] / 2, db[1] + db[3] / 2
    iou = _iou(sbbox, db)
    offset_px = float(np.hypot((cxn - dcx) * PW, (cyn - dcy) * PH))
    diag_px = float(np.hypot(db[2] * PW, db[3] * PH))
    offset_frac = offset_px / max(1.0, diag_px)
    sil_area_frac = cov / (MW * MH)
    dev_area_frac = db[2] * db[3]
    area_ratio = sil_area_frac / max(1e-9, dev_area_frac)

    reasons = []
    if iou < IOU_FAIL_A: reasons.append(f"maskKey:iou<{IOU_FAIL_A}")
    if offset_frac > OFFSET_FRAC_FAIL_A: reasons.append(f"maskKey:offset>{OFFSET_FRAC_FAIL_A}xdiag")
    if area_ratio < AREA_RATIO_FAIL_A: reasons.append(f"maskKey:area_ratio<{AREA_RATIO_FAIL_A}")
    verdict = "FAIL" if reasons else "PASS"
    return {
        "verdict": verdict, "reasons": reasons, "coverage": round(coverage, 4),
        "iou": round(iou, 4), "offset_px": round(offset_px, 1), "offset_frac_diag": round(offset_frac, 4),
        "area_ratio": round(area_ratio, 4), "silhouette_bbox": [round(v, 5) for v in sbbox],
    }


def method_b_paint_vividness(paint, PW, PH, db):
    """Independent 2nd opinion, read directly from paint.png -- NOT anchored to maskDevice.
    2-D extension of extract12.py's snap_to_paint icon-vividness heuristic (buttons branch:
    `sel = (mx - mn) > VIVID_THRESH`), including its own vivid-body-distrust abstention."""
    cx, cy = db[0] + db[2] / 2, db[1] + db[3] / 2
    wx0 = max(0, int((cx - db[2] * (0.5 + PAD_B)) * PW)); wx1 = min(PW, int((cx + db[2] * (0.5 + PAD_B)) * PW))
    wy0 = max(0, int((cy - db[3] * (0.5 + PAD_B)) * PH)); wy1 = min(PH, int((cy + db[3] * (0.5 + PAD_B)) * PH))
    if wx1 <= wx0 or wy1 <= wy0:
        return {"verdict": "INCONCLUSIVE", "reason": "empty-window"}
    win = paint[wy0:wy1, wx0:wx1].astype(int)
    mx = win.max(2); mn = win.min(2)
    sel = (mx - mn) > VIVID_THRESH
    ww, wh = wx1 - wx0, wy1 - wy0
    coverage = float(sel.mean())
    if coverage > VIVID_DISTRUST:
        # matches extract12.py's own gate: whole window is saturated (e.g. a vivid sky/material
        # backdrop) -- vividness can't discriminate icon-from-background here, abstain.
        return {"verdict": "INCONCLUSIVE", "reason": "vivid-body-distrust", "coverage": round(coverage, 4)}
    if int(sel.sum()) < 50:
        return {"verdict": "FAIL", "reason": "no-vivid-content-found", "coverage": round(coverage, 4),
                "iou": 0.0, "offset_px": None, "area_ratio": 0.0}
    ys, xs = np.where(sel)
    sx0n = (wx0 + xs.min()) / PW; sx1n = (wx0 + xs.max() + 1) / PW
    sy0n = (wy0 + ys.min()) / PH; sy1n = (wy0 + ys.max() + 1) / PH
    sbbox = [sx0n, sy0n, sx1n - sx0n, sy1n - sy0n]
    cxn = (wx0 + xs.mean()) / PW; cyn = (wy0 + ys.mean()) / PH
    dcx, dcy = cx, cy
    iou = _iou(sbbox, db)
    offset_px = float(np.hypot((cxn - dcx) * PW, (cyn - dcy) * PH))
    sil_area_frac = int(sel.sum()) / (PW * PH)
    area_ratio = sil_area_frac / max(1e-9, db[2] * db[3])
    verdict = "FAIL" if area_ratio < AREA_RATIO_FAIL_B else "PASS"
    return {
        "verdict": verdict, "coverage": round(coverage, 4), "iou": round(iou, 4),
        "offset_px": round(offset_px, 1), "area_ratio": round(area_ratio, 4),
        "reason": (f"area_ratio<{AREA_RATIO_FAIL_B}" if verdict == "FAIL" else None),
    }


def method_c_circle_fit_advisory(paintg, GW, GH, gmag, db):
    """Non-gating diagnostic. Port of extract12.py's circle_fit gradient-ring search, scoped
    to a tighter +-30% window (the +-50% original range was too eager to jump to a NEIGHBOUR
    button's rim on tightly-packed rows -- see CALIBRATION NOTES). Reported for human triage
    only: verified (fa-pod/queue) to false-positive at the same offset magnitude as a real
    defect (fa-sky/playpause) when a button has a concentric two-tone bezel, so it is not
    trustworthy as a hard PASS/FAIL gate with the effort spent here."""
    cx0 = (db[0] + db[2] / 2) * GW; cy0 = (db[1] + db[3] / 2) * GH
    r0 = (db[2] * GW + db[3] * GH) / 4
    best = (0.0, cx0, cy0, r0)
    ang = np.linspace(0, 2 * np.pi, 72, endpoint=False); ca, sa = np.cos(ang), np.sin(ang)
    for dy in range(int(-r0 * CIRCLEFIT_RNG), int(r0 * CIRCLEFIT_RNG) + 1, 3):
        for dx in range(int(-r0 * CIRCLEFIT_RNG), int(r0 * CIRCLEFIT_RNG) + 1, 3):
            for r in np.arange(r0 * CIRCLEFIT_RLO, r0 * CIRCLEFIT_RHI, 3):
                xs = (cx0 + dx + r * ca).astype(int); ys = (cy0 + dy + r * sa).astype(int)
                ok = (xs >= 0) & (xs < GW) & (ys >= 0) & (ys < GH)
                if ok.sum() < 60: continue
                s = gmag[ys[ok], xs[ok]].mean()
                if s > best[0]: best = (float(s), float(cx0 + dx), float(cy0 + dy), float(r))
    score, fx, fy, fr = best
    off = float(np.hypot(fx - cx0, fy - cy0))
    diag = float(np.hypot(db[2] * GW, db[3] * GH))
    return {"offset_px": round(off, 1), "offset_frac_diag": round(off / max(1.0, diag), 4),
            "score": round(score, 2), "note": "advisory only, not gating -- see docstring"}


def check_button(mask, MW, MH, paint_rgb, paintg, gmag, PW, PH, GW, GH, db, mb, key):
    a = method_a_mask_key(mask, MW, MH, PW, PH, db, mb, key)
    # Method B (paintVividness) was prototyped and DROPPED -- see CALIBRATION NOTES: its
    # colour-saturation heuristic is only meaningful on vivid/glossy icon styles and produces
    # systematic whole-skin false positives on monochrome/engraved icon styles (diablo-gothic,
    # fallout-pipboy, ps1-crunchy all measured near-zero "vividness" on every button, healthy
    # or not -- the signal can't tell icon-from-material there at all). Shipping a signal that
    # fails an entire skin's clean buttons is worse than not having it (restraint-rule).
    b = method_b_paint_vividness(paint_rgb, PW, PH, db)   # computed + recorded, NOT gating
    c = method_c_circle_fit_advisory(paintg, GW, GH, gmag, db)
    reasons = list(a.get("reasons", []))
    fail = a["verdict"] in ("FAIL", "NO-SILHOUETTE")
    out = {
        "verdict": "FAIL" if fail else "PASS",
        "reasons": reasons,
        "iou": a.get("iou"), "offset_px": a.get("offset_px"), "area_ratio": a.get("area_ratio"),
        "coverage": a.get("coverage"),
        "maskKey": a,
        "paintVividnessAdvisory": b,
        "circleFitAdvisory": c,
    }
    return out


def run(assets_dir):
    rj_path = os.path.join(assets_dir, "regions.json")
    mask_path = os.path.join(assets_dir, "mask.png")
    paint_path = os.path.join(assets_dir, "paint.png")
    if not (os.path.exists(rj_path) and os.path.exists(mask_path) and os.path.exists(paint_path)):
        return None
    regs_full = json.load(open(rj_path))
    buttons = regs_full.get("buttons", [])
    keys = regs_full.get("keys", {})
    regions = regs_full.get("regions", {})
    mask = np.asarray(Image.open(mask_path).convert("RGB"))
    MH, MW = mask.shape[:2]
    paint_img = Image.open(paint_path).convert("RGB")
    PW, PH = paint_img.size
    paint_rgb = np.asarray(paint_img)
    paintg = np.asarray(paint_img.convert("L")).astype(float)
    GH, GW = paintg.shape
    gyy, gxx = np.gradient(paintg); gmag = np.hypot(gxx, gyy)

    out = {}
    for b in buttons:
        r = regions.get(b)
        if not r or not r.get("device"):
            out[b] = {"verdict": "MISSING", "reason": "no-device-bbox"}
            continue
        db = r["device"]; mb = r.get("maskDevice") or db
        key = keys.get(b, [255, 255, 255])
        out[b] = check_button(mask, MW, MH, paint_rgb, paintg, gmag, PW, PH, GW, GH, db, mb, key)

    obs_dir = os.path.join(assets_dir, "observe")
    os.makedirs(obs_dir, exist_ok=True)
    out_path = os.path.join(obs_dir, "silcheck.json")
    json.dump(out, open(out_path, "w"), indent=2)
    return out


def _fmt_row(skin, btn, m):
    v = m.get("verdict", "?")
    iou = m.get("iou"); off = m.get("offset_px"); ar = m.get("area_ratio")
    reasons = ",".join(m.get("reasons", [])) or m.get("reason", "")
    return f"  {skin:26} {btn:10} {v:14} iou={iou!s:>7} off={off!s:>7}px area_ratio={ar!s:>7}  {reasons}"


def main():
    args = sys.argv[1:]
    calibrate = "--calibrate" in args
    all_mode = "--all" in args or calibrate
    args = [a for a in args if not a.startswith("--")]

    if all_mode:
        dirs = sorted(d for d in glob.glob("assets-*") if os.path.isdir(d)
                       and not d.endswith(("_biref", "_pbr")))
    elif args:
        dirs = [args[0].rstrip("/")]
    else:
        print(__doc__); sys.exit(1)

    all_results = {}
    for d in dirs:
        skin = d[len("assets-"):] if d.startswith("assets-") else d
        res = run(d)
        if res is None:
            continue
        all_results[skin] = res
        for btn, m in res.items():
            print(_fmt_row(skin, btn, m))

    if calibrate:
        _calibrate(all_results)


def _calibrate(all_results):
    review_path = "review-2026-07-11-round1.json"
    if not os.path.exists(review_path):
        print("\n[calibrate] no review-2026-07-11-round1.json found, skipping"); return
    NAMED = {"fa-sky", "myst-arcanum", "steam-porthole", "wmp-quicksilver"}
    print("\n" + "=" * 100)
    print("CALIBRATION vs review-2026-07-11-round1.json (human ground truth)")
    print("=" * 100)
    header = f"{'skin':26} {'named?':7} {'any-btn-FAIL':13} {'buttons FAIL':40} verdict"
    print(header); print("-" * len(header))
    correct = 0; total = 0
    for skin, res in sorted(all_results.items()):
        named = skin in NAMED
        fails = [b for b, m in res.items() if m.get("verdict") == "FAIL"]
        any_fail = bool(fails)
        expect_fail = named
        ok = (any_fail == expect_fail)
        total += 1; correct += int(ok)
        tag = "OK" if ok else ("MISS(false-neg)" if expect_fail and not any_fail else "false-pos")
        print(f"{skin:26} {str(named):7} {str(any_fail):13} {','.join(fails)[:40]:40} {tag}")
    print("-" * len(header))
    print(f"{correct}/{total} skins classified as expected (named->FAIL, unnamed->no button-silhouette FAIL)")


if __name__ == "__main__":
    main()


# ==== CALIBRATION NOTES (2026-07-12, full 15-skin roster, review-2026-07-11-round1.json) ====
# regions.json is being LIVE-EDITED by a concurrent extract-fix lane in this shared checkout
# (per the task brief's own warning) -- these numbers are the FINAL run of this session,
# after several regions.json updates already landed mid-investigation (confirmed via git
# diff: myst-arcanum's `repeat` button gained a device bbox it didn't have earlier in the
# session, for one). Re-run `python3 silcheck.py --calibrate` for the current live state.
#
# 2/4 named skins caught CLEANLY by the gating method (maskKey), 1 genuine finding on an
# unnamed skin, 2 documented misses with confirmed root cause:
#
#   steam-porthole [OK]  -> playpause FAILs maskKey iou<0.30; next/repeat/queue FAIL maskKey
#                           NO-SILHOUETTE (no blob near that button's key colour in its own
#                           crop -- a genuinely missing/fragmented mask region per button).
#   wmp-quicksilver [OK] -> prev/next/repeat FAIL maskKey NO-SILHOUETTE (same mechanism).
#
#   fa-pod/prev [webbed in as a "false-pos" against the human labels, but NOT noise]: FAILs
#     maskKey NO-SILHOUETTE. Traced the raw pixels (this session): mask.png's guide colour at
#     this button measured (227-232,101-105,132-135) vs the flat key (255,0,128) -- squared-
#     dist ~11259, just OVER build_player.py's own hardcoded <7000 threshold, even though the
#     visible paint.png button (a clean teal rewind icon, confirmed by crop) is perfectly
#     healthy. Since this check is a VERBATIM port of build_player.py's own threshold, this
#     means the SHIPPED player very likely also fails its own no-blob-found floor for this
#     exact button and silently falls back to the generic rounded-rect ink shape at runtime --
#     i.e. this is probably a real defect the human reviewer simply didn't press/notice on
#     this one button of one skin, not a bug in the checker. Left un-tuned deliberately: the
#     point of porting the threshold verbatim is to test what SHIPS, not a looser version of it.
#
#   myst-arcanum/playpause [MISS]. Human note: "button depression silhouettes not aligned."
#     Visual inspection (device-bbox overlay on paint.png, this session) shows the box is
#     large (33% canvas width -- this skin's clockwork-arcanum "play" control is genuinely an
#     oversized ornamental dial) and DOES contain a circular housing at the right place -- but
#     the painted content inside it is a decorative GEAR/CLOCKWORK CLUSTER, not a play/pause
#     glyph (no triangle, no bars -- confirmed by crop). maskKey reads this as healthy (iou
#     0.798, area_ratio 0.972) because mask.png's guide blob is a correctly-shaped, correctly-
#     placed flat-colour circle -- the guide only encodes WHERE a control's housing should be,
#     never WHAT icon should be painted inside it, so this is fundamentally a CONTENT defect
#     (wrong glyph painted) invisible to any geometry-only check, mask.png-based or paint.png-
#     based alike. Per fix-generalizable-rule this belongs in genskin.py's prompt layer (icon-
#     content adherence), not extract12's geometry layer -- flagging for that lane, not
#     something a bbox-vs-silhouette check can catch by construction.
#
#   fa-sky/playpause [MISS]. Human note: "play button depression silhoutte doesnt match.
#     phantom play button." Visual inspection (crop + device-bbox overlay,
#     /tmp/silcheck-crops/press_fa-sky_playpause.png, this session) confirms the defect is
#     REAL: the device bbox sits visibly off-centre from the round chrome/glass button --
#     snap_to_paint's x-shift correction (capped at 20% of button width) undershoots the true
#     offset. maskKey doesn't catch it because it's anchored to maskDevice, which is upstream
#     of the SAME undershoot -- it always re-finds a self-consistent blob near where it already
#     expected one (iou 0.60, area_ratio 0.98 -- healthy-looking by construction, the
#     verify-outputs-rule circularity trap: validating a detector's box against that same
#     detector's own upstream signal). The circleFitAdvisory diagnostic DOES measure this
#     specific defect (offset_frac_diag=0.102, the largest of fa-sky's 5 buttons) -- but the
#     SAME diagnostic measures an equal-or-larger 0.082-0.105 on OTHER buttons in OTHER skins
#     with no review complaint (fa-pod/prev 0.082, fa-pod/queue 0.105), confirmed by visual
#     inspection to be clean, well-centred buttons -- the false reading comes from the gradient
#     search locking onto the INNER glass ring instead of the OUTER chrome rim on a concentric
#     two-tone bezel. Tried tightening the search window (dx,dy +-50%->+-30% of r0) and the
#     radius band (0.7-1.3x r0 -> 0.85-1.15x r0 of the assumed radius) -- both reduced but did
#     not eliminate the ambiguity; the true defect and the concentric-ring artifact land in the
#     SAME magnitude band, so no threshold on this signal alone cleanly separates them at the
#     effort spent here. Reported as an advisory field for human triage, deliberately NOT
#     force-gated with a threshold that would misclassify healthy buttons as broken.
#
# Net: 12/15 skins classified exactly as expected by a strict "named skin -> at least one
# button FAILs" test. Of the 3 "misses" against the raw scorecard: 1 (fa-pod/prev) is very
# likely a genuine defect outside the labeled set, not checker noise; the other 2 have
# confirmed real root causes that a bbox-vs-silhouette geometry check cannot reach by
# construction (a content defect, and a bezel-ring-ambiguity noise floor that swamps the one
# real signal that would catch it) -- documented here rather than papered over with a tuned
# threshold that would trade this recall for false positives elsewhere on the roster.
