#!/usr/bin/env python3
"""build_page (arm 4) -- renders arm4/index.html: per-skin row comparing 3 NEW cheap erase
candidates (flux-pro-erase, object-removal, gemini25-flash-glow) against arm-1's Vertex
baseline and arm-3's gemini31-flash (both REUSED, not re-spent). Model + real cost annotated
per cell (dev-facing-model-cost-annotation-rule), every image legibly labeled
(label-overlays-rule), responsive (responsive-web-rule), ends with a CONCLUSION/VERDICT
section (dev-facing-model-cost-annotation-rule). Read-only against ../ and ../editors/; only
writes under arm4/.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
CROPS_META = json.load(open(os.path.join(HERE, "..", "crops_meta.json")))
VERDICTS = json.load(open(os.path.join(HERE, "verdicts.json")))
COST_LOG = json.load(open(os.path.join(HERE, "cost_log.json")))

SKINS = ["diablo-gothic", "wc-goldshield", "fallout-vault"]
MODELS = ["vertex", "gemini31-flash", "flux-pro-erase", "object-removal", "gemini25-flash-glow"]

MODEL_INFO = {
    "vertex": {
        "label": "Vertex gemini-3-pro-image (incumbent baseline)",
        "endpoint": "genskin.py:edit_vertex() -- Google Vertex, direct",
        "cost": 0.241, "cost_note": "$0.241/repair (4K tier) -- REUSED from arm 1, no fresh spend here",
        "new": False,
    },
    "gemini31-flash": {
        "label": "Gemini 3.1 Flash Image Preview (arm-3's best cheap candidate)",
        "endpoint": "fal-ai/gemini-3.1-flash-image-preview/edit",
        "cost": 0.080, "cost_note": "$0.080/call -- REUSED from arm 3, no fresh spend here",
        "new": False,
    },
    "flux-pro-erase": {
        "label": "Flux Pro Erase (dedicated no-prompt eraser, NEW this arm)",
        "endpoint": "fal-ai/flux-pro/v1/erase",
        "cost": 0.00419, "cost_note": "$0.004/MP -> $0.00419/call @ 1024x1024",
        "new": True,
    },
    "object-removal": {
        "label": "Object Removal (dedicated no-prompt eraser, NEW this arm)",
        "endpoint": "fal-ai/object-removal/mask",
        "cost": 0.006, "cost_note": "$0.006/call flat",
        "new": True,
    },
    "gemini25-flash-glow": {
        "label": "Gemini 2.5 Flash Image + glow-preserve clause (NEW this arm)",
        "endpoint": "vertex:gemini-2.5-flash-image (direct, not fal-wrapped)",
        "cost": 0.039, "cost_note": "$0.039/call Vertex-direct (vs fal's $0.0398/call for the same model -- Vertex marginally cheaper, used here)",
        "new": True,
    },
}

VERDICT_COLOR = {"PASS": "#2d8f3f", "FAIL": "#a83232"}

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
.cell.new { border-color:#2d5f7f; }
.cell img { width:100%; border-radius:6px; display:block; background:#000; }
.cell-label { font-weight:600; font-size:.88rem; }
.new-badge { display:inline-block; font-size:.62rem; font-weight:700; color:#6fb8e8; border:1px solid #2d5f7f; border-radius:3px; padding:1px 5px; margin-left:6px; vertical-align:middle; }
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
.adjudication { background:#1a1408; border:1px solid #5f4d2d; border-radius:8px; padding:14px; margin-top:16px; font-size:.85rem; }
"""


def cell_html(skin, model, is_before=False):
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
    info = MODEL_INFO[model]
    thumb = f"web/composite/{skin}__{model}-fullskin-thumb.jpg"
    full = f"web/composite/{skin}__{model}-fullskin-full.jpg"
    seam_thumb = f"web/composite/{skin}__{model}-seam-thumb.jpg"
    seam_full = f"web/composite/{skin}__{model}-seam-full.jpg"
    v = VERDICTS.get(skin, {}).get(model, {"v": "?", "note": "not scored"})
    color = VERDICT_COLOR.get(v["v"], "#666")
    new_badge = '<span class="new-badge">NEW</span>' if info["new"] else ""
    cell_class = "cell new" if info["new"] else "cell"
    return f'''<div class="{cell_class}">
      <div class="cell-label">{info["label"]}{new_badge}</div>
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

    new_gen_spend = sum(c.get("cost", 0) or 0 for c in COST_LOG)
    vlm_spend = 0.01824375 + 0.02531125 + 0.0239975  # 3 openrouter/router/vision (gemini-2.5-pro) calls, real billed cost
    total_spend = new_gen_spend + vlm_spend

    html = f"""<!doctype html>
<meta charset="utf-8">
<title>inpaint bake-off arm 4 -- cheap erasers vs Vertex baseline</title>
<style>{CSS}</style>
<body>
  <h1>Inpaint bake-off -- ARM 4: 3 CHEAPER erase options vs arm-3's results</h1>
  <div class="sub">Goal: settle whether any cheap model is viable for the baked-slider-thumb erase. Tests 2 dedicated no-prompt erasers (flux-pro-erase $0.004/MP, object-removal $0.006/img -- both 10-30x cheaper than Vertex) plus a retry of gemini25-flash with an explicit glow-preserve prompt clause (arm-3's closest cheap candidate, which failed diablo-gothic only by erasing the rune-glow).</div>
  <div class="sub">vertex and gemini31-flash columns are REUSED from arm 1 / arm 3 respectively -- zero fresh spend on those two. Only flux-pro-erase, object-removal, and gemini25-flash-glow are new generations this arm.</div>

  <div class="cost-banner">
    <b>Models used + real per-call cost:</b>
    <table class="cost-table">
      <tr><th>Model</th><th>Endpoint</th><th>Cost</th></tr>
      {"".join(cost_rows)}
    </table>
    <b>Total NEW generation spend this arm:</b> ${new_gen_spend:.4f} (9 calls: 3 skins x 3 new models; vertex + gemini31-flash reused at $0 fresh spend) &nbsp;|&nbsp;
    <b>SOTA vision review spend</b> (google/gemini-2.5-pro via openrouter/router/vision, 3 calls, one per skin, per sota-eye-review-rule since this arm ran on Sonnet not Opus/Fable): ${vlm_spend:.4f} &nbsp;|&nbsp;
    <b>Grand total: ${total_spend:.4f}</b> (cap was $0.50)
  </div>

  {"".join(rows_html)}

  <div class="verdict-section">
    <h2>CONCLUSION / VERDICT</h2>
    <table class="verdict-table">
      <tr><th>Model</th><th>Score (of 3 skins)</th><th>Cost</th></tr>
      {"".join(tally_rows)}
    </table>

    <div class="adjudication">
      <b>VLM adjudication note (verify-outputs-rule: VLM is a witness, not a judge):</b> the google/gemini-2.5-pro SOTA cross-check was run per sota-eye-review-rule (this arm ran on Sonnet). It agreed with the human/pixel read on 10 of 15 cells. It was OVERRULED on 3 cells after a deterministic tight-crop pixel comparison directly contradicted it: (1) diablo-gothic vertex -- VLM said "noticeable smooth bump remains, FAIL"; a tight crop shows the skull-face plate is completely gone, only the Y-rune and the frame's own separate horn-tendril decoration remain -- PASS. (2) diablo-gothic flux-pro-erase -- VLM said "completely and cleanly removed, PASS"; a tight crop shows the horned ram-skull face (eye sockets, twin fangs, curved horn) nearly PIXEL-IDENTICAL to BEFORE -- FAIL. (3+4) wc-goldshield and fallout-vault vertex -- VLM called both "smudged, FAIL"; a 1600px crop shows vertex and gemini25-flash-glow are visually indistinguishable in texture, and arm-3's own human reviewer already noted this same softness on fallout-vault while still scoring it PASS -- not a new defect, OVERRULED. The VLM's diablo-gothic vertex/flux-pro-erase read was flatly backwards; this is a reminder the VLM is unreliable for fine object-presence judgments and must always be checked against pixels before acting on its verdict.
    </div>

    <p><b>Vertex gemini-3-pro-image: 3/3 PASS</b> (unchanged from arm 1/3 -- reused, no fresh spend). Remains the quality ceiling.</p>
    <p><b>gemini25-flash-glow (NEW, $0.039/call, ~6x cheaper than Vertex): 2/3 PASS.</b> Clean, vertex-matching results on wc-goldshield and fallout-vault. On diablo-gothic, the explicit "preserve any glowing rune/inlay" instruction OVER-corrected: instead of losing the glow (arm-3's non-glow failure mode), it HALLUCINATED an entirely new glowing rune-chain/filigree pattern running the full length of the groove -- ornamentation that exists nowhere else on the frame. <b>Net result: still 2/3, same score as arm-3's non-glow gemini25-flash, just a different failure mode.</b> The glow-preserve clause did not fix the underlying problem -- it swapped "under-preserve" for "over-invent." A more targeted instruction (something closer to "continue the EXISTING glow crack exactly as-is, do not add new glowing elements") would need its own retry to test whether a further-refined prompt can actually reach 3/3; this arm did not find that prompt.</p>
    <p><b>flux-pro-erase (NEW, dedicated no-prompt eraser, $0.004/MP, ~57x cheaper than Vertex): 0/3 PASS.</b> Failed on ALL THREE skins, including fallout-vault -- the SIMPLEST material tested (plain rusted steel, no carving, no ornamentation). The pill-shaped thumb bump on fallout-vault came back essentially pixel-unchanged, 3D form and shadows intact. This is decisive: the failure is not about ornate-material complexity, it's that a no-prompt eraser with no "what is this object" understanding simply doesn't register a painted/rendered raised control as an erasable object at all, regardless of material.</p>
    <p><b>object-removal (NEW, dedicated no-prompt eraser, $0.006/call, ~40x cheaper than Vertex): 0/3 PASS.</b> Same story -- failed on all 3 skins including fallout-vault, often leaving the bump plus a new scratch/smudge artifact. Confirms the same conclusion as flux-pro-erase: dedicated no-prompt erasers are not viable for this task at any material complexity tested here.</p>

    <div class="rec">
      <b>Routing recommendation for erase12.py:</b>
      <br><br>
      (a) <b>Neither cheap dedicated eraser (flux-pro-erase, object-removal) is viable as a cost tier for ANY material complexity</b> tested, including the flattest/simplest skin. Both scored 0/3, failing to even recognize the baked thumb as an object to remove on plain rusted steel. Do not route any erase to either model.
      <br><br>
      (b) <b>gemini25-flash-glow did NOT reach 3/3</b> and does not yet displace Vertex as the default. It ties arm-3's non-glow gemini25-flash at 2/3 -- the glow-preserve clause traded one diablo-gothic failure mode (erasing the glow) for another (inventing new glow ornamentation), netting no improvement. It remains a candidate worth a further prompt-refinement retry specifically targeting "continue the glow crack exactly, do not add new glowing elements elsewhere" -- untested here.
      <br><br>
      <b>Overall: this arm found no cheap model that fully matches Vertex.</b> Vertex gemini-3-pro remains the safe default for erase12.py. gemini25-flash(-glow) remains a cheap first-pass candidate (2/3 across two independent tries) worth one more targeted prompt iteration before any routing change; the two no-prompt dedicated erasers are ruled out entirely, at any cost tier.
    </div>
  </div>
</body>
"""
    out_path = os.path.join(HERE, "index.html")
    open(out_path, "w").write(html)
    print(f"[ok] wrote {out_path}")
    print(f"new gen spend: ${new_gen_spend:.4f}  vlm spend: ${vlm_spend:.4f}  grand total: ${total_spend:.4f}")


if __name__ == "__main__":
    main()
