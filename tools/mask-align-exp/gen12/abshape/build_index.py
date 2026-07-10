#!/usr/bin/env python3
"""build_index — render abshape/index.html from scores.json (+ verdict.json if present).

Two rounds, same protocol (A=outline guides, B=solid filled guides), different themes:
  round 1: fa-pod         (bright translucent cyan "water pod", material_is_dark=False)
  round 2: wc-goldshield  (dark gold/royal-blue heraldic shield, material_is_dark=True)
Round 2 exists to check whether the outline-vs-solid finding from round 1 holds on a
visually contrasting theme, or was a fa-pod-specific artifact. Both rounds ran via
Vertex AI direct (genskin_ab.py's edit_vertex, gcloud-token auth) — NOT fal — so the
2026-07 fal account lock does not block either round.
"""
import os, json, html

HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(HERE, "scores.json")))
V = {}
vp = os.path.join(HERE, "verdict.json")
if os.path.exists(vp): V = json.load(open(vp))

ROUNDS = [
    {"theme": None, "label": "fa-pod", "desc": "bright translucent cyan “water pod” (material_is_dark=False)"},
    {"theme": "wc-goldshield", "label": "wc-goldshield", "desc": "dark gold / royal-blue heraldic shield (material_is_dark=True)"},
]
SEEDS = [121, 134]
COND_LABEL = {"A": "A — OUTLINE guides", "B": "B — SOLID FILLED guides"}

# Hand-verified per-crop residue calls (direct close-up visual inspection, NOT a leak_pct
# threshold heuristic — leak_pct is a single per-generation "worst control" number and does
# not tell you WHICH socket/crop actually shows a ring, and it under-counts the wc-goldshield
# button rings entirely; see verdict.json). tag -> {socket: "ring"|"fill"}.
RESIDUE_OBSERVED = {
    "a-121": {"vol": "ring", "seek": "ring", "shuffle": "ring"},
    "wc-goldshield-a-121": {"vol": "ring", "shuffle": "fill"},
    "wc-goldshield-a-134": {"shuffle": "fill"},
}


def tag_for(theme, cond, seed):
    return f"{cond.lower()}-{seed}" if theme is None else f"{theme}-{cond.lower()}-{seed}"


def cell(theme, cond, seed):
    tag = tag_for(theme, cond, seed)
    s = S.get(tag)
    d = f"assets-abshape-{tag}"
    if not s:
        return f"<div class='cell'><h3>{COND_LABEL[cond]} · seed {seed}</h3><p class='bad'>generation failed / not scored</p></div>"
    empt = s.get("empt_interior_pct", {})
    vis = (V.get("per_gen") or {}).get(tag, "")
    residue = RESIDUE_OBSERVED.get(tag, {})
    crops = "".join(
        f"<figure><a href='{d}/crop-{n}.png'><img src='{d}/crop-{n}.png' alt='{n} socket {tag}'></a>"
        f"<figcaption>{n} socket (must be an empty {'hole' if n != 'seek' else 'channel'})"
        f"{f' — <b class=leaktag>colour-residue {residue[n]}, hand-verified</b>' if n in residue else ''}"
        f"</figcaption></figure>"
        for n in ("vol", "seek", "shuffle")
        if os.path.exists(os.path.join(HERE, d, f"crop-{n}.png"))
    )
    return f"""
  <div class='cell'>
    <h3>{COND_LABEL[cond]} · seed {seed} <span class='tag'>{tag}</span></h3>
    <a href='{d}/paint.png'><img class='paint' src='{d}/paint.png' alt='paint {tag}'></a>
    <div class='crops'>{crops}</div>
    <div class='mini'>
      <a href='{d}/blueprint.png'>blueprint</a> · <a href='{d}/mask.png'>mask</a>
      {" · <a href='" + d + "/overlay.png'>overlay</a>" if os.path.exists(os.path.join(HERE, d, "overlay.png")) else ""}
    </div>
    <table class='mini-scores'>
      <tr><td>leak (worst control)</td><td class='{ "bad" if s["leak_pct"]>0.30 else "ok"}'>{s["leak_pct"]:.4f}%</td></tr>
      <tr><td>emptiness gate</td><td class='{ "ok" if s["empty_ok"] else "bad"}'>{"pass" if s["empty_ok"] else "FAIL"}</td></tr>
      <tr><td>socket interiors (vol/seek/shuffle)</td><td>{empt.get("vol","?")}% / {empt.get("seek","?")}% / {empt.get("shuffle","?")}%</td></tr>
      <tr><td>controls detected</td><td class='{ "ok" if s["controls"]==s["controls_total"] else "bad"}'>{s["controls"]}/{s["controls_total"]}</td></tr>
      <tr><td>seek coverage</td><td>{s.get("seek_cov")}</td></tr>
      <tr><td>gate reasons</td><td>{", ".join(s.get("reasons") or []) or "—"}</td></tr>
    </table>
    {f"<p class='visual'>{html.escape(vis)}</p>" if vis else ""}
  </div>"""


def round_table(theme):
    rows = ""
    for cond in ("A", "B"):
        for seed in SEEDS:
            tag = tag_for(theme, cond, seed)
            s = S.get(tag)
            if not s:
                rows += f"<tr><td>{cond}</td><td>{seed}</td><td colspan='6'>failed</td></tr>"; continue
            e = s.get("empt_interior_pct", {})
            rows += (f"<tr><td>{cond}</td><td>{seed}</td>"
                     f"<td class='{ 'bad' if s['leak_pct']>0.30 else 'ok'}'>{s['leak_pct']:.4f}%</td>"
                     f"<td class='{ 'ok' if s['empty_ok'] else 'bad'}'>{'pass' if s['empty_ok'] else 'FAIL'}</td>"
                     f"<td>{e.get('vol','?')} / {e.get('seek','?')} / {e.get('shuffle','?')}</td>"
                     f"<td class='{ 'ok' if s['controls']==s['controls_total'] else 'bad'}'>{s['controls']}/{s['controls_total']}</td>"
                     f"<td>{s.get('seek_cov')}</td></tr>")
    return rows


def round_section(rnd):
    theme, label, desc = rnd["theme"], rnd["label"], rnd["desc"]
    cells = "".join(cell(theme, cond, seed) for cond in ("A", "B") for seed in SEEDS)
    return f"""
<h2>Round — theme <code>{label}</code></h2>
<div class='anno small'>{html.escape(desc)}.</div>
<div class='tblwrap'><table>
<tr><th>cond</th><th>seed</th><th>leak (worst)</th><th>emptiness</th><th>socket interior % (vol/seek/shuffle)</th><th>controls</th><th>seek cov</th></tr>
{round_table(theme)}
</table></div>
<div class='grid'>{cells}</div>
"""


# ---- cost header: model + gens across both rounds ----
N_GENS = sum(1 for rnd in ROUNDS for cond in ("A", "B") for seed in SEEDS
             if S.get(tag_for(rnd["theme"], cond, seed)))
PER_IMG = 0.24
verdict_html = html.escape(V.get("verdict", "(pending human/agent visual read)")).replace("\n", "<br>")

page = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>abshape A/B — outline vs solid guide shapes (gen12 / fa-pod + wc-goldshield)</title>
<style>
  body {{ background:#101014; color:#ddd; font:14px/1.5 -apple-system, system-ui, sans-serif; margin:0; padding:16px clamp(8px,3vw,40px); }}
  h1 {{ font-size:clamp(18px,2.5vw,26px); margin:.2em 0; }}
  h2 {{ font-size:clamp(16px,2vw,20px); color:#8cf; margin:28px 0 4px; border-top:1px solid #2a2a30; padding-top:18px; }}
  .anno {{ color:#9a9; font-size:12px; border:1px solid #2a2a30; border-radius:8px; padding:8px 12px; background:#16161c; margin:10px 0 18px; max-width:90ch; }}
  .anno.small {{ padding:6px 10px; margin:4px 0 14px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:18px; }}
  .cell {{ background:#16161c; border:1px solid #2a2a30; border-radius:10px; padding:12px; }}
  .cell h3 {{ margin:.1em 0 .5em; font-size:14px; color:#8cf; }}
  .cell h3 .tag {{ color:#667; font-size:11px; font-weight:normal; }}
  img.paint {{ width:100%; height:auto; border-radius:6px; display:block; }}
  .crops {{ display:flex; gap:8px; margin-top:8px; flex-wrap:wrap; }}
  .crops figure {{ flex:1 1 130px; margin:0; }}
  .crops img {{ width:100%; height:auto; border-radius:4px; display:block; border:1px solid #333; }}
  figcaption {{ font-size:11px; color:#889; }}
  .leaktag {{ color:#f96; }}
  .mini {{ font-size:11px; margin-top:6px; }}
  a {{ color:#7ab8ff; }}
  code {{ background:#20202a; padding:1px 5px; border-radius:4px; }}
  table {{ border-collapse:collapse; margin-top:8px; width:100%; }}
  td, th {{ border:1px solid #2a2a30; padding:3px 8px; font-size:12px; text-align:left; }}
  .ok {{ color:#7f7; }} .bad {{ color:#f66; font-weight:bold; }}
  .visual {{ font-size:12px; color:#cb9; }}
  .verdict {{ background:#1a2016; border:1px solid #3a4a30; border-radius:10px; padding:14px 18px; margin:20px 0; max-width:90ch; }}
  .tblwrap {{ overflow-x:auto; }}
</style></head><body>
<h1>abshape A/B — OUTLINE vs SOLID FILLED guide shapes</h1>
<div class='anno'>Experiment: gen12 templated blueprint. Identical structural prompt across conditions
(4-substitution wording diff for B, recorded in each results.json). Two rounds across contrasting
themes, 2 seeds each (121 &amp; 134), n=2/cell.<br>
<b>Model:</b> gemini-3-pro-image-preview via Vertex AI (project muser-2605300220, global endpoint),
4K, 5:4 — same model the fal path proxies. Generation goes through <code>genskin_ab.py</code>'s
Vertex-direct <code>edit_vertex()</code> (gcloud access-token auth), NOT fal, so both rounds ran
independent of any fal account status. Scoring: genskin leak gate + extract12 pass&nbsp;1 (no matte).<br>
<b>Cost:</b> {N_GENS} gens × ~${PER_IMG:.2f}/4K image ≈ <b>${N_GENS*PER_IMG:.2f} total</b>
(round 1 fa-pod: 4 × ${PER_IMG:.2f} ≈ ${4*PER_IMG:.2f}; round 2 wc-goldshield: 4 × ${PER_IMG:.2f} ≈ ${4*PER_IMG:.2f};
extraction/scoring local, $0).</div>

<div class='verdict'><b>Verdict:</b><br>{verdict_html}</div>

{"".join(round_section(rnd) for rnd in ROUNDS)}
</body></html>"""
open(os.path.join(HERE, "index.html"), "w").write(page)
print("-> index.html")
