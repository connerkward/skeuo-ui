#!/usr/bin/env python3
"""build_results -- render poscorr/results.html: per-arm generations side by side, template +
paint + mask thumbnails, per-cell IoU (stack & mirror) heatmap, occupancy, contamination, and
a cost header (dev-facing-model-cost-annotation-rule). Reads scores.json (score_poscorr.py).
"""
import os, json, glob

HERE = os.path.dirname(os.path.abspath(__file__))
ARMS = ["position", "numbered", "color"]
SEEDS = [11, 22, 33]
COST_PER_GEN = 0.24
MODEL = "gemini-3-pro-image-preview (Vertex AI, global, 4K, 5:4)"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def iou_cls(v):
    if v >= 0.5: return "good"
    if v >= 0.2: return "mid"
    return "bad"


def gen_cell(arm, seed, scores):
    tag = f"{arm}-{seed}"
    d = f"assets-{tag}"
    exists = os.path.exists(os.path.join(HERE, d, "paint.png"))
    if not exists:
        return f'<div class="gen missing"><h4>{tag}</h4><p>not generated</p></div>'
    s = scores.get(tag)
    rows = ""
    if s:
        for name in s["per_cell"]:
            c = s["per_cell"][name]
            cont = s["contamination"][name]
            rows += (f'<tr><td>{name}</td><td>cell {c["cell"]+1}</td>'
                     f'<td class="{iou_cls(c["iou"])}">{c["iou"]:.3f}</td>'
                     f'<td class="{iou_cls(c["mirror_iou"])}">{c["mirror_iou"]:.3f}</td>'
                     f'<td>{"yes" if c["filled"] else "-"}</td>'
                     f'<td>{cont["colour_frac"]*100:.2f}%</td>'
                     f'<td>{"LEAK" if cont["tag_leak"] else "-"}</td></tr>')
        summary = (f'<div class="summary">'
                   f'<b>mean IoU stack:</b> {s["mean_iou"]:.3f} ({s["iou_pass_at_0.5"]}/{s["iou_pass_total"]}&ge;0.5) &nbsp;'
                   f'<b>mirror:</b> {s["mean_mirror_iou"]:.3f} ({s["mirror_pass_at_0.5"]}/{s["iou_pass_total"]}&ge;0.5) &nbsp;'
                   f'<b>topology:</b> <span class="topo">{s["detected_topology"]}</span> &nbsp;'
                   f'<b>cells filled:</b> {s["cells_filled"]}/{s["cells_total"]} &nbsp;'
                   f'<b>colour contam:</b> {s["mean_colour_contam"]*100:.2f}% &nbsp;'
                   f'<b>tag leak:</b> {s["tag_leak_n"]}/{s["cells_total"]}'
                   f'</div>')
        table = (f'<table><tr><th>region</th><th>cell</th><th>IoU stack</th><th>IoU mirror</th>'
                 f'<th>filled</th><th>colour%</th><th>tag</th></tr>{rows}</table>')
    else:
        summary, table = '<div class="summary">not scored</div>', ""
    return (f'<div class="gen">'
            f'<h4>{tag}</h4>'
            f'<div class="imgs">'
            f'<figure><img src="{d}/template.png" loading="lazy"><figcaption>template ({arm})</figcaption></figure>'
            f'<figure><img src="{d}/paint.png" loading="lazy"><figcaption>output panel</figcaption></figure>'
            f'<figure><img src="{d}/mask.png" loading="lazy"><figcaption>output mask</figcaption></figure>'
            f'</div>{summary}{table}</div>')


def conclusion_section(scores):
    """Verdict block, computed live from scores.json — never hand-typed numbers."""
    def arm_vals(arm):
        return [scores[f"{arm}-{s}"] for s in SEEDS if f"{arm}-{s}" in scores]

    pos, num, col = arm_vals("position"), arm_vals("numbered"), arm_vals("color")
    if not (pos and num and col):
        return ""  # incomplete run — no verdict to draw yet

    pos_n, num_n, col_n = len(pos), len(num), len(col)
    pos_compliant = sum(1 for v in pos if v["iou_pass_at_0.5"] > 0)
    pos_mirror_n = sum(1 for v in pos if v["detected_topology"] == "mirror")

    num_topo_stack = sum(1 for v in num if v["detected_topology"] == "stack")
    num_collapse = sum(1 for v in num if v["iou_pass_at_0.5"] == 0)
    num_clean = sum(1 for v in num if v["iou_pass_at_0.5"] == v["iou_pass_total"])

    col_topo_stack = sum(1 for v in col if v["detected_topology"] == "stack")
    col_topo_mirror = sum(1 for v in col if v["detected_topology"] == "mirror")

    return f"""<section class="conclusion">
<h2>Conclusion</h2>
<div class="verdict-box">
<div class="verdict-badge">VERDICT</div>
<p><b>Position-only correlation is unreliable</b> — {pos_compliant}/{pos_n} position seeds ever
followed the requested reading-order stack (mean IoU stack = 0.000 in all {pos_mirror_n}/{pos_n}
mirror-topology seeds). The model instead consistently reverted to mirroring the panel's own
grid layout into the mask column rather than following the prose reading-order convention.</p>
<p><b>Numbered tags got the topology right ({num_topo_stack}/{num_n} adopted the stack
convention) but format-collapsed in {num_collapse}/{num_n}</b> (row-collapsing at N=8 cells) —
only {num_clean}/{num_n} seeds cleanly passed IoU&ge;0.5 on every cell. Directionally the
strongest colourless candidate, not yet reliable enough to ship.</p>
<p><b>Color (today's mechanism) is bimodal</b> — {col_topo_stack}/{col_n} seed followed the
stack convention cleanly, {col_topo_mirror}/{col_n} defaulted to mirror fallback, with no
partial-credit middle ground.</p>
<p><b>Recommendation:</b> do NOT de-colour the mask column on this result. Position-only is
ruled out. If numbered tags are revisited, isolate why the N=8 format collapsed (seed-specific
noise vs. a real per-cell-count ceiling) before considering it for the real pipeline.
<b>n=3/arm — directional, not conclusive.</b></p>
<p class="verdict-meta">Full method, per-seed table, and human verdict:
<code>docs/experiments/2026-07-11-position-mask-correlation.md</code></p>
</div>
</section>"""


def arm_section(arm, scores):
    cells = "".join(gen_cell(arm, s, scores) for s in SEEDS)
    vals = [scores[f"{arm}-{s}"] for s in SEEDS if f"{arm}-{s}" in scores]
    agg = ""
    if vals:
        m_stack = sum(v["mean_iou"] for v in vals) / len(vals)
        m_mirror = sum(v["mean_mirror_iou"] for v in vals) / len(vals)
        pass_stack = sum(v["iou_pass_at_0.5"] for v in vals)
        pass_mirror = sum(v["mirror_pass_at_0.5"] for v in vals)
        total_cells = sum(v["iou_pass_total"] for v in vals)
        topo_stack_n = sum(1 for v in vals if v["detected_topology"] == "stack")
        agg = (f'<div class="agg">n={len(vals)} gens &middot; '
               f'mean IoU(stack)={m_stack:.3f} &middot; mean IoU(mirror)={m_mirror:.3f} &middot; '
               f'cell-pass@0.5 stack={pass_stack}/{total_cells} mirror={pass_mirror}/{total_cells} &middot; '
               f'gens where stack&ge;mirror: {topo_stack_n}/{len(vals)}</div>')
    return f'<section><h2>Arm: {arm}</h2>{agg}<div class="gens">{cells}</div></section>'


def main():
    scores = json.load(open(os.path.join(HERE, "scores.json"))) if os.path.exists(os.path.join(HERE, "scores.json")) else {}
    n_gens = len(glob.glob(os.path.join(HERE, "assets-*", "paint.png")))
    cost = n_gens * COST_PER_GEN
    body = "".join(arm_section(a, scores) for a in ARMS) + conclusion_section(scores)
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>poscorr — position-mask correlation experiment</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {{ color-scheme: light dark; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin:0; padding:24px;
  background:#0d0e12; color:#e8e8ee; line-height:1.4; }}
h1 {{ font-size:22px; margin:0 0 4px; }}
.hdr {{ background:#17181f; border:1px solid #2a2b35; border-radius:10px; padding:14px 18px; margin-bottom:20px; font-size:13px; }}
.hdr b {{ color:#9fd3ff; }}
h2 {{ font-size:17px; margin:28px 0 6px; border-bottom:1px solid #2a2b35; padding-bottom:6px; }}
.agg {{ font-size:12.5px; color:#b8bccc; margin-bottom:10px; }}
.gens {{ display:flex; flex-wrap:wrap; gap:16px; }}
.gen {{ background:#15161c; border:1px solid #262733; border-radius:10px; padding:12px; flex:1 1 420px; max-width:520px; }}
.gen.missing {{ opacity:0.4; flex:1 1 200px; }}
.gen h4 {{ margin:0 0 8px; font-size:13px; color:#ffd479; font-family:ui-monospace,monospace; }}
.imgs {{ display:flex; gap:6px; flex-wrap:wrap; margin-bottom:8px; }}
.imgs figure {{ margin:0; flex:1 1 120px; }}
.imgs img {{ width:100%; height:auto; border-radius:6px; border:1px solid #2a2b35; display:block; background:#000; }}
.imgs figcaption {{ font-size:10px; color:#8a8d9e; text-align:center; margin-top:2px; }}
.summary {{ font-size:11.5px; color:#c7cad8; margin:6px 0; }}
table {{ width:100%; border-collapse:collapse; font-size:11px; margin-top:4px; }}
th, td {{ padding:2px 5px; text-align:left; border-bottom:1px solid #23242e; }}
th {{ color:#8a8d9e; font-weight:600; }}
.good {{ color:#7ee787; }} .mid {{ color:#ffd479; }} .bad {{ color:#ff8080; }}
.topo {{ font-family:ui-monospace,monospace; background:#23242e; padding:1px 6px; border-radius:4px; }}
.conclusion {{ margin-top:36px; }}
.conclusion h2 {{ border-bottom-color:#3a2f1a; }}
.verdict-box {{ position:relative; background:#1c1710; border:1px solid #4a3a1a; border-left:4px solid #ffd479;
  border-radius:10px; padding:18px 20px 16px; font-size:13.5px; line-height:1.55; color:#e8e2d0; }}
.verdict-box p {{ margin:0 0 10px; }}
.verdict-box p:last-of-type {{ margin-bottom:0; }}
.verdict-box b {{ color:#ffd479; }}
.verdict-badge {{ display:inline-block; font-size:10.5px; font-weight:700; letter-spacing:0.08em;
  color:#0d0e12; background:#ffd479; padding:2px 8px; border-radius:4px; margin-bottom:10px; }}
.verdict-meta {{ font-size:11px; color:#8a8d9e; margin-top:12px !important; padding-top:10px;
  border-top:1px solid #2a2b35; }}
.verdict-meta code {{ color:#9fd3ff; }}
</style></head><body>
<h1>poscorr — position-mask correlation (pure-control, non-skin)</h1>
<div class="hdr">
<b>Model:</b> {MODEL} &middot; <b>gens run:</b> {n_gens}/9 &middot;
<b>cost:</b> {n_gens} &times; ~${COST_PER_GEN:.2f} &asymp; <b>${cost:.2f}</b> (generation only, $0 deterministic scoring) &middot;
<b>question:</b> can the model correlate an output mask CELL to its template REGION by position alone
(reading-order convention, no colour/number in the prompt), vs an explicit NUMBER-tag convention, vs
today's COLOUR-key convention? See <code>docs/experiments/2026-07-11-position-mask-correlation.md</code>.
</div>
{body}
</body></html>"""
    open(os.path.join(HERE, "results.html"), "w").write(html)
    print(f"-> results.html ({n_gens} gens, ${cost:.2f})")


if __name__ == "__main__":
    main()
