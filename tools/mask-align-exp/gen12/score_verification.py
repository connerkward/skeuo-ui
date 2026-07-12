#!/usr/bin/env python3
"""score_verification.py — recall scorer for the review-2026-07-11 human eval set.

For each of the 15 human-reviewed skins (review-2026-07-11-round1.json, coded into the
defect taxonomy in human_defects.json), checks whether the machine verification stack
(observe12.py SOTA-eye + director_review.py DIRECTOR pass) flagged the SAME defect classes
the human flagged. This is the eval-set scoring step of the verification-recalibration pass
(TODO.md) — run once BEFORE recalibrating the two scripts' prompts (baseline) and once AFTER
(recalibrated), diffed into a before/after table.

Matching is class-by-class over the flattened JSON text of each skin's observe.json /
director-review.json: a class is "hit" if either (a) its own canonical taxonomy tag string
appears verbatim (this is what the RECALIBRATED prompts are designed to emit, so post-
recalibration scoring is close to exact-match), or (b) any of its keyword-heuristic synonyms
appears (this is what makes baseline scoring possible at all, since the pre-recalibration
freeform prose never uses the canonical tag vocabulary). Keyword sets are a deliberately
generous heuristic — see KEYWORDS below — so baseline recall is not artificially deflated by
wording differences; recalibrated recall additionally benefits from the exact tags.

Usage: python3 score_verification.py [--label baseline|recalibrated] [--out FILE.json]
"""
import os, sys, json, re

HERE = os.path.dirname(os.path.abspath(__file__))
HUMAN = json.load(open(os.path.join(HERE, "human_defects.json")))
SKINS = sorted(k for k in HUMAN if not k.startswith("_"))
TAXONOMY = HUMAN["_meta"]["taxonomy"]

LABEL = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--label=")), "run")
OUT = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--out=")), None)

# keyword heuristics: generous synonym sets so BASELINE (pre-recalibration freeform prose)
# scoring is a fair fight, not a strawman. Recalibrated outputs additionally carry the exact
# canonical tag string (checked separately, see hit()), so they don't depend on this list.
KEYWORDS = {
    "baked-thumb": [r"baked"],
    "sprite-slot-mismatch": [r"doesn'?t (match|fit) (the )?slot", r"slot.{0,15}(mismatch|doesn'?t match)",
                              r"too small", r"too large", r"too big", r"scaled?\b.{0,20}slot",
                              r"wrong (scale|size|shape)"],
    "css-misalignment": [r"\bcss\b", r"misalign", r"not aligned", r"offset", r"overlay",
                          r"too (far|long).{0,20}(left|right|past)"],
    "silhouette-mismatch": [r"silhouett", r"depression.{0,20}(doesn'?t match|not align|mismatch)"],
    "orientation": [r"orientation", r"upside.?down", r"sideways", r"rotated", r"wrong way up",
                     r"not upright"],
    "dead-control": [r"failed to work", r"not working", r"doesn'?t work", r"non.?functional",
                      r"\bdead\b", r"unresponsive", r"did not (change|move|respond)"],
    "duplicate-control": [r"duplicate"],
    "phantom-control": [r"phantom", r"ghost control", r"no corresponding function"],
    "placement-wrong": [r"misplaced", r"placed wrong", r"wrong position", r"completely wrong",
                         r"mixed up"],
    "aesthetic": [r"\bugly\b", r"\bboring\b", r"\bweird\b", r"unclear", r"aesthetic"],
}
for k in TAXONOMY:
    KEYWORDS.setdefault(k, [])


def blob_for(path):
    if not os.path.exists(path):
        return None
    try:
        rec = json.load(open(path))
    except Exception:
        return None
    return json.dumps(rec).lower()


def hit(blob, cls):
    if blob is None:
        return None  # no data
    if cls in blob:  # exact canonical tag (recalibrated outputs emit these verbatim)
        return True
    return any(re.search(pat, blob) for pat in KEYWORDS.get(cls, []))


rows = []
class_totals = {c: {"human": 0, "obs_hit": 0, "dir_hit": 0, "either_hit": 0} for c in TAXONOMY}
for sid in SKINS:
    human_defects = HUMAN[sid]["defects"]
    obs_blob = blob_for(os.path.join(HERE, f"assets-{sid}", "observe", "observe.json"))
    dir_blob = blob_for(os.path.join(HERE, f"assets-{sid}", "director-review.json"))
    row = {"skin": sid, "human_defects": human_defects, "obs_available": obs_blob is not None,
           "dir_available": dir_blob is not None, "per_class": {}}
    for cls in human_defects:
        oh = hit(obs_blob, cls)
        dh = hit(dir_blob, cls)
        eh = bool(oh) or bool(dh)
        row["per_class"][cls] = {"observe": oh, "director": dh, "either": eh}
        class_totals[cls]["human"] += 1
        class_totals[cls]["obs_hit"] += 1 if oh else 0
        class_totals[cls]["dir_hit"] += 1 if dh else 0
        class_totals[cls]["either_hit"] += 1 if eh else 0
    rows.append(row)

# ---- print report ----
print(f"\n=== verification recall report [{LABEL}] ===\n")
print(f"{'skin':<26} {'human defects':<55} {'recall(either)':<15}")
for row in rows:
    hits = sum(1 for v in row["per_class"].values() if v["either"])
    tot = len(row["human_defects"])
    marks = ", ".join(f"{c}{'✓' if row['per_class'][c]['either'] else '✗'}" for c in row["human_defects"])
    print(f"{row['skin']:<26} {marks:<55} {hits}/{tot}")

print(f"\n{'defect class':<22} {'human N':<9} {'observe recall':<16} {'director recall':<17} {'either recall':<14}")
overall_human = overall_obs = overall_dir = overall_either = 0
for cls in TAXONOMY:
    t = class_totals[cls]
    if t["human"] == 0:
        continue
    overall_human += t["human"]; overall_obs += t["obs_hit"]; overall_dir += t["dir_hit"]; overall_either += t["either_hit"]
    print(f"{cls:<22} {t['human']:<9} {t['obs_hit']}/{t['human']} ({100*t['obs_hit']/t['human']:.0f}%)"
          f"{'':<4} {t['dir_hit']}/{t['human']} ({100*t['dir_hit']/t['human']:.0f}%){'':<3}"
          f" {t['either_hit']}/{t['human']} ({100*t['either_hit']/t['human']:.0f}%)")
print(f"\nOVERALL ({overall_human} human-flagged defect instances across {len(SKINS)} skins):")
print(f"  observe12 recall:  {overall_obs}/{overall_human} ({100*overall_obs/overall_human:.1f}%)")
print(f"  director recall:   {overall_dir}/{overall_human} ({100*overall_dir/overall_human:.1f}%)")
print(f"  either recall:     {overall_either}/{overall_human} ({100*overall_either/overall_human:.1f}%)")

if OUT:
    json.dump({"label": LABEL, "rows": rows, "class_totals": class_totals,
               "overall": {"human": overall_human, "observe": overall_obs,
                           "director": overall_dir, "either": overall_either}},
              open(OUT, "w"), indent=2)
    print(f"\n-> {OUT}")
