#!/usr/bin/env python3
"""build_results_page — served HTML review page for the knobticks experiment (review-in-browser
+ label-overlays + dev-facing-model-cost-annotation rules: labeled crops, model+cost banner,
per-gen verdicts, a live page not a PNG contact sheet).
Usage: python3 build_results_page.py   -> writes knobticks/index.html
"""
import os, json, html

HERE = os.path.dirname(os.path.abspath(__file__))
scores = json.load(open(os.path.join(HERE, "scores.json")))
adj = {k: v for k, v in json.load(open(os.path.join(HERE, "adjudication.json"))).items()
       if not k.startswith("_")}
# fold in the no-image generation failure as a scored row (it consumed attempts and is a datapoint)
if not any(s["tag"] == "fa-pod-ticks01-501" for s in scores):
    scores.append({"tag": "fa-pod-ticks01-501", "theme": "fa-pod", "arm": "ticks01", "seed": 501,
                   "verdict": "NO-IMAGE", "raw": "generation returned thought-text-only responses with no image part, 3 attempts (seeds 501/1501/2501)",
                   "deterministic": {}, "model_json_parsed": None, "expected_convention": {},
                   "text_part_returned": False, "eye": "n/a"})
N = len(scores)
GEN_MODEL = "gemini-3-pro-image-preview (Vertex AI, responseModalities=[TEXT,IMAGE], 4K, 5:4)"
EYE_MODEL = "google/gemini-2.5-pro (fal openrouter/router/vision, reasoning=true)"
COST_PER_GEN = 0.24  # Vertex 4K image (2000 out tokens x $120/1M) — see genskin.py PAINT_VERTEX note
VLM_COST_PER_CALL = 0.02  # ~$0.01-0.03/call per sota-eye-review-rule precedent
gen_cost = N * COST_PER_GEN
vlm_cost = N * VLM_COST_PER_CALL
total_cost = gen_cost + vlm_cost

rel = sum(1 for r in scores if r["verdict"] == "RELIABLE")
adj_rel = sum(1 for r in scores if adj.get(r["tag"], {}).get("adjudicated", "FAIL").startswith("PASS"))
by_arm = {}
for r in scores:
    by_arm.setdefault(r["arm"], []).append(r)

json_returned = sum(1 for r in scores if r.get("text_part_returned"))
json_parsed = sum(1 for r in scores if r.get("model_json_parsed"))
json_agree = sum(1 for r in scores if r.get("agree_json_vs_deterministic_15deg"))

def esc(s): return html.escape(str(s))

def gen_dir(tag):
    r = next(x for x in scores if x["tag"] == tag)
    return f"assets-knobticks-{r['theme']}-{r['arm']}-{r['seed']}"

cards = []
for arm, items in by_arm.items():
    arm_label = "BAKED TICKS 0..1 (single sweep)" if arm == "ticks01" else "BAKED TICKS -1..0..+1 (center detent / balance)"
    arm_rel = sum(1 for r in items if r["verdict"] == "RELIABLE")
    cards.append(f'<h2>{esc(arm_label)} <span class="tally">{arm_rel}/{len(items)} RELIABLE</span></h2><div class="grid">')
    for r in items:
        d = gen_dir(r["tag"])
        det = r.get("deterministic", {})
        mj = r.get("model_json_parsed")
        ec = r.get("expected_convention", {})
        a = adj.get(r["tag"], {})
        adj_v = a.get("adjudicated", "?")
        adj_cls = "pass" if str(adj_v).startswith("PASS") else "fail"
        verdict_cls = "pass" if r["verdict"] == "RELIABLE" else ("fail" if r["verdict"] == "UNRELIABLE" else "unparsed")
        has_paint = os.path.exists(os.path.join(HERE, d, "paint.png"))
        imgs_html = (f'''
            <a href="{d}/paint.png" target="_blank"><img src="{d}/paint.png" class="thumb" loading="lazy"></a>
            <a href="{d}/crop-knob-labeled.png" target="_blank"><img src="{d}/crop-knob-labeled.png" class="crop" loading="lazy"></a>
            <a href="{d}/crop-cap-strip.png" target="_blank"><img src="{d}/crop-cap-strip.png" class="crop small" loading="lazy"></a>'''
            if has_paint else '<div class="noimg">NO IMAGE — model returned thought-text only, 3 attempts</div>')
        cards.append(f'''
        <div class="card">
          <div class="hdr">
            <span class="tag">{esc(r["theme"])} / seed {esc(r["seed"])}</span>
            <span>
              <span class="verdict {verdict_cls}" title="raw VLM witness verdict">VLM: {esc(r["verdict"])}</span>
              <span class="verdict {adj_cls}" title="adjudicated (VLM cross-checked against direct crop inspection)">ADJ: {esc(adj_v)}</span>
            </span>
          </div>
          <div class="imgs">{imgs_html}
          </div>
          <div class="meta">
            <div class="adjnote"><b>adjudication</b>: {esc(a.get("evidence", "n/a"))}</div>
            <div><b>deterministic ring</b>: r-factor={esc(det.get("ring_radius_factor"))} peaks={esc(det.get("n_peaks"))} span={esc(det.get("span_deg"))}deg</div>
            <div><b>expected</b>: start={esc(ec.get("start_deg"))} end={esc(ec.get("end_deg"))} zero={esc(ec.get("zero"))}</div>
            <div><b>text part returned</b>: {esc(r.get("text_part_returned"))} &nbsp; <b>JSON parsed</b>: {esc(bool(mj))}</div>
            <div><b>model self-report JSON</b>: <code>{esc(json.dumps(mj) if mj else "none")}</code></div>
            <div><b>JSON vs deterministic (+-15deg)</b>: {esc(r.get("agree_json_vs_deterministic_15deg"))}</div>
            <div><b>VLM clock mentions</b>: {esc(r.get("vlm_clock_mentions"))} -> approx {esc(r.get("vlm_angle_guess_deg"))}deg</div>
            <details><summary>full VLM raw reasoning + verdict</summary><pre>{esc(r.get("raw",""))}</pre></details>
          </div>
        </div>''')
    cards.append('</div>')

page = f'''<title>knobticks — baked tick-mark provisioning experiment</title>
<style>
:root {{ color-scheme: light dark; }}
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; margin: 0; padding: 1.5rem;
        background: #0d0f12; color: #e8e8ec; line-height: 1.45; }}
@media (prefers-color-scheme: light) {{ body {{ background: #f4f4f6; color: #16181c; }} }}
h1 {{ font-size: 1.4rem; margin: 0 0 .3rem; }}
h2 {{ font-size: 1.1rem; margin: 2rem 0 .6rem; display: flex; gap: .6rem; align-items: baseline; flex-wrap: wrap; }}
.tally {{ font-size: .85rem; opacity: .75; font-weight: normal; }}
.banner {{ background: #1b1e24; border: 1px solid #333; border-radius: 10px; padding: .9rem 1.1rem;
           font-size: .88rem; max-width: 900px; }}
@media (prefers-color-scheme: light) {{ .banner {{ background: #fff; border-color: #ddd; }} }}
.banner code {{ background: rgba(127,127,127,.18); padding: .1rem .35rem; border-radius: 4px; }}
.grid {{ display: flex; flex-wrap: wrap; gap: 1rem; }}
.card {{ background: #16181d; border: 1px solid #2a2d33; border-radius: 10px; padding: .8rem;
         width: min(100%, 420px); flex: 1 1 380px; }}
@media (prefers-color-scheme: light) {{ .card {{ background: #fff; border-color: #ddd; }} }}
.hdr {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: .5rem; font-size: .85rem; }}
.tag {{ font-weight: 600; }}
.verdict {{ padding: .15rem .5rem; border-radius: 6px; font-weight: 700; font-size: .75rem; letter-spacing: .02em; }}
.verdict.pass {{ background: #163d22; color: #6fe08a; }}
.verdict.fail {{ background: #4a1620; color: #ff8a8a; }}
.verdict.unparsed {{ background: #443b16; color: #f0c860; }}
.imgs {{ display: flex; gap: .5rem; margin-bottom: .6rem; flex-wrap: wrap; }}
.thumb {{ height: 180px; width: auto; border-radius: 6px; border: 1px solid #333; }}
.crop {{ height: 180px; width: auto; border-radius: 6px; border: 1px solid #333; }}
.crop.small {{ height: 120px; }}
.meta {{ font-size: .8rem; opacity: .92; display: flex; flex-direction: column; gap: .25rem; }}
.meta pre {{ white-space: pre-wrap; font-size: .72rem; max-height: 260px; overflow: auto;
             background: rgba(127,127,127,.12); padding: .5rem; border-radius: 6px; }}
.adjnote {{ background: rgba(255,170,60,.10); border-left: 3px solid #d99036; padding: .35rem .5rem;
            border-radius: 4px; }}
.noimg {{ padding: 2rem 1rem; border: 1px dashed #666; border-radius: 8px; opacity: .8; font-size: .85rem; }}
</style>
<h1>knobticks — can the paint model bake tick-mark provisioning + self-report metadata?</h1>
<div class="banner">
  <div><b>generator</b>: <code>{esc(GEN_MODEL)}</code></div>
  <div><b>eye</b>: <code>{esc(EYE_MODEL)}</code></div>
  <div><b>cost</b>: {N} gens x ~${COST_PER_GEN:.2f} = ~${gen_cost:.2f} generation + {N} VLM calls x ~${VLM_COST_PER_CALL:.2f} = ~${vlm_cost:.2f} scoring &nbsp;=&nbsp; <b>~${total_cost:.2f} total</b></div>
  <div><b>overall</b>: VLM witness {rel}/{N} RELIABLE &middot; <b>adjudicated {adj_rel}/{N} PASS</b> &middot;
       text part returned {json_returned}/{N} &middot; JSON parsed {json_parsed}/{N} &middot;
       JSON-vs-pixel agreement {json_agree}/{max(1,json_parsed)} &middot;
       all 4 parsed JSONs echo the prompt's example values (-135/+135) verbatim — no evidence of measurement</div>
</div>
{''.join(cards)}
'''
open(os.path.join(HERE, "index.html"), "w").write(page)
print(f"wrote {os.path.join(HERE, 'index.html')} ({N} gens, {rel}/{N} RELIABLE)")
