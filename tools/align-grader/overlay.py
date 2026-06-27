#!/usr/bin/env python3
"""Labeled overlay for the button-alignment grader (per label-overlays-rule).

build_overlay(frame_path, template_path, out_path, verdicts=None):
  - composite the RGBA frame over neutral gray (70,70,80) so the body is visible,
  - draw each INTERACTIVE control's rect, colored by kind, with a dark-backed
    legible label "<bind>·<kind>",
  - if verdicts {key_or_bind: bool} given, tint each box green(aligned)/red(mis)
    and append the verdict glyph to the label,
  - save a JPEG to out_path; return the list of graded controls (the records the
    overlay drew, so callers can see exactly what was annotated).

CLI: python overlay.py <frame> <template> <out>
"""
import sys

from PIL import Image, ImageDraw, ImageFont

from common import (
    load_template, interactive_regions, rect_to_px, bind_label, KIND_COLOR,
)

BG = (70, 70, 80)
GREEN = (60, 220, 110)
RED = (235, 70, 70)


def _font(size):
    for path in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _text_size(draw, text, font):
    try:
        l, t, r, b = draw.textbbox((0, 0), text, font=font)
        return r - l, b - t
    except Exception:
        return draw.textlength(text, font=font), font.size


def _verdict_for(verdicts, key, region):
    if not verdicts:
        return None
    if key in verdicts:
        return verdicts[key]
    bind = region.get("bind")
    if bind in verdicts:
        return verdicts[bind]
    return None


def build_overlay(frame_path, template_path, out_path, verdicts=None):
    template = load_template(template_path)
    frame = Image.open(frame_path).convert("RGBA")
    W, H = frame.size

    canvas = Image.new("RGBA", (W, H), BG + (255,))
    canvas.alpha_composite(frame)
    canvas = canvas.convert("RGB")
    draw = ImageDraw.Draw(canvas, "RGBA")

    font_size = max(14, int(round(H * 0.012)))
    font = _font(font_size)
    lw = max(2, int(round(H * 0.0025)))

    graded = []
    for key, region in interactive_regions(template):
        rect = region["rect"]
        x0, y0, x1, y1 = rect_to_px(rect, W, H)
        kind = region.get("kind", "?")
        base = KIND_COLOR.get(kind, (200, 200, 200))

        verdict = _verdict_for(verdicts, key, region)
        if verdict is True:
            box_color = GREEN
        elif verdict is False:
            box_color = RED
        else:
            box_color = base

        # Tint fill (faint) + crisp outline.
        draw.rectangle([x0, y0, x1, y1], fill=box_color + (40,))
        draw.rectangle([x0, y0, x1, y1], outline=box_color + (255,), width=lw)

        label = bind_label(region)
        if verdict is True:
            label += " [OK]"
        elif verdict is False:
            label += " [X]"

        tw, th = _text_size(draw, label, font)
        pad = 3
        lx0 = x0
        ly0 = y0 - th - 2 * pad
        if ly0 < 0:  # would clip off the top -> put label inside the box top
            ly0 = y0 + 1
        # dark backing pill for legibility over any art
        draw.rectangle(
            [lx0, ly0, lx0 + tw + 2 * pad, ly0 + th + 2 * pad],
            fill=(15, 15, 20, 220),
        )
        draw.text((lx0 + pad, ly0 + pad), label, fill=(255, 255, 255, 255), font=font)

        graded.append({
            "key": key,
            "bind": region.get("bind") or region.get("id"),
            "kind": kind,
            "rect_px": [x0, y0, x1, y1],
            "verdict": verdict,
        })

    canvas.save(out_path, "JPEG", quality=88)
    return graded


def main():
    if len(sys.argv) != 4:
        print("usage: python overlay.py <frame.png> <template.json> <out.jpg>",
              file=sys.stderr)
        sys.exit(2)
    graded = build_overlay(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f"wrote {sys.argv[3]} with {len(graded)} interactive controls")


if __name__ == "__main__":
    main()
