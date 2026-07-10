#!/usr/bin/env python3
"""Build the standardized per-theme asset set for ALL bproof themes:
  gen12-<id>-device.png / -disp.jpg   (device-area crop of the shipping paint.png,
                                        top devFrac fraction — same construction
                                        used for the original 2 themes)
  froggo-<id>-disp.jpg                (web-size preview of the froggo render)
  crop-<id>-{buttons,knob,slider,screen}-{gen12,froggo}.png
      — matched close-up pairs, boxes computed from regions.json's normalized
        control bboxes (union for buttons cluster, vol for knob, seek for slider,
        visualizer+album_art union for screen), generously padded, then mapped
        onto BOTH the gen12 device crop and the froggo render at each image's own
        resolution. This generalizes the crop pairs across every theme instead of
        hand-picked pixel boxes per theme (only the original 2 themes were
        hand-picked; this script supersedes that for all themes going forward).

IMPORTANT (verified against extract12.py, GH/GW = paint.png's FULL shape, line
"GH, GW = paintg.shape" reading paint.png not a device-only crop): every
regions.json "device" bbox is a fraction of the FULL paint.png canvas (e.g.
3712 tall), NOT of the devFrac-cropped device image (e.g. 2784 tall) — even
though the device crop and the full paint share the same top-left origin and
pixel scale (the crop is just the top devFrac rows, unshifted). So fractional
boxes must be denominated against the FULL paint height, then the resulting
pixel y is valid as-is against the (unshifted) device crop. Using the device
crop's own height as the denominator silently shifts every box up by ~1/3 of
the image (caught 2026-07-10 by cropping "vol" and landing on the play/pause
button instead of the knob socket — see verify-outputs-rule).

Idempotent: skips any output file that already exists, so re-running after adding
a new theme only builds what's missing. Delete stale crop-*.png files before
re-running if the fractional-box interpretation ever changes again.
"""
import json, os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)

THEMES = ["steam-porthole", "diablo-gothic", "fa-pod", "fallout-vault", "wc-goldshield", "claymation"]
PAD = 0.55  # fractional padding added to each side of a control's own box


def union_box(regions, keys):
    """Union of regions.json "device" boxes — fractions of the FULL paint.png
    canvas (see module docstring). Returns (x0,y0,x1,y1) in that same frame."""
    xs0, ys0, xs1, ys1 = [], [], [], []
    for k in keys:
        x, y, w, h = regions[k]["device"]
        xs0.append(x); ys0.append(y); xs1.append(x + w); ys1.append(y + h)
    return min(xs0), min(ys0), max(xs1), max(ys1)


def pad_box(box, pad, w_lim, h_lim):
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    x0 -= bw * pad; x1 += bw * pad
    y0 -= bh * pad; y1 += bh * pad
    return max(0, x0), max(0, y0), min(w_lim, x1), min(h_lim, y1)


def to_px_fullpaint(fbox, W, H):
    """Box denominated in the full-paint.png fraction frame -> pixel coords in
    the (unshifted, top-anchored) device crop of the same theme."""
    x0, y0, x1, y1 = fbox
    return (int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H))


def to_px_devrel(fbox, devFrac, W, H):
    """Box denominated in the full-paint.png fraction frame -> pixel coords in
    an UNRELATED image (the froggo render) that depicts roughly the same device
    framing as the devFrac-cropped area, by first converting y to a
    device-crop-relative fraction (y / devFrac) before scaling to W,H. This is
    an approximation (froggo picked its own layout freely — documented
    confound), not an exact measurement."""
    x0, y0, x1, y1 = fbox
    y0r, y1r = y0 / devFrac, y1 / devFrac
    return (int(x0 * W), int(y0r * H), int(x1 * W), int(y1r * H))


def disp(src_path, dst_path, width=1400, quality=90):
    if os.path.exists(dst_path):
        return
    im = Image.open(src_path).convert("RGB")
    w, h = im.size
    if w > width:
        im = im.resize((width, round(h * width / w)), Image.LANCZOS)
    im.save(dst_path, quality=quality)


def box_wh(b):
    return (b[0], b[1], b[0] + b[2], b[1] + b[3])


def main():
    for sid in THEMES:
        results = json.load(open(os.path.join(GEN12, f"assets-{sid}", "results.json")))
        regions = json.load(open(os.path.join(GEN12, f"assets-{sid}", "regions.json")))["regions"]
        devFrac = results["devFrac"]

        paint = Image.open(os.path.join(GEN12, f"assets-{sid}", "paint.png"))
        GWfull, GHfull = paint.size  # denominator for every regions.json "device" fraction

        # --- gen12 device crop (top devFrac of paint.png, unshifted) ---
        dev_png = os.path.join(HERE, f"gen12-{sid}-device.png")
        if not os.path.exists(dev_png):
            dev = paint.crop((0, 0, GWfull, round(GHfull * devFrac)))
            dev.save(dev_png)
            print(f"[{sid}] wrote {dev_png} {dev.size}")
        disp(dev_png, os.path.join(HERE, f"gen12-{sid}-device-disp.jpg"))

        froggo_png = os.path.join(HERE, f"froggo-{sid}.png")
        if not os.path.exists(froggo_png):
            print(f"[{sid}] SKIP — no froggo render yet ({froggo_png})")
            continue
        disp(froggo_png, os.path.join(HERE, f"froggo-{sid}-disp.jpg"))

        fW, fH = Image.open(froggo_png).size

        pairs = {
            "buttons": union_box(regions, ["playpause", "prev", "next", "repeat", "queue"]),
            "knob": box_wh(regions["vol"]["device"]),
            "slider": box_wh(regions["seek"]["device"]),
        }
        if "visualizer" in regions and "album_art" in regions:
            pairs["screen"] = union_box(regions, ["visualizer", "album_art"])

        g = Image.open(dev_png)
        f = Image.open(froggo_png)
        for key, fbox in pairs.items():
            # pad in the full-paint fraction frame: x in [0,1], y in [0,devFrac]
            fbox_p = pad_box(fbox, PAD, 1.0, devFrac)
            g_out = os.path.join(HERE, f"crop-{sid}-{key}-gen12.png")
            f_out = os.path.join(HERE, f"crop-{sid}-{key}-froggo.png")
            if not os.path.exists(g_out):
                g.crop(to_px_fullpaint(fbox_p, GWfull, GHfull)).save(g_out)
            if not os.path.exists(f_out):
                f.crop(to_px_devrel(fbox_p, devFrac, fW, fH)).save(f_out)
        print(f"[{sid}] crops: {list(pairs)}")


if __name__ == "__main__":
    main()
