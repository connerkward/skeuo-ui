#!/usr/bin/env python3
"""Render out/{scores,diagnosis,structured_results}.json + viz/ into index.html —
the reviewable results page for the imgjson experiment. Regenerate any time with
python3 build_page.py."""
import os, json, html

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

scores = json.load(open(os.path.join(OUT, "scores.json")))
diag = json.load(open(os.path.join(OUT, "diagnosis.json")))
probes = json.load(open(os.path.join(OUT, "modality_probes.json")))
structured = {}
sp = os.path.join(OUT, "structured_results.json")
if os.path.exists(sp):
    structured = json.load(open(sp))

LABELS = {
    "a_text_only": ("A — image model, JSON-only ask", "gemini-3-pro-image-preview", 'responseModalities ["TEXT","IMAGE"]'),
    "b_interleaved": ("B — image model, JSON + re-render interleaved", "gemini-3-pro-image-preview", 'responseModalities ["TEXT","IMAGE"]'),
    "c_text_model": ("C — text model (director), same ask", "gemini-3.1-pro-preview", "responseMimeType application/json"),
}


def acc_rows():
    rows = []
    for k, (label, model, cfg) in LABELS.items():
        s = scores[k].get("summary", {})
        d = diag.get(k, {})
        resc = d.get("swap_plus_affine", {})
        rows.append(f"""<tr><td>{html.escape(label)}<div class=sub>{model}<br>{cfg}</div></td>
<td>{'✓' if scores[k]['parse_ok'] else '✗'}</td>
<td>{s.get('n_matched','—')}/10</td>
<td>{s.get('mean_iou','—')}</td>
<td>{s.get('median_iou','—')}</td>
<td>{s.get('mean_center_err_px','—')} px</td>
<td>{resc.get('mean_iou','—')} / {resc.get('mean_center_err_px','—')} px</td>
<td>{html.escape(str(s.get('worst_control','—')))}</td></tr>""")
    return "\n".join(rows)


def s1_table():
    if "s1_director_prose" not in structured:
        return "<p>(structured tests not yet run)</p>"
    out = []
    for arm in ("prose", "schema"):
        rows = structured[f"s1_director_{arm}"]
        ok = sum(1 for r in rows if r.get("parse_ok"))
        complete = sum(1 for r in rows if r.get("validation", {}).get("complete"))
        out.append(f"<tr><td>{arm}</td><td>{ok}/{len(rows)}</td><td>{complete}/{len(rows)}</td>"
                   f"<td>{html.escape('; '.join((r.get('obj') or {}).get('name','?') + '/' + (r.get('obj') or {}).get('font','?') for r in rows))}</td></tr>")
    return ("<table><tr><th>arm</th><th>parse ok</th><th>all fields valid</th><th>name/font picks</th></tr>"
            + "".join(out) + "</table>")


def struct_acc_table():
    p = os.path.join(OUT, "unambiguous_comparison.json")
    q = os.path.join(OUT, "structured_scores.json")
    if not (os.path.exists(p) and os.path.exists(q)):
        return "<p>(not run)</p>"
    comp = json.load(open(p))
    ss = json.load(open(q))
    c_sum = scores["c_text_model"]["summary"]
    rows = []
    for key, label, full in [
        ("c_prose", "C — prose ask + responseMimeType (current pattern)", c_sum),
        ("s2_schema", "s2 — + responseSchema (enum'd names, all fields required)", ss["s2_bbox_schema"]["summary"]),
        ("s4_json_prompt", "s4 — fenced-JSON task spec in prompt, no schema", ss["s4_json_prompt"]["summary"]),
    ]:
        u = comp[key]
        rows.append(f"<tr><td>{label}</td><td>{full['n_matched']}/10</td><td>{full['mean_iou']}</td>"
                    f"<td>{full['mean_center_err_px']} px</td>"
                    f"<td>{u['mean_iou']}</td><td>{u['mean_ctr_px']} px</td><td>{u['max_ctr_px']} px</td></tr>")
    return ("<table><tr><th>arm</th><th>rows usable</th><th>mean IoU (all)</th><th>mean ctr err (all)</th>"
            "<th>mean IoU (unambig.)</th><th>mean ctr (unambig.)</th><th>max ctr (unambig.)</th></tr>"
            + "".join(rows) + "</table>")


def s_generic(key):
    v = structured.get(key)
    if not v:
        return "(not run)"
    return f"<pre>{html.escape(json.dumps(v, indent=2))}</pre>"


page = f"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>imgjson — can the image model output usable JSON?</title>
<style>
body{{font:15px/1.5 -apple-system,system-ui,sans-serif;margin:0;padding:2rem clamp(1rem,4vw,3rem);background:#141417;color:#e8e8ec;max-width:1100px;margin-inline:auto}}
h1{{font-size:1.5rem}} h2{{font-size:1.15rem;margin-top:2.2rem;border-bottom:1px solid #333;padding-bottom:.3rem}}
table{{border-collapse:collapse;width:100%;font-size:.85rem;margin:.8rem 0;display:block;overflow-x:auto}}
th,td{{border:1px solid #333;padding:.45rem .6rem;text-align:left;vertical-align:top}}
th{{background:#1e1e24}} .sub{{color:#9a9aa4;font-size:.75rem;margin-top:.2rem}}
.meta{{background:#1e1e24;border:1px solid #333;border-radius:8px;padding:.7rem 1rem;font-size:.85rem;color:#c8c8d0}}
.verdict{{background:#182418;border:1px solid #2c4a2c;border-radius:8px;padding:1rem;margin:1rem 0}}
.bad{{color:#ff7a7a}} .good{{color:#7ae08a}} .warn{{color:#ffc266}}
img{{max-width:100%;height:auto;border:1px solid #333;border-radius:6px}}
.grid{{display:flex;flex-wrap:wrap;gap:1rem}} .grid>div{{flex:1 1 300px;min-width:280px}}
pre{{background:#1a1a20;border:1px solid #2c2c34;border-radius:6px;padding:.7rem;overflow-x:auto;font-size:.75rem}}
figcaption{{font-size:.78rem;color:#9a9aa4;margin-top:.3rem}}
</style></head><body>
<h1>imgjson — can <code>gemini-3-pro-image-preview</code> output usable JSON?</h1>
<div class=meta><b>Models:</b> gemini-3-pro-image-preview (image) + gemini-3.1-pro-preview (text/director), both direct Vertex AI
(project muser-2605300220, generateContent) · <b>Source image:</b> gen12 assets-wc-goldshield/paint.png (2304×3712) ·
<b>Ground truth:</b> its regions.json <code>device</code> boxes (extract12-detected geometry) ·
<b>Total spend:</b> ≈$0.45 — image-model calls: A $0.05 + B $0.16 (incl. 1120 image-out tok) + 2 modality probes $0.04 + ~3 debug rolls $0.15;
text-model calls (C + 6×s1 + s2 + s4) ≈ $0.04 total; s3 probes rejected 400 = $0. (Rates: image-out $120/1M tok, text-out $12/1M, in $2/1M.)</div>

<h2>1 · Capability surface (documented vs observed)</h2>
<table>
<tr><th>Config</th><th>Documented (live docs, 2026-07-11)</th><th>Observed (Vertex, this run)</th></tr>
<tr><td><code>responseModalities: ["TEXT"]</code> alone</td><td>not stated for this model</td>
<td class=bad>HTTP 400 "The request is not supported by this model" — TEXT-alone rejected</td></tr>
<tr><td><code>["IMAGE"]</code> alone, JSON-only prompt</td><td>—</td>
<td class=warn>HTTP 200 but finishReason NO_IMAGE, zero parts, burns ~3.1k thinking tokens</td></tr>
<tr><td><code>["TEXT","IMAGE"]</code>, JSON-only prompt</td><td rowspan=2>ai.google.dev: gemini-3-pro-image "can generate interleaved content — text blocks and illustrations inside the same response"</td>
<td class=good>works — 11 text parts, 0 image parts, parseable JSON (after part-joining fix, see §2)</td></tr>
<tr><td><code>["TEXT","IMAGE"]</code>, JSON + re-render ask</td>
<td class=good>works — 15 text parts + 1 image part (814×1312 re-render, same aspect as input) in ONE response</td></tr>
<tr><td>image model + <code>responseMimeType/responseSchema</code></td><td>not stated</td>
<td>{html.escape(json.dumps({k: ('accepted' if v.get('accepted') else v.get('error_verbatim','?')[:90]) for k, v in structured.get('s3_image_schema', {}).items()}))}</td></tr>
</table>

<h2>2 · Parse-rate gotchas (both real)</h2>
<ul>
<li><b>Vertex splits the text stream into many <code>text</code> parts at arbitrary byte boundaries</b> — observed mid-number splits ("0." | "3597"). Join with <code>""</code>, never <code>"\\n"</code>, or the JSON corrupts.</li>
<li><b>The image model ignores "STRICT JSON ONLY, no prose"</b> — it prepends ~2.5k chars of thinking-style narration before the array, every time. A fence/prefix-tolerant extractor (raw_decode at each <code>[</code>/<code>{{</code>) is mandatory. The text model with <code>responseMimeType</code> returns one clean part, no narration.</li>
</ul>

<h2>3 · Box accuracy vs regions.json (deterministic)</h2>
<table>
<tr><th>Test</th><th>parse</th><th>matched</th><th>mean IoU</th><th>median IoU</th><th>mean center err</th><th>after frame-rescue (IoU / ctr-err)</th><th>worst</th></tr>
{acc_rows()}
</table>
<p><b>Frame-rescue diagnosis:</b> test A's raw boxes are near-zero IoU <i>not</i> because the geometry is noise —
x comes back at scale 0.999 but <b>y in a compressed frame</b> (best-fit gt = 0.66·pred + 0.12, residual RMS ≈ 19 px over the 8
unambiguous controls). After a least-squares affine + undoing a visualizer/album_art label swap, A hits mean IoU 0.53 / 49 px —
i.e. the image model <i>sees</i> the layout fine but reports normalized coords against some internal preprocessed frame,
unusable without per-image calibration you'd need ground truth to compute. B (interleaved) stays broken even after rescue
(0.04 IoU) — asking for an image in the same call destroys box quality. C (text model) is already frame-correct; its two big
misses are the vol/shuffle <b>sprite-strip ambiguity</b> (boxed the bottom-strip sprite instead of the device socket — a prompt
defect, not spatial noise) plus one dropped field (playpause returned without <code>h</code>).</p>

<div class=grid>
<div><figure><img src="viz/overlay-a_text_only.png" alt="test A overlay"><figcaption>A — image model. GREEN = regions.json GT · RED = as returned (y-compressed frame) · ORANGE = after affine rescue. Studio overlay, not part of any pipeline artifact.</figcaption></figure></div>
<div><figure><img src="viz/overlay-b_interleaved.png" alt="test B overlay"><figcaption>B — interleaved. Boxes unrescuable (IoU 0.04 after affine).</figcaption></figure></div>
<div><figure><img src="viz/overlay-c_text_model.png" alt="test C overlay"><figcaption>C — text model. Tight on 7 controls; vol/shuffle boxed the sprite-strip copies (ambiguity), playpause dropped its <code>h</code> field.</figcaption></figure></div>
<div><figure><img src="out/b_interleaved_img0.png" alt="B returned image"><figcaption>B's returned IMAGE part (814×1312) — clean warmer re-render, same layout+aspect. Interleaved image+text works; the JSON beside it doesn't.</figcaption></figure></div>
</div>

<h2>4 · Structured OUTPUT — responseSchema (scope expansion)</h2>
<h3>s1 · Director Material shape (text model): prose-JSON vs responseSchema, 3 prompts/arm</h3>
{s1_table()}
<h3>s2/s4 vs C · Bbox extraction, three text-model arms (same image, same task)</h3>
{struct_acc_table()}
<p>All three arms are <b>equal on centers (~13 px mean)</b> over the unambiguous controls — schema enforcement and
JSON-shaped prompts neither help nor hurt spatial quality. What <code>responseSchema</code> DOES buy: <b>field completeness</b>
(10/10 rows with all 5 keys; the prose arm dropped playpause's <code>h</code>, silently shrinking it to 9/10 usable) — and it
did so without the enum/required constraints degrading anything. All three arms share the same vol/shuffle sprite-strip
ambiguity (a prompt defect: those controls appear twice in the paint — the fix is a prompt clause, not structure).</p>
<h3>s3 · Image model + responseMimeType/responseSchema — REJECTED</h3>
{s_generic('s3_image_schema')}
<h2>5 · Structured INPUT — fenced-JSON spec vs prose (s4, text model extraction)</h2>
<p>Identical scores to prose (table above): mean ctr 13.1 px vs 13.2 px. No adherence gain, no loss, on this extraction
task. <b>Paint-generation-side structured prompts NOT tested</b> (needs image gens, out of budget) — untested, not refuted.</p>

<h2>6 · Verdict</h2>
<div class=verdict>
<b>Image-model text/JSON output:</b> real but <b>NOT usable</b> for (a) mask-cell manifests or (b) replacing detection —
TEXT must ride with IMAGE modality, no responseMimeType/Schema (400), narration prefix must be stripped, and box y-coords
arrive in an internal frame (raw IoU 0.003; only affine-rescuable WITH ground truth you wouldn't have). Interleaved
image+JSON in one call works mechanically but box quality collapses (IoU 0.02–0.04 even after rescue).<br><br>
<b>Structured output viability:</b> director <b>YES</b> (responseSchema: 3/3 parse + 3/3 field-complete + enum-safe styles,
equal quality to prose arm — adopt, it deletes the validation failure modes) · extraction <b>YES</b> (equal spatial accuracy,
guarantees field completeness — adopt) · image-model manifest <b>NO</b> (hard 400).<br>
<b>Structured input:</b> measured neutral on extraction (13.1 vs 13.2 px) — <b>not worth adopting for its own sake</b>;
paint-side untested.<br>
<b>Detection replacement:</b> no. Best VLM arm (text model, ~13 px centers) is impressive but still 10–30 px off with
per-control tail risk (30 px) and semantic swap hazards; extract12's pixel-space detection stays load-bearing.
Plausible niche: the text model as a cheap <i>sanity witness</i> over detection (name↔position audit), not geometry.
</div>
</body></html>"""

open(os.path.join(HERE, "index.html"), "w").write(page)
print("wrote index.html")
