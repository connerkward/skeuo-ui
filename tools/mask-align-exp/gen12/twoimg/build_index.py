#!/usr/bin/env python3
"""build_index — render twoimg/results.html from scores.json + per-gen vlm.json.

Matrix: 2 themes (fa-pod, wc-goldshield) x 2 seeds (121, 134) x 2 arms (control, treat).
CONTROL = current single-canvas approach (solid guide shapes baked into the edit target,
the abshape-verdict winner). TREAT = clean scaffold edit target + a SECOND reference image
carrying the same guide shapes, prompted as position-only / never-painted.
"""
import os, json, html

HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(HERE, "scores.json"))) if os.path.exists(os.path.join(HERE, "scores.json")) else {}
V = json.load(open(os.path.join(HERE, "verdict.json"))) if os.path.exists(os.path.join(HERE, "verdict.json")) else {}

THEMES = [
    {"id": "fa-pod", "desc": "bright translucent cyan “Frutiger Aero” water pod (material_is_dark=False)"},
    {"id": "wc-goldshield", "desc": "dark gold / royal-blue heraldic shield (material_is_dark=True)"},
]
SEEDS = [121, 134]
ARM_LABEL = {"control": "CONTROL — single canvas, guides baked in", "treat": "TREAT — clean canvas + 2nd reference image"}
ALL_CTRLS = ["playpause", "prev", "next", "repeat", "queue", "vol", "seek", "shuffle", "visualizer", "album_art"]


def tag_for(theme, arm, seed): return f"{theme}-{arm}-{seed}"


def vlm_for(theme, arm, seed):
    d = os.path.join(HERE, f"assets-twoimg-{tag_for(theme, arm, seed)}", "vlm.json")
    return json.load(open(d)) if os.path.exists(d) else None


def cell(theme, arm, seed):
    tag = tag_for(theme, arm, seed)
    s = S.get(tag)
    d = f"assets-twoimg-{tag}"
    if not s:
        return f"<div class='cell'><h3>{ARM_LABEL[arm]} · seed {seed}</h3><p class='bad'>generation failed / not scored</p></div>"
    bleed = s.get("bleed_ring_pct", {})
    worst = s.get("bleed_ring_worst", {"control": "none", "pct": 0})
    vlm = vlm_for(theme, arm, seed)
    crops = "".join(
        f"<figure><a href='{d}/crop-{n}.png'><img src='{d}/crop-{n}.png' alt='{n} crop {tag}'></a>"
        f"<figcaption>{n} — bleed-ring {bleed.get(n, '?')}%</figcaption></figure>"
        for n in ALL_CTRLS if os.path.exists(os.path.join(HERE, d, f"crop-{n}.png"))
    )
    bp_links = (f"<a href='{d}/blueprint-clean.png'>clean scaffold (edit target)</a> · "
                f"<a href='{d}/blueprint-guided.png'>guided (reference image 2)</a>") if arm == "treat" else \
               f"<a href='{d}/blueprint-guided.png'>blueprint (guides baked in, sole image)</a>"
    bleed_rows = "".join(
        f"<tr><td>{n}</td><td class='{'bad' if bleed.get(n,0) > 2.0 else ('warn' if bleed.get(n,0) > 0.3 else 'ok')}'>{bleed.get(n,'?')}%</td></tr>"
        for n in ALL_CTRLS if n in bleed)
    vlm_html = ""
    if vlm:
        vcls = "ok" if vlm["verdict"] == "PASS" else ("bad" if vlm["verdict"] == "FAIL" else "warn")
        vlm_html = (f"<div class='vlm'><b>SOTA eye ({html.escape(vlm['eye'])}):</b> "
                    f"<span class='{vcls}'>{vlm['verdict']}</span>"
                    f"<details><summary>raw</summary><pre>{html.escape(str(vlm['raw']))}</pre></details></div>")
    return f"""
  <div class='cell'>
    <h3>{ARM_LABEL[arm]} · seed {seed} <span class='tag'>{tag}</span></h3>
    <a href='{d}/paint.png'><img class='paint' src='{d}/paint.png' alt='paint {tag}'></a>
    <div class='mini'>{bp_links} · <a href='{d}/mask.png'>mask</a>
      {" · <a href='" + d + "/overlay.png'>overlay</a>" if os.path.exists(os.path.join(HERE, d, "overlay.png")) else ""}
    </div>
    <div class='crops'>{crops}</div>
    <table class='mini-scores'>
      <tr><td>leak (worst control, genskin gate)</td><td class='{ "bad" if s["leak_pct"]>0.30 else "ok"}'>{s["leak_pct"]:.4f}%</td></tr>
      <tr><td>emptiness gate</td><td class='{ "ok" if s["empty_ok"] else "bad"}'>{"pass" if s["empty_ok"] else "FAIL"}</td></tr>
      <tr><td>controls detected</td><td class='{ "ok" if s["controls"]==s["controls_total"] else "bad"}'>{s["controls"]}/{s["controls_total"]}</td></tr>
      <tr><td>seek coverage</td><td>{s.get("seek_cov")}</td></tr>
      <tr><td>gate reasons</td><td>{", ".join(s.get("reasons") or []) or "—"}</td></tr>
      <tr><td><b>bleed-ring worst (this experiment's own metric)</b></td>
          <td class='{"bad" if worst["pct"]>2.0 else ("warn" if worst["pct"]>0.3 else "ok")}'><b>{worst["control"]} {worst["pct"]:.3f}%</b></td></tr>
    </table>
    <details class='bleedtbl'><summary>per-control bleed-ring % (perimeter-band hue match to guide key)</summary>
      <table>{bleed_rows}</table>
    </details>
    {vlm_html}
  </div>"""


def theme_section(t):
    theme, desc = t["id"], t["desc"]
    rows = ""
    for seed in SEEDS:
        for arm in ("control", "treat"):
            tag = tag_for(theme, arm, seed); s = S.get(tag)
            if not s:
                rows += f"<tr><td>{arm}</td><td>{seed}</td><td colspan='5'>failed</td></tr>"; continue
            worst = s.get("bleed_ring_worst", {"control": "none", "pct": 0})
            rows += (f"<tr><td>{arm}</td><td>{seed}</td>"
                     f"<td class='{ 'bad' if s['leak_pct']>0.30 else 'ok'}'>{s['leak_pct']:.4f}%</td>"
                     f"<td class='{ 'bad' if worst['pct']>2.0 else ('warn' if worst['pct']>0.3 else 'ok')}'>{worst['control']} {worst['pct']:.3f}%</td>"
                     f"<td class='{ 'ok' if s['empty_ok'] else 'bad'}'>{'pass' if s['empty_ok'] else 'FAIL'}</td>"
                     f"<td class='{ 'ok' if s['controls']==s['controls_total'] else 'bad'}'>{s['controls']}/{s['controls_total']}</td>"
                     f"<td>{s.get('seek_cov')}</td></tr>")
    cells = "".join(cell(theme, arm, seed) for seed in SEEDS for arm in ("control", "treat"))
    return f"""
<h2>Theme — <code>{theme}</code></h2>
<div class='anno small'>{html.escape(desc)}.</div>
<div class='tblwrap'><table>
<tr><th>arm</th><th>seed</th><th>leak (genskin gate, worst)</th><th>bleed-ring (this exp's metric, worst)</th><th>emptiness</th><th>controls</th><th>seek cov</th></tr>
{rows}
</table></div>
<div class='grid'>{cells}</div>
"""


N_GENS = sum(1 for t in THEMES for arm in ("control", "treat") for seed in SEEDS if S.get(tag_for(t["id"], arm, seed)))
PER_IMG = 0.24  # Vertex 4K gemini-3-pro-image-preview, per gen12/TODO.md
VLM_CALLS = sum(1 for t in THEMES for arm in ("control", "treat") for seed in SEEDS if vlm_for(t["id"], arm, seed))
PER_VLM = 0.02
verdict_html = html.escape(V.get("verdict", "(pending human review — see docs/experiments/2026-07-10-twoimg-conditioning.md)")).replace("\n", "<br>")

page = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>twoimg — multi-image conditioning vs single-canvas guide bleed (gen12)</title>
<style>
  body {{ background:#101014; color:#ddd; font:14px/1.5 -apple-system, system-ui, sans-serif; margin:0; padding:16px clamp(8px,3vw,40px); }}
  h1 {{ font-size:clamp(18px,2.5vw,26px); margin:.2em 0; }}
  h2 {{ font-size:clamp(16px,2vw,20px); color:#8cf; margin:28px 0 4px; border-top:1px solid #2a2a30; padding-top:18px; }}
  .anno {{ color:#9a9; font-size:12px; border:1px solid #2a2a30; border-radius:8px; padding:8px 12px; background:#16161c; margin:10px 0 18px; max-width:100ch; }}
  .anno.small {{ padding:6px 10px; margin:4px 0 14px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); gap:18px; }}
  .cell {{ background:#16161c; border:1px solid #2a2a30; border-radius:10px; padding:12px; min-width:0; }}
  .cell h3 {{ margin:.1em 0 .5em; font-size:14px; color:#8cf; }}
  .cell h3 .tag {{ color:#667; font-size:11px; font-weight:normal; }}
  img.paint {{ width:100%; height:auto; border-radius:6px; display:block; max-width:100%; }}
  .crops {{ display:flex; gap:8px; margin-top:8px; flex-wrap:wrap; }}
  .crops figure {{ flex:1 1 110px; margin:0; }}
  .crops img {{ width:100%; height:auto; border-radius:4px; display:block; border:1px solid #333; }}
  figcaption {{ font-size:11px; color:#889; }}
  .mini {{ font-size:11px; margin-top:6px; word-break:break-word; }}
  a {{ color:#7ab8ff; }}
  code {{ background:#20202a; padding:1px 5px; border-radius:4px; }}
  table {{ border-collapse:collapse; margin-top:8px; width:100%; }}
  td, th {{ border:1px solid #2a2a30; padding:3px 8px; font-size:12px; text-align:left; }}
  .ok {{ color:#7f7; }} .bad {{ color:#f66; font-weight:bold; }} .warn {{ color:#fc6; font-weight:bold; }}
  .verdict {{ background:#1a2016; border:1px solid #3a4a30; border-radius:10px; padding:14px 18px; margin:20px 0; max-width:100ch; }}
  .tblwrap {{ overflow-x:auto; }}
  .vlm {{ margin-top:8px; font-size:12px; border-top:1px dashed #333; padding-top:6px; }}
  .vlm pre {{ white-space:pre-wrap; font-size:11px; color:#aab; max-height:220px; overflow:auto; }}
  details.bleedtbl {{ margin-top:6px; font-size:11px; }}
</style></head><body>
<h1>twoimg — separate the layout from the canvas (multi-image conditioning)</h1>
<div class='anno'><b>Hypothesis:</b> guide-colour bleed happens because colour-coded guide shapes are
physically painted INTO the edit-target canvas — sending the layout as a SECOND reference image
with a guide-pixel-FREE clean target makes bleed impossible by construction (verified: the clean
scaffold contains zero pixels within RGB-distance 60 of any guide key, checked programmatically
before any generation ran).<br>
<b>Arms</b> (both use SOLID FILLED guide shapes, the abshape-verdict 2026-07-09 winner):
CONTROL = current single joint canvas (left=guided blueprint, right=black mask target), 1 input
image. TREAT = image 1 (edit target) is a CLEAN scaffold with the SAME geometry and ZERO guide-
coloured pixels; image 2 is the SAME guided blueprint as CONTROL, sent purely as a layout
reference the prompt says is never painted.<br>
<b>Model:</b> gemini-3-pro-image-preview via Vertex AI direct (project muser-2605300220, global),
4K, 5:4 — same underlying model the fal path proxies, chosen because it's the already-proven
~20%-cheaper path (gen12/TODO.md) and both fal's <code>image_urls: array&lt;string&gt;</code> schema
AND Vertex's multi-<code>inline_data</code>-part <code>generateContent</code> shape confirmed
multi-image support before this ran (see genskin_twoimg.py docstring).<br>
<b>Scoring:</b> ../extract12.py pass 1 (no matte) for the shared gates (leak/emptiness/controls/
region-placement) PLUS a bespoke <b>perimeter-band hue-distance bleed-ring metric</b> (this
script's own — the shared leak gate under-counts thin rings/bezels per the abshape verdict, so
this experiment measures its actual target defect directly).<br>
<b>SOTA eye review</b> (this agent is Sonnet, sub-SOTA — per sota-eye-review-rule the final visual
call is routed through a SOTA vision model): {VLM_CALLS} calls to <code>google/gemini-2.5-pro</code>
via fal <code>openrouter/router/vision</code>, one per generation, each sent the downscaled full
paint + full-res vol/seek/shuffle/playpause/queue crops with guide-colour NAMES stated, asked for
a per-control residue call (NONE/RING/FLOODED) + emptiness + one VERDICT line.<br>
<b>Cost:</b> {N_GENS} gens × ~${PER_IMG:.2f}/4K image ≈ <b>${N_GENS*PER_IMG:.2f}</b> generation +
{VLM_CALLS} VLM calls × ~${PER_VLM:.2f} ≈ <b>${VLM_CALLS*PER_VLM:.2f}</b> review ≈
<b>${N_GENS*PER_IMG + VLM_CALLS*PER_VLM:.2f} total</b> (extraction/scoring local, $0).</div>

<div class='verdict'><b>Verdict:</b><br>{verdict_html}</div>

{"".join(theme_section(t) for t in THEMES)}
</body></html>"""
open(os.path.join(HERE, "results.html"), "w").write(page)
print("-> results.html")
