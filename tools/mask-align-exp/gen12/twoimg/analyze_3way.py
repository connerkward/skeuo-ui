#!/usr/bin/env python3
"""analyze_3way — parse all 12 vlm.json + scores.json into the 3-way (control/treat/neutral)
comparison: color bleed, DIGIT bleed, layout adherence, cavity emptiness.
Read-only vs gens; writes threeway.json for build_index.py to render.

Adjudication notes (verify-rule: the VLM is a witness, not a judge):
- DIGIT axis: the hunt prompt includes "tick-mark / callout dot / number-like tag ...
  faint/stylized/ambiguous", which flags normal skeuo knob pointer-notches/bezel ticks. Any
  DIGITS-FOUND in the control/treat arms is by construction spontaneous (their inputs contain
  zero digits) — those calibrate the detector's false-positive floor. The hypothesis axis is
  ACTUAL NUMERALS in the NEUTRAL arm (whose reference carries printed 1-10 tags):
  digit_numeral_controls below keeps only finds whose description mentions a numeral/digit
  shape rather than tick/notch/rib/dot, and neutral-arm finds are listed verbatim either way.
- COLOR axis in the NEUTRAL arm: neutral's two input images are verifiably colourless, but the
  TEXT prompt still maps each control to its named guide colour + exact RGB (the right-column
  mask spec needs it). Exact-key hues on neutral paints (verified by eye: wc-134's SPRING GREEN
  repeat gem / ROSE PINK next gem / VIOLET-PURPLE shuffle disk) are therefore TEXT-side
  semantic bleed — a third pathway beyond canvas-pixel and reference-image bleed.

Usage: python3 analyze_3way.py
"""
import os, re, json

HERE = os.path.dirname(os.path.abspath(__file__))
THEMES = ["fa-pod", "wc-goldshield"]
SEEDS = [121, 134]
ARMS = ["control", "treat", "neutral"]

S = json.load(open(os.path.join(HERE, "scores.json")))

COLOR_LINE = re.compile(r"^([a-z_]+)\s*(?:\([^)]*\))?:\s*(NONE|RING|FLOODED)(?:,\s*(FILLED|EMPTY))?", re.M)
CAVITY_LINE = re.compile(r"^([a-z_]+)\s*(?:\([^)]*\))?\s*(?:cavity)?:?\s*(EMPTY|FILLED)\s*$", re.M)
DIGIT_LINE = re.compile(r"^([a-z_]+)\s*(?:\([^)]*\))?:\s*DIGITS-(NONE|FOUND)(.*)$", re.M)
# "numeral"/"digit"/"number N" in the description = an actual numeral; bare digits like
# "4-o'clock position" are clock-position phrasing for a tick-mark, not a numeral
NUMERAL_WORDS = re.compile(r"numeral|digit\b|number\s+\"?\d", re.I)

# LAYOUT adherence vs the locked template is NOT fully captured by extract12's region-misplaced
# gate: the mask column moves WITH a rearranged paint, so a self-consistent rearrangement
# passes the gate. These are direct-visual-inspection calls on the full paints against the
# authored template (control/treat adjudicated 2026-07-10 — recorded in verdict.json per-gen
# notes; neutral adjudicated 2026-07-11 — all 4 rearranged rows/screens; fa-pod-neutral-134
# additionally overflows the canvas right edge).
LAYOUT_ADHERES = {
    "fa-pod-control-121": True, "fa-pod-control-134": True,
    "wc-goldshield-control-121": True,   # display split into 2 windows, but rows follow template
    "wc-goldshield-control-134": True,
    "fa-pod-treat-121": False, "fa-pod-treat-134": False,
    "wc-goldshield-treat-121": False, "wc-goldshield-treat-134": False,
    "fa-pod-neutral-121": False, "fa-pod-neutral-134": False,
    "wc-goldshield-neutral-121": False, "wc-goldshield-neutral-134": False,
}


def analyze_gen(theme, arm, seed):
    tag = f"{theme}-{arm}-{seed}"
    d = os.path.join(HERE, f"assets-twoimg-{tag}")
    sc = S.get(tag, {})
    vlm_path = os.path.join(d, "vlm.json")
    vlm = json.load(open(vlm_path)) if os.path.exists(vlm_path) else None
    raw = (vlm or {}).get("raw", "") or ""

    color_hits = sorted(set(c for c, v, _ in COLOR_LINE.findall(raw) if v in ("RING", "FLOODED")))
    cavity_hits = set(c for c, v in CAVITY_LINE.findall(raw) if v == "FILLED")
    inline_filled = set(c for c, v, f in COLOR_LINE.findall(raw) if f == "FILLED")
    digit_finds = [(c, desc.strip()) for c, v, desc in DIGIT_LINE.findall(raw) if v == "FOUND"]
    # keep only finds whose description reads as an actual numeral (vs tick/notch/rib)
    numeral_finds = sorted(set(c for c, desc in digit_finds if NUMERAL_WORDS.search(desc or "")))

    return {
        "tag": tag, "theme": theme, "arm": arm, "seed": seed,
        "gate_pass": sc.get("empty_ok", False) and not sc.get("reasons", []),
        "gate_reasons": sc.get("reasons", []),
        "empty_ok": sc.get("empty_ok"),
        "leak_pct": sc.get("leak_pct"),
        "bleed_ring_worst": sc.get("bleed_ring_worst"),
        "vlm_verdict": (vlm or {}).get("verdict", "MISSING"),
        "digit_verdict": (vlm or {}).get("digit_verdict", "MISSING"),
        "color_residue_controls": color_hits,
        "cavity_filled_controls": sorted(cavity_hits | inline_filled),
        "digit_found_controls": sorted(set(c for c, _ in digit_finds)),
        "digit_numeral_controls": numeral_finds,
        "layout_adheres": LAYOUT_ADHERES.get(tag),
    }


def main():
    gens = [analyze_gen(t, a, s) for t in THEMES for a in ARMS for s in SEEDS]
    by_arm = {a: [g for g in gens if g["arm"] == a] for a in ARMS}
    summary = {}
    for arm, gs in by_arm.items():
        n = len(gs)
        summary[arm] = {
            "n": n,
            "gate_pass": f"{sum(1 for g in gs if g['gate_pass'])}/{n}",
            "vlm_pass": f"{sum(1 for g in gs if g['vlm_verdict'] == 'PASS')}/{n}",
            "color_bleed_gens": f"{sum(1 for g in gs if g['color_residue_controls'])}/{n}",
            "digit_mark_gens": f"{sum(1 for g in gs if g['digit_found_controls'])}/{n}",
            "digit_numeral_gens": f"{sum(1 for g in gs if g['digit_numeral_controls'])}/{n}",
            "layout_adherence_gens": f"{sum(1 for g in gs if g['layout_adheres'])}/{n}",
            "cavity_empty_gens": f"{sum(1 for g in gs if not g['cavity_filled_controls'] and g['empty_ok'])}/{n}",
        }
    out = {"gens": gens, "summary": summary}
    json.dump(out, open(os.path.join(HERE, "threeway.json"), "w"), indent=1)
    print(json.dumps(summary, indent=2))
    for g in gens:
        print(f"{g['tag']:32} gate={'PASS' if g['gate_pass'] else 'FAIL':4} vlm={g['vlm_verdict']:8} "
              f"digit={g['digit_verdict']:12} layout={'ok' if g['layout_adheres'] else 'DRIFT':5} "
              f"color={g['color_residue_controls']} cavity={g['cavity_filled_controls']} "
              f"digitmarks={g['digit_found_controls']} numerals={g['digit_numeral_controls']}")


if __name__ == "__main__":
    main()
