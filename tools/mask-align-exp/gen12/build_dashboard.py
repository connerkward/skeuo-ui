#!/usr/bin/env python3
"""build_dashboard — the gen12 oversight dashboard. Scans every assets-*/ for orch.json +
results.json + regions.json and emits a served, self-navigating dashboard12.html with: a summary
table (skin × mode × gate × rolls × seed), a per-skin PROCESS STRIP (blueprint → joint → paint →
mask → overlay → live player), the gate verdict + notes, and EXPLAINER sections with inline-SVG
diagrams of the novel pipeline steps. Usage: python3 build_dashboard.py"""
import os, json, glob

HERE = os.path.dirname(os.path.abspath(__file__))
skins = []
for d in sorted(glob.glob(os.path.join(HERE, "assets-*"))):
    if d.endswith("_biref"): continue
    sid = os.path.basename(d).replace("assets-", "")
    orch = res = reg = {}
    try: orch = json.load(open(os.path.join(d, "orch.json")))
    except Exception: pass
    try: res = json.load(open(os.path.join(d, "results.json")))
    except Exception: pass
    try: reg = json.load(open(os.path.join(d, "regions.json")))
    except Exception: pass
    gate = reg.get("gate", {})
    skins.append({"id": sid, "title": res.get("title", orch.get("title", sid)),
                  "mode": res.get("mode", "?"), "passed": orch.get("passed", gate.get("PASS")),
                  "rolls": orch.get("rolls", "?"), "seed": orch.get("final_seed", res.get("seed", "?")),
                  "gate": gate, "leak": res.get("leak"),
                  "reasons": (orch.get("gate") or {}).get("reasons") or gate.get("reasons") or []})

npass = sum(1 for s in skins if s["passed"])
n = len(skins)


def card(s):
    sid = s["id"]; g = s["gate"]
    imgs = "".join(
        f'<a href="assets-{sid}/{f}" target=_blank><figure><img src="assets-{sid}/{f}" loading=lazy>'
        f'<figcaption>{lbl}</figcaption></figure></a>'
        for f, lbl in [("blueprint.png", "blueprint / scaffold"), ("joint-4k.png", "joint 4K (fal)"),
                       ("paint.png", "paint (device+strip)"), ("mask.png", "region mask"),
                       ("overlay.png", "mask×paint overlay")])
    badge = '<span class="pass">GATE PASS</span>' if s["passed"] else '<span class="fail">GATE FAIL</span>'
    reasons = ("<b>reasons:</b> " + ", ".join(s["reasons"])) if s["reasons"] else "clean — all checks green"
    det = (f'controls {g.get("controls","?")}/{g.get("controls_total","?")} · '
           f'seek-cov {g.get("seek_cov","?")} · empty {"ok" if g.get("empty_ok") else "FAIL"} · '
           f'align {"ok" if g.get("state_align_ok") else "x"} · leak {s["leak"]}')
    return f'''<section class=card id="{sid}">
  <div class=chead><h3>{s["title"]} <span class=mode>{s["mode"]}</span></h3>
    <div>{badge} · {s["rolls"]} roll(s) · seed {s["seed"]}</div></div>
  <div class=strip>{imgs}
    <a href="assets-{sid}/player.html" target=_blank><figure class=play><div class=pl>▶ LIVE<br>PLAYER</div>
      <figcaption>interactive</figcaption></figure></a></div>
  <div class=gate>{det}<br><span class=rz>{reasons}</span></div>
</section>'''


rows = "".join(
    f'<tr class="{"rp" if s["passed"] else "rf"}"><td><a href="#{s["id"]}">{s["id"]}</a></td>'
    f'<td>{s["mode"]}</td><td>{"✓ PASS" if s["passed"] else "✗ FAIL"}</td><td>{s["rolls"]}</td>'
    f'<td>{s["seed"]}</td><td>{s["gate"].get("controls","?")}/{s["gate"].get("controls_total","?")}</td>'
    f'<td>{s["gate"].get("seek_cov","?")}</td><td>{", ".join(s["reasons"]) or "—"}</td></tr>'
    for s in skins)

# --- explainer SVG diagrams (inline, self-contained) ---
EXPLAINERS = '''
<h2>How the novel steps work</h2>
<div class=exgrid>
  <div class=ex><h4>Coverage-span seek travel</h4>
    <svg viewBox="0 0 320 90"><rect x="0" y="0" width="320" height="90" fill="#0d0f14"/>
      <rect x="40" y="35" width="240" height="20" rx="10" fill="#1b2230" stroke="#3a4a63"/>
      <rect x="40" y="35" width="20" height="20" rx="10" fill="#2a3345"/><rect x="260" y="35" width="20" height="20" rx="10" fill="#2a3345"/>
      <rect x="46" y="38" width="34" height="14" rx="7" fill="#6aa0ff"/>
      <line x1="40" y1="70" x2="280" y2="70" stroke="#5f7" stroke-width="2"/><text x="150" y="84" fill="#8fa" font-size="11" text-anchor="middle">travel = full painted groove (rim→rim)</text>
      <text x="150" y="22" fill="#9ab" font-size="11" text-anchor="middle">walk out through recess + bezel rims; stop at body/backdrop</text></svg>
    <p>The mask bbox undershoots the painted channel, so the extractor walks the paint outward from centre through the dark recess AND its bright bezel rims, stopping only at solid body or backdrop — the thumb then covers the whole slot end-to-end.</p></div>
  <div class=ex><h4>Matte-hole-centroid knob seat</h4>
    <svg viewBox="0 0 200 90"><rect width="200" height="90" fill="#0d0f14"/>
      <circle cx="100" cy="45" r="34" fill="#12161d" stroke="#3a4a63"/>
      <circle cx="108" cy="41" r="30" fill="none" stroke="#f55" stroke-dasharray="4 3"/><text x="150" y="30" fill="#f88" font-size="10">gradient fit</text>
      <circle cx="100" cy="45" r="30" fill="none" stroke="#5f7"/><text x="150" y="66" fill="#8fa" font-size="10">hole centroid</text></svg>
    <p>A gradient circle-fit nails the socket radius but its centre drifts on an asymmetric specular arc. The centre is snapped to the BiRefNet matte alpha-hole centroid (geometric, no lighting bias); radius kept.</p></div>
  <div class=ex><h4>Silhouette-IoU switch registration</h4>
    <svg viewBox="0 0 220 90"><rect width="220" height="90" fill="#0d0f14"/>
      <rect x="30" y="30" width="70" height="34" rx="17" fill="#243" stroke="#5f7"/><text x="65" y="80" fill="#8fa" font-size="10" text-anchor="middle">OFF</text>
      <rect x="120" y="30" width="70" height="34" rx="17" fill="#234" stroke="#6af"/><text x="155" y="80" fill="#9bf" font-size="10" text-anchor="middle">ON → scaled+shifted to OFF box (IoU max)</text></svg>
    <p>The OFF and ON cut silhouettes are registered by scale + (dx,dy) that maximise their IoU, so the housing sits at the same spot in both states — only the lever moves. Rendered box shift &lt;1px.</p></div>
  <div class=ex><h4>Rotational placement</h4>
    <svg viewBox="0 0 200 90"><rect width="200" height="90" fill="#0d0f14"/>
      <g transform="rotate(-25 100 45)"><rect x="55" y="34" width="90" height="22" rx="11" fill="#243" stroke="#5f7"/>
        <circle cx="72" cy="45" r="13" fill="#8ab"/></g><text x="100" y="82" fill="#8fa" font-size="10" text-anchor="middle">PCA angle of device-slot pixels → rotate the part</text></svg>
    <p>A slot following an organic body is tilted. Its major-axis angle (PCA over the device-region mask pixels only — excluding strip cells) rotates the placed part to seat along the slot.</p></div>
  <div class=ex><h4>Templated vs templateless</h4>
    <svg viewBox="0 0 300 90"><rect width="300" height="90" fill="#0d0f14"/>
      <rect x="14" y="18" width="120" height="54" rx="8" fill="#12161d" stroke="#3a4a63"/><text x="74" y="14" fill="#9ab" font-size="10" text-anchor="middle">TEMPLATED</text>
      <circle cx="44" cy="40" r="8" fill="none" stroke="#f5a"/><circle cx="74" cy="40" r="8" fill="none" stroke="#5af"/><circle cx="104" cy="40" r="8" fill="none" stroke="#fd5"/>
      <text x="74" y="64" fill="#789" font-size="9" text-anchor="middle">positions locked, model styles</text>
      <rect x="166" y="18" width="120" height="54" rx="8" fill="#12161d" stroke="#3a4a63"/><text x="226" y="14" fill="#9ab" font-size="10" text-anchor="middle">TEMPLATELESS</text>
      <text x="226" y="44" fill="#789" font-size="9" text-anchor="middle">blank scaffold → model</text><text x="226" y="58" fill="#789" font-size="9" text-anchor="middle">designs; post-hoc detect</text></svg>
    <p>Templated locks control POSITIONS (model restyles surface + sculpts a bold outer housing). Templateless gives a blank scaffold — the model designs the whole player and the extractor recovers every control post-hoc from the returned mask.</p></div>
  <div class=ex><h4>Auto-regen gate loop</h4>
    <svg viewBox="0 0 300 90"><rect width="300" height="90" fill="#0d0f14"/>
      <rect x="14" y="34" width="60" height="24" rx="4" fill="#1b2230" stroke="#3a4a63"/><text x="44" y="50" fill="#9ab" font-size="9" text-anchor="middle">gen+extract</text>
      <path d="M74 46 h30" stroke="#5a7" fill="none" marker-end="url(#a)"/><rect x="104" y="34" width="44" height="24" rx="4" fill="#1b2230" stroke="#3a4a63"/><text x="126" y="50" fill="#9ab" font-size="9" text-anchor="middle">GATE?</text>
      <path d="M148 46 h34" stroke="#5f7" fill="none" marker-end="url(#a)"/><rect x="182" y="34" width="50" height="24" rx="4" fill="#152" stroke="#5f7"/><text x="207" y="50" fill="#8fa" font-size="9" text-anchor="middle">player</text>
      <path d="M126 58 v16 h-82 v-28" stroke="#f85" fill="none" marker-end="url(#a)"/><text x="150" y="86" fill="#f96" font-size="9">FAIL → reseed (≤4)</text>
      <defs><marker id="a" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0 0 L6 3 L0 6 z" fill="#8ab"/></marker></defs></svg>
    <p>Each skin rolls seeds through the full pipeline until the structured GATE passes (empty sockets · 10/10 controls · seek coverage · biref parts · leak) or 4 tries — auto-selecting a clean generation without human babysitting.</p></div>
</div>
<h2>Roster → Spotify Web API</h2>
<p class=roster>play/pause · prev · next · repeat · queue (baked icon buttons) · volume (knob) · seek (slider) · shuffle (2-state toggle) · album-art + visualizer (display regions). All map to Spotify Web API capabilities; the visualizer is decorative (audio-analysis is deprecated for new apps — confirm at wiring time).</p>
'''

HTML = f'''<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>gen12 — skin batch oversight</title><style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}
body{{margin:0;background:#0a0b0e;color:#cdd3dd;font:14px/1.55 system-ui,sans-serif;padding:24px;max-width:1200px;margin:auto}}
h1{{font-size:22px;margin:0 0 4px}}.sub{{color:#8a90a0;font:12px ui-monospace,monospace;margin-bottom:18px}}
h2{{margin:34px 0 12px;font-size:17px;border-bottom:1px solid #ffffff18;padding-bottom:6px}}
table{{width:100%;border-collapse:collapse;font:12.5px ui-monospace,monospace;margin-bottom:10px}}
th,td{{text-align:left;padding:6px 9px;border-bottom:1px solid #ffffff12}}th{{color:#9aa}}
tr.rp td:nth-child(3){{color:#6f9}}tr.rf td:nth-child(3){{color:#f77}}
a{{color:#7ab7ff;text-decoration:none}}a:hover{{text-decoration:underline}}
.stat{{display:inline-block;background:#12161d;border:1px solid #ffffff14;border-radius:8px;padding:8px 14px;margin:0 8px 8px 0;font:13px ui-monospace,monospace}}
.card{{background:#0e1116;border:1px solid #ffffff14;border-radius:12px;padding:16px;margin:16px 0}}
.chead{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:12px;font:12px ui-monospace,monospace}}
.chead h3{{margin:0;font-size:16px}}.mode{{font:11px ui-monospace,monospace;color:#8a90a0;border:1px solid #ffffff20;border-radius:5px;padding:1px 6px;margin-left:6px}}
.pass{{color:#0a0;background:#6f9;border-radius:5px;padding:2px 8px;font-weight:700}}.fail{{color:#300;background:#f88;border-radius:5px;padding:2px 8px;font-weight:700}}
.strip{{display:flex;gap:10px;overflow-x:auto;padding-bottom:6px}}
.strip figure{{margin:0;flex:0 0 auto;width:150px}}.strip img{{width:150px;height:auto;border-radius:6px;border:1px solid #ffffff14;background:#000}}
.strip figcaption{{font:10px ui-monospace,monospace;color:#8a90a0;margin-top:4px;text-align:center}}
.play{{width:110px!important}}.pl{{width:110px;height:150px;display:flex;align-items:center;justify-content:center;text-align:center;background:linear-gradient(160deg,#16324e,#0d1c2e);border:1px solid #2a6;border-radius:6px;color:#8fd;font:700 13px ui-monospace,monospace}}
.gate{{font:11.5px ui-monospace,monospace;color:#9ab;margin-top:10px}}.rz{{color:#8a90a0}}
.exgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}}
.ex{{background:#0e1116;border:1px solid #ffffff14;border-radius:10px;padding:12px}}.ex h4{{margin:0 0 8px;font-size:13px}}.ex svg{{width:100%;height:auto;border-radius:6px;margin-bottom:8px}}.ex p{{font-size:12.5px;color:#9aa;margin:0}}
.roster{{font:12px ui-monospace,monospace;color:#9ab;background:#12161d;border:1px solid #ffffff14;border-radius:8px;padding:12px}}
@media (prefers-color-scheme:light){{body{{background:#f6f7f9;color:#1a1d22}}.card,.ex,.stat,.roster{{background:#fff;border-color:#00000015}}}}
</style></head><body>
<h1>gen12 — media-player skin batch</h1>
<div class=sub>{npass}/{n} skins passed the auto-regen gate · Spotify-roster · one nano-banana-pro gen + BiRefNet per roll · fully local extraction</div>
<div><span class=stat>{n} skins</span><span class=stat>{npass} gate-pass</span><span class=stat>{sum(1 for s in skins if s["mode"]=="templated")} templated</span><span class=stat>{sum(1 for s in skins if s["mode"]=="templateless")} templateless</span></div>
<h2>Overview</h2>
<table><thead><tr><th>skin</th><th>mode</th><th>gate</th><th>rolls</th><th>seed</th><th>controls</th><th>seek-cov</th><th>fail reasons</th></tr></thead>
<tbody>{rows}</tbody></table>
<h2>Per-skin process</h2>
{"".join(card(s) for s in skins)}
{EXPLAINERS}
<div class=sub style="margin-top:30px">gen12 pipeline: genskin.py · extract12.py · biref12.py · build_player.py · orchestrate12.py — tools/mask-align-exp/gen12/</div>
</body></html>'''

open(os.path.join(HERE, "dashboard12.html"), "w").write(HTML)
print(f"[dashboard] {npass}/{n} passed -> dashboard12.html")
