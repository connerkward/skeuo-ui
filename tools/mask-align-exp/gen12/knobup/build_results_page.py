#!/usr/bin/env python3
"""knobup/build_results_page.py — served results page for the KNOB_POINTER_UP compliance
experiment. Reads ONLY knobup/results.json (written by run_experiment.py) and each gen's
regions.json / biref cap sprite — never re-derives a knob_zero_deg, per verify-outputs-rule §7
and the annotate2.py precedent (tools/mask-align-exp/gen12/knobzero-proof/annotate2.py) this
script's crop-annotation code is adapted from. Writes knobup/index.html.
"""
import os, sys, json, math
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)

# pre-fix (clause OFF, detect-and-counter-rotate-only era) distribution — supplied verbatim by
# the task, the 6 mainline templated skins' knob_zero_deg before this experiment existed.
HISTORICAL = [85.6, 144.0, 95.0, 355.0, 4.0, 359.0]

UPSCALE = 4


def font(size, bold=False):
    names = (["/System/Library/Fonts/Supplemental/Arial Bold.ttf"] if bold else []) + [
        "/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf"]
    for p in names:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def angle_to_xy(cx, cy, R, deg, frac=1.0):
    theta = math.radians(deg)
    return cx + R * frac * math.sin(theta), cy - R * frac * math.cos(theta)


def draw_pointer(draw, cx, cy, R, deg, color, width, r_lo_frac=0.0):
    x0, y0 = angle_to_xy(cx, cy, R, deg, r_lo_frac)
    x1, y1 = angle_to_xy(cx, cy, R, deg, 1.02)
    draw.line([(x0, y0), (x1, y1)], fill=color, width=width)
    ah = 12
    theta = math.radians(deg)
    perp = theta + math.pi / 2
    ax1 = x1 - ah * math.sin(theta) + ah * 0.5 * math.sin(perp)
    ay1 = y1 + ah * math.cos(theta) - ah * 0.5 * math.cos(perp)
    ax2 = x1 - ah * math.sin(theta) - ah * 0.5 * math.sin(perp)
    ay2 = y1 + ah * math.cos(theta) + ah * 0.5 * math.cos(perp)
    draw.polygon([(x1, y1), (ax1, ay1), (ax2, ay2)], fill=color)


def annotate_cap(row):
    """Reads knob_zero_deg + knob_zero_geo FROM the gen's own regions.json (stored, not
    re-derived) and draws the up-target (green, fixed 0°) + the detected pointer (red, stored
    value) on the raw cut cap sprite. Returns the output PNG's relative path, or None."""
    sid = row["id"]
    assets_dir = os.path.join(HERE, f"assets-{sid}")
    biref_dir = assets_dir + "_biref"
    if row.get("recovered_cut"):
        # recovery path (recover_caps.py): sprite is vol_recovered.png; the detector's own
        # angle+geo were stored on the row itself — same no-re-derivation contract.
        kn = "vol"
        zero = row.get("knob_zero_deg")
        geo = row.get("knob_zero_geo")
        src = os.path.join(biref_dir, "vol_recovered.png")
        if not os.path.exists(src):
            return None
    else:
        regions_path = os.path.join(assets_dir, "regions.json")
        if not os.path.exists(regions_path):
            return None
        regj = json.load(open(regions_path))
        kn = next((k for k, v in regj.get("roles", {}).items() if v == "knob"), "vol")
        r = regj.get("regions", {}).get(kn, {})
        zero = r.get("knob_zero_deg")
        geo = r.get("knob_zero_geo")
        src = os.path.join(biref_dir, f"{kn}.png")
        if not os.path.exists(src):
            return None
    im = Image.open(src).convert("RGBA")
    if geo is None:
        cx, cy = im.width / 2.0, im.height / 2.0
        R = min(im.width, im.height) / 2.0
    else:
        cx, cy, R = geo
    im2 = im.resize((im.width * UPSCALE, im.height * UPSCALE), Image.LANCZOS)
    cx2, cy2, R2 = cx * UPSCALE, cy * UPSCALE, R * UPSCALE
    canvas = Image.new("RGBA", im2.size, (18, 18, 22, 255))
    canvas.alpha_composite(im2)
    draw = ImageDraw.Draw(canvas, "RGBA")
    # up-target reference (green, fixed at 0deg — the convention, not measured)
    draw_pointer(draw, cx2, cy2, R2, 0.0, (60, 220, 120, 200), 4, r_lo_frac=0.55)
    if zero is not None:
        draw_pointer(draw, cx2, cy2, R2, zero, (255, 70, 70, 255), 6)
    draw.ellipse([cx2 - 5, cy2 - 5, cx2 + 5, cy2 + 5], fill=(255, 255, 255, 255))
    band_h = 40
    cap = Image.new("RGBA", (canvas.width, band_h), (12, 12, 16, 235))
    cd = ImageDraw.Draw(cap)
    ztxt = "no anomaly (null)" if zero is None else f"{zero:.2f}° (err {row.get('abs_error_from_up'):.1f}°)"
    srcnote = "recovered cut" if row.get("recovered_cut") else f"biref {kn}.png"
    cd.text((14, 8), f"knob_zero_deg = {ztxt} [{srcnote}] — green=up target, red=detected (stored, not re-derived)",
             fill=(255, 190, 190, 255), font=font(16))
    out = Image.new("RGBA", (canvas.width, canvas.height + band_h), (0, 0, 0, 0))
    out.paste(canvas, (0, 0))
    out.paste(cap, (0, canvas.height), cap)
    dst_name = f"{sid}-cap-annotated.png"
    out.convert("RGB").save(os.path.join(HERE, dst_name), quality=95)
    return dst_name


def hist_svg(values, title, color, w=520, h=140):
    """A dumb, dependency-free angular dot-strip: x = angle 0..360 mapped linearly (0/360 both
    at the ends, so 'up' compliance reads as dots clustered at BOTH edges), y = jitter to avoid
    overlap. No binning/KDE (no library, no invented smoothing) — literal stored values plotted."""
    margin = 40
    pw = w - 2 * margin
    dots = []
    for i, v in enumerate(values):
        x = margin + (v / 360.0) * pw
        y = 50 + (i % 5) * 14
        dots.append(f'<circle cx="{x:.1f}" cy="{y}" r="6" fill="{color}" fill-opacity="0.85"/>')
    ticks = "".join(
        f'<line x1="{margin + f*pw:.1f}" y1="{h-30}" x2="{margin + f*pw:.1f}" y2="{h-24}" stroke="#888"/>'
        f'<text x="{margin + f*pw:.1f}" y="{h-10}" font-size="11" fill="#aaa" text-anchor="middle">{int(f*360)}°</text>'
        for f in (0, 0.25, 0.5, 0.75, 1.0))
    band_lo = margin + (350 / 360.0) * pw
    band_hi_wrap = margin + pw
    band_lo2 = margin
    band_hi2 = margin + (10 / 360.0) * pw
    return f'''<svg width="{w}" height="{h}" style="background:#111;border-radius:8px">
      <rect x="{band_lo:.1f}" y="20" width="{band_hi_wrap-band_lo:.1f}" height="{h-50}" fill="#2a5" fill-opacity="0.18"/>
      <rect x="{band_lo2:.1f}" y="20" width="{band_hi2-band_lo2:.1f}" height="{h-50}" fill="#2a5" fill-opacity="0.18"/>
      <line x1="{margin}" y1="{h-30}" x2="{margin+pw}" y2="{h-30}" stroke="#555"/>
      {ticks}
      {"".join(dots)}
      <text x="{margin}" y="16" font-size="13" fill="#ddd">{title}</text>
    </svg>'''


# Visual adjudication of each gen's cap crop (full-res inspection, 2026-07-11/12 — the
# verify-rule §1b close-up pass). The stored detector value stays the METRIC; these notes flag
# where the detector abstained (z below its bar) or where a cut needed recovery.
ADJUDICATION = {
    "knobup-steam-porthole-101": "pointer visually UP; mainline biref missed the cut (parts-tray card), recovered via cell-crop",
    "knobup-steam-porthole-202": "pointer visually at ~3 o'clock — model disobeyed the clause",
    "knobup-steam-porthole-303": "pointer visually at ~100° (right); detector abstained (z=4.3 < 5 bar) — non-compliant either way",
    "knobup-steam-porthole-404": "pointer visually UP — clean compliance",
    "knobup-myst-arcanum-101": "pointer visually ~90-105° (cap cut with a 3/4-perspective CAMERA violation, skews the read)",
    "knobup-myst-arcanum-202": "pointer visually UP but embossed low-contrast; detector abstained (z=4.2 < 5 bar) — visually compliant, unmeasured",
    "knobup-myst-arcanum-303": "keyway notch at ~100° — model disobeyed",
    "knobup-myst-arcanum-404": "wedge notch points DOWN (~162°) — model disobeyed",
}

CONCLUSION = """
<b>Compliance is LOW: 2/8 detector-measured within ±10° of up</b> (steam-404 at 0.10°, steam-101 at
0.51° via recovered cut); +1 more (myst-202) is visually up but embossed too low-contrast for the
detector's z-bar → <b>3/8 by best adjudication</b>. The threshold for flipping the architecture was
6/8. <b>And the baseline was NOT random:</b> the task's historical pre-fix values (85.6°, 144°, 95°,
355°, 4°, 359°) are bimodal — 3/6 already within ±10° of up (errors 5°, 4°, 1°) — so clause-ON
(2-3/8, 25-38%) shows <b>no improvement over clause-OFF (3/6, 50%)</b> at these sample sizes. The
model's competing prior (a right-side pointer at ~60-110°, seen in 4/8 gens here and 3/6
historically) is not overridden by one light sentence.
<br><br><b>Verdict: detect-and-counter-rotate stays PRIMARY. KNOB_POINTER_UP stays default OFF</b> —
the clause is not demonstrably harmful, but it is not demonstrably a useful prior either, and it is
not free (prompt bulk costs quality, per the bproof lesson). No build_player.py change is specced —
the counter-rotation fallback demotion is moot at this compliance level.
"""


def main():
    rows = json.load(open(os.path.join(HERE, "results.json")))
    for r in rows:
        r["_crop"] = annotate_cap(r)

    n = len(rows)
    n_ok = sum(1 for r in rows if r["compliant_10deg"])
    n_hist_ok = sum(1 for v in HISTORICAL if min(v, 360 - v) <= 10.0)

    cards = []
    for r in rows:
        badge = ("PASS", "#2a5") if r["compliant_10deg"] else ("FAIL", "#c33")
        img = (f'<img src="{r["_crop"]}" style="width:100%;border-radius:6px" loading="lazy">'
               if r["_crop"] else '<div style="padding:2rem;color:#888">no crop (extraction failed)</div>')
        err = r.get("abs_error_from_up")
        errtxt = f'{err:.1f}°' if err is not None else "n/a"
        zd = r.get("knob_zero_deg")
        zdtxt = f'{zd:.2f}' if isinstance(zd, float) else str(zd)
        adj = ADJUDICATION.get(r["id"], "")
        cards.append(f'''
        <div style="background:#1a1a1e;border-radius:10px;padding:10px;border:1px solid #333">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <b>{r["theme"]} · seed {r["seed"]}</b>
            <span style="background:{badge[1]};color:#fff;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:700">{badge[0]}</span>
          </div>
          {img}
          <div style="font-size:13px;color:#bbb;margin-top:6px">knob_zero_deg = {zdtxt}  ·  error from up = {errtxt}</div>
          <div style="font-size:12px;color:#8a8;margin-top:4px">adjudication: {adj}</div>
        </div>''')

    html = f'''<!doctype html><html><head><meta charset="utf-8">
<title>KNOB_POINTER_UP compliance — knobup experiment</title>
<style>
body{{font-family:-apple-system,Helvetica,Arial,sans-serif;background:#0d0d10;color:#eee;margin:0;padding:24px;max-width:1100px}}
h1{{font-size:20px}} h2{{font-size:16px;margin-top:2rem;border-top:1px solid #333;padding-top:1rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;margin-top:1rem}}
.banner{{background:#1a1a1e;border:1px solid #333;border-radius:8px;padding:12px 16px;font-size:13px;color:#aaa;margin-bottom:1rem}}
code{{background:#222;padding:1px 5px;border-radius:4px}}
</style></head><body>
<h1>KNOB_POINTER_UP compliance experiment — {n_ok}/{n} compliant (±10° of up)</h1>
<div class="banner">
  Model: <code>fal-ai/gemini-3-pro-image-preview/edit</code> (Vertex AI direct, PAINT_VERTEX=True) &middot;
  8 gens &times; ~$0.24&ndash;0.30/4K image &asymp; <b>$2</b> total &middot; extraction/biref: $0 (local, BIREF_LOCAL) &middot;
  detector: <code>knob_angle.py::detect_from_sprite</code> (the shared, independent verifier extract12.py's mainline pipeline uses)
</div>
<p>User insight (verbatim): "maybe instead of all this bullshit [detect-and-counter-rotate] you can
just specify in prompt that the tick on knob face should point upwards 0 degrees?" — this experiment
tests whether the paint model actually OBEYS that instruction, measured independently by the
existing detector, not by re-asking the model.</p>

<h2>Before / after angular distribution</h2>
<p style="font-size:13px;color:#999">Dots = individual detected <code>knob_zero_deg</code> values (0&deg; = up,
clockwise). Green bands mark the &plusmn;10&deg; compliance window at both wrap edges.</p>
<div style="display:flex;gap:24px;flex-wrap:wrap">
  <div>{hist_svg(HISTORICAL, f"BEFORE — pre-fix, clause OFF (n=6, {n_hist_ok}/6 within ±10°)", "#c33")}</div>
  <div>{hist_svg([r["knob_zero_deg"] for r in rows if r["knob_zero_deg"] is not None], f"AFTER — KNOB_POINTER_UP ON (n={sum(1 for r in rows if r['knob_zero_deg'] is not None)}, {n_ok}/{n} within ±10°)", "#39c")}</div>
</div>

<h2>Per-generation crops (angle drawn from stored regions.json values, never re-derived)</h2>
<div class="grid">{"".join(cards)}</div>

<h2>Conclusion</h2>
<div class="banner" id="conclusion" style="font-size:14px;color:#ddd">{CONCLUSION}</div>
</body></html>'''
    open(os.path.join(HERE, "index.html"), "w").write(html)
    print(f"wrote {os.path.join(HERE, 'index.html')}  ({n_ok}/{n} compliant, historical {n_hist_ok}/6)")


if __name__ == "__main__":
    main()
