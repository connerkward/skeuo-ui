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
# cost annotation (dev-facing-model-cost-annotation-rule): sum rolls × per-roll model spend
total_rolls = sum(s["rolls"] for s in skins if isinstance(s["rolls"], int))
GEN_MODEL = "fal-ai/gemini-3-pro-image-preview/edit"; MATTE_MODEL = "fal-ai/birefnet/v2"
cost_lo = total_rolls * (0.15 + 0.005); cost_hi = cost_lo * 1.15
cost_line = (f"models: <b>{GEN_MODEL}</b> (paint+mask, ~$0.15/roll) + <b>{MATTE_MODEL}</b> (~$0.005/roll) · "
             f"extraction/player = local $0 · est. total ≈ <b>${cost_lo:.2f}</b> "
             f"({total_rolls} rolls × ~$0.155)")


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

EXPLAINERS = '''<h2>How it works — interactive walkthrough (real artifacts)</h2>
<div id=walk class=walk>
  <div class=wnav id=wnav></div>
  <div class=wbody><a id=wlink target=_blank><img id=wimg alt="pipeline step"></a>
    <div class=wcap><h4 id=wtitle></h4><p id=wdesc></p></div></div>
</div>
<script>
fetch('explainer/steps.json').then(r=>r.json()).then(d=>{
  const nav=document.getElementById('wnav'); let cur=0;
  function show(i){ cur=i; const s=d.steps[i];
    document.getElementById('wimg').src='explainer/'+s.img;
    document.getElementById('wlink').href='explainer/'+s.img;
    document.getElementById('wtitle').textContent=s.t;
    document.getElementById('wdesc').textContent=s.d;
    [...nav.children].forEach((b,j)=>b.classList.toggle('on',j===i)); }
  d.steps.forEach((s,i)=>{ const b=document.createElement('button'); b.className='wstep';
    b.textContent=s.t.split('·')[0].trim(); b.title=s.t; b.onclick=()=>show(i); nav.appendChild(b); });
  document.addEventListener('keydown',e=>{ if(/INPUT|TEXTAREA/.test(e.target.tagName))return;
    if(e.key==='ArrowRight'&&cur<d.steps.length-1)show(cur+1); if(e.key==='ArrowLeft'&&cur>0)show(cur-1); });
  show(0);
}).catch(()=>{ document.getElementById('walk').innerHTML='<p style="color:#888">run build_explainer.py to generate the walkthrough images</p>'; });
</script>
<h2>Concepts — for someone new to this</h2>

<div class=ex ex-wide>
  <h4>0 · The big picture: why a "mask" makes this reliable</h4>
  <svg viewBox="0 0 460 120"><rect width="460" height="120" fill="#0d0f14"/>
    <rect x="14" y="16" width="120" height="88" rx="6" fill="#161a22" stroke="#3a4a63"/><text x="74" y="12" fill="#9ab" font-size="10" text-anchor="middle">blueprint (we draw)</text>
    <circle cx="44" cy="45" r="9" fill="none" stroke="#f5a"/><circle cx="74" cy="45" r="9" fill="none" stroke="#5af"/><circle cx="104" cy="45" r="9" fill="none" stroke="#fd5"/><rect x="34" y="72" width="80" height="14" rx="7" fill="none" stroke="#7f7"/>
    <path d="M140 60 h26" stroke="#5a7" fill="none" marker-end="url(#a)"/><text x="153" y="54" fill="#789" font-size="8">gen</text>
    <rect x="172" y="16" width="120" height="88" rx="6" fill="#12202e" stroke="#3a4a63"/><text x="232" y="12" fill="#9ab" font-size="10" text-anchor="middle">LEFT: finished skin</text>
    <circle cx="202" cy="45" r="9" fill="#6ad"/><circle cx="232" cy="45" r="11" fill="#e55"/><circle cx="262" cy="45" r="9" fill="#dd6"/><rect x="192" y="72" width="80" height="14" rx="7" fill="#334"/>
    <rect x="300" y="16" width="120" height="88" rx="6" fill="#000" stroke="#3a4a63"/><text x="360" y="12" fill="#9ab" font-size="10" text-anchor="middle">RIGHT: colour mask</text>
    <circle cx="330" cy="45" r="9" fill="#f5a"/><circle cx="360" cy="45" r="11" fill="#5af"/><circle cx="390" cy="45" r="9" fill="#fd5"/><rect x="320" y="72" width="80" height="14" rx="7" fill="#7f7"/>
    <defs><marker id="a" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0 0 L6 3 L0 6 z" fill="#8ab"/></marker></defs></svg>
  <p><b>The problem.</b> Detecting buttons in a finished image ("computer vision on a screenshot") is fragile and famously unreliable. <b>The trick.</b> We hand the image model a <span class=kt>blueprint</span> — a technical drawing where every control is a coloured outline at a fixed spot — beside a black panel, and ask for <em>two</em> pictures that line up pixel-for-pixel: the <b>LEFT</b> is the finished skin, the <b>RIGHT</b> is a <span class=kt>mask</span> (a "colour-by-numbers" map where each control is one flat solid colour). Because the halves are aligned, the coloured blobs on the right are an exact <em>coordinate cheat-sheet</em> for the left — we never guess where a control is, the model literally labels it for us. Everything below is how we turn that cheat-sheet into a working, draggable player.</p>
  <p class=kt-defs><b>Key terms —</b> <b>image-edit model:</b> an AI (here nano-banana / Gemini image) that redraws an input image following a prompt · <b>mask / segmentation map:</b> an image where pixel colour = which object that pixel belongs to · <b>guide colour:</b> a unique colour we assign to each control, chosen far from the skin's real colours so it can't be confused.</p>
</div>

<div class=exgrid>
  <div class=ex><h4>1 · Coverage-span seek travel</h4>
    <svg viewBox="0 0 320 84"><rect width="320" height="84" fill="#0d0f14"/>
      <rect x="20" y="30" width="280" height="20" rx="10" fill="#161a22"/><rect x="52" y="32" width="216" height="16" rx="8" fill="#1b2230" stroke="#3a4a63"/>
      <rect x="52" y="32" width="14" height="16" rx="7" fill="#2a3345"/><rect x="254" y="32" width="14" height="16" rx="7" fill="#2a3345"/>
      <rect x="58" y="34" width="30" height="12" rx="6" fill="#6aa0ff"/>
      <line x1="52" y1="64" x2="268" y2="64" stroke="#5f7" stroke-width="2"/><text x="160" y="78" fill="#8fa" font-size="10" text-anchor="middle">travel = end-cap → end-cap (recess + bezel rims)</text>
      <text x="160" y="20" fill="#789" font-size="9" text-anchor="middle">walk out until solid body / background</text></svg>
    <p><b>Problem.</b> The thumb must slide the whole length of the groove. The mask's rough rectangle for the groove is usually a little short, so the thumb would stop before the ends.</p>
    <p><b>How.</b> The groove is a dark <span class=kt>recess</span> cut into a brighter body. We read one horizontal line of pixels through its centre and look at their <span class=kt>luminance</span> (brightness). Starting at the middle we <b>walk outward one pixel at a time</b>: keep going while pixels are dark (the channel floor) <em>or</em> bright (the metal <span class=kt>bezel</span> rim that frames the slot); <b>stop</b> only when we hit the solid body (bright for many pixels in a row → we've left the slot) or the near-black background. The distance between the left-stop and right-stop is the slot's true visual width — that becomes the thumb's <b>travel range</b>.</p>
    <p class=kt-defs><b>luminance</b> = perceived brightness · <b>recess</b> = the sunken channel · <b>bezel</b> = the raised rim around a slot.</p></div>

  <div class=ex><h4>2 · Matte-hole knob seat</h4>
    <svg viewBox="0 0 200 84"><rect width="200" height="84" fill="#0d0f14"/>
      <circle cx="90" cy="42" r="30" fill="#12161d" stroke="#3a4a63"/>
      <circle cx="98" cy="38" r="27" fill="none" stroke="#f55" stroke-dasharray="4 3"/><text x="150" y="26" fill="#f88" font-size="9">gradient fit</text><text x="150" y="37" fill="#a77" font-size="8">(radius ✓, centre drifts)</text>
      <circle cx="90" cy="42" r="27" fill="none" stroke="#5f7"/><circle cx="90" cy="42" r="2" fill="#5f7"/><text x="150" y="58" fill="#8fa" font-size="9">hole centroid</text><text x="150" y="69" fill="#7a7" font-size="8">(true centre)</text></svg>
    <p><b>Problem.</b> A round knob must sit dead-centre in its socket, but a bright glare on one side fools simple centre-finding.</p>
    <p><b>How.</b> Two signals combined. <b>(a) Circle fit</b> (a mini <span class=kt>Hough transform</span>): try thousands of candidate circles — centre (x,y) and radius r — and score each by how much <span class=kt>gradient</span> (edge strength) lies along its outline. The socket's rim is a strong edge, so the best-scoring circle locks onto the rim and gives a trustworthy <b>radius</b>. But its <em>centre</em> slides toward a glary side. <b>(b)</b> So we take the centre from elsewhere: <span class=kt>BiRefNet</span> (a background-removal network) outputs an <span class=kt>alpha matte</span> — a transparency map of the device — in which an <em>empty</em> socket appears as a HOLE. The geometric <span class=kt>centroid</span> (average of all the hole's pixel positions) is the socket's true centre, immune to lighting. Final seat = <b>fit radius + hole centroid</b>.</p>
    <p class=kt-defs><b>gradient</b> = how fast brightness changes (big at edges) · <b>Hough transform</b> = vote over many candidate shapes, keep the best · <b>alpha matte</b> = per-pixel opacity · <b>centroid</b> = average position.</p></div>

  <div class=ex><h4>3 · Silhouette-IoU switch registration</h4>
    <svg viewBox="0 0 220 84"><rect width="220" height="84" fill="#0d0f14"/>
      <rect x="24" y="28" width="66" height="30" rx="15" fill="#243" stroke="#5f7"/><circle cx="42" cy="43" r="10" fill="#8fa"/><text x="57" y="74" fill="#8fa" font-size="9" text-anchor="middle">OFF</text>
      <rect x="118" y="28" width="66" height="30" rx="15" fill="#234" stroke="#6af"/><circle cx="166" cy="43" r="10" fill="#9bf"/><text x="151" y="74" fill="#9bf" font-size="9" text-anchor="middle">ON — slid to max overlap</text></svg>
    <p><b>Problem.</b> A toggle has two states drawn as two separate cut-outs. Flipping it should move only the lever — but the two cut-outs are trimmed slightly differently, so naively centring them makes the whole switch jump.</p>
    <p><b>How.</b> We <span class=kt>register</span> (align) the ON cut-out onto the OFF one. Reduce each to a black-and-white <span class=kt>silhouette</span> (shape only, ignore colour). Scale ON to OFF's size, then <b>slide it over a grid of offsets</b> (dx, dy); at each position compute <span class=kt>IoU</span> = <b>Intersection over Union</b> = (area where both shapes overlap) ÷ (area covered by either). The offset with the <b>highest IoU</b> is where the two housings line up best. We save that scale+shift; the player applies it so the housing stays frozen and only the lever slides.</p>
    <p class=kt-defs><b>register</b> = align two images · <b>silhouette</b> = filled outline shape · <b>IoU</b> = overlap ÷ union, a 0–1 similarity score (1 = identical).</p></div>

  <div class=ex><h4>4 · Device-only PCA slot rotation</h4>
    <svg viewBox="0 0 220 84"><rect width="220" height="84" fill="#0d0f14"/>
      <g transform="rotate(-24 110 42)"><rect x="62" y="31" width="96" height="22" rx="11" fill="#243" stroke="#5f7"/><circle cx="80" cy="42" r="12" fill="#8ab"/></g>
      <line x1="70" y1="58" x2="150" y2="26" stroke="#fd5" stroke-dasharray="3 3"/><text x="110" y="78" fill="#8fa" font-size="9" text-anchor="middle">principal axis → tilt angle → rotate part</text></svg>
    <p><b>Problem.</b> On a curvy organic body a slot may be tilted (e.g. 30°). The switch/thumb image is drawn flat, so it looks wrong unless rotated to match.</p>
    <p><b>How.</b> Find the slot's orientation with <span class=kt>PCA</span> (Principal Component Analysis). Take every pixel belonging to that slot (from the mask) as a cloud of (x,y) <span class=kt>points</span>; PCA returns the direction the cloud is most stretched along — its <span class=kt>principal axis</span> — and the angle of that axis is the tilt. We rotate the placed part by it. <b>The bug we fixed:</b> that slot's colour appears in THREE places in the mask (the slot itself + the two strip cells at the bottom of the sheet). Feeding all of them to PCA smears the cloud between top and bottom and yields a nonsense 48°. Restricting to the <b>device-region pixels only</b> (top of the image, excluding the strip band) gives the real angle.</p>
    <p class=kt-defs><b>PCA</b> = finds the axis a point-cloud varies most along · <b>principal axis / eigenvector</b> = that direction · <b>point cloud</b> = a set of (x,y) locations.</p></div>

  <div class=ex><h4>5 · Templated vs templateless</h4>
    <svg viewBox="0 0 300 84"><rect width="300" height="84" fill="#0d0f14"/>
      <rect x="12" y="14" width="126" height="56" rx="8" fill="#12161d" stroke="#3a4a63"/><text x="75" y="10" fill="#9ab" font-size="10" text-anchor="middle">TEMPLATED</text>
      <circle cx="42" cy="38" r="8" fill="none" stroke="#f5a"/><circle cx="72" cy="38" r="8" fill="none" stroke="#5af"/><circle cx="102" cy="38" r="8" fill="none" stroke="#fd5"/><text x="75" y="62" fill="#789" font-size="8" text-anchor="middle">positions locked, model styles + sculpts</text>
      <rect x="162" y="14" width="126" height="56" rx="8" fill="#12161d" stroke="#3a4a63"/><text x="225" y="10" fill="#9ab" font-size="10" text-anchor="middle">TEMPLATELESS</text>
      <text x="225" y="40" fill="#789" font-size="8" text-anchor="middle">blank canvas → model designs</text><text x="225" y="54" fill="#789" font-size="8" text-anchor="middle">→ we detect it afterwards</text></svg>
    <p><b>Two generation modes we compare.</b> <b>Templated</b>: the blueprint fixes WHERE each control sits (coloured outlines at set spots); the model must keep those positions and only restyle the surface + sculpt the bold outer housing. Reliable layout, but the model can still drift. <b>Templateless</b>: we give a nearly-blank canvas and let the model design the whole player wherever it likes; then the extractor recovers every control purely from the colour mask the model drew — <span class=kt>post-hoc detection</span>. More creative freedom, more variance. Running both lets us see which wins per theme (templateless often produced the boldest clean results).</p>
    <p class=kt-defs><b>post-hoc detection</b> = figuring out positions <em>after</em> generation, from the output, rather than dictating them up front.</p></div>

  <div class=ex><h4>6 · Auto-regen gate loop</h4>
    <svg viewBox="0 0 300 84"><rect width="300" height="84" fill="#0d0f14"/>
      <rect x="12" y="30" width="60" height="24" rx="4" fill="#1b2230" stroke="#3a4a63"/><text x="42" y="45" fill="#9ab" font-size="8" text-anchor="middle">generate+extract</text>
      <path d="M72 42 h26" stroke="#5a7" fill="none" marker-end="url(#b)"/><rect x="100" y="30" width="44" height="24" rx="4" fill="#1b2230" stroke="#3a4a63"/><text x="122" y="45" fill="#9ab" font-size="9" text-anchor="middle">GATE?</text>
      <path d="M144 42 h34" stroke="#5f7" fill="none" marker-end="url(#b)"/><rect x="178" y="30" width="54" height="24" rx="4" fill="#152" stroke="#5f7"/><text x="205" y="45" fill="#8fa" font-size="9" text-anchor="middle">keep it</text>
      <path d="M122 54 v14 h-80 v-12" stroke="#f85" fill="none" marker-end="url(#b)"/><text x="150" y="80" fill="#f96" font-size="9">FAIL → new seed (≤4×)</text>
      <defs><marker id="b" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0 0 L6 3 L0 6 z" fill="#8ab"/></marker></defs></svg>
    <p><b>Problem.</b> Image models are <span class=kt>stochastic</span> — the same prompt gives a different picture each time. One roll might install a knob where the socket should be empty, or forget a control.</p>
    <p><b>How.</b> We never trust one roll. After each generation the <span class=kt>gate</span> runs an automatic checklist: are all 10 controls found? are the sockets actually empty (no baked-in parts)? does the slider cover its groove? did we successfully cut every moving part? is any leftover guide-colour bleeding through? If <em>any</em> check fails, we change the random <span class=kt>seed</span> and generate again — up to 4 tries — keeping the first roll that passes. That's why 12/14 skins came out clean with no human babysitting each attempt.</p>
    <p class=kt-defs><b>stochastic</b> = randomised, non-repeatable · <b>seed</b> = the number that fixes the model's randomness (change it → a different image) · <b>gate</b> = an automatic accept/reject test.</p></div>
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
.walk{{background:#0e1116;border:1px solid #ffffff14;border-radius:12px;padding:14px}}
.wnav{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}}
.wstep{{background:#161a22;border:1px solid #ffffff22;color:#9ab;border-radius:8px;padding:6px 12px;font:12px ui-monospace,monospace;cursor:pointer}}
.wstep.on{{background:#1b3a5c;border-color:#3a7cff88;color:#cfe6ff}}
.wbody img{{width:100%;height:auto;border-radius:8px;border:1px solid #ffffff14;background:#000}}
.wcap h4{{margin:10px 0 4px;font-size:15px}}.wcap p{{margin:0;color:#9ab;font-size:13.5px;max-width:90ch}}
@media (prefers-color-scheme:light){{body{{background:#f6f7f9;color:#1a1d22}}.card,.ex,.stat,.hnotes,.htoggle{{background:#fff;border-color:#00000018}}.bar{{background:#f6f7f9ee}}}}
</style></head><body>
<h1>gen12 — human review</h1>
<div class=sub>auto-gate {npass}/{n} · set YOUR pass/fail per skin, note what's wrong; verdicts autosave. Live players are embedded — drag knobs/seek, click buttons.</div>
<div class=sub>{cost_line}</div>
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
