#!/usr/bin/env python3
"""make_masks — variant A: derive a housing silhouette mask from the baseline lever's OWN
alpha cut (dilate a few px), plus a thin rim-highlight ring mask (a wider dilation minus the
housing fill). $0, deterministic, no generation — the render-time approach for variant A.
Also exports a cropped, tightly-trimmed copy of the lever sprite itself (transparent PNG) for
use as the moving part in the HTML across variants A and B."""
import os

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
# NOTE: deliberately using the SHAPEMATCH regen's lever, not the baseline's. Column-height
# profiling found the baseline lever's ALPHA SILHOUETTE is a plain rounded-rect (its "paddle
# end" is only surface shading, not a true silhouette bump — max height is ~within 3px of full
# across 90% of its width) while the shapematch lever has a genuine dogbone/keyhole silhouette
# (height dips ~44% at the waist, x=306-442 vs the lobes at x=136-578). Using the baseline lever
# here would derive... another pill, defeating the point. Using the genuinely-shaped lever makes
# this a fair test of "can a fun silhouette drive a matching housing at render time" — all three
# variants then house the SAME dogbone-family switch, differing only in HOW the housing is made.
LEVER = os.path.join(GEN12, "assets-fallout-pipboy-shapematch_biref", "shuffle_lever.png")


def dilate_alpha(alpha, px):
    """Binary dilation via PIL MaxFilter (odd kernel size ~= 2*px+1)."""
    if px <= 0:
        return alpha
    k = 2 * px + 1
    im = Image.fromarray(alpha)
    return np.asarray(im.filter(ImageFilter.MaxFilter(k)))


def main():
    im = Image.open(LEVER).convert("RGBA")
    a = np.asarray(im)
    alpha = a[:, :, 3]
    binm = (alpha > 100).astype(np.uint8) * 255

    # tight trim (small margin) for the exported lever sprite PNG itself
    ys, xs = np.where(binm > 0)
    tpad = 6
    ty0, ty1 = max(0, ys.min() - tpad), min(binm.shape[0], ys.max() + tpad)
    tx0, tx1 = max(0, xs.min() - tpad), min(binm.shape[1], xs.max() + tpad)
    lever_trim = im.crop((tx0, ty0, tx1, ty1))
    lever_trim.save(os.path.join(HERE, "lever-sprite.png"))
    print(f"[lever] trimmed to {lever_trim.size}")

    # WIDE canvas for dilation: MaxFilter does not grow the canvas, so dilating within the
    # source's OWN tight bounds (the biref cut PNG is already trimmed close to the object, with
    # almost no margin) clips the dilated shape at the canvas edge and saturates housing+rim to
    # solid (the bug this replaced — rim ring collapsed to zero). Fix: paste the tight-trimmed
    # binary silhouette into the CENTRE of a freshly-allocated, genuinely blank canvas sized
    # with room >= the largest dilation radius on every side, then dilate that.
    # dilation kept modest (12%/6% of the short axis, not 22%) so the dogbone WAIST survives —
    # a heavier dilation smooths the waist/lobe contrast away into a near-pill, defeating the
    # point of deriving the housing from a genuinely non-pill silhouette.
    short_axis = min(lever_trim.size)
    housing_px = max(6, int(short_axis * 0.12))
    rim_px = housing_px + max(4, int(short_axis * 0.06))
    wpad = rim_px + 8
    tight_bin = np.asarray(lever_trim.convert("RGBA"))[:, :, 3]
    tight_bin = (tight_bin > 100).astype(np.uint8) * 255
    tw, th = lever_trim.size
    canvas_w, canvas_h = tw + 2 * wpad, th + 2 * wpad
    wide_bin = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
    wide_bin[wpad:wpad + th, wpad:wpad + tw] = tight_bin
    # fill small interior holes (the lever's own attachment-loop cutouts) before deriving the
    # HOUSING — a recessed socket is a solid cavity; two floating unpainted islands inside it
    # would be physically nonsensical. The exported lever sprite itself keeps its real holes.
    from scipy import ndimage as _ndi
    wide_bin = (_ndi.binary_fill_holes(wide_bin > 0).astype(np.uint8)) * 255

    housing_mask = dilate_alpha(wide_bin, housing_px)
    rim_mask = dilate_alpha(wide_bin, rim_px)
    rim_ring = np.clip(rim_mask.astype(int) - housing_mask.astype(int), 0, 255).astype(np.uint8)

    # CSS mask-image needs the shape in the ALPHA channel, not luminance: a plain "L" grayscale
    # PNG has no alpha channel at all (every pixel implicitly opaque), so the browser's default
    # alpha-mode masking saw uniform opacity everywhere and the mask had NO clipping effect
    # (confirmed live — the housing/rim rendered as solid rectangles, not the dogbone). Fix:
    # encode the shape as the ALPHA of an RGBA image (color channels unused/white).
    def _as_alpha_png(mask_u8):
        rgba = np.zeros((*mask_u8.shape, 4), dtype=np.uint8)
        rgba[:, :, :3] = 255
        rgba[:, :, 3] = mask_u8
        return Image.fromarray(rgba, "RGBA")

    _as_alpha_png(housing_mask).save(os.path.join(HERE, "a-housing-mask.png"))
    _as_alpha_png(rim_ring).save(os.path.join(HERE, "a-rim-mask.png"))
    # lever's own offset WITHIN the wide dilation canvas (so the HTML can align them concentrically)
    lever_off = [wpad, wpad]
    import json
    json.dump({"housing_canvas_size": list(housing_mask.shape[::-1]),
                "lever_size": list(lever_trim.size), "lever_offset_in_housing": lever_off,
                "housing_dilate_px": housing_px, "rim_dilate_px": rim_px},
               open(os.path.join(HERE, "a-mask-meta.json"), "w"), indent=1)
    print(f"[mask] lever short-axis={short_axis}px housing_dilate={housing_px}px "
          f"rim_dilate={rim_px}px -> housing {housing_mask.shape} (WxH "
          f"{housing_mask.shape[1]}x{housing_mask.shape[0]}), rim ring "
          f"{int((rim_ring > 0).sum())}px, lever_offset={lever_off}")


if __name__ == "__main__":
    main()
