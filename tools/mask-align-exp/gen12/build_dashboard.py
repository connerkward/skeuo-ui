#!/usr/bin/env python3
"""build_dashboard — the gen12 oversight + HUMAN-REVIEW dashboard. Per skin: the LIVE interactive
player hoisted to the top, a human PASS/FAIL gate toggle, and a "what's wrong" notes box — all
persisted in localStorage with an export so verdicts can be read back. Below that: the auto-gate
verdict, the process strip (blueprint→paint→mask→overlay), and explainer diagrams.
Usage: python3 build_dashboard.py"""
import os, json, glob, re, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
# run-id annotation (max rolls): read the real default out of orchestrate12.py rather than
# duplicating the number here, so if that default ever changes this label doesn't silently drift.
try:
    _orch_src = open(os.path.join(HERE, "orchestrate12.py")).read()
    _m = re.search(r"len\(sys\.argv\)\s*>\s*2\s*else\s*(\d+)", _orch_src)
    ROLLS_MAX = int(_m.group(1)) if _m else 4
except Exception:
    ROLLS_MAX = 4
skins = []
for d in sorted(glob.glob(os.path.join(HERE, "assets-*"))):
    # only the real theme roster directly under gen12/ — exclude sidecar dirs
    # (_biref/_pbr suffixed passes) and any experiment subtree (abshape/, bproof/)
    if d.endswith("_biref") or d.endswith("_pbr"): continue
    if "/abshape/" in d or "/bproof/" in d: continue
    sid = os.path.basename(d).replace("assets-", "")
    orch = res = reg = dr = {}
    for fn, tgt in [("orch.json", "orch"), ("results.json", "res"), ("regions.json", "reg"),
                    ("director-review.json", "dr")]:
        try:
            v = json.load(open(os.path.join(d, fn)))
            if tgt == "orch": orch = v
            elif tgt == "res": res = v
            elif tgt == "reg": reg = v
            else: dr = v
        except Exception: pass
    gate = reg.get("gate", {})
    # PBR card link gate: player-pbr.html + its _pbr/meta.json exist. Previously required a
    # non-empty emissive extraction (meta.json emissiveCoverage>0 / lights present), because a
    # zero-glow build would advertise "dynamic lighting" with no lighting effect. That's now
    # moot — build_player_pbr.py's EMISSIVE_ENABLED=False (user verdict 2026-07-10: baked
    # emissive glowed nonsensically) means the shipped PBR player is relight-only (pointer
    # light + patina normal/roughness/metalness + specular + glass), which doesn't depend on
    # the emissive extraction succeeding at all — gating the link on it was checking the wrong
    # thing. The existence of the built player + its meta.json is the real precondition.
    pbr = (os.path.exists(os.path.join(d, "player-pbr.html"))
           and os.path.exists(os.path.join(HERE, f"assets-{sid}_pbr", "meta.json")))
    # run-id annotation: which generation is this card CURRENTLY showing? seed+roll come from
    # orch.json; "painted" is paint.png's own mtime (not orch.json's) so a manual re-roll or an
    # agent mid-regen that overwrote paint.png but hasn't re-run the orchestrator yet is visible
    # as a mismatch, not silently absorbed into the last-known-good orch.json numbers.
    paint_path = os.path.join(d, "paint.png")
    orch_path = os.path.join(d, "orch.json")
    paint_mtime = os.path.getmtime(paint_path) if os.path.exists(paint_path) else None
    orch_mtime = os.path.getmtime(orch_path) if os.path.exists(orch_path) else None
    painted_str = (datetime.datetime.fromtimestamp(paint_mtime).strftime("%Y-%m-%d %H:%M")
                   if paint_mtime else "?")
    # >2s margin so ordinary same-second write ordering from the pipeline itself doesn't false-flag
    mid_regen = paint_mtime is not None and orch_mtime is not None and paint_mtime > orch_mtime + 2
    skins.append({"id": sid, "title": res.get("title", orch.get("title", sid)),
                  "mode": res.get("mode", "?"), "passed": orch.get("passed", gate.get("PASS")),
                  "rolls": orch.get("rolls", "?"), "seed": orch.get("final_seed", res.get("seed", "?")),
                  "gate": gate, "leak": res.get("leak"), "pbr": pbr,
                  "painted": painted_str, "mid_regen": mid_regen, "dr": dr,
                  "reasons": (orch.get("gate") or {}).get("reasons") or gate.get("reasons") or []})
npass = sum(1 for s in skins if s["passed"]); n = len(skins)
# cost annotation (dev-facing-model-cost-annotation-rule): sum rolls × per-roll model spend
total_rolls = sum(s["rolls"] for s in skins if isinstance(s["rolls"], int))
GEN_MODEL = "fal-ai/gemini-3-pro-image-preview/edit"; MATTE_MODEL = "fal-ai/birefnet/v2"
n_dr = sum(1 for s in skins if s.get("dr"))
DR_MODEL = "vertex:gemini-3.1-pro-preview"
cost_lo = total_rolls * (0.15 + 0.005) + n_dr * 0.02; cost_hi = total_rolls * (0.15 + 0.005) * 1.15 + n_dr * 0.05
cost_line = (f"models: <b>{GEN_MODEL}</b> (paint+mask, ~$0.15/roll) + <b>{MATTE_MODEL}</b> (~$0.005/roll) + "
             f"<b>{DR_MODEL}</b> (director review, ~$0.02-0.05/skin) · "
             f"extraction/player = local $0 · est. total ≈ <b>${cost_lo:.2f}-${cost_hi:.2f}</b> "
             f"({total_rolls} rolls × ~$0.155 + {n_dr} director reviews)")


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
    pbr_link = (f' · <a class=pbrlink href="assets-{sid}/player-pbr.html" target=_blank>'
                f'&#10024; dynamic lighting</a>') if s.get("pbr") else ''
    dr = s.get("dr") or {}
    dr_line = ''
    if dr:
        dv = dr.get("verdict", "?"); dscore = dr.get("score_0_10", "?")
        drcls = "pass" if dv == "PASS" else "fail"
        dr_notes = "; ".join(dr.get("notes") or [])[:220]
        dr_line = (f'<br><span class=auto>director ({dr.get("model","?")}, '
                    f'~${dr.get("cost_estimate_usd","?")}): '
                    f'<span class="{drcls}">{dv} {dscore}/10</span> '
                    f'<span class=rz>{dr_notes}</span></span>')
    # run-id line: fixed spot so two dashboard visits (before/after another agent regenerates
    # this skin) are comparable at a glance — same identity fields, same position, every card.
    midflag = (' <span class=midregen title="paint.png mtime is newer than orch.json — this card '
               'may be showing a mid-regeneration or a manual roll not yet aggregated into orch.json">'
               '&#9888; paint newer than orch — mid-regen/unaggregated</span>') if s.get("mid_regen") else ''
    runid = (f'<div class=runid>gen12 · seed {s["seed"]} · roll {s["rolls"]}/{ROLLS_MAX} · '
             f'painted {s["painted"]}{midflag}</div>')
    return f'''<section class=card id="c-{sid}" data-id="{sid}">
  <div class=chead><h3>{s["title"]} <span class=mode>{s["mode"]}</span>{pbr_link}</h3>
    <div class=hverdict><span class=hlabel>your gate:</span>
      <button class="htoggle" data-id="{sid}">— unset —</button></div></div>
  {runid}
  <div class=live><iframe src="assets-{sid}/player.html" loading=lazy title="{sid} player"></iframe>
    <div class=side>
      <textarea class=hnotes data-id="{sid}" placeholder="what's wrong with this skin? (autosaves)"></textarea>
      <div class=auto>{autob} · <span class=det>{det}</span><br><span class=rz>{reasons}</span>{dr_line}</div>
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
<h2>Live algorithm animations <span class=alive>LIVE</span> — real pixels, real math</h2>
<p class=animsub>All four panels re-run extract12.py's actual algorithms in-browser on real batch artifacts
(paint+mask by <b>fal-ai/gemini-3-pro-image-preview/edit</b>, matte/cuts by <b>fal-ai/birefnet/v2</b> — already paid for above; animation compute = local $0).</p>
<div class=animctl id=animctl><span>speed</span>
  <button data-sp=0.25>0.25×</button><button data-sp=0.5>0.5×</button><button data-sp=1 class=on>1×</button><button data-sp=2>2×</button><button data-sp=4>4×</button>
  <button id=anim-pause>⏸ pause</button></div>
<div class=animgrid>
  <div class=anim><h4>Matte-hole knob seat — gradient circle-fit → centroid snap <span class=askin>steam-porthole · vol</span><button class=arst data-anim=anim-knob title="restart animation">⟲</button></h4>
    <canvas id=anim-knob></canvas><div class=acap id=anim-knob-cap>loading…</div></div>
  <div class=anim><h4>Coverage-span seek travel — level-aware walk → thumb travel <span class=askin>wc-goldshield · seek</span><button class=arst data-anim=anim-travel title="restart animation">⟲</button></h4>
    <canvas id=anim-travel></canvas><div class=acap id=anim-travel-cap>loading…</div></div>
  <div class=anim><h4>Slot rotation — device-only PCA axis + elongation gate <span class=askin>n64-cutscene · shuffle</span><button class=arst data-anim=anim-pca title="restart animation">⟲</button></h4>
    <canvas id=anim-pca></canvas><div class=acap id=anim-pca-cap>loading…</div></div>
  <div class=anim><h4>Switch state registration — silhouette-IoU (dx,dy) search <span class=askin>steam-porthole · shuffle</span><button class=arst data-anim=anim-iou title="restart animation">⟲</button></h4>
    <canvas id=anim-iou></canvas><div class=acap id=anim-iou-cap>loading…</div></div>
</div>
<script src=explainer_anim.js></script>
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
    <p><b>Problem.</b> The thumb must slide the whole length of the groove. The mask's rough rectangle is usually a little short — and many slots are <em>stepped</em>: a near-black channel sits inside a lighter recessed trough, so a fixed "dark = slot" threshold stops at the channel's end instead of the slot's real end.</p>
    <p><b>How (level-aware).</b> The mask cell — the model's own declaration of the slot — is the base span; we never walk inside it (a baked-in handle can't derail anything). From <b>each cell edge we walk outward</b> comparing every pixel column against the <b>local body level</b>, measured from the flanking material just outside that end: keep going while columns sit <em>clearly below body</em> (recessed at <b>any</b> depth — dark channel or lighter trough) or are a bright <span class=kt>bezel</span> rim; <b>stop</b> on a short sustained run at body level, a long bright run, or the known backdrop <em>colour</em>. The result — cell plus walked end caps, clamped to ±12% of the cell — is the thumb's <b>travel range</b>.</p>
    <p class=kt-defs><b>luminance</b> = perceived brightness · <b>recess</b> = the sunken channel · <b>bezel</b> = the raised rim around a slot · <b>body level</b> = the surrounding material's typical brightness, estimated per side.</p></div>

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

  <div class=ex><h4>5b · Material-aware silhouette press</h4>
    <svg viewBox="0 0 320 96"><rect width="320" height="96" fill="#0d0f14"/>
      <!-- 1: silhouette clipped from the mask -->
      <path d="M28 38 C26 26 40 18 54 20 C70 16 82 24 80 36 C84 48 72 58 56 56 C42 60 30 52 28 38 Z"
            fill="#1b2230" stroke="#5af"/>
      <text x="54" y="74" fill="#5af" font-size="8" text-anchor="middle">silhouette clip</text>
      <text x="54" y="84" fill="#789" font-size="8" text-anchor="middle">from mask</text>
      <!-- 2: same silhouette, own pixels shifted down + darkened -->
      <g transform="translate(90 0)">
        <path d="M28 38 C26 26 40 18 54 20 C70 16 82 24 80 36 C84 48 72 58 56 56 C42 60 30 52 28 38 Z"
              fill="none" stroke="#3a4a63" stroke-dasharray="3 2"/>
        <path d="M28 41 C26 29 40 21 54 23 C70 19 82 27 80 39 C84 51 72 61 56 59 C42 63 30 55 28 41 Z"
              fill="#141922" stroke="#8ab"/>
        <text x="54" y="74" fill="#9ab" font-size="8" text-anchor="middle">own pixels,</text>
        <text x="54" y="84" fill="#789" font-size="8" text-anchor="middle">shifted + −15% luminance</text>
      </g>
      <!-- 3: re-shade — top inner shadow + bottom catch-light -->
      <g transform="translate(180 0)">
        <path d="M28 41 C26 29 40 21 54 23 C70 19 82 27 80 39 C84 51 72 61 56 59 C42 63 30 55 28 41 Z"
              fill="#141922" stroke="#3a4a63"/>
        <path d="M30 34 C32 25 42 20 54 22 C66 19 76 24 79 32" fill="none" stroke="#000" stroke-width="4" opacity="0.55" stroke-linecap="round"/>
        <path d="M33 52 C42 59 66 60 76 51" fill="none" stroke="#cfe6ff" stroke-width="2" opacity="0.8" stroke-linecap="round"/>
        <text x="54" y="74" fill="#cdd3dd" font-size="8" text-anchor="middle">top shadow /</text>
        <text x="54" y="84" fill="#789" font-size="8" text-anchor="middle">bottom catch-light</text>
      </g>
      <path d="M82 40 h6" stroke="#5a7" marker-end="url(#p5b)"/><path d="M172 40 h6" stroke="#5a7" marker-end="url(#p5b)"/>
      <defs><marker id="p5b" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0 0 L6 3 L0 6 z" fill="#8ab"/></marker></defs></svg>
    <p><b>Problem.</b> A dark gradient blob over a pressed button looks fake: wrong shape, too dark on glass, invisible on stone.</p>
    <p><b>How.</b> The pressed state is built from the button's <span class=kt>own pixels</span>: its exact <span class=kt>silhouette</span> is cut from the colour mask and used to clip a copy of the paint that is shifted down ~3% (physical travel), darkened in proportion to the material's measured luminance (subtle on light glass, stronger on dark stone), and re-shaded the way real light flips when a part sinks — a shape-following inner shadow on the top edge, a faint catch-light on the bottom edge. No black wash; glass stays glassy, stone stays stone.</p>
    <p class=kt-defs><b>silhouette clip</b> = restrict drawing to the exact blob shape · <b>catch-light</b> = the thin bright edge where a sunken surface still faces the light.</p></div>
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
.pbrlink{{font:11px ui-monospace,monospace;color:#ffcf7a;text-decoration:none;border:1px solid #ffcf7a44;border-radius:5px;padding:1px 7px}}.pbrlink:hover{{border-color:#ffcf7a;background:#ffcf7a1a}}
.runid{{font:11px ui-monospace,monospace;color:#7a8090;margin:-4px 0 12px}}
.midregen{{color:#0a0604;background:#ffb454;border-radius:4px;padding:1px 6px;font-weight:700;margin-left:6px}}
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
.animgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}}
.anim{{background:#0e1116;border:1px solid #ffffff14;border-radius:10px;padding:12px;min-width:0}}
.anim h4{{margin:0 0 8px;font-size:13px}}
.anim canvas{{width:100%;height:auto;border-radius:8px;background:#000;border:1px solid #ffffff14;display:block}}
.acap{{font:11px ui-monospace,monospace;color:#8a90a0;margin-top:7px;min-height:42px;line-height:1.45}}
.animsub{{font:12px ui-monospace,monospace;color:#8a90a0;margin:0 0 10px}}
.askin{{font:11px ui-monospace,monospace;color:#8a90a0;border:1px solid #ffffff20;border-radius:5px;padding:1px 6px;margin-left:6px;font-weight:400}}
.alive{{color:#041;background:#6f9;border-radius:4px;padding:1px 7px;font:700 11px ui-monospace,monospace;vertical-align:2px;animation:alive-blink 1.6s ease-in-out infinite}}
.animctl{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 12px;font:11px ui-monospace,monospace;color:#8a90a0}}
.animctl button{{background:#161a22;border:1px solid #ffffff22;color:#cdd3dd;border-radius:5px;font:11px ui-monospace,monospace;padding:2px 9px;cursor:pointer}}
.animctl button:hover{{border-color:#6f9}}
.animctl button.on{{background:#6f9;color:#041;border-color:#6f9;font-weight:700}}
.arst{{float:right;background:#161a22;border:1px solid #ffffff22;color:#cdd3dd;border-radius:5px;font:12px ui-monospace,monospace;padding:0 7px;cursor:pointer;line-height:18px}}
.arst:hover{{border-color:#6f9;color:#6f9}}
@keyframes alive-blink{{50%{{opacity:.45}}}}
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
