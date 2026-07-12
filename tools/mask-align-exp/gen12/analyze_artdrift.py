#!/usr/bin/env python3
"""analyze_artdrift — $0 analysis (no new generations) answering the pre-review triage
question: are the 3 drift-gate album_art fails (fallout-pipboy, steam-porthole,
wmp-quicksilver; commit 14d1d51c) a systematic layout-archetype weakness, or random
variance? Reads existing regions.json/paint.png/mask.png across the mainline roster PLUS
the driftbisect/driftbisect2/servingbisect experiment gens (28 extra templated data
points, same theme families, different seeds/prompts/serving paths) and:

  1. Computes the drift VECTOR (dx, dy px + angle) for every control in every templated
     gen, template-centre vs detected-device-centre (twoimg/roster_audit.py's
     drift_table(), same metric the drift gate uses — not re-derived).
  2. For album_art + visualizer specifically, tests hypothesis (a) identity SWAP: does
     detected album_art sit closer to the TEMPLATE visualizer slot than its own template
     slot (and vice versa)?
  3. Tests hypothesis (c) mask-vs-refit: for each gen, does the MASK blob centroid (BiRefNet
     alpha, if the _biref sidecar exists) agree with the template, while the regionRefit
     (regs[k].device, the shape-fit that becomes the final placement) disagrees? That would
     mean the paint is fine and extract12's refit is the bug, not the model.
  4. Writes artdrift_data.json (consumed by artdrift.html) with per-gen per-control vectors,
     swap-test verdicts, and crops (paths only — the HTML crops via <canvas> from the real
     paint.png/mask.png, no new PNGs baked).

Usage: python3 analyze_artdrift.py   (writes artdrift_data.json)
"""
import json, os, glob, math
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))

# mainline roster: 6 templated skins (3 PASS, 3 FAIL per the live drift gate, commit 14d1d51c)
MAINLINE = [
    ("mainline", "fa-pod", "assets-fa-pod"),
    ("mainline", "fallout-pipboy", "assets-fallout-pipboy"),
    ("mainline", "ps1-crunchy", "assets-ps1-crunchy"),
    ("mainline", "steam-porthole", "assets-steam-porthole"),
    ("mainline", "wc-goldshield", "assets-wc-goldshield"),
    ("mainline", "wmp-quicksilver", "assets-wmp-quicksilver"),
]

def _glob_bisect():
    out = []
    for d in sorted(glob.glob("driftbisect/assets-bisect-*")):
        if d.endswith("_biref"): continue
        base = os.path.basename(d)
        out.append(("driftbisect", base, d))
    for d in sorted(glob.glob("driftbisect2/assets-*")):
        if d.endswith("_biref"): continue
        base = os.path.basename(d)
        out.append(("driftbisect2", base, d))
    for d in sorted(glob.glob("servingbisect/assets-*")):
        if d.endswith("_biref"): continue
        base = os.path.basename(d)
        out.append(("servingbisect", base, d))
    return out

ALL_DIRS = MAINLINE + _glob_bisect()

# archetype detection from template centres (genskin.py LAYOUTS: vpod album_art x=0.5,
# hcapsule album_art x=0.28) -- read from the gen's OWN template dict, not hardcoded per skin,
# so a bisect gen that regenerated under a different layout is still classified correctly.
def archetype_of(template):
    aa = template.get("album_art")
    if not aa: return "unknown"
    return "vpod" if aa[0] > 0.39 else "hcapsule"


def drift_vec(t, dev, W, H):
    cx, cy = dev[0] + dev[2] / 2, dev[1] + dev[3] / 2
    dxp, dyp = (cx - t[0]) * W, (cy - t[1]) * H
    mag = (dxp ** 2 + dyp ** 2) ** 0.5
    ang = math.degrees(math.atan2(dyp, dxp))  # 0=right,90=down(image y+),180/-180=left,-90=up
    return {"dx_px": round(dxp, 1), "dy_px": round(dyp, 1), "mag_px": round(mag, 1),
            "angle_deg": round(ang, 1), "det_center_frac": [round(cx, 4), round(cy, 4)]}


def mask_blob_centroid(mask_path, key_rgb, tol=40):
    """Centroid of the BiRefNet-cut region whose paint colour matches key_rgb (the guide-key
    baked for this control), restricted to alpha>0 pixels -- i.e. where the MODEL painted a
    blob for this control, independent of extract12's later shape-refit. Returns frac coords
    or None if no matching pixels (control's guide colour wasn't isolable in the cut)."""
    if not os.path.exists(mask_path) or key_rgb is None:
        return None
    im = Image.open(mask_path).convert("RGBA")
    arr = np.asarray(im)
    H, W = arr.shape[:2]
    alpha = arr[..., 3] > 10
    if not alpha.any():
        return None
    rgb = arr[..., :3].astype(int)
    kr = np.array(key_rgb, dtype=int)
    dist = np.sqrt(((rgb - kr) ** 2).sum(axis=-1))
    hit = alpha & (dist < tol)
    if hit.sum() < 50:
        return None
    ys, xs = np.nonzero(hit)
    return [round(float(xs.mean()) / W, 4), round(float(ys.mean()) / H, 4), int(hit.sum())]


def load_gen(group, gid, d):
    rp = os.path.join(d, "regions.json")
    resp = os.path.join(d, "results.json")
    if not os.path.exists(rp):
        return None
    regions = json.load(open(rp))
    template = regions.get("template") or {}
    regs = regions.get("regions", {})
    if not template or not regs:
        return None
    paint_path = os.path.join(d, "paint.png")
    if not os.path.exists(paint_path):
        return None
    W, H = Image.open(paint_path).size
    keys = {}
    if os.path.exists(resp):
        results = json.load(open(resp))
        keys = {k: tuple(v) for k, v in (results.get("keys") or {}).items()}
    # biref sidecar mask (for the paint-vs-refit check) — <dir>_biref/mask.png or cut.png
    mask_path = None
    for cand in (d + "_biref/mask.png", d + "_biref/cut.png", os.path.join(d, "mask.png")):
        if os.path.exists(cand):
            mask_path = cand
            break

    arche = archetype_of(template)
    gate = regions.get("gate", {})
    drift = regions.get("drift", {})

    controls = {}
    for k, t in template.items():
        dev = (regs.get(k) or {}).get("device")
        if not dev:
            continue
        v = drift_vec(t, dev, W, H)
        v["template_center_frac"] = [round(t[0], 4), round(t[1], 4)]
        v["from_template_fallback"] = bool((regs.get(k) or {}).get("fromTemplate"))
        if k in ("album_art", "visualizer"):
            mc = mask_blob_centroid(mask_path, keys.get(k)) if mask_path else None
            v["mask_blob_center_frac"] = mc[:2] if mc else None
            v["mask_blob_px"] = mc[2] if mc else None
        controls[k] = v

    return {
        "group": group, "id": gid, "dir": d, "dims": [W, H], "archetype": arche,
        "gate_pass": gate.get("PASS"), "drift_mean_px": drift.get("mean_px"),
        "drift_worst": drift.get("worst"),
        "template": {k: [round(v[0], 4), round(v[1], 4)] for k, v in template.items()},
        "controls": controls,
        "mask_path_used": mask_path,
    }


def swap_test(gen):
    """For album_art & visualizer: is the detected centre CLOSER to the OTHER control's
    template slot than to its OWN template slot? If yes for album_art (or vice versa for
    visualizer), that's positive evidence for the identity-swap hypothesis (a)."""
    c = gen["controls"]
    t = gen["template"]
    if "album_art" not in c or "visualizer" not in t or "album_art" not in t:
        return None
    aa_det = c["album_art"]["det_center_frac"]
    viz_t = t["visualizer"]
    aa_t = t["album_art"]
    d_own = math.dist(aa_det, aa_t)
    d_other = math.dist(aa_det, viz_t)
    aa_swapped = d_other < d_own

    viz_swapped = None
    if "visualizer" in c:
        viz_det = c["visualizer"]["det_center_frac"]
        d_own_v = math.dist(viz_det, viz_t)
        d_other_v = math.dist(viz_det, aa_t)
        viz_swapped = d_other_v < d_own_v

    return {
        "album_art_closer_to_visualizer_slot": aa_swapped,
        "album_art_dist_own_frac": round(d_own, 4), "album_art_dist_other_frac": round(d_other, 4),
        "visualizer_closer_to_album_art_slot": viz_swapped,
    }


def main():
    gens = []
    for group, gid, d in ALL_DIRS:
        g = load_gen(group, gid, d)
        if g is None:
            print(f"  skip {group}/{gid} (missing template/regions/paint)")
            continue
        g["swap_test"] = swap_test(g)
        gens.append(g)
        st = g["swap_test"]
        aa = g["controls"].get("album_art", {})
        flag = ""
        if st and st["album_art_closer_to_visualizer_slot"]:
            flag = "  <-- ALBUM_ART CLOSER TO VISUALIZER TEMPLATE SLOT"
        print(f"[{g['group']:12s}] {g['id']:32s} arche={g['archetype']:9s} "
              f"gate={'PASS' if g['gate_pass'] else 'FAIL'!s:5} "
              f"album_art drift={aa.get('mag_px','-'):>8} px @ {aa.get('angle_deg','-')}deg{flag}")

    # summary stats
    aa_vectors = [(g["group"], g["id"], g["archetype"], g["controls"]["album_art"])
                  for g in gens if "album_art" in g["controls"]]
    n_swap_hits = sum(1 for g in gens if g["swap_test"] and g["swap_test"]["album_art_closer_to_visualizer_slot"])
    print(f"\n{len(aa_vectors)} gens with album_art drift computed; "
          f"{n_swap_hits} show album_art closer to visualizer's template slot than its own.")

    out = {
        "generated_from": "analyze_artdrift.py ($0, no new generations)",
        "n_gens": len(gens),
        "n_swap_hits": n_swap_hits,
        "gens": gens,
    }
    with open(os.path.join(HERE, "artdrift_data.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote artdrift_data.json ({len(gens)} gens)")


if __name__ == "__main__":
    main()
