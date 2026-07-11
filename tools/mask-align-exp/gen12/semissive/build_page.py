#!/usr/bin/env python3
"""semissive/build_page.py — builds results.html, a served review page (NOT a PNG contact
sheet, per review-in-browser-rule) for the 3-skin semantic-emissive prototype.

Usage: python3 build_page.py
Writes semissive/results.html. Serve the semissive/ dir directly so the relative
out/<id>/*.png paths resolve.
"""
import glob
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SKINS = ["diablo-gothic", "fallout-pipboy", "fa-pod"]


def load(sid, name, default=None):
    p = os.path.join(HERE, "out", sid, name)
    return json.load(open(p)) if os.path.exists(p) else default


def spend(sid):
    p = os.path.join(HERE, "out", sid, "spend.jsonl")
    if not os.path.exists(p):
        return 0.0, []
    lines = [json.loads(l) for l in open(p) if l.strip()]
    return sum(l["usd"] for l in lines), lines


def e(s):
    return html.escape(str(s))


def region_card(r):
    color = r.get("color_hex", "#888")
    return f"""<div class="region-card">
      <div class="swatch" style="background:{e(color)}"></div>
      <div>
        <div class="rc-label">{e(r.get('label','?'))}</div>
        <div class="rc-meta">{e(color)} · intensity {e(r.get('intensity_0_1'))} · pulse {e(r.get('pulse'))}</div>
        <div class="rc-why">{e(r.get('why',''))}</div>
      </div>
    </div>"""


def refine_card(r):
    kept = r.get("kept")
    badge = "kept" if kept else "dropped"
    extra = ""
    if kept:
        extra = (f"SAM score {r.get('sam_score',0):.2f} · SAM ROI {r.get('sam_coverage_frac',0)*100:.2f}% "
                 f"→ refined {r.get('refined_coverage_frac',0)*100:.2f}%"
                 + (" (gate fell back to raw SAM ROI — uniform material)" if r.get("local_gate_fallback_to_raw_sam") else " (local hue/val/sat gate discriminated within the ROI)"))
    else:
        extra = f"dropped: {r.get('drop_reason')} (score {r.get('sam_score',0):.2f})"
    return f"""<div class="region-card {badge}">
      <div class="swatch" style="background:{e(r.get('color_hex','#888'))}"></div>
      <div>
        <div class="rc-label">{e(r.get('label','?'))} <span class="badge">{badge}</span></div>
        <div class="rc-meta">{extra}</div>
      </div>
    </div>"""


def sota_block(sv):
    if not sv:
        return "<p class='muted'>no sota-eval.json</p>"
    verdict = sv.get("verdict", "?")
    cls = "pass" if verdict == "PASS" else "fail"
    per = "".join(
        f"<li><b>{e(r.get('label'))}</b> — <span class='v-{e(r.get('verdict'))}'>{e(r.get('verdict'))}</span>: {e(r.get('note'))}</li>"
        for r in sv.get("per_region", []))
    missing = "".join(f"<li>{e(m)}</li>" for m in sv.get("missing", []))
    return f"""
    <div class="sota {cls}">
      <div class="sota-verdict">SOTA-eye verdict: <b>{e(verdict)}</b> (sensible={e(sv.get('sensible'))})</div>
      <p class="rc-why">{e(sv.get('overall_note',''))}</p>
      {'<ul>'+per+'</ul>' if per else ''}
      {'<div class="missing"><b>Flagged missing:</b><ul>'+missing+'</ul></div>' if missing else ''}
      <div class="rc-meta">{e(sv.get('model'))} · ${sv.get('cost_usd', sv.get('cost_estimate_usd','?'))} · {e(sv.get('elapsed_s'))}s</div>
    </div>"""


def skin_section(sid):
    judge = load(sid, "judge.json", {})
    refine = load(sid, "refine.json", {})
    sota = load(sid, "sota-eval.json", {})
    s_usd, s_lines = spend(sid)

    j_regions = judge.get("emissive_regions", [])
    r_regions = refine.get("regions", [])

    return f"""
  <section class="skin">
    <h2>{e(sid)}</h2>
    <div class="cost-line">spend this skin: ${s_usd:.4f} ({', '.join(f"{l['stage']} ${l['usd']:.4f}" for l in s_lines)})</div>

    <div class="grid-4">
      <figure><img src="out/{sid}/src.png" loading="lazy"><figcaption>paint (device crop)</figcaption></figure>
      <figure><img src="out/{sid}/overlay.png" loading="lazy"><figcaption>SAM boxes — labeled, per label-overlays-rule</figcaption></figure>
      <figure><img src="out/{sid}/preview.png" loading="lazy"><figcaption>semantic-emissive preview</figcaption></figure>
      <figure><img src="out/{sid}/classical-preview.png" loading="lazy"><figcaption>OLD classical (top-hat) preview — rejected baseline</figcaption></figure>
    </div>

    <div class="two-col">
      <div>
        <h3>Stage 1 — judge output ({e(judge.get('model'))}, {e(judge.get('elapsed_s'))}s, finish={e(judge.get('structured_io',{}).get('finish_reason'))})</h3>
        {''.join(region_card(r) for r in j_regions) if j_regions else "<p class='muted'>0 regions — judge decided nothing should glow.</p>"}
      </div>
      <div>
        <h3>Stage 2 — refiner output ({e(refine.get('sam_model'))}, {refine.get('sam_calls',0)} calls)</h3>
        {''.join(refine_card(r) for r in r_regions) if r_regions else "<p class='muted'>no regions to refine.</p>"}
        <div class="rc-meta">final coverage {refine.get('emissiveCoverage',0)*100:.3f}% of frame · classical coverage (rejected baseline) — see per-skin note below</div>
      </div>
    </div>

    <h3>Stage 3 — independent SOTA-eye cross-check</h3>
    {sota_block(sota)}
  </section>"""


def main():
    total = 0.0
    per_skin_spend = {}
    for sid in SKINS:
        s, _ = spend(sid)
        per_skin_spend[sid] = s
        total += s

    sections = "".join(skin_section(sid) for sid in SKINS)

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>semissive — 2-stage semantic emissive prototype</title>
<style>
:root {{ color-scheme: light dark; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 1400px;
  margin: 0 auto; padding: 24px; line-height: 1.5; background: #0b0c10; color: #e8e8ea; }}
@media (prefers-color-scheme: light) {{ body {{ background: #f7f7f9; color: #16171a; }} }}
h1 {{ font-size: 1.6rem; margin-bottom: 4px; }}
h2 {{ border-top: 2px solid #444; padding-top: 24px; margin-top: 40px; text-transform: capitalize; }}
h3 {{ font-size: 1rem; opacity: 0.85; }}
.dev-banner {{ background: #1c2333; border: 1px solid #3a4260; border-radius: 8px; padding: 12px 16px;
  font-size: 0.85rem; margin-bottom: 20px; }}
@media (prefers-color-scheme: light) {{ .dev-banner {{ background: #eef1fb; border-color: #c7d0f0; }} }}
.grid-4 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin: 16px 0; }}
figure {{ margin: 0; background: #16181d; border-radius: 8px; overflow: hidden; border: 1px solid #2a2d35; }}
@media (prefers-color-scheme: light) {{ figure {{ background: #fff; border-color: #ddd; }} }}
figure img {{ width: 100%; height: auto; display: block; background: #000; }}
figcaption {{ font-size: 0.75rem; padding: 6px 8px; opacity: 0.75; }}
.two-col {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; margin: 16px 0; }}
.region-card {{ display: flex; gap: 10px; padding: 8px; border-radius: 6px; background: #16181d; margin-bottom: 8px; align-items: flex-start; }}
@media (prefers-color-scheme: light) {{ .region-card {{ background: #fff; border: 1px solid #eee; }} }}
.region-card.dropped {{ opacity: 0.55; }}
.swatch {{ width: 22px; height: 22px; border-radius: 5px; flex: none; border: 1px solid rgba(128,128,128,0.4); margin-top: 2px; }}
.rc-label {{ font-weight: 600; font-size: 0.9rem; }}
.rc-meta {{ font-size: 0.75rem; opacity: 0.65; margin: 2px 0; }}
.rc-why {{ font-size: 0.82rem; opacity: 0.85; }}
.badge {{ font-size: 0.65rem; padding: 1px 6px; border-radius: 10px; background: #2d6a4f; margin-left: 6px; }}
.dropped .badge {{ background: #7a2e2e; }}
.sota {{ border-radius: 8px; padding: 14px 16px; border: 1px solid #333; }}
.sota.pass {{ border-color: #2d6a4f; background: rgba(45,106,79,0.12); }}
.sota.fail {{ border-color: #7a4a2e; background: rgba(122,74,46,0.12); }}
.sota-verdict {{ font-weight: 700; margin-bottom: 6px; }}
.sota ul {{ margin: 6px 0; padding-left: 18px; font-size: 0.85rem; }}
.v-sensible {{ color: #4caf7d; }}
.v-questionable {{ color: #d9a441; }}
.v-nonsensical {{ color: #e05c5c; }}
.missing {{ margin-top: 8px; font-size: 0.85rem; }}
.cost-line {{ font-size: 0.78rem; opacity: 0.7; margin-bottom: 6px; }}
.muted {{ opacity: 0.55; font-size: 0.85rem; }}
a {{ color: inherit; }}
</style>
</head>
<body>
<h1>semissive — 2-stage semantic emissive extraction (prototype)</h1>
<p class="muted">docs/design/2026-07-11-semantic-emissive-research.md · 3 skins · structured JSON in/out throughout</p>
<div class="dev-banner">
  <b>Models:</b> Stage 1 judge = <code>vertex:gemini-3.1-pro-preview</code> (responseSchema+responseMimeType enforced JSON) ·
  Stage 2 refiner = <code>fal-ai/sam-3/image</code> (native text-prompt segmentation, $0.005/call) ·
  Stage 3 cross-check = <code>fal:openrouter/router/vision:google/gemini-2.5-pro</code> (reasoning=true, no schema enforcement on this endpoint) ·
  <b>Total spend this prototype: ${total:.4f}</b> ({', '.join(f"{sid} ${v:.4f}" for sid, v in per_skin_spend.items())}) — well under the $1 budget.
</div>
{sections}
<footer style="margin-top:40px; opacity:0.6; font-size:0.8rem;">
  Generated by build_page.py — read alongside docs/experiments/2026-07-11-semantic-emissive-prototype.md for the full verdict.
</footer>
</body>
</html>
"""
    out_path = os.path.join(HERE, "results.html")
    open(out_path, "w").write(html_doc)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
