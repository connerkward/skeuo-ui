#!/usr/bin/env python3
"""build_page — renders inpaintbake/index.html from the bake-off's scoring artifacts.
Grid: defect crop (row) x model (column), full-res click-through, per-cell cost + a
MY-EYES verdict badge (authoritative — adjudicated against deterministic + VLM per
verify-outputs-rule), per-model totals, and the routing recommendation.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))

CROPS_META = json.load(open(os.path.join(HERE, "crops_meta.json")))
DET = {(r["skin"], r["model"]): r for r in json.load(open(os.path.join(HERE, "det_scores.json")))}
VLM = {(r["skin"], r["model"]): r for r in json.load(open(os.path.join(HERE, "vlm_judgments.json")))}
EYES = json.load(open(os.path.join(HERE, "my_eyes_verdicts.json")))

MODEL_INFO = {
    "lama": {"label": "LaMa (local)", "endpoint": "advimman/lama, MPS local", "unit_cost": 0.0,
             "unit": "$0 (local)"},
    "z-image-turbo": {"label": "Z-Image Turbo Inpaint", "endpoint": "fal-ai/z-image/turbo/inpaint",
                       "unit_cost": 0.01, "unit": "$0.01/MP"},
    "qwen-inpaint": {"label": "Qwen Image Edit Inpaint", "endpoint": "fal-ai/qwen-image-edit/inpaint",
                      "unit_cost": 0.03, "unit": "$0.03/MP"},
    "flux-pro-fill": {"label": "FLUX.1 [pro] Fill", "endpoint": "fal-ai/flux-pro/v1/fill",
                       "unit_cost": 0.05, "unit": "$0.05/MP"},
    "flux-dev-fill": {"label": "FLUX.1 [dev] Fill", "endpoint": "fal-ai/flux-lora-fill",
                       "unit_cost": 0.035, "unit": "$0.035/MP"},
    "vertex": {"label": "Vertex gemini-3-pro-image (incumbent)", "endpoint": "genskin.py:edit_vertex()",
                "unit_cost": 0.241, "unit": "$0.241/repair (4K output tier, corrected)"},
    "bria-eraser": {"label": "Bria Eraser (bonus arm)", "endpoint": "fal-ai/bria/eraser",
                     "unit_cost": 0.04, "unit": "$0.04/generation"},
}
MODEL_ORDER = ["lama", "z-image-turbo", "qwen-inpaint", "flux-pro-fill", "flux-dev-fill", "vertex"]
BONUS_MODEL = "bria-eraser"
SKINS = list(CROPS_META.keys())

VERDICT_COLOR = {"PASS": "#2d8f3f", "PARTIAL": "#b8860b", "FAIL": "#a83232"}
VERDICT_LABEL = {"PASS": "PASS", "PARTIAL": "PARTIAL", "FAIL": "FAIL"}


def cell_cost(model, skin):
    info = MODEL_INFO[model]
    if model == "vertex" and skin == "diablo-gothic":
        return 0.0, "reused from production log (3 prior real attempts already spent there)"
    if info["unit_cost"] == 0 and model == "lama":
        return 0.0, "local, $0"
    mp = (1024 * 1024) / 1_000_000.0
    if model in ("z-image-turbo", "qwen-inpaint", "flux-pro-fill", "flux-dev-fill"):
        return round(info["unit_cost"] * mp, 4), f"{info['unit']} x {mp:.3f}MP crop"
    if model == "vertex":
        return info["unit_cost"], info["unit"]
    if model == "bria-eraser":
        return info["unit_cost"], info["unit"]
    return info["unit_cost"], info["unit"]


def verdict_for(skin, model):
    return EYES.get(skin, {}).get(model, {"v": "?", "note": "not scored"})


def det_for(skin, model):
    return DET.get((skin, model))


def vlm_for(skin, model):
    return VLM.get((skin, model))


def cell_html(skin, model):
    thumb = f"web/{skin}__{model}-thumb.jpg"
    full = f"web/{skin}__{model}-full.jpg"
    fullskin_thumb = f"web/composite/{skin}__{model}-fullskin-thumb.jpg"
    fullskin_full = f"web/composite/{skin}__{model}-fullskin-full.jpg"
    seam_thumb = f"web/composite/{skin}__{model}-seam-thumb.jpg"
    seam_full = f"web/composite/{skin}__{model}-seam-full.jpg"
    v = verdict_for(skin, model)
    d = det_for(skin, model)
    vlm = vlm_for(skin, model)
    cost, cost_note = cell_cost(model, skin)
    color = VERDICT_COLOR.get(v["v"], "#666")
    overruled = ""
    if vlm and vlm.get("verdict") and vlm.get("verdict") != v["v"] and vlm.get("verdict") in ("PASS", "FAIL"):
        overruled = f'<div class="witness-flag">VLM said {vlm.get("verdict")} — overruled on pixel inspection</div>'
    det_line = ""
    if d:
        det_line = (f'<div class="witness">detector: {"cleared" if d["cleared_by_detector"] else "flagged"} '
                    f'· seam-Δ {d["seam_delta"]}</div>')
    if not os.path.exists(os.path.join(HERE, thumb)):
        return '<td class="cell empty">—</td>'
    composite_block = ""
    has_composite = os.path.exists(os.path.join(HERE, seam_thumb))
    if has_composite:
        composite_block = f'''
      <div class="model-tag">{MODEL_INFO[model]["endpoint"]}</div>
      <div class="composite-pair">
        <a href="{seam_full}" target="_blank" rel="noopener" class="seam-link">
          <img src="{seam_thumb}" loading="lazy" alt="{skin} x {model} seam (composited onto full skin)">
          <span class="img-cap">seam (composite, crop_box boxed)</span>
        </a>
        <a href="{fullskin_full}" target="_blank" rel="noopener" class="fullskin-link">
          <img src="{fullskin_thumb}" loading="lazy" alt="{skin} x {model} full skin composite">
          <span class="img-cap">full skin (click for native)</span>
        </a>
      </div>'''
    return f'''<td class="cell">
      {composite_block}
      <details class="isolated-crop">
        <summary>isolated crop (as originally scored)</summary>
        <a href="{full}" target="_blank" rel="noopener">
          <img src="{thumb}" loading="lazy" alt="{skin} x {model} isolated crop">
        </a>
      </details>
      <div class="badge" style="background:{color}">{v["v"]}</div>
      <div class="cost">${cost:.4f}</div>
      {det_line}
      {overruled}
      <div class="note">{v["note"]}</div>
    </td>'''


def before_cell(skin):
    thumb = f"web/{skin}__BEFORE-thumb.jpg"
    full = f"web/{skin}__BEFORE-full.jpg"
    seam_thumb = f"web/composite/{skin}__BEFORE-seam-thumb.jpg"
    seam_full = f"web/composite/{skin}__BEFORE-seam-full.jpg"
    fullskin_thumb = f"web/composite/{skin}__BEFORE-fullskin-thumb.jpg"
    fullskin_full = f"web/composite/{skin}__BEFORE-fullskin-full.jpg"
    material = CROPS_META[skin]["material"]
    composite_block = ""
    if os.path.exists(os.path.join(HERE, seam_thumb)):
        composite_block = f'''
      <div class="composite-pair">
        <a href="{seam_full}" target="_blank" rel="noopener" class="seam-link">
          <img src="{seam_thumb}" loading="lazy" alt="{skin} before seam">
          <span class="img-cap">defect seam (baked, boxed)</span>
        </a>
        <a href="{fullskin_full}" target="_blank" rel="noopener" class="fullskin-link">
          <img src="{fullskin_thumb}" loading="lazy" alt="{skin} before full skin">
          <span class="img-cap">full skin (defect, boxed)</span>
        </a>
      </div>'''
    return f'''<td class="cell before">
      {composite_block}
      <details class="isolated-crop">
        <summary>isolated crop (as originally scored)</summary>
        <a href="{full}" target="_blank" rel="noopener">
          <img src="{thumb}" loading="lazy" alt="{skin} before">
        </a>
      </details>
      <div class="skin-label">{skin}</div>
      <div class="material">{material}</div>
    </td>'''


def score_val(v):
    return {"PASS": 1.0, "PARTIAL": 0.5, "FAIL": 0.0}.get(v, 0.0)


def model_totals():
    rows = []
    for model in MODEL_ORDER + [BONUS_MODEL]:
        verdicts = []
        total_cost = 0.0
        n = 0
        seam_deltas = []
        for skin in SKINS:
            v = EYES.get(skin, {}).get(model)
            if v is None:
                continue
            verdicts.append(v["v"])
            c, _ = cell_cost(model, skin)
            total_cost += c
            n += 1
            d = det_for(skin, model)
            if d:
                seam_deltas.append(d["seam_delta"])
        if n == 0:
            continue
        avg_score = sum(score_val(v) for v in verdicts) / n
        pass_rate = sum(1 for v in verdicts if v == "PASS") / n
        avg_seam = sum(seam_deltas) / len(seam_deltas) if seam_deltas else None
        avg_cost = total_cost / n
        eff_cost = (avg_cost / avg_score) if avg_score > 0 else None
        rows.append({
            "model": model, "label": MODEL_INFO[model]["label"], "n": n,
            "pass_rate": pass_rate, "avg_score": avg_score, "avg_seam": avg_seam,
            "avg_cost": avg_cost, "eff_cost": eff_cost,
        })
    return rows


def render_totals_table(rows):
    trs = []
    for r in rows:
        eff = f"${r['eff_cost']:.4f}" if r["eff_cost"] else "n/a (0% pass)"
        seam = f"{r['avg_seam']:.1f}" if r["avg_seam"] is not None else "—"
        trs.append(f'''<tr>
          <td>{r["label"]}</td>
          <td>{r["n"]}</td>
          <td>{r["pass_rate"]*100:.0f}%</td>
          <td>{r["avg_score"]*100:.0f}%</td>
          <td>{seam}</td>
          <td>${r["avg_cost"]:.4f}</td>
          <td>{eff}</td>
        </tr>''')
    return "\n".join(trs)


def main():
    totals = model_totals()
    total_spend = 1.700 + 0.350  # generation + VLM judging, see report
    header_cols = "".join(f'<th>{MODEL_INFO[m]["label"]}<br><span class="unit">{MODEL_INFO[m]["unit"]}</span></th>'
                           for m in MODEL_ORDER)
    rows_html = []
    for skin in SKINS:
        cells = "".join(cell_html(skin, m) for m in MODEL_ORDER)
        rows_html.append(f'<tr>{before_cell(skin)}{cells}</tr>')
    bonus_rows = []
    for skin in SKINS:
        if os.path.exists(os.path.join(HERE, f"web/{skin}__{BONUS_MODEL}-thumb.jpg")):
            bonus_rows.append(f'<tr>{before_cell(skin)}<td class="cell" colspan="{len(MODEL_ORDER)-1}">'
                               f'</td>{cell_html(skin, BONUS_MODEL)}</tr>')

    totals_rows = render_totals_table(totals)

    html = f'''<meta charset="utf-8">
<title>inpaint bake-off — gen12</title>
<style>
:root {{ color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{
  background:#0a0a0d; color:#e4e4e8; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  margin:0; padding:24px; line-height:1.5;
}}
h1 {{ font-size:1.5rem; margin:0 0 4px; }}
h2 {{ font-size:1.15rem; margin:32px 0 12px; border-bottom:1px solid #2a2a32; padding-bottom:6px; }}
.sub {{ color:#9a9aa8; font-size:.9rem; margin-bottom:4px; }}
.cost-banner {{
  background:#151822; border:1px solid #2a2a32; border-radius:8px; padding:12px 16px;
  margin:16px 0; font-size:.85rem; color:#c8c8d4;
}}
.cost-banner b {{ color:#fff; }}
.table-wrap {{ overflow-x:auto; max-width:100%; border-radius:8px; }}
table {{ border-collapse:collapse; width:100%; min-width:900px; }}
th, td {{ border:1px solid #22222a; padding:8px; text-align:left; vertical-align:top; }}
th {{ background:#14141a; font-size:.78rem; font-weight:600; position:sticky; top:0; }}
.unit {{ color:#8a8a98; font-weight:400; }}
td.cell {{ width:16%; min-width:230px; font-size:.72rem; }}
td.cell img {{ width:100%; height:auto; border-radius:4px; display:block; border:1px solid #26262e; }}
td.before {{ background:#101014; }}
.model-tag {{ color:#6a6a78; font-size:.62rem; font-family:ui-monospace,monospace; margin-bottom:5px; }}
.composite-pair {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:8px; }}
.composite-pair a {{ flex:1 1 90px; min-width:90px; text-decoration:none; }}
.img-cap {{ display:block; color:#7a7a88; font-size:.6rem; margin-top:2px; text-align:center; }}
.seam-link img {{ border-color:#3a3a4a; }}
details.isolated-crop {{ margin:6px 0; }}
details.isolated-crop summary {{ cursor:pointer; color:#7a7a88; font-size:.62rem; margin-bottom:4px; }}
details.isolated-crop img {{ opacity:.9; }}
.skin-label {{ font-weight:700; margin-top:6px; font-size:.85rem; }}
.material {{ color:#8a8a98; font-size:.68rem; margin-top:2px; }}
.badge {{
  display:inline-block; margin-top:6px; padding:2px 8px; border-radius:4px;
  font-size:.7rem; font-weight:700; color:#fff; letter-spacing:.02em;
}}
.cost {{ color:#9fd39f; font-size:.68rem; margin-top:4px; font-family:ui-monospace,monospace; }}
.witness {{ color:#8a8a98; font-size:.65rem; margin-top:3px; }}
.witness-flag {{ color:#e0a030; font-size:.65rem; margin-top:3px; font-weight:600; }}
.note {{ color:#b8b8c4; font-size:.68rem; margin-top:5px; }}
.empty {{ color:#555; text-align:center; }}
.totals-table td, .totals-table th {{ text-align:right; }}
.totals-table td:first-child, .totals-table th:first-child {{ text-align:left; }}
.conclusion {{
  background:#12180f; border:1px solid #2a3822; border-radius:8px; padding:16px 20px;
  margin:20px 0; font-size:.92rem;
}}
.conclusion h3 {{ margin-top:0; color:#a8d888; }}
.finding {{
  background:#1a1410; border:1px solid #3a2c1a; border-radius:8px; padding:14px 18px;
  margin:14px 0; font-size:.88rem;
}}
.finding b {{ color:#e0a030; }}
code {{ background:#1a1a22; padding:1px 5px; border-radius:3px; font-size:.85em; }}
</style>

<h1>Inpaint bake-off — erasing baked slider handles from gen12 skin paints</h1>
<div class="sub">2026-07-12 · tools/mask-align-exp/gen12/inpaintbake/ · 5 genuine baked-thumb
defects x 6 finalist models (+1 bonus no-prompt eraser) x deterministic + VLM + human-eyes scoring</div>

<div class="cost-banner">
  <b>Models used:</b> LaMa (advimman/lama, local MPS, $0) · Z-Image Turbo Inpaint
  (fal-ai/z-image/turbo/inpaint) · Qwen Image Edit Inpaint (fal-ai/qwen-image-edit/inpaint) ·
  FLUX.1 [pro] Fill (fal-ai/flux-pro/v1/fill) · FLUX.1 [dev] Fill (fal-ai/flux-lora-fill) ·
  Vertex gemini-3-pro-image (incumbent, via genskin.py:edit_vertex()) · bonus: Bria Eraser
  (fal-ai/bria/eraser).<br>
  <b>Total spend this bake-off: ~$2.05</b> (generation ~$1.70 + VLM judging ~$0.35), under the
  $3 cap. SOTA-eye witness: google/gemini-2.5-pro via fal openrouter/router/vision, reasoning=true.
</div>

<div class="finding">
  <b>Phase-1 pricing correction found live in genskin.py:</b> the shared <code>edit_vertex()</code>
  helper hardcodes <code>imageConfig.imageSize: "4K"</code> on every call, regardless of input
  crop size — so Vertex output ALWAYS lands in Google's 4K output-token tier ($0.24/image), not
  the 1K-2K tier ($0.134/image) the 2026-07-12 pricing doc assumed from crop size alone.
  Corrected real cost: <b>~$0.241/repair</b> (vs the ~$0.136 previously recorded). See
  the experiment record for the full re-verification.
</div>

<div class="finding">
  <b>Biggest bake-off finding — three of the four cheap prompt+mask fal models hallucinate
  unrelated content instead of erasing.</b> Z-Image Turbo, FLUX Pro Fill, and FLUX Dev Fill
  scored <b>0/5 by eye</b> — not "imperfect," but generating a WRONG OBJECT in the masked region
  (a chrome part, a plastic toggle, a screw/dial) or even literal READABLE TEXT captions
  ("...REMOVED", a fake tooltip box) in place of the erased handle. The deterministic detector
  and even the VLM witness missed several of these (see per-cell "VLM overruled" flags below) —
  only direct full-res pixel inspection caught them. A no-prompt dedicated eraser (Bria Eraser,
  bonus arm) did NOT exhibit this failure mode, supporting the hypothesis that PROMPT-DRIVEN
  fill models treat "remove X, continue Y" as a generation instruction rather than a
  conservative local erase.
</div>

<div class="finding" style="border-color:#1a3a3a; background:#0f1818;">
  <b>Composite-onto-full-skin view added.</b> An isolated 1024x1024 crop can look flawless while
  the paste BOUNDARY against the surrounding skin incoheres — wrong tone, a visible ring, a
  hallucinated object sitting on unrelated material. Every cell below now composites the model's
  result crop back onto its full source skin (2304x3712) using the <b>exact same feathered-blend
  math production ships</b> (<code>erase12.py:erase_model()</code> — full strength interior,
  alpha ramps to 0 over the outer ~12% margin), via <code>build_composites.py</code> — so the seam
  shown here is the seam production would actually produce. Each cell shows the padded seam
  close-up (crop_box x1.5) plus a full-skin thumbnail, both with a <span style="color:#e62828">red
  box</span> marking crop_box for orientation; click either for the native-res image. The original
  isolated-crop scoring image is still available, collapsed under "isolated crop".
</div>

<h2>Results grid — defect crop x model</h2>
<div class="table-wrap">
<table>
<thead><tr><th>BEFORE (defect)</th>{header_cols}</tr></thead>
<tbody>
{"".join(rows_html)}
</tbody>
</table>
</div>

<h2>Bonus arm — Bria Eraser (no-prompt), 2 crops, budget top-up ($0.08)</h2>
<div class="sub">Tested after seeing the hallucination pattern above, to check whether a
no-prompt dedicated eraser avoids it. It does — see finding above.</div>
<div class="table-wrap">
<table>
<tbody>
{"".join(bonus_rows)}
</tbody>
</table>
</div>

<h2>Per-model scoreboard</h2>
<div class="table-wrap">
<table class="totals-table">
<thead><tr><th>Model</th><th>n</th><th>PASS rate</th><th>avg score (PASS=1,PARTIAL=.5,FAIL=0)</th>
<th>avg seam-Δ (lower better)</th><th>avg $/repair</th><th>$/effective PASS</th></tr></thead>
<tbody>
{totals_rows}
</tbody>
</table>
</div>

<div class="conclusion">
<h3>Routing recommendation</h3>
<p><b>Keep Vertex (gemini-3-pro-image, incumbent) as the reliable tier</b> — 5/5 PASS by eye in
this sample, corrected cost ~$0.241/repair. It remains the highest-quality, lowest-style-risk
option (same model that painted the skin, continuing its own work) and is the only arm with a
100% clean record across both flat/simple and ornate/complex material.</p>
<p><b>Add LaMa as a genuine $0 tier-0 pre-pass</b> — 50% PASS/PARTIAL-clean on flat/simple
material (fallout-vault: excellent; fallout-pipboy, n64-cutscene: partial/acceptable), FAILs on
ornate material (wc-goldshield: actively worsens the emblem). Gate its output with the
deterministic detector (site-scoped, see script note below) + a quick visual check before
accepting — free, so even a coin-flip pass rate is worth trying first.</p>
<p><b>PROMOTE Bria Eraser (fal-ai/bria/eraser, no-prompt, $0.04/repair) to a proper full
follow-up run.</b> On the 2 hardest crops tested it avoided the hallucination failure entirely
and came within striking distance of Vertex quality on the hardest case (diablo-gothic) at
~6x lower cost. This bake-off only spent $0.08 confirming the hypothesis — a full 5-crop run
(~$0.20) is the natural next step before shipping it as a tier-1 fallback ahead of Vertex.</p>
<p><b>DROP Z-Image Turbo Inpaint, FLUX Pro Fill, and FLUX Dev Fill from the candidate list for
this task.</b> Despite being individually the cheapest options ($0.01-0.05/repair), all three
scored 0/5 by eye due to a severe and consistent hallucination failure mode — not a marginal
quality gap, a wrong-content failure a human reviewer would need to catch on every single
output. Cost advantage does not offset a 0% usable-output rate. (A much more restrictive
"do not generate any new object/icon/text, only extend surrounding material" prompt might fix
this — untested here, flagged as a possible follow-up, not a reason to ship as-is.)</p>
<p><b>Qwen Image Edit Inpaint</b> sits in the middle (50% by eye) with a comparatively SAFE
failure mode — it leaves an obvious flat black void rather than hallucinating a plausible-looking
wrong object, which is easier for a downstream gate/human to catch. Worth keeping as an
optional pre-Vertex tier only if a gate is built to catch the void-failure case; not a
standalone recommendation on its own.</p>
<p><b>Final proposed chain:</b> LaMa ($0) → Bria Eraser ($0.04, pending full validation) →
Vertex ($0.241, reliable fallback). This keeps the previously-recommended free tier-0, adds a
cheap and now-evidenced tier-1, and never removes the proven, reliable, but priciest incumbent
from the chain.</p>
</div>

<div class="sub" style="margin-top:24px;">
Full experiment record: <a href="file:///Users/conner/dev/skeuo-ui/docs/experiments/2026-07-12-inpaint-bakeoff.md">docs/experiments/2026-07-12-inpaint-bakeoff.md</a>
</div>
'''
    open(os.path.join(HERE, "index.html"), "w").write(html)
    print(f"wrote {os.path.join(HERE, 'index.html')} ({len(html)} bytes)")


if __name__ == "__main__":
    main()
