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
therefore an exact multiple of 2deg (verified: 84.0, 142.0, 94.0, 354.0, 4.0, 0.0 — no skin ever
landed on an odd or fractional degree), carrying a real, systematic, generalizable bias of
roughly +1 to +2deg vs the true painted-pointer angle (confirmed by re-running this SAME
algorithm with 3-point parabolic sub-bin refinement on all 6 skins' raw sprites: every one
shifted by +1.0..+1.9deg). That bias is this module's `bin_center_refine=True` fix (default).

Checked and RULED OUT as contributors (measured directly, not assumed): (b) rotation-center
error — alpha-centroid vs alpha-bbox-center differs <1.5px / <0.3deg on all 6 sprites, and
build_player.py's tight()+background-size:cover always centers on the bbox center anyway, so
this was never the render's actual origin; (c) CSS transform-origin / aspect distortion — the
`--ar` custom property (`PW+'/'+DEVH`) makes any seat-radius-derived square box render as a true
geometric square in pixels regardless of PW/PH/devFrac, and `.pknob .cap`'s default 50%/50%
transform-origin correctly coincides with that square's center; verified algebraically and via
the closed-loop render measurement. (d) the OLD proof page's `annotate.py` reimplemented this
same centroid/radius geometry independently instead of reading extract12.py's stored output —
a real verify-outputs-rule §7 proxy-trap violation on principle, fixed by having the regenerated
proof page read the detector's OWN stored angle + geometry, never re-derive it — even though in
practice its reimplementation happened to match closely here (same reason as (b) above).
"""
import numpy as np


def radial_anomaly_angle(gray, cx, cy, R, extra_mask=None, nbins=180, r_lo=0.28, r_hi=0.94,
                          z_thresh=5.0, prom=2.5, max_width_deg=40, bin_center_refine=True):
    """Find a narrow local angular anomaly (a carved pointer/notch) in `gray`'s gradient-magnitude
    profile around (cx,cy), scanning the ring r_lo*R..r_hi*R. `extra_mask` (e.g. an alpha mask)
    is AND-ed with the ring; pass None for a plain rendered crop with no alpha (ring alone gates).
    Returns (angle_deg_CW_from_up_or_None, info_str). bin_center_refine=False reproduces the
    legacy (pre-fix) bin-edge behavior exactly, for baseline/regression comparisons.
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
        return None, "ring-too-small"
    bw = 360.0 / nbins
    bin_idx = np.clip((theta[ring] / bw).astype(int), 0, nbins - 1)
    prof = np.zeros(nbins)
    cnt = np.zeros(nbins)
    np.add.at(prof, bin_idx, gmag[ring])
    np.add.at(cnt, bin_idx, 1)
    valid = cnt > 3
    if valid.sum() < nbins * 0.5:
        return None, "insufficient-angular-coverage"
    avgprof = np.full(nbins, np.nan)
    avgprof[valid] = prof[valid] / cnt[valid]
    med = np.nanmedian(avgprof)
    mad = np.nanmedian(np.abs(avgprof - med)) + 1e-6
    z = (avgprof - med) / mad
    zz = np.nan_to_num(z, nan=-999)
    peak = int(np.nanargmax(zz))
    peak_z = float(z[peak])
    others = np.delete(z, peak)
    others = others[np.isfinite(others)]
    p90 = float(np.nanpercentile(others, 90)) if len(others) else 0.0
    half = med + (avgprof[peak] - med) * 0.5
    lo = peak
    while zz[(lo - 1) % nbins] > -900 and avgprof[(lo - 1) % nbins] > half and (peak - lo) < nbins // 2:
        lo -= 1
    hi = peak
    while zz[(hi + 1) % nbins] > -900 and avgprof[(hi + 1) % nbins] > half and (hi - peak) < nbins // 2:
        hi += 1
    width_deg = (hi - lo) * bw
    if peak_z < z_thresh or (peak_z - p90) < prom:
        return None, f"no-strong-anomaly (z={peak_z:.1f})"
    if width_deg > max_width_deg:
        return None, f"anomaly-too-wide (likely specular, width={width_deg:.0f}deg)"
    if bin_center_refine:
        # 3-point parabolic sub-bin refinement around the peak bin (bin CENTER, not the legacy
        # bin-EDGE `peak*bw` which carried a systematic -bw/2 bias). Tested against a weighted
        # circular-mean-over-width alternative on real rendered crops; the parabolic fit tracked
        # the true (visually-verified) pointer tip more accurately — the circular mean got pulled
        # off-center by mildly asymmetric shoulders on wider anomalies (steam-porthole, n64).
        ip1 = (peak + 1) % nbins
        im1 = (peak - 1) % nbins
        y0v, y1v, y2v = avgprof[im1], avgprof[peak], avgprof[ip1]
        frac = 0.0
        if np.isfinite(y0v) and np.isfinite(y2v):
            denom = y0v - 2 * y1v + y2v
            if abs(denom) > 1e-9:
                frac = max(-0.5, min(0.5, 0.5 * (y0v - y2v) / denom))
        angle = (peak + 0.5 + frac) * bw
    else:
        angle = peak * bw  # legacy bin-edge, no sub-bin refinement
    return angle % 360.0, f"z={peak_z:.1f} width={width_deg:.0f}deg"


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
    angle, info = radial_anomaly_angle(gray, cx, cy, R, extra_mask=alpha, nbins=nbins, r_lo=r_lo,
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
    """
    from PIL import Image
    im = Image.open(png_path).convert("RGB")
    arr = np.asarray(im).astype(float)
    H, W = arr.shape[:2]
    cx, cy = W / 2.0, H / 2.0
    R = min(W, H) / 2.0
    gray = arr.mean(2)
    angle, info = radial_anomaly_angle(gray, cx, cy, R, extra_mask=None, r_hi=r_hi,
                                        z_thresh=z_thresh, bin_center_refine=bin_center_refine)
    return angle, info, (cx, cy, R)


def angular_error(measured_deg, target_deg=0.0):
    if measured_deg is None:
        return None
    d = abs((measured_deg - target_deg + 180.0) % 360.0 - 180.0)
    return d
