#!/usr/bin/env python3
"""build_layout — compute pixel placements for the three switch-slot-compare variants and
write compare-data.json for the HTML page to consume. All housing/lever assets were derived
in the SAME native paint-pixel space (both source paints are 2304x3712), so placement is done
in plain pixel coordinates, no fractional rescaling needed."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
meta = json.load(open(os.path.join(HERE, "prep_meta.json")))
mmeta = json.load(open(os.path.join(HERE, "a-mask-meta.json")))

hw, hh = mmeta["housing_canvas_size"]
lw, lh = mmeta["lever_size"]
loff = mmeta["lever_offset_in_housing"]

# ---- A & B share the baseline crop geometry (same crop, same erased device slot) ----
cw_ab, ch_ab = meta["crop_ab_size"]
dx, dy, dw, dh = meta["dev_in_crop_ab"]
dev_cx_ab, dev_cy_ab = (dx + dw / 2) * cw_ab, (dy + dh / 2) * ch_ab
housing_left_ab = dev_cx_ab - hw / 2
housing_top_ab = dev_cy_ab - hh / 2
lever_left_ab = housing_left_ab + loff[0]
lever_top_ab = housing_top_ab + loff[1]

# ---- C: crop its own device rect ----
# NOTE ON A REAL FINDING: regions.json's shuffle device/track bbox (from extract12's level-aware
# walk, calibrated on plain pill/groove shapes) under-captures this dogbone housing's true visual
# extent -- confirmed by direct pixel measurement (dark-recess bbox scanned straight off
# c-backdrop.png): true width ~928px / true centre ~(564,845), vs. the walk-derived device rect's
# centre ~(608,821) at a NARROWER width. The walk's "compact run" + rim-budget heuristics
# (extract12.py's SHUFFLE TRACK + DETENTS block) are tuned for a simple channel and visibly clip
# the round bulb at this shape's right end short. This is placement-invariants-rule territory --
# a pipeline fix belongs in extract12.py's track walk, not here -- but THIS script is throwaway
# demo/compare tooling, not the shipping pipeline, so a direct pixel-measured override is the
# right fix for the page itself. Logged here rather than silently patched.
cw_c, ch_c = meta["crop_c_size"]
# measured directly off a 100px-gridded c-backdrop.png (read by eye against the grid, cross-
# checked twice): the true dogbone spans x=[150,1030] y=[740,1005] -> centre (590,872.5),
# width 880, height 265. The true shape is notably FLATTER (aspect ~3.3) than the housing mask
# derived from the strip lever (aspect ~1.86, 809x436) -- the walk-derived device rect this
# script originally used was both off-centre AND the wrong aspect for this housing, so an
# isotropic scale alone (tried first, still visibly offset) isn't enough; scale x/y independently.
true_center_c = (590.0, 872.5)
true_w_c, true_h_c = 880.0, 265.0
scale_x_c, scale_y_c = true_w_c / hw, true_h_c / hh
housing_left_c = true_center_c[0] - (hw * scale_x_c) / 2
housing_top_c = true_center_c[1] - (hh * scale_y_c) / 2
lever_left_c = housing_left_c + loff[0] * scale_x_c
lever_top_c = housing_top_c + loff[1] * scale_y_c

# travel = lobe-to-lobe slide, matching the shape's two lobe centres found in the column-height
# profile (x~153 and x~561 within the lever's own 683px-wide local space, i.e. the two dogbone
# lobes) so the lever visibly seats lobe-to-lobe rather than an arbitrary fraction. NOTE: this
# is used for C too, not regions.json's walk-derived `detents` -- that field comes from the same
# under-measuring track walk flagged above (calibrated on plain channels, it clips this dogbone's
# extent short), so it isn't a trustworthy travel span here either. The lobe-profile travel is
# the one grounded-in-real-pixels number available; scaled per-variant by that variant's own
# housing scale.
lobe_l_x, lobe_r_x = 153, 561  # within the lever's own local width, from profiling in make_masks
travel_ab = [round(lobe_l_x - lw / 2), round(lobe_r_x - lw / 2)]
travel_c = [round((lobe_l_x - lw / 2) * scale_x_c), round((lobe_r_x - lw / 2) * scale_x_c)]

data = {
    "note": "pixel placements for switch-slot-compare.html; all in native paint-pixel space",
    "a": {"backdrop": "switchslot-compare/clean-backdrop.png", "crop_size": [cw_ab, ch_ab],
          "housing_mask": "switchslot-compare/a-housing-mask.png",
          "rim_mask": "switchslot-compare/a-rim-mask.png",
          "housing_size": [hw, hh], "housing_pos": [round(housing_left_ab), round(housing_top_ab)],
          "lever": "switchslot-compare/lever-sprite.png", "lever_size": [lw, lh],
          "lever_pos": [round(lever_left_ab), round(lever_top_ab)], "travel_x": travel_ab},
    "b": {"backdrop": "switchslot-compare/b-backdrop.png", "crop_size": [cw_ab, ch_ab],
          "lever": "switchslot-compare/lever-sprite.png", "lever_size": [lw, lh],
          "lever_pos": [round(lever_left_ab), round(lever_top_ab)], "travel_x": travel_ab},
    "c": {"backdrop": "switchslot-compare/c-backdrop.png", "crop_size": [cw_c, ch_c],
          "lever": "switchslot-compare/lever-sprite.png",
          "lever_size": [round(lw * scale_x_c), round(lh * scale_y_c)],
          "lever_pos": [round(lever_left_c), round(lever_top_c)], "travel_x": travel_c,
          "_measured_scale_correction_xy": [round(scale_x_c, 3), round(scale_y_c, 3)]},
}
json.dump(data, open(os.path.join(HERE, "compare-data.json"), "w"), indent=1)
print(json.dumps(data, indent=1))
