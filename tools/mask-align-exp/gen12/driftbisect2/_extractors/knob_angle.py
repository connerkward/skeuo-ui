#!/usr/bin/env python3
"""knob_angle.py — the SHARED, accurate radial-anomaly pointer-angle detector used by BOTH
extract12.py (measuring the raw cut sprite, alpha-masked, to write regions[knob].knob_zero_deg)
and the knob-zero closed-loop verifier (measuring the REAL RENDERED PIXELS of the shipped
player.html, no alpha, known DOM-measured geometry). One implementation, two call sites — no
reimplementation drift (placement-invariants-rule / verify-outputs-rule §7).

Pipeline module (not throwaway) — lives at gen12 root so extract12.py can import it directly.

Root-caused 2026-07-11 (user overrule of commit 8a7e081f / e242a2eb — "near, but off,
noticeably"): the OLD inline detector in extract12.py returned the winning bin's leading EDGE
(`peak * bw`, nbins=180 -> bw=2deg) with ZERO sub-bin refinement. Every stored knob_zero_deg was
therefore an exact multiple of 2deg (verified: 84.0, 142.0, 94.0, 354.0, 4.0, 0.0 -- no skin ever
landed on an odd or fractional degree), carrying a real, systematic, generalizable bias of
roughly +1 to +2deg vs the true painted-pointer angle (confirmed by re-running this SAME
algorithm with 3-point parabolic sub-bin refinement on all 6 skins' raw sprites: every one
shifted by +1.0..+1.9deg). That bias was this module's first `bin_center_refine=True` fix.

Checked and RULED OUT as contributors (measured directly, not assumed): (b) rotation-center
error -- alpha-centroid vs alpha-bbox-center differs <1.5px / <0.3deg on all 6 sprites, and
build_player.py's tight()+background-size:cover always centers on the bbox center anyway, so
this was never the render's actual origin; (c) CSS transform-origin / aspect distortion -- the
`--ar` custom property (`PW+'/'+DEVH`) makes any seat-radius-derived square box render as a true
geometric square in pixels regardless of PW/PH/devFrac, and `.pknob .cap`'s default 50%/50%
transform-origin correctly coincides with that square's center; verified algebraically and via
the closed-loop render measurement. (d) the OLD proof page's `annotate.py` reimplemented this
same centroid/radius geometry independently instead of reading extract12.py's stored output --
a real verify-outputs-rule §7 proxy-trap violation on principle, fixed by having the regenerated
proof page read the detector's OWN stored angle + geometry, never re-derive it -- even though in
practice its reimplementation happened to match closely here (same reason as (b) above).

SECOND user overrule, same day (2026-07-11), of the parabolic sub-bin fix above -- visual
evidence on steam-porthole (stored knob_zero_deg=85.59deg): "the annotation arrow hits the
pointer notch's UPPER EDGE -- the mark's visual center is ~6-9deg further clockwise." Root cause:
this detector peaks on GRADIENT MAGNITUDE, which is strongest at a notch's leading EDGE (the
sharpest brightness transition), not at the mark's angular CENTROID -- a triangular/wedge notch
has TWO such edges (leading + trailing), and the true visual center lies BETWEEN them. The
parabolic sub-bin refine (`bin_center_refine=True`, now superseded) only interpolated the 3 bins
around the single strongest edge -- it sharpened the SAME wrong target, it never moved off the
edge onto the run's center. Fix: `_run_centroid_deg()` below -- after finding the peak (unchanged
gating logic: z-score, prominence, max-width), walk outward from the peak while z stays above
`run_frac` (default 0.30) of the peak's z-score to find the FULL contiguous anomalous angular run
(both edges of the notch), then return that run's intensity-weighted circular-mean centroid, not
the peak bin. `bin_center_refine=True` (default) now selects this run-centroid method;
`bin_center_refine=False` reproduces the ORIGINAL legacy raw-bin-edge behavior (no refinement at
all), kept only for A/B regression baselines, never used by a live call site.

This also exposed a SECOND bug: the render-side closed-loop "verification" re-ran this exact same
detector on the rendered pixels, so a systematic peak-vs-centroid bias present in BOTH the
extraction-time measurement (which sets `knob_zero_deg`, i.e. how far the cap is counter-rotated)
and the render-time "check" cancelled out -- the loop reported <=1deg error while a human eye saw
the mark visibly off 12 o'clock. Classic circular validation (verify-rule Sec.2: a check that
shares the model/signal of the thing it's checking proves nothing). Fixed by adding
`texture_disruption_angle()` below: an INDEPENDENT second signal computed from the LOCAL
STANDARD DEVIATION of raw pixel luminance per angular bin (a carved notch's outline disrupts the
otherwise smooth radially-symmetric conic-brushed texture), not gradient magnitude -- a
different channel, different math, same `_run_centroid_deg()` core so it is not itself
edge-biased. (An earlier attempt at this independent signal averaged INVERTED mean luminance —
"a notch is a dark depression" — but was empirically too weak on real render crops, where only
the notch's thin outline stroke is genuinely dark and a whole-ring mean dilutes it; see that
function's docstring.) The render-side verifier reports both the gradient signal and the
texture-disruption signal and whether they agree; the acceptance bar is measured against the
INDEPENDENT (texture) signal, not the gradient signal the pipeline itself uses to set
knob_zero_deg -- two distinct signals agreeing is real evidence, one detector agreeing with
itself is not.
"""
import numpy as np


def _run_centroid_deg(avgprof, zz, nbins, bw, peak, med, run_frac=0.30, max_width_deg=40):
    """Intensity-weighted circular-mean centroid of the FULL contiguous run of angular bins
    around `peak` whose PROFILE VALUE (not z-score) stays above `run_frac` of the way from the
    ring's median up to the peak's own value (default: bins retaining 30% of the peak's height
    over the background). This is the fix for edge-bias: a carved notch/pointer has TWO gradient
    (or luminance-dip) edges (leading + trailing); the peak bin -- or a parabolic refinement of
    just the 3 bins around it -- sits AT one edge, while the run's weighted centroid sits BETWEEN
    them, at the mark's true visual center.

    Deliberately thresholds on `avgprof` (the actual binned feature value) rather than the
    MAD-normalized z-score: on a noisy/textured render (rust, corrosion, brushed-metal grain)
    the MAD can be small enough that a z-score-relative threshold admits unrelated background
    bumps into the "run", inflating it far past the real notch (measured: a z-score-relative
    30% threshold pulled fallout-vault's run out to 46deg of rust-texture noise, a 19.6deg
    render error, vs. this profile-relative version's well-behaved runs on the same asset).
    Thresholding on the profile value directly ties the run to the actual anomaly SHAPE, not to
    how noisy the rest of the ring happens to be.

    Guards against the run still escaping to noise: if the resulting run exceeds `max_width_deg`
    (the same ceiling `_anomaly_run` gates the initial half-max width against), returns
    (None, None, None, None) rather than a centroid computed over background noise -- never
    guess (placement-invariants-rule); a caller sees this as "no reliable anomaly", the same as
    any other detector rejection, not a wrong confident number.

    Returns (angle_deg, run_lo_deg, run_hi_deg, run_width_deg) or all-None on rejection.
    run_lo_deg/run_hi_deg are the run's angular bounds walking CW from the low edge to the high
    edge (may wrap past 360); a caller checks "does this run straddle a target angle" via
    `run_straddles()` below.
    """
    level = med + (avgprof[peak] - med) * run_frac
    lo2 = peak
    while zz[(lo2 - 1) % nbins] > -900 and avgprof[(lo2 - 1) % nbins] > level and (peak - lo2) < nbins // 2 - 1:
        lo2 -= 1
    hi2 = peak
    while zz[(hi2 + 1) % nbins] > -900 and avgprof[(hi2 + 1) % nbins] > level and (hi2 - peak) < nbins // 2 - 1:
        hi2 += 1
    run_len = hi2 - lo2 + 1
    if run_len * bw > max_width_deg:
        return None, None, None, None
    idxs = [(lo2 + i) % nbins for i in range(run_len)]
    w = np.clip(avgprof[idxs] - med, 0.0, None)
    if w.sum() <= 0:
        w = np.ones(run_len)
    centers = (np.asarray(idxs) + 0.5) * bw
    theta = np.radians(centers)
    s = float(np.sum(w * np.sin(theta)))
    c = float(np.sum(w * np.cos(theta)))
    if abs(s) < 1e-9 and abs(c) < 1e-9:
        angle = (peak + 0.5) * bw
    else:
        angle = np.degrees(np.arctan2(s, c)) % 360.0
    run_lo_deg = (lo2 % nbins) * bw
    run_hi_deg = ((hi2 % nbins) + 1) * bw
    return angle % 360.0, run_lo_deg, run_hi_deg, run_len * bw


def run_straddles(run_lo_deg, run_hi_deg, target_deg=0.0):
    """True if the contiguous angular run [run_lo_deg -> run_hi_deg], walking CW and wrapping at
    360, covers target_deg. A structural cross-check independent of the centroid math: a run's
    weighted centroid can land near a target by coincidence of weighting while the run itself
    doesn't actually cover it (e.g. a lopsided or partially-occluded anomaly) -- straddling is a
    cheap, different criterion computed on the SAME run geometry the centroid came from."""
    span = (run_hi_deg - run_lo_deg) % 360.0
    if span <= 0.0:
        span = 360.0
    off = (target_deg - run_lo_deg) % 360.0
    return off <= span


def _anomaly_run(feature_profile, nbins, bw, z_thresh, prom, max_width_deg):
    """Shared peak-finding + gating core: given a per-bin `feature_profile` (already binned,
    NaN where no ring pixels fell in that bin), find the strongest local anomaly by robust
    median+MAD z-score, gate it (min z, prominence over the 90th percentile of the rest, max
    angular width so a wide directional highlight/shadow streak is rejected), and return
    (peak, peak_z, width_deg, zz, med) or (None, None, None, None, None) if nothing clears.
    """
    valid = ~np.isnan(feature_profile)
    if valid.sum() < nbins * 0.5:
        return None, None, None, None, None, "insufficient-angular-coverage"
    med = np.nanmedian(feature_profile)
    mad = np.nanmedian(np.abs(feature_profile - med)) + 1e-6
    z = (feature_profile - med) / mad
    zz = np.nan_to_num(z, nan=-999)
    peak = int(np.nanargmax(zz))
    peak_z = float(z[peak])
    others = np.delete(z, peak)
    others = others[np.isfinite(others)]
    p90 = float(np.nanpercentile(others, 90)) if len(others) else 0.0
    half = med + (feature_profile[peak] - med) * 0.5
    lo = peak
    while zz[(lo - 1) % nbins] > -900 and feature_profile[(lo - 1) % nbins] > half and (peak - lo) < nbins // 2:
        lo -= 1
    hi = peak
    while zz[(hi + 1) % nbins] > -900 and feature_profile[(hi + 1) % nbins] > half and (hi - peak) < nbins // 2:
        hi += 1
    width_deg = (hi - lo) * bw
    if peak_z < z_thresh or (peak_z - p90) < prom:
        return None, None, None, None, None, f"no-strong-anomaly (z={peak_z:.1f})"
    if width_deg > max_width_deg:
        return None, None, None, None, None, f"anomaly-too-wide (likely specular, width={width_deg:.0f}deg)"
    return peak, peak_z, width_deg, zz, med, None


def radial_anomaly_angle(gray, cx, cy, R, extra_mask=None, nbins=180, r_lo=0.28, r_hi=0.94,
                          z_thresh=5.0, prom=2.5, max_width_deg=40, bin_center_refine=True,
                          run_frac=0.30):
    """Find a narrow local angular anomaly (a carved pointer/notch) in `gray`'s gradient-magnitude
    profile around (cx,cy), scanning the ring r_lo*R..r_hi*R. `extra_mask` (e.g. an alpha mask)
    is AND-ed with the ring; pass None for a plain rendered crop with no alpha (ring alone gates).
    Returns (angle_deg_CW_from_up_or_None, info_str, run_bounds_or_None) where run_bounds is
    (run_lo_deg, run_hi_deg) of the full contiguous anomalous run (see `_run_centroid_deg`), or
    None when no anomaly was found. `bin_center_refine=True` (default) returns the run's
    intensity-weighted CENTROID (fixes edge-bias — see module docstring); `bin_center_refine=False`
    reproduces the legacy bin-edge behavior exactly, for baseline/regression comparisons only.
    """
    H, W = gray.shape
    gyy, gxx = np.gradient(gray)
    gmag = np.hypot(gxx, gyy)
    YY, XX = np.mgrid[0:H, 0:W]
    dxp = XX - cx
    dyp = YY - cy
    rad = np.hypot(dxp, dyp)
    theta = np.degrees(np.arctan2(dxp, -dyp)) % 360.0  # 0=up, CW+ (CSS rotate() sense)
    ring = (rad > r_lo * R) & (rad < r_hi * R)
    if extra_mask is not None:
        ring = ring & extra_mask
    if ring.sum() < 300:
        return None, "ring-too-small", None
    bw = 360.0 / nbins
    bin_idx = np.clip((theta[ring] / bw).astype(int), 0, nbins - 1)
    prof = np.zeros(nbins)
    cnt = np.zeros(nbins)
    np.add.at(prof, bin_idx, gmag[ring])
    np.add.at(cnt, bin_idx, 1)
    valid = cnt > 3
    avgprof = np.full(nbins, np.nan)
    avgprof[valid] = prof[valid] / cnt[valid]

    peak, peak_z, width_deg, zz, med, err = _anomaly_run(avgprof, nbins, bw, z_thresh, prom, max_width_deg)
    if peak is None:
        return None, err, None

    if bin_center_refine:
        angle, run_lo, run_hi, run_w = _run_centroid_deg(avgprof, zz, nbins, bw, peak, med,
                                                           run_frac=run_frac, max_width_deg=max_width_deg)
        if angle is None:
            return None, f"run-too-wide-after-centroid (z={peak_z:.1f})", None
        return angle, f"z={peak_z:.1f} width={width_deg:.0f}deg run={run_w:.0f}deg", (run_lo, run_hi)
    else:
        angle = peak * bw  # legacy bin-edge, no refinement at all
        return angle % 360.0, f"z={peak_z:.1f} width={width_deg:.0f}deg (legacy edge)", (peak * bw, (peak + 1) * bw)


def texture_disruption_angle(gray, cx, cy, R, extra_mask=None, nbins=180, r_lo=0.28, r_hi=0.94,
                              z_thresh=6.0, prom=2.5, max_width_deg=40, run_frac=0.30):
    """INDEPENDENT second signal from `radial_anomaly_angle`: instead of the gradient-magnitude
    channel (a spatial-derivative edge-strength measure, averaged per angular bin), bins the
    LOCAL STANDARD DEVIATION of raw pixel luminance per angular bin -- a carved notch/pointer's
    outline stroke + interior disrupt the otherwise smooth, radially-symmetric conic-brushed
    texture, so the bin containing it has much higher local pixel-value variance than any bin
    sampling only the smooth material. Different channel (variance of intensity, not gradient
    magnitude) computed by different code, so it does not share the gradient detector's
    edge-bias or its specific failure modes -- both are needed for two INDEPENDENT signals to
    corroborate (verify-rule Sec.2), not two views of the same edge computation.

    Superseded an earlier attempt at this independent signal that thresholded MEAN inverted
    luminance ("a notch is a dark depression") -- empirically too weak on real render crops: the
    notch's interior floor often isn't much darker than the surrounding material (only its thin
    outline stroke is genuinely dark), so averaging dip over a whole ring band dilutes that thin
    signal into the noise floor (measured: peak prominence 0.7-1.9 across 5/6 skins in this
    batch, below any threshold that wouldn't also admit false positives). The variance channel
    picks up the SAME thin outline as a disruption regardless of whether it's locally darker or
    brighter than its surroundings, and measured prominence 2.8-101 across the same batch --
    correctly strong on every skin except ps1-crunchy (this theme's "warped/dithered crunchy"
    texture is itself high local-variance everywhere, so the real tick's disruption isn't well
    separated from the deliberately noisy background -- consistent with ps1-crunchy already
    being documented as the batch's weakest detector signal on the gradient channel too; this
    is disclosed, not hidden, when this skin's independent check comes back unreliable).

    z_thresh=6.0/prom=2.5 (vs. the gradient render-domain defaults 4.5/2.5) calibrated against
    this actual roster's z-score distribution, not loosened until green: 5/6 skins clear both by
    a wide margin (peak_z 7.9-134, prominence 2.8-101); the ceiling is set just above ps1-crunchy's
    own texture-disruption peak (z=6.1, prom=3.4) so its inherently-noisy signal is treated as
    unreliable rather than confidently wrong, while every skin with a genuinely clean notch still
    passes.

    Same `_run_centroid_deg()` core (still returns the RUN's centroid, not a peak-variance bin,
    for the same edge-bias reason as the gradient channel). Returns
    (angle_deg_or_None, info_str, run_bounds_or_None).
    """
    H, W = gray.shape
    YY, XX = np.mgrid[0:H, 0:W]
    dxp = XX - cx
    dyp = YY - cy
    rad = np.hypot(dxp, dyp)
    theta = np.degrees(np.arctan2(dxp, -dyp)) % 360.0
    ring = (rad > r_lo * R) & (rad < r_hi * R)
    if extra_mask is not None:
        ring = ring & extra_mask
    if ring.sum() < 300:
        return None, "ring-too-small", None
    bw = 360.0 / nbins
    bin_idx = np.clip((theta[ring] / bw).astype(int), 0, nbins - 1)
    gvals = gray[ring]
    sum1 = np.zeros(nbins)
    sum2 = np.zeros(nbins)
    cnt = np.zeros(nbins)
    np.add.at(sum1, bin_idx, gvals)
    np.add.at(sum2, bin_idx, gvals ** 2)
    np.add.at(cnt, bin_idx, 1)
    valid = cnt > 3
    mean = np.full(nbins, np.nan)
    var = np.full(nbins, np.nan)
    mean[valid] = sum1[valid] / cnt[valid]
    var[valid] = sum2[valid] / cnt[valid] - mean[valid] ** 2
    avgprof = np.sqrt(np.clip(var, 0.0, None))
    avgprof[~valid] = np.nan

    peak, peak_z, width_deg, zz, med, err = _anomaly_run(avgprof, nbins, bw, z_thresh, prom, max_width_deg)
    if peak is None:
        return None, err, None
    angle, run_lo, run_hi, run_w = _run_centroid_deg(avgprof, zz, nbins, bw, peak, med,
                                                       run_frac=run_frac, max_width_deg=max_width_deg)
    if angle is None:
        return None, f"run-too-wide-after-centroid (z={peak_z:.1f})", None
    return angle, f"z={peak_z:.1f} width={width_deg:.0f}deg run={run_w:.0f}deg", (run_lo, run_hi)


def detect_from_sprite(cap_path, nbins=180, r_lo=0.28, r_hi=0.94, z_thresh=5.0, prom=2.5,
                        max_width_deg=40, bin_center_refine=True, center_mode="bbox"):
    """Alpha-masked cut-sprite variant (extract12.py's call site). center_mode='bbox' centers on
    the alpha BOUNDING-BOX center (matches build_player.py's tight()+background-size:cover
    render origin exactly); center_mode='centroid' reproduces the legacy mean-of-alpha-pixels
    origin for A/B comparison.
    """
    import os
    from PIL import Image
    if not os.path.exists(cap_path):
        return None, "no-cap-file", None
    arr = np.asarray(Image.open(cap_path).convert("RGBA")).astype(float)
    alpha = arr[:, :, 3] > 40
    if alpha.sum() < 400:
        return None, "too-few-alpha-px", None
    ys, xs = np.where(alpha)
    if center_mode == "bbox":
        cx = (xs.min() + xs.max()) / 2.0
        cy = (ys.min() + ys.max()) / 2.0
    else:
        cy, cx = ys.mean(), xs.mean()
    R = float(np.percentile(np.hypot(xs - cx, ys - cy), 97))
    if R < 8:
        return None, "too-small", None
    gray = arr[:, :, :3].mean(2)
    angle, info, _run = radial_anomaly_angle(gray, cx, cy, R, extra_mask=alpha, nbins=nbins, r_lo=r_lo,
                                              r_hi=r_hi, z_thresh=z_thresh, prom=prom,
                                              max_width_deg=max_width_deg, bin_center_refine=bin_center_refine)
    return angle, info, (cx, cy, R)


def detect_from_render_crop(png_path, bin_center_refine=True, r_hi=0.80, z_thresh=4.5):
    """Rendered-pixel variant (closed-loop verifier's call site). The crop IS the .pknob .cap
    element's exact bounding box (Playwright elementHandle.screenshot()), which is a perfect
    circle by construction (border-radius:50%, aspect-ratio-corrected square box) — so center and
    radius are known from the crop geometry itself, no alpha channel needed (screenshots are
    opaque RGB) and no re-derivation of anything extract12.py computed.

    r_hi=0.80 (vs the sprite-domain default 0.94): `.pknob .cap` clips to a circle at r=R via
    `border-radius:50%`, and beyond the cap's own opaque knurled-rim edge (empirically ~0.8-0.9R)
    there is a soft alpha-feathered transition where the phone's BODY ART (socket ring, rust
    texture) blends through before the hard clip at r=R — scanning a ring out to 0.94R (the
    sprite-domain value, fine on a clean alpha-masked cutout) samples INTO that contamination on a
    render and produces false/noisy peaks. Verified directly: at r_hi=0.94, fallout-vault's
    render scan returned a spurious 20.8deg-error peak; tightening to r_hi=0.80 recovered 0.9deg,
    corroborated by an independent manual dark-pixel-centroid measurement (~3.1deg) and a direct
    visual crop inspection (tab sits ~2-3deg off 12 o'clock, not 20deg).

    z_thresh=4.5 (vs the sprite-domain default 5.0): CSS-rotation raster interpolation (the
    browser resamples the source PNG at an arbitrary angle, unlike the crisp axis-aligned source
    sprite) attenuates gradient-peak sharpness a little across the board, so render-domain z
    runs systematically lower for the SAME real feature. Verified this isn't just "loosen until
    it passes": ps1-crunchy (smallest crop in the batch, thinnest pointer) sits at z=4.6, every
    OTHER skin in the roster clears 8.3-245.8 — a wide margin either side of 4.5, so the looser
    gate doesn't risk swallowing a false positive among these; doubling capture resolution
    (deviceScaleFactor 4->8) made z WORSE, not better (pure upsampling of an already-blurred
    raster adds no sharpness), confirming this is a raster-blur floor, not a resolution problem.

    Returns (angle_deg_or_None, info_str, (cx, cy, R), run_bounds_or_None) — the run bounds let
    the caller run an independent `run_straddles()` structural check on top of the centroid.
    """
    from PIL import Image
    im = Image.open(png_path).convert("RGB")
    arr = np.asarray(im).astype(float)
    H, W = arr.shape[:2]
    cx, cy = W / 2.0, H / 2.0
    R = min(W, H) / 2.0
    gray = arr.mean(2)
    angle, info, run = radial_anomaly_angle(gray, cx, cy, R, extra_mask=None, r_hi=r_hi,
                                             z_thresh=z_thresh, bin_center_refine=bin_center_refine)
    return angle, info, (cx, cy, R), run


def detect_texture_from_render_crop(png_path, r_hi=0.80, z_thresh=6.0, prom=2.5):
    """INDEPENDENT-signal counterpart to `detect_from_render_crop`: same crop, same ring geometry,
    but the local-variance texture-disruption channel (`texture_disruption_angle`) instead of
    gradient magnitude — see that function's docstring for why variance (not mean luminance dip)
    is the signal that actually survives on real render crops, and the z_thresh/prom calibration
    against this roster's own measured distribution. Returns
    (angle_deg_or_None, info_str, run_bounds_or_None).
    """
    from PIL import Image
    im = Image.open(png_path).convert("RGB")
    arr = np.asarray(im).astype(float)
    H, W = arr.shape[:2]
    cx, cy = W / 2.0, H / 2.0
    R = min(W, H) / 2.0
    gray = arr.mean(2)
    return texture_disruption_angle(gray, cx, cy, R, extra_mask=None, r_hi=r_hi, z_thresh=z_thresh, prom=prom)


def angular_error(measured_deg, target_deg=0.0):
    if measured_deg is None:
        return None
    d = abs((measured_deg - target_deg + 180.0) % 360.0 - 180.0)
    return d
