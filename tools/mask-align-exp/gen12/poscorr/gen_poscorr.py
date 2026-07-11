#!/usr/bin/env python3
"""gen_poscorr -- generate one position-mask-correlation gen (arm x seed) via Vertex.

Reuses the proven single-request Vertex call pattern from
twoimg/genskin_twoimg.py:edit_vertex_multi() verbatim (just imported, not re-derived) --
it already handles N inline_data image parts + text, seed, 429 backoff. This experiment
only ever sends ONE image (the template), so it's a 1-element image_paths list.

Usage: python3 gen_poscorr.py <arm: position|numbered|color> <seed:int> [--blueprint-only]
Writes poscorr/assets-<arm>-<seed>/{template.png,paint.png,mask.png,joint.png,results.json}
"""
import os, sys, io, json, time, base64

HERE = os.path.dirname(os.path.abspath(__file__))
TWOIMG = os.path.join(os.path.dirname(HERE), "twoimg")
sys.path.insert(0, TWOIMG)
from genskin_twoimg import edit_vertex_multi, MODEL  # proven Vertex call, imported not re-derived

sys.path.insert(0, HERE)
from template import build_template, COL_W, H, N, BAND_H, GUIDE_COLORS, REGION_ORDER
from PIL import Image

ARMS = ("position", "numbered", "color")


def build_prompt(arm):
    common_head = (
        f"ONE image provided, two side-by-side columns of EQUAL size, output at 5:4, "
        f"{2*COL_W}x{H}px geometry. LEFT column: a plain neutral grey PANEL on a light "
        f"backdrop containing exactly {N} small abstract flat-colour REGIONS of different "
        f"shapes and sizes (circles, an oval, rounded rectangles, a diamond) -- purely "
        f"geometric shapes, not icons, not letters, not any recognizable object. RIGHT "
        f"column: on a pure BLACK background, a vertical stack of exactly {N} EQUAL-HEIGHT "
        f"horizontal CELLS separated by thin grey divider lines, numbered here only for your "
        f"reference as cell 1 (topmost) through cell {N} (bottommost), reading top to bottom. "
        f"All {N} cells are currently EMPTY (pure black).\n"
    )
    task_common = (
        f"YOUR TASK: for every cell, identify which region on the LEFT panel is ASSIGNED to "
        f"it (rule below), then paint INSIDE that cell ONLY a single SOLID WHITE FILLED "
        f"silhouette that matches that region's exact shape and size (same shape family, same "
        f"proportions), centered in the cell, leaving generous black margin around it. Do this "
        f"for all {N} cells -- one silhouette per cell, matching all {N} regions. Do not resize, "
        f"rotate, or distort the shape; do not merge, skip, or duplicate any region. Every "
        f"silhouette must be plain solid WHITE on black, regardless of the source region's own "
        f"colour -- the mask column encodes SHAPE and CELL ASSIGNMENT only, never colour.\n"
    )
    no_extra = (
        "Do not alter the LEFT panel's regions in any way (same shapes, same positions, same "
        "neutral fill). ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS anywhere in either column.\n"
    )

    if arm == "position":
        rule = (
            "ASSIGNMENT RULE -- POSITION ONLY, no colours or numbers exist anywhere in this "
            "image or in this instruction: read the LEFT panel's regions in READING ORDER -- "
            f"top-to-bottom by row, left-to-right within each row (there are {N//2} rows of 2 "
            f"regions each). The 1st region in reading order is ASSIGNED to cell 1 (topmost), "
            f"the 2nd region to cell 2, and so on down to the {N}th region assigned to cell "
            f"{N} (bottommost). This reading-order correspondence is the ONLY signal for which "
            "shape goes in which cell -- there are no colours, tags, or numbers marking the "
            "correspondence anywhere; you must determine each region's rank purely from its "
            "row/column position on the panel.\n"
        )
        no_extra += ("Do NOT print any numbers, digits, tick-marks, or labels anywhere in "
                      "either column -- neither on the panel nor in the mask cells.\n")
    elif arm == "numbered":
        rule = (
            "ASSIGNMENT RULE -- NUMBER TAGS: each region on the LEFT panel carries a small "
            "printed number tag (1.." + str(N) + ") on top of it, and each cell in the RIGHT "
            "column carries the matching printed number tag near its left edge. A region is "
            "ASSIGNED to the cell that carries the SAME number as the region's own tag (region "
            "tagged '3' -> cell tagged '3').\n"
        )
        no_extra += (
            "The number tags in BOTH columns are drafting/reference marks ONLY -- like "
            "masking tape with a grease-pencil number, used purely so you can match region to "
            "cell -- and MUST NOT appear in your finished output. Your output must contain "
            "ZERO printed numbers, digits, or tags anywhere, on the panel OR in the mask "
            "cells: paint the panel exactly as given but with its number tags removed/absent, "
            "and paint each mask cell's silhouette with NO number tag surviving in it.\n"
        )
    else:  # color
        names = "; ".join(f"{GUIDE_COLORS[n][1]}" for n in REGION_ORDER)
        rule = (
            "ASSIGNMENT RULE -- COLOUR KEY: each region on the LEFT panel is filled a solid "
            f"guide colour ({names}, one per region, in reading order), and each cell in the "
            "RIGHT column carries a small colour SWATCH chip near its left edge. A region is "
            "ASSIGNED to the cell whose swatch matches the region's own fill colour (a "
            "PURE RED region -> the cell with the PURE RED swatch).\n"
        )
        no_extra += (
            "The colour swatch chips in the RIGHT column are drafting/reference marks ONLY -- "
            "used purely so you can match region to cell by colour -- and MUST NOT appear in "
            "your finished output: paint each mask cell's silhouette in plain SOLID WHITE "
            "(never in the region's or swatch's own colour) with NO swatch chip surviving in "
            "it. Do NOT change the LEFT panel regions' own guide colours (keep them as given).\n"
        )

    return common_head + rule + task_common + no_extra


def main():
    arm = sys.argv[1]
    seed = int(sys.argv[2])
    assert arm in ARMS, f"arm must be one of {ARMS}"
    tag = f"{arm}-{seed}"
    OUT = os.path.join(HERE, f"assets-{tag}")
    os.makedirs(OUT, exist_ok=True)

    img, gt = build_template(arm)
    tpath = os.path.join(OUT, "template.png")
    img.save(tpath)
    prompt = build_prompt(arm)
    res = {"arm": arm, "seed": seed, "model": MODEL, "N": N, "col_w": COL_W, "H": H,
           "band_h": BAND_H, "prompt": prompt, "prompt_len": len(prompt), "ground_truth": gt}
    json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)

    if "--blueprint-only" in sys.argv:
        print(f"[blueprint-only] {tag} prompt {len(prompt)} chars -> {OUT}")
        return

    t = time.time()
    out = edit_vertex_multi([tpath], prompt, seed)
    open(os.path.join(OUT, "joint.png"), "wb").write(out)
    im = Image.open(io.BytesIO(out)).convert("RGB")
    w, h = im.size
    half = w // 2
    im.crop((0, 0, half, h)).save(os.path.join(OUT, "paint.png"))
    im.crop((half, 0, w, h)).save(os.path.join(OUT, "mask.png"))
    res["dims"] = [w, h]
    json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)
    print(f"[gen] {tag} {time.time()-t:.0f}s dims={w}x{h} -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
