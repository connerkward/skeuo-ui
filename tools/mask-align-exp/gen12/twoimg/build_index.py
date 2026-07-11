#!/usr/bin/env python3
"""build_index — render twoimg/results.html from scores.json + per-gen vlm.json.

Matrix: 2 themes (fa-pod, wc-goldshield) x 2 seeds (121, 134) x 3 arms (control, treat,
neutral). CONTROL = current single-canvas approach (solid guide shapes baked into the edit
target, the abshape-verdict winner). TREAT = clean scaffold edit target + a SECOND reference
image carrying the SAME coloured guide shapes, prompted as position-only / never-painted
(FALSIFIED 2026-07-10 — bleed is semantic, not pixel-tracing, and layout adherence drifted
4/4). NEUTRAL = clean scaffold edit target + a SECOND reference image that is COLOURLESS
line-art with a small NUMBER (1-10) beside each control instead of colour — tests whether a
numbered reference just swaps colour-contamination for DIGIT-contamination.

Also renders a Task-2 section (roster_audit.json): a $0 template-adherence audit over the
EXISTING mainline gen12 roster (no new generations) — per-control drift px + guide-hue
perimeter contamination, plus an oldest-commit-vs-current historical comparison.
"""
import os, json, html

HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(HERE, "scores.json"))) if os.path.exists(os.path.join(HERE, "scores.json")) else {}
V = json.load(open(os.path.join(HERE, "verdict.json"))) if os.path.exists(os.path.join(HERE, "verdict.json")) else {}
RA = json.load(open(os.path.join(HERE, "roster_audit.json"))) if os.path.exists(os.path.join(HERE, "roster_audit.json")) else {}
TW = json.load(open(os.path.join(HERE, "threeway.json"))) if os.path.exists(os.path.join(HERE, "threeway.json")) else {}

THEMES = [
    {"id": "fa-pod", "desc": "bright translucent cyan “Frutiger Aero” water pod (material_is_dark=False)"},
    {"id": "wc-goldshield", "desc": "dark gold / royal-blue heraldic shield (material_is_dark=True)"},
]
SEEDS = [121, 134]
ARMS = ("control", "treat", "neutral")
ARM_LABEL = {"control": "CONTROL — single canvas, guides baked in",
             "treat": "TREAT — clean canvas + 2nd COLOURED reference image (falsified)",
             "neutral": "NEUTRAL — clean canvas + 2nd COLOURLESS numbered reference image"}
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
    if arm == "treat":
        bp_links = (f"<a href='{d}/blueprint-clean.png'>clean scaffold (edit target)</a> · "
                    f"<a href='{d}/blueprint-guided.png'>guided (reference image 2)</a>")
    elif arm == "neutral":
        bp_links = (f"<a href='{d}/blueprint-clean.png'>clean scaffold (edit target)</a> · "
                    f"<a href='{d}/blueprint-neutral-ref.png'>colourless numbered reference (image 2)</a>")
    else:
        bp_links = f"<a href='{d}/blueprint-guided.png'>blueprint (guides baked in, sole image)</a>"
    bleed_rows = "".join(
        f"<tr><td>{n}</td><td class='{'bad' if bleed.get(n,0) > 2.0 else ('warn' if bleed.get(n,0) > 0.3 else 'ok')}'>{bleed.get(n,'?')}%</td></tr>"
        for n in ALL_CTRLS if n in bleed)
    vlm_html = ""
    if vlm:
        vcls = "ok" if vlm["verdict"] == "PASS" else ("bad" if vlm["verdict"] == "FAIL" else "warn")
        dv = vlm.get("digit_verdict", "N/A")
        dcls = "ok" if dv == "CLEAN" else ("bad" if dv == "CONTAMINATED" else "warn")
        vlm_html = (f"<div class='vlm'><b>SOTA eye ({html.escape(vlm['eye'])}):</b> "
                    f"<span class='{vcls}'>{vlm['verdict']}</span>"
                    f" · <b>digit-check:</b> <span class='{dcls}'>{dv}</span>"
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
        for arm in ARMS:
            tag = tag_for(theme, arm, seed); s = S.get(tag)
            if not s:
                rows += f"<tr><td>{arm}</td><td>{seed}</td><td colspan='6'>failed</td></tr>"; continue
            worst = s.get("bleed_ring_worst", {"control": "none", "pct": 0})
            vlm = vlm_for(theme, arm, seed)
            dv = (vlm or {}).get("digit_verdict", "—")
            dcls = "ok" if dv == "CLEAN" else ("bad" if dv == "CONTAMINATED" else "warn")
            rows += (f"<tr><td>{arm}</td><td>{seed}</td>"
                     f"<td class='{ 'bad' if s['leak_pct']>0.30 else 'ok'}'>{s['leak_pct']:.4f}%</td>"
                     f"<td class='{ 'bad' if worst['pct']>2.0 else ('warn' if worst['pct']>0.3 else 'ok')}'>{worst['control']} {worst['pct']:.3f}%</td>"
                     f"<td class='{ 'ok' if s['empty_ok'] else 'bad'}'>{'pass' if s['empty_ok'] else 'FAIL'}</td>"
                     f"<td class='{ 'ok' if s['controls']==s['controls_total'] else 'bad'}'>{s['controls']}/{s['controls_total']}</td>"
                     f"<td>{s.get('seek_cov')}</td>"
                     f"<td class='{dcls}'>{dv}</td></tr>")
    cells = "".join(cell(theme, arm, seed) for seed in SEEDS for arm in ARMS)
    return f"""
<h2>Theme — <code>{theme}</code></h2>
<div class='anno small'>{html.escape(desc)}.</div>
<div class='tblwrap'><table>
<tr><th>arm</th><th>seed</th><th>leak (genskin gate, worst)</th><th>bleed-ring (this exp's metric, worst)</th><th>emptiness</th><th>controls</th><th>seek cov</th><th>digit-check (SOTA eye)</th></tr>
{rows}
</table></div>
<div class='grid'>{cells}</div>
"""


def threeway_section():
    """3-way arm summary from threeway.json (analyze_3way.py): color bleed, digit bleed,
    layout adherence, cavity emptiness — the comparison the neutral pass was run to answer."""
    if not TW:
        return ""
    sm = TW.get("summary", {})
    ROWS = [
        ("colour bleed (gens with any RING/FLOODED guide-hue residue, SOTA-eye adjudicated)", "color_bleed_gens", True),
        ("DIGIT bleed — actual numerals baked in (SOTA-eye digit hunt, adjudicated)", "digit_numeral_gens", True),
        ("digit-LIKE marks incl. tick/notch false-positives (raw detector rate)", "digit_mark_gens", True),
        ("layout adherence to locked template (visual inspection of full paints)", "layout_adherence_gens", False),
        ("cavity emptiness (vol/seek/shuffle empty, gate + VLM agree)", "cavity_empty_gens", False),
        ("extract12 gate PASS", "gate_pass", False),
        ("SOTA-eye VERDICT PASS", "vlm_pass", False),
    ]
    def frac_cls(v, bad_high):
        n, d = v.split("/")
        r = int(n) / int(d)
        good = (1 - r) if bad_high else r
        return "ok" if good >= 0.75 else ("warn" if good >= 0.5 else "bad")
    rows = ""
    for label, key, bad_high in ROWS:
        tds = "".join(f"<td class='{frac_cls(sm[a][key], bad_high)}'>{sm[a][key]}</td>" for a in ARMS)
        rows += f"<tr><td>{label}</td>{tds}</tr>"
    return f"""
<h2>3-way summary — control vs treat vs neutral</h2>
<div class='anno'><b>Digit verdict (the neutral pass's primary hypothesis):</b> the user predicted
"number tags will just contaminate the input with numbers instead of colors." <b>REFUTED at n=4</b> —
zero numerals were baked into any neutral gen (SOTA-eye DIGITS-NONE on all 40 control crops), and the
detector is demonstrably over-sensitive (it flags knob pointer-notches/tick-marks in the control/treat
arms, whose inputs contained no digits at all — those are spontaneous skeuo detailing, the detector's
false-positive floor). <br><b>But neutral is REJECTED as a default anyway:</b> 0/4 layout adherence
(all four rearranged the template; fa-pod-134 also overflowed the canvas), 0/4 clean on cavity
emptiness, and 3/4 gens show guide-hue residue — with a NEW finding: neutral's images are verifiably
colourless, yet wc-134 painted its next/repeat/shuffle gems in their EXACT named guide keys (ROSE
PINK / SPRING GREEN / VIOLET-PURPLE). The colour association survives in the TEXT prompt (the
right-column mask spec must name each control's colour + RGB) — a THIRD bleed pathway:
<b>canvas-pixel &lt; reference-image &lt; text-prompt</b>, and no conditioning topology removes the
text one while the mask column exists. CONTROL (single canvas, guides baked in) remains the winner.</div>
<div class='tblwrap'><table>
<tr><th>axis</th><th>CONTROL (solid canvas)</th><th>TREAT (coloured ref)</th><th>NEUTRAL (colourless + number tags)</th></tr>
{rows}
</table></div>
"""


def roster_audit_section():
    """Task 2 ($0, no new gens): template-adherence over the EXISTING mainline gen12 roster,
    from roster_audit.json (produced by roster_audit.py — reads ../assets-*/regions.json +
    results.json + paint.png, read-only)."""
    if not RA:
        return ""
    live = RA.get("live", [])
    deltas = {d["id"]: d for d in RA.get("oldest_vs_current_delta", [])}
    gate = RA.get("gate_sweep_15_skins", {})
    templateless_passing = sorted(k for k, v in gate.items() if v.get("mode") == "templateless" and v.get("pass"))
    failing = sorted(k for k, v in gate.items() if not v.get("pass"))
    rows = ""
    for L in live:
        d = deltas.get(L["id"])
        delta_html = (f"<td class='{'bad' if d['delta_px']>0 else 'ok'}'>{d['old_mean_drift_px']:.0f}px "
                      f"(seed {d['old_seed']}) → {d['new_mean_drift_px']:.0f}px "
                      f"({'+' if d['delta_px']>=0 else ''}{d['delta_px']:.0f}px)</td>") if d else "<td>n/a</td>"
        rows += (f"<tr><td><code>{L['id']}</code></td>"
                 f"<td>{L['mean_drift_px']:.0f}px</td>"
                 f"<td>{L['max_drift_control']} ({L['max_drift_px']:.0f}px)</td>"
                 f"<td class='{'bad' if L['mean_contam_pct']>1 else ('warn' if L['mean_contam_pct']>0.1 else 'ok')}'>{L['mean_contam_pct']}%</td>"
                 f"<td class='{'bad' if L['max_contam_pct']>2 else ('warn' if L['max_contam_pct']>0.3 else 'ok')}'>{L['max_contam_control']} ({L['max_contam_pct']}%)</td>"
                 f"{delta_html}</tr>")
    n_worse = sum(1 for d in deltas.values() if d["delta_px"] > 0)
    return f"""
<h2>Task 2 — $0 roster template-adherence audit (existing data, no new generations)</h2>
<div class='anno'><b>Question:</b> the user's complaint — "the paint step is just not following
the template at all anymore, even in the controls — all the controls had colour contamination."
Audited from data already on disk (<code>../assets-*/regions.json</code> + <code>results.json</code>
+ <code>paint.png</code>) plus git history — <b>zero new generations, $0</b>.<br>
<b>Gate sweep</b> — a live gate check over all 15 <code>assets-*</code> skins under gen12/ found
{RA.get('n_pass')}/15 PASS. Of those {RA.get('n_pass')} passing skins, only
<b>{RA.get('n_templated_passing')} are TEMPLATED mode</b> (the ones a template-drift metric is even
meaningful for) — the rest are templateless/freeform: <code>{', '.join(templateless_passing) or '—'}</code>.
Failing (not counted either way): <code>{', '.join(failing) or '—'}</code>.<br>
<b>Metrics:</b> <code>mean_drift_px</code> = mean distance (px, on the skin's own paint canvas)
between each control's AUTHORED template centre and its DETECTED device centre (extract12's own
snapped/drift-corrected estimate). <code>contam %</code> reuses the twoimg experiment's own
perimeter-band hue-bleed metric (<code>bleed_ring_pct</code>) verbatim against each control's own
guide key — same metric, same thresholds, so these numbers are directly comparable to the arms
above.<br>
<b>Historical comparison:</b> oldest common commit touching these skins' <code>regions.json</code>
is <code>{RA.get('historical_oldest',[{}])[0].get('commit','?')}</code> (the original 14-skin
themed batch) vs the current committed state. {n_worse}/{len(deltas)} templated-passing skins show
MORE drift now than at that original batch (contamination-trend not compared historically — needs
the historical paint.png pixels, out of scope for a $0 pass).</div>
<div class='tblwrap'><table>
<tr><th>skin</th><th>mean drift (px)</th><th>max-drift control</th><th>mean contam %</th>
<th>worst-contam control</th><th>drift: oldest commit → current</th></tr>
{rows}
</table></div>
"""


N_GENS = sum(1 for t in THEMES for arm in ARMS for seed in SEEDS if S.get(tag_for(t["id"], arm, seed)))
PER_IMG = 0.24  # Vertex 4K gemini-3-pro-image-preview, per gen12/TODO.md
VLM_CALLS = sum(1 for t in THEMES for arm in ARMS for seed in SEEDS if vlm_for(t["id"], arm, seed))
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
<div class='anno'><b>Hypothesis (TREAT, falsified):</b> guide-colour bleed happens because colour-coded
guide shapes are physically painted INTO the edit-target canvas — sending the layout as a SECOND
reference image with a guide-pixel-FREE clean target makes bleed impossible by construction
(verified: the clean scaffold contains zero pixels within RGB-distance 60 of any guide key,
checked programmatically before any generation ran). <b>Result: FALSIFIED</b> — bleed is
semantic (the model reads the reference's colours and repaints them), not pixel-tracing, and
layout adherence drifted 4/4 gens.<br>
<b>Hypothesis (NEUTRAL, this pass):</b> if colour is the vector, does replacing the coloured
reference with a COLOURLESS numbered line-art reference (thin grey outlines + a small 1-10 tag
per control, mapped to controls in the text prompt) avoid bleed WITHOUT the digit itself leaking
into the paint? The user's prior prediction: "number tags will just contaminate the input with
numbers instead of colours" — treated as the primary hypothesis under test, not a nuisance.<br>
<b>Arms</b> (guide shapes are SOLID FILLED where coloured, the abshape-verdict 2026-07-09 winner):
CONTROL = current single joint canvas (left=guided blueprint, right=black mask target), 1 input
image. TREAT = image 1 (edit target) is a CLEAN scaffold with the SAME geometry and ZERO guide-
coloured pixels; image 2 is the SAME guided blueprint as CONTROL, sent purely as a layout
reference the prompt says is never painted. NEUTRAL = image 1 is the SAME clean scaffold as TREAT;
image 2 is COLOURLESS mid-grey outline shapes with a printed number (1-10) beside each control, the
prompt textually maps each number to a control and hardens against painting digits/outlines.<br>
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
paint + full-res crops of ALL 10 controls with guide-colour NAMES stated, asked for a per-control
residue call (NONE/RING/FLOODED) + emptiness + a per-control DIGIT hunt (DIGITS-NONE/DIGITS-FOUND)
+ one VERDICT line + one DIGIT-VERDICT (CLEAN/CONTAMINATED) line.<br>
<b>Cost:</b> {N_GENS} gens × ~${PER_IMG:.2f}/4K image ≈ <b>${N_GENS*PER_IMG:.2f}</b> generation +
{VLM_CALLS} VLM calls × ~${PER_VLM:.2f} ≈ <b>${VLM_CALLS*PER_VLM:.2f}</b> review ≈
<b>${N_GENS*PER_IMG + VLM_CALLS*PER_VLM:.2f} total</b> (extraction/scoring local, $0).</div>

<div class='verdict'><b>Verdict:</b><br>{verdict_html}</div>

{threeway_section()}

{"".join(theme_section(t) for t in THEMES)}

{roster_audit_section()}
</body></html>"""
open(os.path.join(HERE, "results.html"), "w").write(page)
print("-> results.html")
