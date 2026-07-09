#!/usr/bin/env python3
"""build_index — render abshape/index.html from scores.json (+ verdict.json if present)."""
import os, json, html

HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(HERE, "scores.json")))
V = {}
vp = os.path.join(HERE, "verdict.json")
if os.path.exists(vp): V = json.load(open(vp))

RUNS = [("A", 121), ("A", 134), ("B", 121), ("B", 134)]
COND_LABEL = {"A": "A — OUTLINE guides (current)", "B": "B — SOLID FILLED guides"}

def cell(cond, seed):
    tag = f"{cond.lower()}-{seed}"
    s = S.get(tag)
    d = f"assets-abshape-{tag}"
    if not s:
        return f"<div class='cell'><h3>{COND_LABEL[cond]} · seed {seed}</h3><p>generation failed</p></div>"
    empt = s.get("empt_interior_pct", {})
    vis = (V.get("per_gen") or {}).get(tag, "")
    return f"""
  <div class='cell'>
    <h3>{COND_LABEL[cond]} · seed {seed}</h3>
    <a href='{d}/paint.png'><img class='paint' src='{d}/paint.png' alt='paint {tag}'></a>
    <div class='crops'>
      <figure><a href='{d}/crop-vol.png'><img src='{d}/crop-vol.png' alt='vol socket {tag}'></a><figcaption>vol socket (must be an empty hole)</figcaption></figure>
      <figure><a href='{d}/crop-seek.png'><img src='{d}/crop-seek.png' alt='seek slot {tag}'></a><figcaption>seek slot (must be an empty channel)</figcaption></figure>
    </div>
    <div class='mini'>
      <a href='{d}/blueprint.png'>blueprint</a> · <a href='{d}/mask.png'>mask</a> · <a href='{d}/overlay.png'>overlay</a>
    </div>
    <table class='mini-scores'>
      <tr><td>leak (worst control)</td><td class='{ "bad" if s["leak_pct"]>0.30 else "ok"}'>{s["leak_pct"]:.4f}%</td></tr>
      <tr><td>emptiness gate</td><td class='{ "ok" if s["empty_ok"] else "bad"}'>{"pass" if s["empty_ok"] else "FAIL"}</td></tr>
      <tr><td>socket interiors (vol/seek/shuffle)</td><td>{empt.get("vol","?")}% / {empt.get("seek","?")}% / {empt.get("shuffle","?")}%</td></tr>
      <tr><td>controls detected</td><td class='{ "ok" if s["controls"]==s["controls_total"] else "bad"}'>{s["controls"]}/{s["controls_total"]}</td></tr>
      <tr><td>seek coverage</td><td>{s.get("seek_cov")}</td></tr>
    </table>
    {f"<p class='visual'>{html.escape(vis)}</p>" if vis else ""}
  </div>"""

rows_tbl = ""
for cond, seed in RUNS:
    tag = f"{cond.lower()}-{seed}"
    s = S.get(tag)
    if not s: rows_tbl += f"<tr><td>{cond}</td><td>{seed}</td><td colspan='5'>failed</td></tr>"; continue
    e = s.get("empt_interior_pct", {})
    rows_tbl += (f"<tr><td>{cond}</td><td>{seed}</td>"
                 f"<td class='{ 'bad' if s['leak_pct']>0.30 else 'ok'}'>{s['leak_pct']:.4f}%</td>"
                 f"<td class='{ 'ok' if s['empty_ok'] else 'bad'}'>{'pass' if s['empty_ok'] else 'FAIL'}</td>"
                 f"<td>{e.get('vol','?')} / {e.get('seek','?')} / {e.get('shuffle','?')}</td>"
                 f"<td class='{ 'ok' if s['controls']==s['controls_total'] else 'bad'}'>{s['controls']}/{s['controls_total']}</td>"
                 f"<td>{s.get('seek_cov')}</td></tr>")

verdict_html = html.escape(V.get("verdict", "(pending human/agent visual read)")).replace("\n", "<br>")

page = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>abshape A/B — outline vs solid guide shapes (gen12 / fa-pod)</title>
<style>
  body {{ background:#101014; color:#ddd; font:14px/1.5 -apple-system, system-ui, sans-serif; margin:0; padding:16px clamp(8px,3vw,40px); }}
  h1 {{ font-size:clamp(18px,2.5vw,26px); margin:.2em 0; }}
  .anno {{ color:#9a9; font-size:12px; border:1px solid #2a2a30; border-radius:8px; padding:8px 12px; background:#16161c; margin:10px 0 18px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:18px; }}
  .cell {{ background:#16161c; border:1px solid #2a2a30; border-radius:10px; padding:12px; }}
  .cell h3 {{ margin:.1em 0 .5em; font-size:14px; color:#8cf; }}
  img.paint {{ width:100%; height:auto; border-radius:6px; display:block; }}
  .crops {{ display:flex; gap:8px; margin-top:8px; flex-wrap:wrap; }}
  .crops figure {{ flex:1 1 130px; margin:0; }}
  .crops img {{ width:100%; height:auto; border-radius:4px; display:block; border:1px solid #333; }}
  figcaption {{ font-size:11px; color:#889; }}
  .mini {{ font-size:11px; margin-top:6px; }}
  a {{ color:#7ab8ff; }}
  table {{ border-collapse:collapse; margin-top:8px; width:100%; }}
  td, th {{ border:1px solid #2a2a30; padding:3px 8px; font-size:12px; text-align:left; }}
  .ok {{ color:#7f7; }} .bad {{ color:#f66; font-weight:bold; }}
  .visual {{ font-size:12px; color:#cb9; }}
  .verdict {{ background:#1a2016; border:1px solid #3a4a30; border-radius:10px; padding:14px 18px; margin:20px 0; max-width:75ch; }}
  .tblwrap {{ overflow-x:auto; }}
</style></head><body>
<h1>abshape A/B — OUTLINE vs SOLID FILLED guide shapes</h1>
<div class='anno'>Experiment: gen12 templated blueprint, theme <b>fa-pod</b>, identical structural prompt
(4-substitution wording diff for B, recorded in each results.json), seeds 121 &amp; 134.<br>
Model: <b>gemini-3-pro-image-preview</b> via Vertex AI (project muser-2605300220, global endpoint),
4K, 5:4 — same model the fal path proxies. Scoring: genskin leak gate + extract12 pass&nbsp;1 (no matte).<br>
Cost: 4 gens × ~$0.24/4K image ≈ <b>$0.96 total</b> (extraction local, $0).</div>

<div class='tblwrap'><table>
<tr><th>cond</th><th>seed</th><th>leak (worst)</th><th>emptiness</th><th>socket interior % (vol/seek/shuffle)</th><th>controls</th><th>seek cov</th></tr>
{rows_tbl}
</table></div>

<div class='verdict'><b>Verdict:</b><br>{verdict_html}</div>

<div class='grid'>
{cell('A',121)}{cell('B',121)}{cell('A',134)}{cell('B',134)}
</div>
</body></html>"""
open(os.path.join(HERE, "index.html"), "w").write(page)
print("-> index.html")
