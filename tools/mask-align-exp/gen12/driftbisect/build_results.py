#!/usr/bin/env python3
"""build_results — render driftbisect/results.html from bisect_scores.json.
Matrix: 2 themes x 2 seeds x 3 arms (A prod verbatim / B clause removed / C clause+lock)."""
import os, json, html

HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(HERE, "bisect_scores.json")))
from run_manifest import THEMES, ARMS

ARM_LABEL = {
    "A": "A — production prompt verbatim (bold-silhouette clause present)",
    "B": "B — clause REMOVED (conservative locked housing)",
    "C": "C — clause kept + numeric position-lock addendum (centres within 2%)",
}
RUNS = {(r["id"], r["seed"], r["arm"]): r for r in S["runs"]}
NF = S["noise_floor_px"]


def drift_cls(v):
    if v is None: return ""
    return "ok" if v < 350 else ("warn" if v < 600 else "bad")


def cell(sid, seed, arm):
    r = RUNS.get((sid, seed, arm))
    d = f"assets-bisect-{sid}-{arm.lower()}-{seed}"
    if not r or r.get("error"):
        return f"<div class='cell'><h4>{ARM_LABEL[arm]} · seed {seed}</h4><p class='bad'>missing / failed</p></div>"
    pcd = r["per_control_drift_px"]
    rows = "".join(f"<tr><td>{k}</td><td class='{drift_cls(v)}'>{v}</td></tr>"
                   for k, v in sorted(pcd.items(), key=lambda kv: -kv[1]))
    gate = r.get("gate_pass")
    gcls = "ok" if gate else "bad"
    return f"""
  <div class='cell'>
    <h4>{ARM_LABEL[arm]} · seed {seed}</h4>
    <p><b class='{drift_cls(r['mean_drift_px'])}'>mean drift {r['mean_drift_px']}px</b>
       · worst {r['max_drift_control']} ({r['max_drift_px']}px)
       · gate <span class='{gcls}'>{'PASS' if gate else 'FAIL'}</span>
       <span class='dim'>{html.escape(', '.join(r.get('gate_reasons') or []))}</span></p>
    <div class='imgs'>
      <figure><a href='{d}/overlay-drift.png'><img src='{d}/overlay-drift.png' loading='lazy'></a>
        <figcaption>drift overlay (studio annotation — toggleable to raw paint via link)</figcaption></figure>
      <figure><a href='{d}/paint.png'><img src='{d}/paint.png' loading='lazy'></a>
        <figcaption><a href='{d}/paint.png'>raw paint</a> · <a href='{d}/blueprint.png'>blueprint</a> · <a href='{d}/mask.png'>mask</a></figcaption></figure>
    </div>
    <details><summary>per-control drift px</summary><table>{rows}</table></details>
  </div>"""


theme_sections = ""
for sid, (spec_path, seeds) in THEMES.items():
    per_arm = S["by_theme_arm"][sid]
    delta = S["delta_vs_A_px"][sid]
    theme_sections += f"""
<h2>{sid}</h2>
<p class='summ'>theme mean drift (2 seeds): A <b>{per_arm['A']}px</b> · B <b>{per_arm['B']}px</b>
(&Delta; vs A {delta['B']:+.0f}px) · C <b>{per_arm['C']}px</b> (&Delta; vs A {delta['C']:+.0f}px)
&nbsp;<span class='dim'>positive &Delta; = arm reduced drift; must exceed +{NF}px on BOTH themes to clear the noise floor</span></p>
"""
    for seed in seeds:
        theme_sections += f"<div class='row'>" + "".join(cell(sid, seed, arm) for arm in ARMS) + "</div>"

ba = S["by_arm"]
cf = S["clears_noise_floor"]
arm_rows = "".join(
    f"<tr><td>{ARM_LABEL[a]}</td><td>{ba[a]['mean_of_means_px']}px</td>"
    f"<td>{', '.join(str(v) for v in ba[a]['values'])}</td></tr>" for a in ARMS)

page = f"""<!doctype html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>drift-clause bisect — gen12</title>
<style>
 body{{font:15px/1.5 -apple-system,system-ui,sans-serif;background:#111;color:#ddd;margin:0;padding:1.2rem;max-width:100%;}}
 h1{{font-size:1.4rem}} h2{{margin-top:2rem;border-bottom:1px solid #333;padding-bottom:.3rem}}
 .dim{{color:#888;font-size:.85em}} .ok{{color:#5c5}} .warn{{color:#dbaa2a}} .bad{{color:#e55}}
 .row{{display:flex;flex-wrap:wrap;gap:1rem;margin:.8rem 0}}
 .cell{{flex:1 1 300px;min-width:280px;background:#1a1a1e;border:1px solid #2a2a30;border-radius:8px;padding:.8rem}}
 .cell h4{{margin:.1rem 0 .4rem;font-size:.95rem}}
 .imgs{{display:flex;gap:.5rem;flex-wrap:wrap}} figure{{margin:0;flex:1 1 130px;min-width:120px}}
 img{{width:100%;height:auto;border-radius:4px}} figcaption{{font-size:.75rem;color:#999}}
 table{{border-collapse:collapse;font-size:.85rem}} td{{border:1px solid #333;padding:.15rem .5rem}}
 .summ{{background:#1c2026;padding:.5rem .8rem;border-radius:6px}}
 .conclusion{{background:#20262e;border:1px solid #3a4a5a;border-radius:8px;padding:1rem 1.2rem;margin-top:2.5rem}}
 .meta{{background:#191d16;border:1px solid #2e3a26;border-radius:6px;padding:.6rem .9rem;font-size:.85rem}}
</style></head><body>
<h1>Drift-clause bisect — is the BOLD-silhouette clause driving template drift?</h1>
<div class='meta'><b>models + cost:</b> paint = <code>gemini-3-pro-image-preview</code> via Vertex AI
(project muser-2605300220, 4K, 5:4, $0.24/gen) — 12 kept gens + 1 unbilled 429 retry ≈ <b>$2.88</b>;
matte = local BiRefNet_HR@2048 (MPS, $0); extraction/scoring deterministic ($0). Total ≈ <b>$2.88</b>.
All arms FORCED conditioning='solid' (blueprint arm-draw trial and twoimg both bypassed).</div>

<p>Metric: <code>mean_drift_px</code> — mean over controls of the distance between the authored template
centre and extract12's detected device centre, on the paint's own pixel grid (~2300&times;3712) —
computed by the SAME <code>drift_table()</code> code as <code>twoimg/roster_audit.py</code>
(imported, not reimplemented). Noise floor: <b>{NF}px</b> (roster audit measured ±82–99px arm-less
run-to-run swings; the design note requires an effect clearly above ~100–150px on BOTH themes).</p>

<h2>Per-arm pooled result (n=4 gens/arm)</h2>
<table><tr><td><b>arm</b></td><td><b>mean of per-gen means</b></td><td><b>per-gen values (px)</b></td></tr>{arm_rows}</table>
<p>Noise-floor check (&Delta; vs A must be &gt; +{NF}px on both themes):
B → both themes: <b class='{ 'ok' if cf['B']['both_themes'] else 'bad'}'>{cf['B']['both_themes']}</b>
(wc {cf['B']['per_theme_delta_px']['wc-goldshield']:+.0f}px, fa-pod {cf['B']['per_theme_delta_px']['fa-pod']:+.0f}px) ·
C → both themes: <b class='{ 'ok' if cf['C']['both_themes'] else 'bad'}'>{cf['C']['both_themes']}</b>
(wc {cf['C']['per_theme_delta_px']['wc-goldshield']:+.0f}px, fa-pod {cf['C']['per_theme_delta_px']['fa-pod']:+.0f}px)</p>

{theme_sections}

<div class='conclusion'>
<h2 style='margin-top:0'>Conclusion</h2>
<p><b>Neither arm clears the noise floor on both themes — the bold-silhouette clause is NOT
confirmed as the drift driver, and no prompt change should ship from this result.</b></p>
<ul>
<li><b>B (clause removed)</b> is a clean MIXED result: fa-pod improved (+230px, clears the floor
alone) but wc-goldshield got WORSE (−252px) — consistent within each theme across both seeds
(wc 744/636 vs A's 392/484; fa-pod 267/338 vs A's 570/494). Under the design note's decision
rule a mixed result means a theme-specific confound, not a clean clause effect: do not ship a
global prompt change off it.</li>
<li><b>C (clause + numeric position-lock)</b> helped NOTHING: numerically worse than A on both
themes (−152px / −136px), both below the floor. An explicit "centres within 2%" sentence does
not buy adherence from this model — consistent with the bproof constraint-load finding that
piling on constraint text has diminishing/negative returns.</li>
<li><b>Visual check (real artifacts):</b> B's paints ARE visibly more conservative (plain shield /
plain capsule vs A's ornate winged housings) — the clause does control silhouette boldness. It
just doesn't control drift monotonically: wc-goldshield's conservative B gens rearranged the
control LAYOUT (buttons collapsed to one row) more than the bold A gens did.</li>
<li><b>Baseline validity:</b> arm A's means (392–570px) closely reproduce the live roster audit's
current values (fa-pod 503, wc 462) under FORCED solid conditioning — so the audit-measured drift
level is reproducible without the random arm-draw, ruling the arm-draw out as the sole driver too.</li>
<li><b>Caveat:</b> per the task spec this bisect ran on wc-goldshield + fa-pod — the audit's two
IMPROVERS, not the two worst regressors (fallout-pipboy +808px, steam-porthole +335px). A clause
effect that only manifests on the regressing themes would be invisible here.</li>
<li><b>Recommended next step</b> (per the design note's fall-through): bisect the remaining
suspects — the extraction-algorithm commits (<code>ac28cd74</code>, <code>86f69c75</code>,
<code>a8bbaad0</code>) by re-running CURRENT extract12 against the ORIGINAL baseline paints
(zero new gens, $0 — separates "the paint drifted more" from "the detector measures differently"),
and if that's clean, repeat this bisect on fallout-pipboy + steam-porthole.</li>
</ul>
<p class='dim'>n=2 seeds/theme/arm; every number above sits against a ±{NF}px noise floor. Nothing
here is significant in a statistical sense — the decision rule is the design note's "clears the
floor on both themes" bar, which nothing cleared.</p>
</div>
</body></html>"""

open(os.path.join(HERE, "results.html"), "w").write(page)
print("-> results.html")
