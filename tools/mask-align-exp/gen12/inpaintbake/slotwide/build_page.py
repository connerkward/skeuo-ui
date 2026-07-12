#!/usr/bin/env python3
"""build_page — renders slotwide/index.html: the SECOND bake-off arm (whole-slot mask, not a
tight thumb-hole patch). Grid: skin (row) x model (col), full-skin composite (click->full-res)
+ zoomed seam crop, model+cost annotated per dev-facing-model-cost-annotation-rule, my-eyes
verdicts from direct visual inspection (verify-outputs-rule: looked at the real composited
artifact, not a metric), CONCLUSION section at the bottom.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
META = json.load(open(os.path.join(HERE, "slot_crops_meta.json")))
COST = json.load(open(os.path.join(HERE, "cost_log.json")))
SKINS = list(META.keys())
MODEL_ORDER = ["lama", "bria", "vertex"]

MODEL_INFO = {
    "lama": {"label": "LaMa (local, classical)", "endpoint": "advimman/lama, MPS local, $0"},
    "bria": {"label": "Bria Eraser", "endpoint": "fal-ai/bria/eraser, $0.04/call"},
    "vertex": {"label": "Vertex gemini-3-pro-image", "endpoint": "genskin.py:edit_vertex(), 2K tier ~$0.134/call"},
}

# my-eyes verdicts — direct inspection of the composited full-skin artifacts + seam crops
# (composited/<skin>__<model>__full.png, __seam.png), per verify-outputs-rule / verify-rule.
VERDICTS = {
    "diablo-gothic": {
        "lama": {"v": "PARTIAL", "note": "Erases the skull ornament + runes cleanly into a "
                 "uniform brown-grey channel — no residual bulge or highlight. But the result "
                 "reads flatter/lighter than the dark carved-obsidian groove elsewhere on this "
                 "skin; loses the deep-shadow recess look."},
        "bria": {"v": "FAIL", "note": "Invents a diamond-quilted leather/padding texture inside "
                 "the groove — a pattern that exists NOWHERE else on this skin. Classic "
                 "hallucination: wide context gave it license to 'design' rather than erase."},
        "vertex": {"v": "FAIL", "note": "Did not erase the defect at all — KEPT the skull "
                   "ornament in place and additionally hallucinated new glowing rune glyphs "
                   "carved into the channel. Worse than doing nothing: more baked content, "
                   "not less."},
    },
    "wc-goldshield": {
        "lama": {"v": "PASS", "note": "Cleanly removes the sliding puck/handle, leaves a "
                 "continuous gold-groove track; the fixed swivel-mount hardware at the left end "
                 "(not part of the defect) is correctly preserved."},
        "bria": {"v": "FAIL", "note": "The round gold thumb/puck is still fully present at the "
                 "left end of the groove, essentially unchanged from the source — the model did "
                 "not engage with the erase task."},
        "vertex": {"v": "FAIL", "note": "Same failure as Bria: the thumb is still sitting in the "
                   "groove, unremoved."},
    },
    "fallout-vault": {
        "lama": {"v": "PARTIAL", "note": "Handle removed, groove reads mostly clean, but a "
                 "faint seam/texture patch is visible down the middle of the repainted region — "
                 "slightly less coherent than the other two here."},
        "bria": {"v": "PASS", "note": "Handle fully removed, groove empty and continuous, rust "
                 "texture flows through the repaired region convincingly."},
        "vertex": {"v": "PASS", "note": "Best of the three for this skin: handle removed AND the "
                   "yellow hazard-stripe trim (called out in the material brief) is carried "
                   "through the groove rim, reading as intentional design rather than a patch."},
    },
}

VERDICT_COLOR = {"PASS": "#2d8f3f", "PARTIAL": "#b8860b", "FAIL": "#a83232"}


def cost_for(skin, model):
    for c in COST:
        if c.get("skin") == skin and c.get("model") == model and "cost" in c:
            return c["cost"]
    return None


def cell_html(skin, model):
    full = f"composited/{skin}__{model}__full.png"
    seam = f"composited/{skin}__{model}__seam.png"
    v = VERDICTS[skin][model]
    color = VERDICT_COLOR[v["v"]]
    cost = cost_for(skin, model)
    cost_str = "$0 (local)" if cost == 0.0 else (f"${cost:.3f}" if cost is not None else "?")
    return f"""
    <td>
      <div class="model-tag">{MODEL_INFO[model]['endpoint']}</div>
      <a href="{full}" target="_blank"><img class="thumb" src="{full}" loading="lazy"></a>
      <div class="seamlabel">zoomed seam (slot &times;1.5 pad)</div>
      <a href="{seam}" target="_blank"><img class="seam" src="{seam}" loading="lazy"></a>
      <div class="badge" style="background:{color}">{v['v']}</div>
      <div class="note">{v['note']}</div>
      <div class="cost">{cost_str}</div>
    </td>"""


def row_html(skin):
    m = META[skin]
    cells = "".join(cell_html(skin, mdl) for mdl in MODEL_ORDER)
    return f"""
    <tr>
      <th class="rowhead">
        <div class="skinname">{skin}</div>
        <div class="material">{m['material']}</div>
        <div class="geom">slot {int(m['slot_box_px'][2]-m['slot_box_px'][0])}&times;{int(m['slot_box_px'][3]-m['slot_box_px'][1])}px
        &middot; {'vertical' if m['vertical'] else 'horizontal'} &middot; crop aspect {m['vertex_aspect']}</div>
      </th>{cells}
    </tr>"""


total_cost = sum(c.get("cost", 0) or 0 for c in COST)

html = f"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>inpaint bake-off — ARM 2: whole-slot mask</title>
<style>
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:24px; background:#0a0a0d; color:#e4e4e8;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
h1 {{ font-size:1.3rem; margin:0 0 4px; }}
.sub {{ color:#8a8a96; font-size:.85rem; margin-bottom:6px; }}
.costline {{ background:#151822; border:1px solid #2a2a32; border-radius:8px; padding:10px 16px;
  font-family:ui-monospace,monospace; font-size:.78rem; color:#9fd39f; margin-bottom:18px;
  display:inline-block; }}
.tablewrap {{ overflow-x:auto; max-width:100%; }}
table {{ border-collapse:collapse; width:100%; min-width:900px; }}
th, td {{ border:1px solid #22222a; padding:10px; vertical-align:top; text-align:left; }}
th.colhead {{ background:#14141a; font-size:.82rem; font-weight:600; position:sticky; top:0; }}
th.rowhead {{ background:#101014; min-width:170px; max-width:220px; }}
.skinname {{ font-weight:700; font-size:.95rem; }}
.material {{ color:#8a8a96; font-size:.68rem; margin-top:4px; line-height:1.3; }}
.geom {{ color:#5f7fbf; font-size:.62rem; margin-top:6px; font-family:ui-monospace,monospace; }}
.model-tag {{ color:#6a6a78; font-size:.6rem; font-family:ui-monospace,monospace; margin-bottom:6px; }}
img.thumb {{ width:100%; max-width:260px; display:block; border-radius:4px; border:1px solid #2a2a32; }}
img.seam {{ width:100%; max-width:260px; display:block; border-radius:4px; border:1px solid #2a2a32;
  margin-top:2px; }}
.seamlabel {{ color:#5f5f6a; font-size:.58rem; margin-top:8px; margin-bottom:2px; }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:.68rem; font-weight:700;
  margin-top:8px; color:#0a0a0d; }}
.note {{ color:#b0b0ba; font-size:.68rem; line-height:1.35; margin-top:6px; }}
.cost {{ color:#9fd39f; font-size:.66rem; margin-top:6px; font-family:ui-monospace,monospace; }}
.conclusion {{ margin-top:28px; background:#12180f; border:1px solid #2a3822; border-radius:8px;
  padding:18px 22px; }}
.conclusion h2 {{ margin-top:0; font-size:1rem; }}
.conclusion p {{ font-size:.85rem; line-height:1.55; color:#d0d0d8; }}
.conclusion ul {{ font-size:.82rem; line-height:1.6; color:#c8c8d2; }}
code {{ background:#1a1a22; padding:1px 5px; border-radius:3px; font-size:.85em; }}
</style></head><body>
<h1>Inpaint bake-off — ARM 2: WHOLE-SLOT mask (vs. the tight-thumb-crop arm in <code>../</code>)</h1>
<div class="sub">Isolated arm in <code>slotwide/</code> — hypothesis: masking the ENTIRE slider
slot/groove and repainting it clean blends more coherently than patching a tight hole around
just the baked thumb. 3 skins &times; 3 non-hallucinating erasers (z-image-turbo and other
cheap generative fillers deliberately excluded per correction). Models: {', '.join(MODEL_INFO[m]['label'] for m in MODEL_ORDER)}.</div>
<div class="costline">Total generation spend: ${total_cost:.3f} (cap was $2.00) &middot;
LaMa $0 (local, classical, non-generative) + Bria Eraser $0.04&times;3 + Vertex 2K-tier
$0.134&times;3</div>
<div class="tablewrap">
<table>
<tr><th class="colhead">skin / slot geometry</th>{"".join(f'<th class="colhead">{MODEL_INFO[m]["label"]}</th>' for m in MODEL_ORDER)}</tr>
{"".join(row_html(s) for s in SKINS)}
</table>
</div>

<div class="conclusion">
<h2>CONCLUSION / VERDICT</h2>
<p><strong>Whole-slot masking does NOT reliably improve blend coherence over the tight-crop
arm — it makes the generative models (Bria, Vertex) WORSE on 2 of 3 skins, while the classical
LaMa baseline stays the most consistently correct performer.</strong></p>
<ul>
<li><strong>diablo-gothic:</strong> LaMa PARTIAL (clean erase, slightly flattened material) &middot;
Bria FAIL (hallucinated a diamond-quilted texture that exists nowhere else on the skin) &middot;
Vertex FAIL (didn't erase at all — kept the skull ornament AND added new glowing rune glyphs).</li>
<li><strong>wc-goldshield:</strong> LaMa PASS (clean erase, correctly preserves the fixed swivel
mount) &middot; Bria FAIL (thumb still fully present, unchanged) &middot; Vertex FAIL (same —
thumb not removed).</li>
<li><strong>fallout-vault:</strong> LaMa PARTIAL (clean but a faint seam patch visible) &middot;
Bria PASS (clean, coherent rust continuity) &middot; Vertex PASS (best result — carries the
yellow hazard trim through the repair, reads as intentional).</li>
</ul>
<p><strong>Why the hypothesis failed for the generative models:</strong> a wider unmasked
context window doesn't just give the model more material to match — it gives it more visual
"permission" to invent (diablo's quilting, diablo's runes) or simply not commit to the erase
instruction at all (both goldshield failures). The tight-crop arm's mask sits close around the
thumb with less surrounding decorative detail to riff on, which appears to constrain the model
toward literally erasing rather than redesigning. LaMa has no such failure mode because it has
no generative/hallucination capacity to begin with — it's texture-continuation only, which is
exactly why it's the most reliable of the three here (2 PASS/PARTIAL-clean, 1 PARTIAL, 0 FAIL)
even though its output sometimes reads slightly flatter than the surrounding material.</p>
<p><strong>Routing recommendation for erase12:</strong> do NOT widen erase12's mask to the full
slot as a blanket policy — it regresses Bria and Vertex on 2/3 skins tested here. If whole-slot
masking is used at all, pair it with LaMa specifically (classical, deterministic, doesn't
hallucinate) rather than a generative eraser. The tight-crop arm's per-model routing decision
(see <code>../index.html</code>) should stand as the primary conclusion; this arm is a negative
result on the wide-context hypothesis, not a replacement recommendation.</p>
</div>
</body></html>"""

open(os.path.join(HERE, "index.html"), "w").write(html)
print(f"index.html written, total_cost=${total_cost:.3f}")
