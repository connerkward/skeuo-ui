#!/usr/bin/env python3
"""build_page — render jsonspec/results.html from scores.json + vlm.json + bonus_probe.json.

Matrix: 2 themes (wc-goldshield, fa-pod) x 2 seeds (121, 134) x 2 arms (control, treat).
CONTROL = verbatim production prose prompt (imported from genskin.py, unedited). TREATMENT =
identical semantic content delivered as a fenced ```json``` machine-readable spec block
instead of prose, same shared blueprint image. Responsive per the repo's responsive-web-rule.
"""
import os, json, html

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    p = os.path.join(HERE, name)
    return json.load(open(p)) if os.path.exists(p) else {}


S = _load("scores.json")
BONUS = _load("bonus_probe.json")
V = _load("verdict.json")

THEMES = [
    {"id": "wc-goldshield", "desc": "dark gold / royal-blue heraldic shield (material_is_dark=True)"},
    {"id": "fa-pod", "desc": "bright translucent cyan “Frutiger Aero” water pod (material_is_dark=False)"},
]
SEEDS = [121, 134]
ARMS = ("control", "treat")
ARM_LABEL = {"control": "CONTROL — verbatim production prose prompt",
             "treat": "TREATMENT — fenced ```json``` machine-readable spec"}
ALL_CTRLS = ["playpause", "prev", "next", "repeat", "queue", "vol", "seek", "shuffle", "visualizer", "album_art"]


def tag_for(theme, arm, seed): return f"{theme}-{arm}-{seed}"


def vlm_for(theme, arm, seed):
    d = os.path.join(HERE, f"assets-jsonspec-{tag_for(theme, arm, seed)}", "vlm.json")
    return json.load(open(d)) if os.path.exists(d) else None


def cell(theme, arm, seed):
    tag = tag_for(theme, arm, seed)
    s = S.get(tag)
    d = f"assets-jsonspec-{tag}"
    if not s:
        return f"<div class='cell'><h3>{ARM_LABEL[arm]} · seed {seed}</h3><p class='bad'>generation failed / not scored</p></div>"
    bleed = s.get("bleed_ring_pct", {})
    worst = s.get("bleed_ring_worst", {"control": "none", "pct": 0})
    vlm = vlm_for(theme, arm, seed)
    crops = "".join(
        f"<figure><a href='{d}/crop-{n}.png'><img src='{d}/crop-{n}.png' alt='{n} crop {tag}' loading='lazy'></a>"
        f"<figcaption>{n} — bleed {bleed.get(n, '?')}% · drift {s.get('drift_px', {}).get(n, '?')}px</figcaption></figure>"
        for n in ALL_CTRLS if os.path.exists(os.path.join(HERE, d, f"crop-{n}.png"))
    )
    vlm_html = ""
    if vlm:
        vcls = "ok" if vlm["verdict"] == "PASS" else ("bad" if vlm["verdict"] == "FAIL" else "warn")
        vlm_html = (f"<div class='vlm'><b>SOTA eye ({html.escape(vlm['eye'])}):</b> "
                    f"<span class='{vcls}'>{vlm['verdict']}</span>"
                    f"<details><summary>raw</summary><pre>{html.escape(str(vlm['raw']))}</pre></details></div>")
    reasons = ", ".join(s.get("reasons") or []) or "none"
    return f"""
  <div class='cell'>
    <h3>{ARM_LABEL[arm]} · seed {seed} <span class='tag'>{tag}</span></h3>
    <a href='{d}/paint.png'><img class='paint' src='{d}/paint.png' alt='paint {tag}' loading='lazy'></a>
    <div class='mini'><a href='{d}/blueprint.png'>shared blueprint</a> · <a href='{d}/mask.png'>mask</a>
      · <a href='{d}/results.json'>prompt (results.json)</a> · prompt {s.get('prompt_len', '?')} chars
    </div>
    <div class='crops'>{crops}</div>
    <table class='mini-scores'>
      <tr><td>gate</td><td class='{"ok" if s["gate_pass"] else "bad"}'>{"PASS" if s["gate_pass"] else "FAIL"} <span class='reasons'>({html.escape(reasons)})</span></td></tr>
      <tr><td>leak (genskin gate, worst control)</td><td class='{"bad" if s["leak_pct"]>0.30 else "ok"}'>{s["leak_pct"]:.4f}%</td></tr>
      <tr><td>emptiness gate</td><td class='{"ok" if s["empty_ok"] else "bad"}'>{"pass" if s["empty_ok"] else "FAIL"}</td></tr>
      <tr><td>controls detected</td><td class='{"ok" if s["controls"]==s["controls_total"] else "bad"}'>{s["controls"]}/{s["controls_total"]}</td></tr>
      <tr><td>seek coverage</td><td class='{"ok" if (s.get("seek_cov") or 0)>=0.7 else "bad"}'>{s.get("seek_cov")}</td></tr>
      <tr><td>mean guide-hue bleed-ring (perimeter)</td><td class='{"bad" if (s.get("mean_bleed_pct") or 0)>2 else ("warn" if (s.get("mean_bleed_pct") or 0)>0.3 else "ok")}'>{s.get("mean_bleed_pct")}%</td></tr>
      <tr><td>worst-control bleed</td><td>{worst["control"]} = {worst["pct"]}%</td></tr>
      <tr><td>mean template drift</td><td class='{"bad" if (s.get("mean_drift_px") or 0)>60 else "ok"}'>{s.get("mean_drift_px")}px</td></tr>
    </table>
    {vlm_html}
  </div>"""


def theme_section(theme):
    rows = "".join(f"<div class='seedrow'><h4>seed {seed}</h4><div class='arms'>"
                    + "".join(cell(theme["id"], arm, seed) for arm in ARMS) + "</div></div>"
                    for seed in SEEDS)
    return f"<section><h2>{theme['id']} <span class='desc'>{theme['desc']}</span></h2>{rows}</section>"


def summary_table():
    rows = []
    for theme in THEMES:
        for arm in ARMS:
            vals = [S[tag_for(theme["id"], arm, s)] for s in SEEDS if tag_for(theme["id"], arm, s) in S]
            if not vals: continue
            n_pass = sum(1 for v in vals if v["gate_pass"])
            mean_bleed = round(sum(v.get("mean_bleed_pct") or 0 for v in vals) / len(vals), 4)
            mean_drift = round(sum(v.get("mean_drift_px") or 0 for v in vals) / len(vals), 1)
            vlms = [vlm_for(theme["id"], arm, s) for s in SEEDS]
            n_vlm_pass = sum(1 for v in vlms if v and v["verdict"] == "PASS")
            rows.append(f"<tr><td>{theme['id']}</td><td>{ARM_LABEL[arm]}</td>"
                        f"<td>{n_pass}/{len(vals)}</td><td>{mean_bleed}%</td><td>{mean_drift}px</td>"
                        f"<td>{n_vlm_pass}/{len([v for v in vlms if v])}</td></tr>")
    return ("<table class='summary'><tr><th>theme</th><th>arm</th><th>gate PASS</th>"
            "<th>mean bleed-ring</th><th>mean drift</th><th>SOTA-eye PASS</th></tr>"
            + "".join(rows) + "</table>")


def bonus_section():
    if not BONUS:
        return "<p class='warn'>bonus_probe.json not present — run bonus_probe.py</p>"
    smry = BONUS.get("summary", {})
    rows = "".join(f"<tr><td>{k}</td><td>{v['iou']}</td><td>{v['center_err_px']}px</td></tr>"
                    for k, v in (BONUS.get("per_control") or {}).items())
    return f"""
  <table class='summary'>
    <tr><th>metric</th><th>value</th></tr>
    <tr><td>convention tested</td><td>{html.escape(BONUS.get('prompt_convention', ''))}</td></tr>
    <tr><td>model</td><td>{html.escape(BONUS.get('model', ''))}</td></tr>
    <tr><td>parse ok</td><td>{BONUS.get('parse_ok')}</td></tr>
    <tr><td>n returned / matched</td><td>{BONUS.get('n_returned')} / {BONUS.get('n_matched_scoreable')}</td></tr>
    <tr><td><b>mean IoU (this probe)</b></td><td><b>{smry.get('mean_iou')}</b></td></tr>
    <tr><td>mean center error</td><td>{smry.get('mean_center_err_px')}px</td></tr>
    <tr><td>vs imgjson test A raw (ad-hoc x,y,w,h @0-1)</td><td>mean IoU 0.003, mean ctr err 507px</td></tr>
    <tr><td>vs imgjson test A after affine frame-rescue (needs GT, diagnostic only)</td><td>mean IoU 0.53, mean ctr err 49px</td></tr>
  </table>
  <details><summary>per-control</summary><table class='summary'><tr><th>control</th><th>IoU</th><th>center err</th></tr>{rows}</table></details>
  <p class='mini'>raw response head: <code>{html.escape((BONUS.get('raw_text_head') or '')[:400])}…</code></p>
"""



def conclusion_html():
    if not V:
        return "<p class='warn'>verdict.json not present</p>"
    ag = V.get("aggregates", {})
    notes = "".join(f"<li>{html.escape(n)}</li>" for n in V.get("adjudication_notes", []))
    bonus_line = ("<p><b>Bonus (Google box-convention probe):</b> Google documents box_2d="
                  "[ymin,xmin,ymax,xmax] @ 0-1000 for its image-UNDERSTANDING models only — no doc claims "
                  "bounding boxes for gemini-3-pro-image. Asked with that exact convention, the image model "
                  "returned boxes whose last two elements were TRANSPOSED ([ymin,xmin,xmax,ymax]); read as "
                  "documented they score IoU 0.096, but under the transposed reading they hit "
                  "<b>mean IoU 0.79, 9/10 controls at 2-26px center error</b> — the 0-1000 scale fixes the "
                  "broken y-frame that the ad-hoc 0-1 convention produced (imgjson test A: IoU 0.003, "
                  "y-scale ~0.66). The model reasons in its trained 0-1000 box space; our 0-1 ask was the "
                  "frame breaker. (n=1 call; element-order stability untested.)</p>")
    return (f"<p><b>{html.escape(V.get('conclusion',''))}</b></p>"
            f"<p>Aggregates: gate PASS control {ag.get('gate_pass',{}).get('control')}/4 vs treat "
            f"{ag.get('gate_pass',{}).get('treat')}/4 · bleed lower in treat "
            f"{ag.get('bleed_lower_in_treat_pairs')}/4 pairs (mean {ag.get('mean_bleed',{}).get('control')}% → "
            f"{ag.get('mean_bleed',{}).get('treat')}%) · drift lower in treat "
            f"{ag.get('drift_lower_in_treat_pairs')}/4 pairs (mean {ag.get('mean_drift',{}).get('control')}px → "
            f"{ag.get('mean_drift',{}).get('treat')}px)</p>"
            f"<details open><summary>Adjudication notes (VLM claims vs pixels)</summary><ul>{notes}</ul></details>"
            + bonus_line
            + f"<p class='mini'>Spend: {html.escape(V.get('spend',''))}</p>")


PAGE = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>jsonspec — fenced-JSON blueprint spec vs prose prompt (paint generation)</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ font: 14px/1.5 -apple-system, system-ui, sans-serif; background: #14151a; color: #e8e8ec; margin: 0; padding: 24px; }}
  h1 {{ font-size: 20px; margin: 0 0 6px; }}
  h2 {{ font-size: 17px; border-bottom: 1px solid #333; padding-bottom: 6px; margin-top: 36px; }}
  h2 .desc {{ font-weight: 400; color: #9a9aa4; font-size: 13px; }}
  h4 {{ color: #9a9aa4; margin: 18px 0 8px; }}
  .cost {{ color: #9a9aa4; font-size: 12.5px; margin-bottom: 18px; }}
  .arms {{ display: flex; flex-wrap: wrap; gap: 16px; }}
  .cell {{ flex: 1 1 460px; min-width: 0; background: #1b1c22; border: 1px solid #2c2d34; border-radius: 10px; padding: 14px; }}
  .cell h3 {{ font-size: 13.5px; margin: 0 0 8px; }}
  .tag {{ color: #6a6a74; font-weight: 400; font-size: 11px; }}
  img.paint {{ width: 100%; max-width: 420px; height: auto; display: block; border-radius: 6px; margin-bottom: 8px; }}
  .mini {{ font-size: 11.5px; color: #9a9aa4; margin-bottom: 8px; }}
  .mini a {{ color: #7ab8ff; }}
  .crops {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }}
  .crops figure {{ margin: 0; width: 90px; }}
  .crops img {{ width: 100%; height: auto; border-radius: 4px; display: block; max-width: 100%; }}
  .crops figcaption {{ font-size: 9.5px; color: #8a8a94; word-break: break-word; }}
  table.mini-scores {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  table.mini-scores td {{ padding: 3px 4px; border-top: 1px solid #26272e; }}
  table.mini-scores td:first-child {{ color: #9a9aa4; }}
  .reasons {{ color: #8a8a94; font-size: 10.5px; }}
  .ok {{ color: #6fd88a; }} .bad {{ color: #ff7a7a; }} .warn {{ color: #ffcf6f; }}
  .vlm {{ margin-top: 10px; font-size: 12px; background: #14151a; padding: 8px; border-radius: 6px; }}
  .vlm pre {{ white-space: pre-wrap; font-size: 10.5px; color: #b5b5c0; max-height: 240px; overflow: auto; }}
  table.summary {{ border-collapse: collapse; width: 100%; max-width: 900px; font-size: 12.5px; margin: 10px 0 20px; }}
  table.summary th, table.summary td {{ border: 1px solid #2c2d34; padding: 6px 10px; text-align: left; }}
  table.summary th {{ background: #1b1c22; }}
  code {{ background: #1b1c22; padding: 1px 4px; border-radius: 3px; }}
  .conclusion {{ background: #1b1c22; border: 1px solid #2c2d34; border-radius: 10px; padding: 18px 20px; margin-top: 30px; }}
  @media (prefers-color-scheme: light) {{ :root {{ color-scheme: light; }} }}
</style></head><body>
<h1>jsonspec — does a fenced-JSON blueprint spec help IMAGE GENERATION itself?</h1>
<p class="cost">Model: gemini-3-pro-image-preview (Vertex AI, global, 4K/5:4) · 8 gens ·
~$0.24/gen ≈ $1.92 · SOTA eye: google/gemini-2.5-pro via fal openrouter/router/vision
(reasoning:true) · bonus probe: 1 extra Vertex call ≈ $0.24 · total ≈ $2.2</p>

<h2>Summary</h2>
{summary_table()}

{"".join(theme_section(t) for t in THEMES)}

<h2>Bonus — Google's documented box_2d convention, re-probed</h2>
{bonus_section()}

<div class="conclusion">
<h2 style="margin-top:0;border:none;">Conclusion</h2>
{conclusion_html()}
</div>
</body></html>
"""

open(os.path.join(HERE, "results.html"), "w").write(PAGE)
print("-> results.html")
