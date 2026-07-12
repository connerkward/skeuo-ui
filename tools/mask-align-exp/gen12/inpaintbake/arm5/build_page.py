#!/usr/bin/env python3
"""build_page (arm 5) -- renders arm5/index.html: the two cost-efficient frontrunners (Gemini
2.5 Flash Image, GPT Image 2) head-to-head on 5 skins with the PLAIN shipping erase12.py prompt
(no glow/rune/inlay clause). Per-skin row: BEFORE (baked defect) | Gemini | GPT, each with a
seam-zoom + full-skin composite (crop pasted back with production's feathered blend), verdict
badge + note. Model + real per-call cost annotated (dev-facing-model-cost-annotation-rule),
every image legibly labeled (label-overlays-rule), responsive (responsive-web-rule), ends with a
CONCLUSION/VERDICT section pulled from verdicts.json. Read-only against arm5_crops_meta.json +
verdicts.json; only writes index.html.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
CROPS_META = json.load(open(os.path.join(HERE, "arm5_crops_meta.json")))
VERDICTS = json.load(open(os.path.join(HERE, "verdicts.json")))

SKINS = ["diablo-gothic", "fallout-pipboy", "n64-cutscene", "claymation", "steam-porthole"]
MODELS = ["gemini25-flash", "gpt-image-2"]

# real measured per-call cost, this arm (see cost_log.json)
GEMINI_COST = 0.039
GPT_COST = 0.0548
N_CALLS_EACH = 5

MODEL_INFO = {
    "gemini25-flash": {
        "label": "Gemini 2.5 Flash Image (“Nano Banana”)",
        "endpoint": "Vertex AI direct · gemini-2.5-flash-image (imageSize 2K)",
        "cost": GEMINI_COST,
        "cost_note": "$0.039/call (Vertex 2K tier, direct — not fal-wrapped, per generation-spend-rule §3)",
    },
    "gpt-image-2": {
        "label": "GPT Image 2 (OpenAI, via fal)",
        "endpoint": "fal openai/gpt-image-2/edit · quality=medium",
        "cost": GPT_COST,
        "cost_note": "$0.0548/call REAL BILLED (x-fal-billable-units=0.0548 × $1/unit, measured live all 5 calls; quality=high measured $0.22/call and was rejected as 4× the price)",
    },
}

VERDICT_COLOR = {"PASS": "#2d8f3f", "SOFT": "#b8860b", "HARD": "#a83232"}
VERDICT_LABEL = {"PASS": "PASS — clean", "SOFT": "SOFT fail", "HARD": "HARD fail"}

CSS = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body {
  background:#0a0a0d; color:#e4e4e8; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  margin:0; padding:20px; line-height:1.5; max-width:1500px; margin:0 auto;
}
h1 { font-size:1.4rem; margin:0 0 6px; }
h2 { font-size:1.1rem; margin:32px 0 12px; border-bottom:1px solid #2a2a32; padding-bottom:6px; }
.sub { color:#9a9aa8; font-size:.9rem; margin-bottom:4px; }
.cost-banner {
  background:#14141a; border:1px solid #2a2a32; border-radius:8px; padding:12px 16px;
  margin:16px 0 28px; font-size:.86rem; color:#c8c8d4;
}
.cost-banner b { color:#e4e4e8; }
.cost-table { width:100%; border-collapse:collapse; margin:10px 0 14px; font-size:.82rem; }
.cost-table th, .cost-table td { text-align:left; padding:6px 10px; border-bottom:1px solid #22222a; vertical-align:top; }
.cost-table th { color:#9a9aa8; font-weight:600; }
.skin-block { margin-bottom:40px; }
.skin-title { font-size:1.08rem; font-weight:700; margin-bottom:2px; }
.skin-material { color:#9a9aa8; font-size:.82rem; margin-bottom:4px; font-style:italic; }
.skin-control { color:#7a7a86; font-size:.76rem; margin-bottom:14px; }
.row { display:flex; flex-wrap:wrap; gap:16px; }
.cell {
  flex:1 1 300px; max-width:460px; background:#131318; border:1px solid #24242c; border-radius:10px;
  padding:12px; display:flex; flex-direction:column; gap:8px;
}
.cell.before { border-color:#4a2a2a; background:#181212; }
.cell img { width:100%; border-radius:6px; display:block; background:#000; }
.cell-label { font-weight:700; font-size:.92rem; }
.cell-endpoint { font-size:.73rem; color:#8a8a96; word-break:break-word; }
.cell-cost { font-size:.78rem; color:#c8b060; }
.imgs { display:flex; flex-direction:column; gap:8px; }
.img-cap { font-size:.68rem; color:#7a7a86; text-align:center; margin-top:-4px; }
a.imglink { text-decoration:none; }
.badge {
  display:inline-block; padding:3px 10px; border-radius:4px; font-size:.74rem; font-weight:800;
  color:#fff; width:fit-content; letter-spacing:.02em;
}
.note { font-size:.79rem; color:#c4c4cc; }
.verdict-section {
  background:#101014; border:2px solid #3a3a44; border-radius:12px; padding:22px; margin-top:40px;
}
.verdict-section h2 { border:none; margin-top:0; }
.verdict-table { width:100%; border-collapse:collapse; margin:12px 0 18px; font-size:.86rem; }
.verdict-table th, .verdict-table td { text-align:left; padding:8px 10px; border-bottom:1px solid #24242c; vertical-align:top; }
.verdict-table th { color:#9a9aa8; }
.verdict-table td.g { color:#8fd6a0; } .verdict-table td.gp { color:#d8c07a; } .verdict-table td.b { color:#e29a9a; }
.rec { background:#14241a; border:1px solid #2d5f3f; border-radius:8px; padding:16px; margin-top:14px; font-size:.9rem; }
.legend { font-size:.78rem; color:#9a9aa8; margin:6px 0 0; }
"""


def cell_before(skin):
    thumb = f"web/composite/{skin}__BEFORE-seam-thumb.jpg"
    full = f"web/composite/{skin}__BEFORE-seam-full.jpg"
    fthumb = f"web/composite/{skin}__BEFORE-fullskin-thumb.jpg"
    ffull = f"web/composite/{skin}__BEFORE-fullskin-full.jpg"
    return f'''<div class="cell before">
      <div class="cell-label">BEFORE — baked defect (input)</div>
      <div class="cell-endpoint">the pre-erase paint, defect present — what both models were asked to repair</div>
      <div class="imgs">
        <a class="imglink" href="{full}" target="_blank" rel="noopener"><img src="{thumb}" loading="lazy" alt="{skin} BEFORE, seam-zoom"></a>
        <div class="img-cap">seam-zoom (click → full-res)</div>
        <a class="imglink" href="{ffull}" target="_blank" rel="noopener"><img src="{fthumb}" loading="lazy" alt="{skin} BEFORE, full skin"></a>
        <div class="img-cap">full skin, repair box outlined red (click → full-res)</div>
      </div>
    </div>'''


def cell_model(skin, model):
    info = MODEL_INFO[model]
    thumb = f"web/composite/{skin}__{model}-seam-thumb.jpg"
    full = f"web/composite/{skin}__{model}-seam-full.jpg"
    fthumb = f"web/composite/{skin}__{model}-fullskin-thumb.jpg"
    ffull = f"web/composite/{skin}__{model}-fullskin-full.jpg"
    v = VERDICTS.get(skin, {}).get(model, {"v": "?", "note": ""})
    color = VERDICT_COLOR.get(v["v"], "#666")
    return f'''<div class="cell">
      <div class="cell-label">{info["label"]}</div>
      <div class="cell-endpoint">{info["endpoint"]}</div>
      <div class="cell-cost">{info["cost_note"]}</div>
      <div class="imgs">
        <a class="imglink" href="{full}" target="_blank" rel="noopener"><img src="{thumb}" loading="lazy" alt="{skin} x {model}, seam-zoom composite"></a>
        <div class="img-cap">seam-zoom, composited back onto full skin (click → full-res)</div>
        <a class="imglink" href="{ffull}" target="_blank" rel="noopener"><img src="{fthumb}" loading="lazy" alt="{skin} x {model}, full skin composite"></a>
        <div class="img-cap">full skin, repair box outlined red (click → full-res)</div>
      </div>
      <div class="badge" style="background:{color}">{VERDICT_LABEL.get(v["v"], v["v"])}</div>
      <div class="note">{v["note"]}</div>
    </div>'''


def main():
    rows = []
    for skin in SKINS:
        meta = CROPS_META[skin]
        cells = [cell_before(skin)] + [cell_model(skin, m) for m in MODELS]
        rows.append(f'''
    <div class="skin-block">
      <div class="skin-title">{skin}</div>
      <div class="skin-material">material: {meta["material"]}</div>
      <div class="skin-control">control / defect: {meta.get("control", "seek (slider)")}</div>
      <div class="row">{"".join(cells)}</div>
    </div>''')

    # tally: PASS / SOFT / HARD per model
    tally = {m: {"PASS": 0, "SOFT": 0, "HARD": 0} for m in MODELS}
    for skin in SKINS:
        for m in MODELS:
            tally[m][VERDICTS[skin][m]["v"]] += 1

    def clean_count(m):  # PASS + SOFT = "acceptable" (erased, no invented geometry / no black box)
        return tally[m]["PASS"], tally[m]["PASS"] + tally[m]["SOFT"]

    g_pass, g_ok = clean_count("gemini25-flash")
    p_pass, p_ok = clean_count("gpt-image-2")

    tally_rows = []
    for m in MODELS:
        t = tally[m]
        cls = "g" if m == "gemini25-flash" else "gp"
        tally_rows.append(
            f"<tr><td>{MODEL_INFO[m]['label']}</td>"
            f"<td class='{cls}'>{t['PASS']} PASS · {t['SOFT']} SOFT · {t['HARD']} HARD</td>"
            f"<td>${MODEL_INFO[m]['cost']:.4f}/call</td></tr>")

    total_gen = N_CALLS_EACH * (GEMINI_COST + GPT_COST)
    glow_gen = 5 * 0.039 + 6 * 0.0548 + 1 * 0.2195  # discarded glow-clause run (real prior spend)

    html = f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>inpaint bake-off arm 5 — Gemini 2.5 Flash vs GPT Image 2, PLAIN prompt, 5 skins</title>
<style>{CSS}</style>
<body>
  <h1>Inpaint bake-off — ARM 5: Gemini 2.5 Flash vs GPT Image 2, PLAIN erase prompt, 5 skins</h1>
  <div class="sub">The two cost-efficient frontrunners from arm 3, run head-to-head across a BROADER material range (5 skins vs arm-3's 3) to see whether the ranking generalizes.</div>
  <div class="sub"><b>Prompt = the plain shipping erase12.py instruction</b> ("remove the part sitting in the groove/socket, continue the material, no new object/icon") — <b>no glow/rune/inlay/emissive clause</b>. A preserve-glow variant was tried first and discarded: it over-constrained the model into <i>inventing</i> new glow ornamentation (a hallucinated skull medallion on diablo). Same crop + mask + prompt to both models (controlled comparison).</div>

  <div class="cost-banner">
    <b>Models used + real measured per-call cost:</b>
    <table class="cost-table">
      <tr><th>Model</th><th>Endpoint</th><th>Cost (measured this arm)</th></tr>
      <tr><td>{MODEL_INFO['gemini25-flash']['label']}</td><td>{MODEL_INFO['gemini25-flash']['endpoint']}</td><td>{MODEL_INFO['gemini25-flash']['cost_note']}</td></tr>
      <tr><td>{MODEL_INFO['gpt-image-2']['label']}</td><td>{MODEL_INFO['gpt-image-2']['endpoint']}</td><td>{MODEL_INFO['gpt-image-2']['cost_note']}</td></tr>
    </table>
    <b>Arm-5 generation spend (this run):</b> 5 Gemini × $0.039 + 5 GPT × $0.0548 = <b>${total_gen:.4f}</b>
    &nbsp;|&nbsp; <b>Discarded glow-clause run</b> (real prior spend, archived under discarded-glowclause/, NOT in this verdict): ~${glow_gen:.3f}
    &nbsp;|&nbsp; matte/composite/scoring steps: $0 (local code).
    <div class="legend">Legend — <b style="color:#8fd6a0">PASS</b>: defect erased, material continued cleanly, no lost feature, no hallucination. <b style="color:#d8c07a">SOFT fail</b>: erased but a material feature lost / minor texture mismatch; no invented geometry. <b style="color:#e29a9a">HARD fail</b>: defect NOT removed, OR new geometry hallucinated, OR catastrophic (black box).</div>
  </div>

  {"".join(rows)}

  <div class="verdict-section">
    <h2>CONCLUSION / VERDICT</h2>
    <table class="verdict-table">
      <tr><th>Model</th><th>Score across 5 skins</th><th>Cost</th></tr>
      {"".join(tally_rows)}
    </table>
    <p><b>On the 4 genuine slider-groove skins</b> (diablo-gothic, fallout-pipboy, n64-cutscene, claymation) — the cases this pipeline actually erases — <b>Gemini 2.5 Flash went 4/4 clean PASS</b> and <b>GPT Image 2 went 3/4 PASS + 1 SOFT</b> (GPT lost the diablo rune-glow and muddied the groove; Gemini preserved it). Both models cleanly emptied the fallout-pipboy slot, the n64 channel, and the claymation clay slot with material-consistent fill and no hallucination.</p>
    <p><b>The plain prompt fixed arm-3's worry, not caused it.</b> Arm 3 flagged Gemini erasing the diablo rune-glow. Under the PLAIN prompt (no glow instruction) Gemini <i>naturally preserved and continued</i> the rune-inlay cracks while removing the baked skull medallion — a clean PASS. The glow clause was the problem (it made the model invent glow ornamentation), not the fix. Dropping it was correct.</p>
    <p><b>steam-porthole was an ambiguous target and broke both models.</b> Its masked region is a round brass control that reads as a legitimate play/pause button (rewind|play/pause|ff row), not a slider thumb — so it is a weak erase target. Gemini regenerated the button in place (didn't erase, but did no damage); <b>GPT Image 2 returned a solid BLACK SQUARE</b> filling the mask (its mask-fill-collapse failure mode — the real raw output). That black-box behavior is a serious production risk for gpt-image-2 on any mask it can't reconcile, and it never happened with Gemini.</p>
    <div class="rec">
      <b>Routing recommendation:</b> <b>Gemini 2.5 Flash Image (Vertex direct, $0.039/call) is the winner</b> — 4/4 clean on real slider-groove erases including the ornate rune-glow case, at ~40% lower per-call cost than GPT Image 2 medium ($0.0548) and ~6× cheaper than the Vertex gemini-3-pro incumbent ($0.241/repair, 4K tier). It never produced a catastrophic (black-box) result. <b>GPT Image 2 is a viable but riskier #2</b> (also cheap, mostly clean, but one lost-detail SOFT and one catastrophic black-box in five). Do NOT use the preserve-glow prompt clause — the plain instruction lets Gemini handle emissive material correctly on its own. The one open gap is round-socket / wrong-icon defects (steam-porthole), which neither model handles from a generic slider-erase prompt — those need either a different mask/prompt or the incumbent Vertex path.
    </div>
  </div>
</body>
"""
    out_path = os.path.join(HERE, "index.html")
    open(out_path, "w").write(html)
    print(f"[ok] wrote {out_path}")
    print(f"gemini: {g_pass} PASS / {g_ok} acceptable of 5   gpt: {p_pass} PASS / {p_ok} acceptable of 5")
    print(f"arm5 gen spend: ${total_gen:.4f}")


if __name__ == "__main__":
    main()
