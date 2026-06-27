"""Shared helpers for the align-grader (deterministic + vlm halves honor this).

SEAM CONTRACT:
- Interactive controls = regions whose kind is in INTERACTIVE_KINDS.
- rect (normalized) -> frame pixels: [x*W, y*H, w*W, h*H].
- Records are keyed by a UNIQUE key (region id) but always carry `bind`.
  (`bind` alone is not unique: an EQ has 6 regions all bound to "eqBand".)
"""
import json

INTERACTIVE_KINDS = {
    "button", "knob", "toggle",
    "slider-h", "slider-v", "slider-arc", "slider-path",
    "segmented", "xy",
}

# Box color per kind (RGB). Display/flourish kinds are skipped, not colored.
KIND_COLOR = {
    "button":     (80, 200, 255),
    "knob":       (255, 180, 60),
    "toggle":     (180, 120, 255),
    "slider-h":   (120, 230, 130),
    "slider-v":   (120, 230, 130),
    "slider-arc": (90, 210, 170),
    "slider-path": (90, 210, 170),
    "segmented":  (255, 130, 160),
    "xy":         (240, 230, 90),
}


def load_template(template_path):
    with open(template_path) as f:
        return json.load(f)


def interactive_regions(template):
    """Yield (key, region) for every interactive region, in template order.

    key is the region's unique id (falls back to a synthesized one). The
    record itself carries `bind` per the seam contract; the key just keeps
    same-bind siblings (EQ bands) from clobbering each other.
    """
    out = []
    for i, r in enumerate(template.get("regions", [])):
        if r.get("kind") not in INTERACTIVE_KINDS:
            continue
        key = r.get("id") or r.get("bind") or f"region{i}"
        out.append((key, r))
    return out


def rect_to_px(rect, W, H):
    """Normalized rect -> integer pixel box (x0, y0, x1, y1), clamped to image."""
    x0 = rect["x"] * W
    y0 = rect["y"] * H
    x1 = (rect["x"] + rect["w"]) * W
    y1 = (rect["y"] + rect["h"]) * H
    x0i = max(0, min(W - 1, int(round(x0))))
    y0i = max(0, min(H - 1, int(round(y0))))
    x1i = max(x0i + 1, min(W, int(round(x1))))
    y1i = max(y0i + 1, min(H, int(round(y1))))
    return x0i, y0i, x1i, y1i


def bind_label(region):
    """Human label for a region: its bind (or id) plus kind."""
    name = region.get("bind") or region.get("id") or "?"
    return f"{name}·{region.get('kind', '?')}"
