#!/usr/bin/env python3
"""build_page (arm 3 / editors) -- renders editors/index.html: per-skin row comparing every
general image-editing model tested against the Vertex gemini-3-pro baseline (reused from arm 1,
not re-spent). Model + real cost annotated per cell (dev-facing-model-cost-annotation-rule),
every image legibly labeled (label-overlays-rule), responsive (responsive-web-rule), ends with
a CONCLUSION/VERDICT section pulled from verdicts.json (dev-facing-model-cost-annotation-rule).
Read-only against the parent inpaintbake/ dir; only writes under editors/.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
CROPS_META = json.load(open(os.path.join(HERE, "..", "crops_meta.json")))
VERDICTS = json.load(open(os.path.join(HERE, "verdicts.json")))

SKINS = ["diablo-gothic", "wc-goldshield", "fallout-vault"]
MODELS = ["vertex", "gemini25-flash", "gemini31-flash", "finegrain", "gpt-image-2"]

MODEL_INFO = {
    "vertex": {
        "label": "Vertex gemini-3-pro-image (incumbent baseline)",
        "endpoint": "genskin.py:edit_vertex() -- Google Vertex, direct",
        "cost": 0.241, "cost_note": "$0.241/repair (4K output tier) -- REUSED from arm 1, no fresh spend here",
    },
    "gemini25-flash": {
        "label": "Gemini 2.5 Flash Image (“Nano Banana”)",
        "endpoint": "fal-ai/gemini-25-flash-image/edit",
        "cost": 0.040, "cost_note": "$0.040/call (fal listed price, flat per image)",
    },
    "gemini31-flash": {
        "label": "Gemini 3.1 Flash Image Preview (“Nano Banana 2”)",
        "endpoint": "fal-ai/gemini-3.1-flash-image-preview/edit",
        "cost": 0.080, "cost_note": "$0.080/call (fal listed price, flat per image)",
    },
    "finegrain": {
        "label": "Finegrain Eraser (dedicated eraser, mask-based, premium mode)",
        "endpoint": "fal-ai/finegrain-eraser/mask",
        "cost": 0.045, "cost_note": "$0.045/call (fal listed price, unit=images)",
    },
    "gpt-image-2": {
        "label": "GPT Image 2 (OpenAI, via fal)",
        "endpoint": "openai/gpt-image-2/edit",
        "cost": 0.0612, "cost_note": "$0.0612/call REAL BILLED cost (x-fal-billable-units header x $1/unit list price) -- NOT the ambiguous $1/“unit” fal shows; actual measured across 3 calls: $0.0613, $0.0612, $0.0612",
    },
}

VERDICT_COLOR = {"PASS": "#2d8f3f", "FAIL": "#a83232", "FAIL (borderline)": "#b8860b"}

CSS = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body {
  background:#0a0a0d; color:#e4e4e8; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  margin:0; padding:20px; line-height:1.5;
}
h1 { font-size:1.4rem; margin:0 0 6px; }
h2 { font-size:1.1rem; margin:32px 0 12px; border-bottom:1px solid #2a2a32; padding-bottom:6px; }
.sub { color:#9a9aa8; font-size:.88rem; margin-bottom:4px; }
.cost-banner {
  background:#14141a; border:1px solid #2a2a32; border-radius:8px; padding:12px 16px;
  margin:16px 0; font-size:.85rem; color:#c8c8d4;
}
.cost-banner b { color:#e4e4e8; }
.cost-table { width:100%; border-collapse:collapse; margin:10px 0 24px; font-size:.82rem; }
.cost-table th, .cost-table td { text-align:left; padding:6px 10px; border-bottom:1px solid #22222a; }
.cost-table th { color:#9a9aa8; font-weight:600; }
.skin-block { margin-bottom:40px; }
.skin-title { font-size:1.05rem; font-weight:600; margin-bottom:4px; }
.skin-material { color:#9a9aa8; font-size:.82rem; margin-bottom:14px; font-style:italic; }
.row {
  display:flex; flex-wrap:wrap; gap:14px;
}
.cell {
  flex:1 1 220px; max-width:280px; background:#131318; border:1px solid #24242c; border-radius:10px;
  padding:10px; display:flex; flex-direction:column; gap:6px;
}
.cell.before { border-color:#4a2a2a; background:#181212; }
.cell img { width:100%; border-radius:6px; display:block; background:#000; }
.cell-label { font-weight:600; font-size:.88rem; }
.cell-endpoint { font-size:.72rem; color:#8a8a96; word-break:break-word; }
.cell-cost { font-size:.78rem; color:#c8b060; }
.badge {
  display:inline-block; padding:2px 8px; border-radius:4px; font-size:.72rem; font-weight:700;
  color:#fff; width:fit-content;
}
.note { font-size:.76rem; color:#b8b8c4; }
.img-cap { font-size:.68rem; color:#7a7a86; text-align:center; }
a.imglink { text-decoration:none; }
.verdict-section {
  background:#101014; border:2px solid #3a3a44; border-radius:12px; padding:20px; margin-top:40px;
}
.verdict-section h2 { border:none; margin-top:0; }
.verdict-table { width:100%; border-collapse:collapse; margin:12px 0; font-size:.85rem; }
.verdict-table th, .verdict-table td { text-align:left; padding:8px 10px; border-bottom:1px solid #24242c; }
.verdict-table th { color:#9a9aa8; }
.rec { background:#14241a; border:1px solid #2d5f3f; border-radius:8px; padding:14px; margin-top:16px; }
"""


def cell_html(skin, model, is_before=False):
    info = MODEL_INFO.get(model)
    if is_before:
        thumb = f"web/composite/{skin}__BEFORE-fullskin-thumb.jpg"
        full = f"web/composite/{skin}__BEFORE-fullskin-full.jpg"
        seam_thumb = f"web/composite/{skin}__BEFORE-seam-thumb.jpg"
        seam_full = f"web/composite/{skin}__BEFORE-seam-full.jpg"
        return f'''<div class="cell before">
      <div class="cell-label">BEFORE (baked defect)</div>
      <a class="imglink" href="{seam_full}" target="_blank" rel="noopener">
        <img src="{seam_thumb}" loading="lazy" alt="{skin} before repair -- baked defect, seam-zoom crop">
        <div class="img-cap">seam-zoom (click for full-res)</div>
      </a>
      <a class="imglink" href="{full}" target="_blank" rel="noopener">
        <img src="{thumb}" loading="lazy" alt="{skin} before repair -- full skin context">
        <div class="img-cap">full skin, crop_box boxed (click for full-res)</div>
      </a>
    </div>'''
    thumb = f"web/composite/{skin}__{model}-fullskin-thumb.jpg"
    full = f"web/composite/{skin}__{model}-fullskin-full.jpg"
    seam_thumb = f"web/composite/{skin}__{model}-seam-thumb.jpg"
    seam_full = f"web/composite/{skin}__{model}-seam-full.jpg"
    v = VERDICTS.get(skin, {}).get(model, {"v": "?", "note": "not scored"})
    color = VERDICT_COLOR.get(v["v"], "#666")
    return f'''<div class="cell">
      <div class="cell-label">{info["label"]}</div>
      <div class="cell-endpoint">{info["endpoint"]}</div>
      <div class="cell-cost">{info["cost_note"]}</div>
      <a class="imglink" href="{seam_full}" target="_blank" rel="noopener">
        <img src="{seam_thumb}" loading="lazy" alt="{skin} x {model} seam-zoom crop, composited onto full skin">
        <div class="img-cap">seam-zoom (click for full-res)</div>
      </a>
      <a class="imglink" href="{full}" target="_blank" rel="noopener">
        <img src="{thumb}" loading="lazy" alt="{skin} x {model} full skin composite">
        <div class="img-cap">full skin, crop_box boxed (click for full-res)</div>
      </a>
      <div class="badge" style="background:{color}">{v["v"]}</div>
      <div class="note">{v["note"]}</div>
    </div>'''


def main():
    rows_html = []
    for skin in SKINS:
        meta = CROPS_META[skin]
        cells = [cell_html(skin, None, is_before=True)] + [cell_html(skin, m) for m in MODELS]
        rows_html.append(f'''
    <div class="skin-block">
      <div class="skin-title">{skin}</div>
      <div class="skin-material">material: {meta["material"]}</div>
      <div class="row">
        {"".join(cells)}
      </div>
    </div>''')

    cost_rows = []
    for m in MODELS:
        info = MODEL_INFO[m]
        cost_rows.append(f"<tr><td>{info['label']}</td><td>{info['endpoint']}</td><td>{info['cost_note']}</td></tr>")

    # tally
    tally = {m: {"PASS": 0, "FAIL": 0} for m in MODELS}
    for skin in SKINS:
        for m in MODELS:
            v = VERDICTS[skin][m]["v"]
            key = "PASS" if v == "PASS" else "FAIL"
            tally[m][key] += 1

    tally_rows = []
    for m in MODELS:
        t = tally[m]
        tally_rows.append(f"<tr><td>{MODEL_INFO[m]['label']}</td><td>{t['PASS']}/3 PASS</td><td>{MODEL_INFO[m]['cost_note']}</td></tr>")

    total_gen_spend = 3*0.040 + 3*0.080 + 3*0.045 + (0.0613+0.0612+0.0612)
    total_vlm_spend = 0.0346825 + 0.0318275 + 0.0304725
    total_spend = total_gen_spend + total_vlm_spend

    html = f"""<!doctype html>
<meta charset="utf-8">
<title>inpaint bake-off arm 3 -- general editors vs Vertex baseline</title>
<style>{CSS}</style>
<body>
  <h1>Inpaint bake-off -- ARM 3: general image-editing models vs Vertex gemini-3-pro baseline</h1>
  <div class="sub">Goal: find a model CHEAPER than Vertex that matches its quality erasing baked slider thumbs on ORNATE (carved/rune/gothic) skins, where dedicated erasers (LaMa, Bria, and here Finegrain) fail to understand the material.</div>
  <div class="sub">All edits sent the TIGHT crop_box from arm 1/2's crops_meta.json (not whole-slot) for apples-to-apples comparison. Vertex column is REUSED from arm 1's results -- zero fresh spend.</div>

  <div class="cost-banner">
    <b>Models used + real per-call cost:</b>
    <table class="cost-table">
      <tr><th>Model</th><th>Endpoint</th><th>Cost</th></tr>
      {"".join(cost_rows)}
    </table>
    <b>Total generation spend:</b> ${total_gen_spend:.4f} (9 edit calls across 3 models x 3 skins, Vertex reused at $0) &nbsp;|&nbsp;
    <b>SOTA vision review spend</b> (google/gemini-2.5-pro via openrouter/router/vision, 3 calls, one per skin, per sota-eye-review-rule since this arm ran on Sonnet not Opus/Fable): ${total_vlm_spend:.4f} &nbsp;|&nbsp;
    <b>Grand total: ${total_spend:.4f}</b> (cap was $1.00)
  </div>

  {"".join(rows_html)}

  <div class="verdict-section">
    <h2>CONCLUSION / VERDICT</h2>
    <table class="verdict-table">
      <tr><th>Model</th><th>Score (of 3 ornate skins)</th><th>Cost</th></tr>
      {"".join(tally_rows)}
    </table>
    <p><b>Vertex gemini-3-pro-image scored 3/3 PASS</b> -- clean erasure, no hallucination, material-consistent on every skin tested. It remains the quality ceiling in this bake-off.</p>
    <p><b>gemini25-flash (Nano Banana, $0.040/call, ~6x cheaper than Vertex) scored 2/3 PASS.</b> It matched Vertex cleanly on wc-goldshield and fallout-vault (no hallucinated objects, correct groove geometry, texture close to Vertex). Its one failure (diablo-gothic) was NOT object hallucination -- it erased the glowing rune-inlay crack detail entirely, leaving flat material where Vertex preserved the glow. That is a describable, narrower failure mode than the other candidates' outright invented geometry.</p>
    <p><b>gemini31-flash ($0.080/call) scored 1/3</b> -- hallucinated a spiral/scroll motif on wc-goldshield and left residual horn shapes on diablo-gothic; only clean on fallout-vault.</p>
    <p><b>finegrain-eraser (dedicated eraser, $0.045/call) scored 0/3</b> -- confirms the bake-off's core hypothesis: a dedicated eraser without real "understanding" of ornate carved/gothic material either barely erases the defect (diablo-gothic: horns nearly untouched) or replaces it with a different, ill-fitting blob/claw shape (wc-goldshield, fallout-vault) rather than reconstructing plausible surrounding material.</p>
    <p><b>gpt-image-2 (real cost $0.0612/call, not the ambiguous $1/"unit" fal lists) scored 1/3 clean + 1 borderline.</b> Clean on fallout-vault (VLM: texture "far superior" to Vertex there), borderline-fail on wc-goldshield (correct shape, slightly smudged texture), and failed on diablo-gothic (invented a mismatched diamond-facet pattern instead of continuing the Y-rune).</p>
    <div class="rec">
      <b>Routing recommendation:</b> No cheaper model FULLY matches Vertex across all 3 ornate skins tested. <b>gemini25-flash is the closest cheaper candidate</b> (2/3 clean matches, ~$0.04 vs Vertex's $0.241 -- a 6x cost reduction) and its one failure mode (losing a glow/inlay highlight, not inventing geometry) is arguably the least damaging kind of miss and may be fixable with a prompt addition explicitly instructing "preserve and continue any glowing crack/rune/inlay pattern through the erased region" (untested here, would need a follow-up arm).
      <br><br>
      Given the mixed record, the safe default for erase12.py remains <b>Vertex gemini-3-pro</b> for ornate/rune-carved material specifically, with <b>gemini25-flash as a cheap first-pass candidate</b> worth a scored retry with the inlay-preservation prompt fix before displacing Vertex as the default. Do not route ornate-material erases to finegrain-eraser (or by extension LaMa/Bria per arms 1-2) -- 0/3 confirms dedicated erasers don't generalize to this material class.
    </div>
  </div>
</body>
"""
    out_path = os.path.join(HERE, "index.html")
    open(out_path, "w").write(html)
    print(f"[ok] wrote {out_path}")
    print(f"total gen spend: ${total_gen_spend:.4f}  vlm spend: ${total_vlm_spend:.4f}  grand total: ${total_spend:.4f}")


if __name__ == "__main__":
    main()
