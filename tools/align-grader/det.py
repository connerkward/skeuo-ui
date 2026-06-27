#!/usr/bin/env python3
"""Deterministic (no-LLM) half of the button-alignment grader.

grade_det(frame_path, template_path) -> {key: {bind, presence, offset, aligned}}

How it works (independent of any LLM, per verify-outputs-rule):
- For each interactive region, take a WINDOW = rect expanded 60% per side, clamped.
- Build a saliency map = local gradient magnitude of luminance, computed only over
  OPAQUE device pixels (alpha > 20). Transparent background contributes zero, so the
  cut-out edge of the body does not masquerade as a control feature.
- presence = mean saliency inside the rect / mean saliency over the whole opaque body.
    ~>1  : a real, detailed control feature sits in the rect.
    ~<0.6: the rect covers blank/flat body (a missing or mis-placed control).
- offset = distance from rect CENTER to the saliency-weighted CENTROID inside the
    window, normalized by 0.5*max(rect_w_px, rect_h_px), clipped to 1.
    0 = the detail is centered in the rect; 1 = it sits a full half-extent away.
- aligned = (presence >= 0.8) and (offset <= 0.5).

Threshold rationale:
- presence >= 0.8: a control should be AT LEAST as detailed as the average body
    pixel. 1.0 would demand strictly-above-average and reject low-contrast-but-present
    controls; 0.8 leaves headroom for soft/glossy controls while still rejecting the
    blank-body case (which lands well under 0.6 in practice).
- offset <= 0.5: the feature centroid must fall within half an extent of the rect
    center, i.e. the detected detail is substantially inside the box rather than
    straddling its edge. 0.5 tolerates honest centroid wobble from asymmetric
    highlights/shadows without passing a feature that has slid out of the box.

CLI: python det.py <frame> <template>  -> prints JSON.
"""
import sys
import json

import numpy as np
from PIL import Image

from common import (
    load_template, interactive_regions, rect_to_px,
)

EPS = 1e-6


def _luma_and_alpha(frame_path):
    img = Image.open(frame_path).convert("RGBA")
    arr = np.asarray(img).astype(np.float32)
    r, g, b, a = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    opaque = a > 20.0
    return luma, opaque, img.width, img.height


def _saliency(luma, opaque):
    """Local gradient magnitude of luminance over opaque pixels only.

    abs diff with the right and down neighbor (forward differences), masked so
    transparent pixels and the body cut-edge contribute zero gradient.
    """
    H, W = luma.shape
    # Zero out transparent pixels so the body edge isn't a giant gradient cliff.
    lum = np.where(opaque, luma, 0.0)

    dx = np.zeros_like(lum)
    dy = np.zeros_like(lum)
    dx[:, :-1] = np.abs(lum[:, 1:] - lum[:, :-1])
    dy[:-1, :] = np.abs(lum[1:, :] - lum[:-1, :])
    grad = np.sqrt(dx * dx + dy * dy)

    # Only count gradient where this pixel and the contributing neighbor are
    # both opaque, so the transparent boundary never registers as a feature.
    op = opaque.astype(np.float32)
    # Pixel is valid if opaque and has at least one opaque in-bounds neighbor.
    vx = np.zeros_like(op); vx[:, :-1] = op[:, :-1] * op[:, 1:]
    vy = np.zeros_like(op); vy[:-1, :] = op[:-1, :] * op[1:, :]
    valid = np.clip(vx + vy, 0.0, 1.0) * op
    grad = grad * valid
    return grad


def grade_det(frame_path, template_path):
    template = load_template(template_path)
    luma, opaque, W, H = _luma_and_alpha(frame_path)
    sal = _saliency(luma, opaque)

    # Body baseline: mean saliency over opaque pixels.
    body_mask = opaque
    body_count = float(body_mask.sum())
    body_mean = float(sal[body_mask].sum() / (body_count + EPS)) if body_count > 0 else 0.0

    results = {}
    for key, region in interactive_regions(template):
        rect = region["rect"]
        rx0, ry0, rx1, ry1 = rect_to_px(rect, W, H)
        rw = rx1 - rx0
        rh = ry1 - ry0

        # --- presence: mean saliency in rect / body mean -------------------
        rect_sal = sal[ry0:ry1, rx0:rx1]
        rect_op = opaque[ry0:ry1, rx0:rx1]
        rect_op_count = float(rect_op.sum())
        if rect_op_count > 0:
            rect_mean = float(rect_sal[rect_op].sum() / (rect_op_count + EPS))
        else:
            rect_mean = 0.0
        presence = rect_mean / (body_mean + EPS)

        # --- offset: window saliency-weighted centroid vs rect center ------
        ew = int(round(rw * 0.6))
        eh = int(round(rh * 0.6))
        wx0 = max(0, rx0 - ew); wy0 = max(0, ry0 - eh)
        wx1 = min(W, rx1 + ew); wy1 = min(H, ry1 + eh)
        win = sal[wy0:wy1, wx0:wx1]

        rect_cx = (rx0 + rx1) / 2.0
        rect_cy = (ry0 + ry1) / 2.0

        wsum = float(win.sum())
        if wsum > EPS:
            ys, xs = np.mgrid[wy0:wy1, wx0:wx1]
            cx = float((xs * win).sum() / wsum)
            cy = float((ys * win).sum() / wsum)
            dist = ((cx - rect_cx) ** 2 + (cy - rect_cy) ** 2) ** 0.5
            norm = 0.5 * max(rw, rh)
            offset = min(1.0, dist / (norm + EPS))
        else:
            # No saliency anywhere in the window -> nothing to align to.
            offset = 1.0

        aligned = (presence >= 0.8) and (offset <= 0.5)

        results[key] = {
            "bind": region.get("bind") or region.get("id"),
            "presence": round(presence, 4),
            "offset": round(offset, 4),
            "aligned": bool(aligned),
        }
    return results


def main():
    if len(sys.argv) != 3:
        print("usage: python det.py <frame.png> <template.json>", file=sys.stderr)
        sys.exit(2)
    res = grade_det(sys.argv[1], sys.argv[2])
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
