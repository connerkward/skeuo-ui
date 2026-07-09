#!/usr/bin/env python3
"""build_dashboard — the gen12 oversight + HUMAN-REVIEW dashboard. Per skin: the LIVE interactive
player hoisted to the top, a human PASS/FAIL gate toggle, and a "what's wrong" notes box — all
persisted in localStorage with an export so verdicts can be read back. Below that: the auto-gate
verdict, the process strip (blueprint→paint→mask→overlay), and explainer diagrams.
Usage: python3 build_dashboard.py"""
import os, json, glob

HERE = os.path.dirname(os.path.abspath(__file__))
skins = []
for d in sorted(glob.glob(os.path.join(HERE, "assets-*"))):
    if d.endswith("_biref"): continue
    sid = os.path.basename(d).replace("assets-", "")
    orch = res = reg = {}
    for fn, tgt in [("orch.json", "orch"), ("results.json", "res"), ("regions.json", "reg")]:
        try:
            v = json.load(open(os.path.join(d, fn)))
            if tgt == "orch": orch = v
            elif tgt == "res": res = v
            else: reg = v
        except Exception: pass
    gate = reg.get("gate", {})
    skins.append({"id": sid, "title": res.get("title", orch.get("title", sid)),
                  "mode": res.get("mode", "?"), "passed": orch.get("passed", gate.get("PASS")),
                  "rolls": orch.get("rolls", "?"), "seed": orch.get("final_seed", res.get("seed", "?")),
                  "gate": gate, "leak": res.get("leak"),
                  "reasons": (orch.get("gate") or {}).get("reasons") or gate.get("reasons") or []})
npass = sum(1 for s in skins if s["passed"]); n = len(skins)


def card(s):
    sid = s["id"]; g = s["gate"]
    imgs = "".join(
        f'<a href="assets-{sid}/{f}" target=_blank><figure><img src="assets-{sid}/{f}" loading=lazy>'
        f'<figcaption>{lbl}</figcaption></figure></a>'
        for f, lbl in [("blueprint.png", "blueprint"), ("paint.png", "paint"), ("mask.png", "mask"),
                       ("overlay.png", "overlay")])
    autob = '<span class="pass">auto PASS</span>' if s["passed"] else '<span class="fail">auto FAIL</span>'
    reasons = ("reasons: " + ", ".join(s["reasons"])) if s["reasons"] else "all checks green"
    det = (f'controls {g.get("controls","?")}/{g.get("controls_total","?")} · seek-cov {g.get("seek_cov","?")} · '
           f'empty {"ok" if g.get("empty_ok") else "FAIL"} · align {"ok" if g.get("state_align_ok") else "x"} · '
           f'leak {s["leak"]} · {s["rolls"]} roll(s) · seed {s["seed"]}')
    return f'''<section class=card id="c-{sid}" data-id="{sid}">
  <div class=chead><h3>{s["title"]} <span class=mode>{s["mode"]}</span></h3>
    <div class=hverdict><span class=hlabel>your gate:</span>
      <button class="htoggle" data-id="{sid}">— unset —</button></div></div>
  <div class=live><iframe src="assets-{sid}/player.html" loading=lazy title="{sid} player"></iframe>
    <div class=side>
      <textarea class=hnotes data-id="{sid}" placeholder="what's wrong with this skin? (autosaves)"></textarea>
      <div class=auto>{autob} · <span class=det>{det}</span><br><span class=rz>{reasons}</span></div>
      <details class=proc><summary>process images</summary><div class=strip>{imgs}</div></details>
    </div></div>
</section>'''


rows = "".join(
    f'<tr class="{"rp" if s["passed"] else "rf"}"><td><a href="#c-{s["id"]}">{s["id"]}</a></td>'
    f'<td>{s["mode"]}</td><td>{"✓" if s["passed"] else "✗"}</td>'
    f'<td class="hcell" data-id="{s["id"]}">—</td><td>{s["rolls"]}</td><td>{", ".join(s["reasons"]) or "—"}</td></tr>'
    for s in skins)

EXPLAINERS = '''<h2>How the novel steps work</h2><div class=exgrid>
  <div class=ex><h4>Coverage-span seek travel</h4><p>The mask bbox undershoots the painted channel, so the extractor walks the paint outward from centre through the dark recess AND its bright bezel rims, stopping at solid body or backdrop — the thumb covers the whole slot.</p></div>
  <div class=ex><h4>Matte-hole knob seat</h4><p>A gradient circle-fit gives the radius; the centre snaps to the BiRefNet alpha-hole centroid (geometric, no specular bias).</p></div>
  <div class=ex><h4>Silhouette-IoU switch registration</h4><p>OFF/ON cut silhouettes registered by the scale+offset that maximise IoU, so the housing sits still and only the lever moves.</p></div>
  <div class=ex><h4>Device-only slot rotation</h4><p>Slot tilt = PCA major-axis of the DEVICE-region mask pixels only (strip cells excluded); the part is rotated to seat along a tilted slot.</p></div>
  <div class=ex><h4>Templated vs templateless</h4><p>Templated locks control positions (model styles + sculpts a bold housing); templateless gives a blank scaffold and detects everything post-hoc.</p></div>
  <div class=ex><h4>Auto-regen gate loop</h4><p>Each skin reseeds through the full pipeline until the structured gate passes (empty sockets · 10/10 controls · seek coverage · biref parts · leak) or 4 tries.</p></div>
</div>'''

HTML = f'''<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>gen12 — human review</title><style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}
body{{margin:0;background:#0a0b0e;color:#cdd3dd;font:14px/1.55 system-ui,sans-serif;padding:22px;max-width:1180px;margin:auto}}
h1{{font-size:22px;margin:0 0 4px}}.sub{{color:#8a90a0;font:12px ui-monospace,monospace;margin-bottom:14px}}
h2{{margin:32px 0 12px;font-size:17px;border-bottom:1px solid #ffffff18;padding-bottom:6px}}
a{{color:#7ab7ff;text-decoration:none}}a:hover{{text-decoration:underline}}
.bar{{position:sticky;top:0;z-index:20;background:#0a0b0eee;backdrop-filter:blur(6px);padding:10px 0;border-bottom:1px solid #ffffff14;margin-bottom:14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
.stat{{background:#12161d;border:1px solid #ffffff14;border-radius:8px;padding:6px 12px;font:12px ui-monospace,monospace}}
.btn{{background:#1b3a5c;border:1px solid #2a6cff55;color:#bfe;border-radius:8px;padding:7px 13px;font:12px ui-monospace,monospace;cursor:pointer}}.btn:hover{{background:#245}}
table{{width:100%;border-collapse:collapse;font:12.5px ui-monospace,monospace}}th,td{{text-align:left;padding:5px 9px;border-bottom:1px solid #ffffff12}}th{{color:#9aa}}
.hcell.hp{{color:#6f9;font-weight:700}}.hcell.hf{{color:#f77;font-weight:700}}
.card{{background:#0e1116;border:1px solid #ffffff14;border-radius:12px;padding:16px;margin:18px 0;scroll-margin-top:70px}}
.card.hp{{border-color:#2a6}}.card.hf{{border-color:#a33}}
.chead{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:12px}}
.chead h3{{margin:0;font-size:17px}}.mode{{font:11px ui-monospace,monospace;color:#8a90a0;border:1px solid #ffffff20;border-radius:5px;padding:1px 6px;margin-left:6px}}
.hverdict{{display:flex;align-items:center;gap:8px}}.hlabel{{font:11px ui-monospace,monospace;color:#8a90a0}}
.htoggle{{border:1px solid #ffffff26;background:#161a22;color:#9aa;border-radius:8px;padding:7px 16px;font:700 12px ui-monospace,monospace;cursor:pointer;min-width:120px}}
.htoggle.hp{{background:#153;border-color:#3a7;color:#7fe}}.htoggle.hf{{background:#511;border-color:#a44;color:#f99}}
.live{{display:flex;gap:16px;flex-wrap:wrap}}
.live iframe{{flex:0 0 auto;width:320px;height:520px;border:1px solid #ffffff18;border-radius:10px;background:#0c0d10}}
.side{{flex:1 1 300px;display:flex;flex-direction:column;gap:10px;min-width:280px}}
.hnotes{{width:100%;min-height:120px;resize:vertical;background:#0b0d12;border:1px solid #ffffff20;border-radius:8px;color:#dde;padding:10px;font:13px ui-monospace,monospace}}
.hnotes:focus{{outline:1px solid #3a6cff88}}
.auto{{font:11px ui-monospace,monospace;color:#9ab}}.det{{color:#8a90a0}}.rz{{color:#7a8090}}
.pass{{color:#062;background:#6f9;border-radius:4px;padding:1px 6px;font-weight:700}}.fail{{color:#400;background:#f88;border-radius:4px;padding:1px 6px;font-weight:700}}
.proc summary{{cursor:pointer;color:#8ab;font:11px ui-monospace,monospace}}
.strip{{display:flex;gap:8px;overflow-x:auto;padding-top:8px}}.strip figure{{margin:0;flex:0 0 auto;width:120px}}.strip img{{width:120px;border-radius:6px;border:1px solid #ffffff14;background:#000}}.strip figcaption{{font:10px ui-monospace,monospace;color:#8a90a0;text-align:center;margin-top:3px}}
.exgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}}.ex{{background:#0e1116;border:1px solid #ffffff14;border-radius:10px;padding:12px}}.ex h4{{margin:0 0 6px;font-size:13px}}.ex p{{font-size:12.5px;color:#9aa;margin:0}}
@media (prefers-color-scheme:light){{body{{background:#f6f7f9;color:#1a1d22}}.card,.ex,.stat,.hnotes,.htoggle{{background:#fff;border-color:#00000018}}.bar{{background:#f6f7f9ee}}}}
</style></head><body>
<h1>gen12 — human review</h1>
<div class=sub>auto-gate {npass}/{n} · set YOUR pass/fail per skin, note what's wrong; verdicts autosave. Live players are embedded — drag knobs/seek, click buttons.</div>
<div class=bar>
  <span class=stat id=hsum>your gate: 0 pass · 0 fail · {n} unset</span>
  <button class=btn onclick=exportFb()>⬇ download verdicts JSON</button>
  <button class=btn onclick=copyFb()>⧉ copy JSON</button>
  <button class=btn onclick="localStorage.clear();location.reload()">reset</button>
</div>
<h2>Overview</h2>
<table><thead><tr><th>skin</th><th>mode</th><th>auto</th><th>your gate</th><th>rolls</th><th>auto-fail reasons</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Per-skin review</h2>
{"".join(card(s) for s in skins)}
{EXPLAINERS}
<script>
const KEY='gen12-review';
function load(){{ try{{return JSON.parse(localStorage.getItem(KEY))||{{}}}}catch(e){{return {{}}}} }}
let _pt=null;
function pushServer(){{ clearTimeout(_pt); _pt=setTimeout(()=>{{ fetch('/save',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:fbJSON()}}).catch(()=>{{}}); }},400); }}
function save(o){{ localStorage.setItem(KEY, JSON.stringify(o)); pushServer(); }}
function applyToggle(btn, v){{ btn.classList.remove('hp','hf'); btn.textContent = v==='pass'?'✓ PASS':v==='fail'?'✗ FAIL':'— unset —';
  if(v==='pass')btn.classList.add('hp'); if(v==='fail')btn.classList.add('hf');
  const card=document.getElementById('c-'+btn.dataset.id); card.classList.remove('hp','hf'); if(v)card.classList.add(v==='pass'?'hp':'hf');
  const cell=document.querySelector('.hcell[data-id="'+btn.dataset.id+'"]'); if(cell){{cell.classList.remove('hp','hf');cell.textContent=v==='pass'?'PASS':v==='fail'?'FAIL':'—';if(v)cell.classList.add(v==='pass'?'hp':'hf');}}
}}
function summary(){{ const o=load(); let p=0,f=0,u=0; document.querySelectorAll('.htoggle').forEach(b=>{{const v=(o[b.dataset.id]||{{}}).gate; if(v==='pass')p++;else if(v==='fail')f++;else u++;}});
  document.getElementById('hsum').textContent='your gate: '+p+' pass · '+f+' fail · '+u+' unset'; }}
const store=load();
document.querySelectorAll('.htoggle').forEach(btn=>{{ const id=btn.dataset.id; applyToggle(btn,(store[id]||{{}}).gate||'');
  btn.onclick=()=>{{ const o=load(); const cur=(o[id]||{{}}).gate||''; const nxt=cur===''?'pass':cur==='pass'?'fail':''; o[id]={{...(o[id]||{{}}),gate:nxt}}; save(o); applyToggle(btn,nxt); summary(); }}; }});
document.querySelectorAll('.hnotes').forEach(ta=>{{ const id=ta.dataset.id; ta.value=(store[id]||{{}}).notes||'';
  ta.oninput=()=>{{ const o=load(); o[id]={{...(o[id]||{{}}),notes:ta.value}}; save(o); }}; }});
summary();
function fbJSON(){{ const o=load(); const out={{}}; document.querySelectorAll('.htoggle').forEach(b=>{{const id=b.dataset.id;const e=o[id]||{{}};out[id]={{gate:e.gate||'unset',notes:e.notes||''}};}}); return JSON.stringify(out,null,2); }}
function exportFb(){{ const blob=new Blob([fbJSON()],{{type:'application/json'}}); const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='gen12-review.json'; a.click(); }}
function copyFb(){{ navigator.clipboard.writeText(fbJSON()).then(()=>alert('verdicts copied to clipboard')); }}
</script></body></html>'''
open(os.path.join(HERE, "dashboard12.html"), "w").write(HTML)
print(f"[dashboard] human-review · auto {npass}/{n} -> dashboard12.html")
