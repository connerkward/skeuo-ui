#!/usr/bin/env python3
"""Build .proof/grader-report.html from the last-*.json result files.

Self-contained, responsive, dark. Headline confusion matrix + per-skin
as-is vs shifted overlays. Negatives use the 0.35 shift (clean: boxes leave
the device entirely) as the primary ground-truth; the 0.18 row is shown too
to document why a small shift under-generates negatives on dense skins.
"""
import json, os, html

HERE = os.path.dirname(os.path.abspath(__file__))
PROOF = "/Users/conner/dev/skeuo-ui/.proof"
SKINS = ["a-glossy-blue-robot-spea-simple-nano-banana-2-0oyq",
         "a-small-green-frog-minimal-nano-banana-2-cr73",
         "lime-green-glossy-y2k-bu-simple-nano-banana-2-bdw7"]
NEG = "-shift0.35"   # primary (clean) negative condition


def load(sid, cond):
    return json.load(open(os.path.join(HERE, f"last-{sid}{cond}.json")))


def confusion(neg_cond):
    TP=TN=FP=FN=0; dva=0; dvt=0; unan=0; vt=0
    for sid in SKINS:
        for cond, truth in [("", True), (neg_cond, False)]:
            d = load(sid, cond)
            for r in d["controls"]:
                pred=r["aligned"]; det=r["det"]["aligned"]; vlm=r["vlm"]["aligned"]
                dvt+=1
                if det==vlm: dva+=1
                votes=r["vlm"].get("votes") or []
                if votes:
                    vt+=1
                    if len(set(votes))==1: unan+=1
                if truth and pred: TP+=1
                elif truth and not pred: FN+=1
                elif (not truth) and pred: FP+=1
                else: TN+=1
    N=TP+TN+FP+FN
    return dict(TP=TP,TN=TN,FP=FP,FN=FN,N=N,
                acc=(TP+TN)/N, prec=(TP/(TP+FP) if TP+FP else 1.0),
                rec=(TP/(TP+FN) if TP+FN else 1.0),
                agree=dva/dvt, unan=(unan/vt if vt else 0))


def img_rel(name):
    return name  # report lives in .proof; images are siblings


def control_rows(d):
    out=[]
    for r in d["controls"]:
        det=r["det"]; vlm=r["vlm"]
        cls = "ok" if r["aligned"] else "bad"
        votes = "".join("T" if v else "F" for v in (vlm.get("votes") or []))
        out.append(
            f"<tr class='{cls}'><td>{html.escape(str(r['bind']))}</td>"
            f"<td>{html.escape(str(r['kind']))}</td>"
            f"<td>{det['presence']}</td><td>{det['offset']}</td>"
            f"<td>{'Y' if det['aligned'] else 'n'}</td>"
            f"<td>{'Y' if vlm['aligned'] else 'n'}</td>"
            f"<td>{votes}</td><td>{vlm.get('confidence')}</td>"
            f"<td><b>{'aligned' if r['aligned'] else 'MIS'}</b></td></tr>"
        )
    return "\n".join(out)


def main():
    cm = confusion(NEG)
    cm18 = confusion("-shift0.18")

    skin_blocks=[]
    for sid in SKINS:
        asis = load(sid, "")
        shift = load(sid, NEG)
        asis_img = f"grade-{sid}.jpg"
        shift_img = f"grade-{sid}{NEG}.jpg"
        skin_blocks.append(f"""
        <section class="skin">
          <h3>{html.escape(sid)}</h3>
          <div class="pair">
            <figure>
              <figcaption>as-is &middot; truth = aligned &middot;
                score {asis['score']*100:.0f}% ({asis['n_aligned']}/{asis['n_total']})
                &middot; det≠vlm {asis['disagreements']}x</figcaption>
              <a href="{asis_img}"><img src="{asis_img}" loading="lazy"></a>
              <table class="ctl"><thead><tr><th>bind</th><th>kind</th><th>pres</th><th>off</th><th>det</th><th>vlm</th><th>votes</th><th>conf</th><th>combined</th></tr></thead>
              <tbody>{control_rows(asis)}</tbody></table>
            </figure>
            <figure>
              <figcaption>shift 0.35 &middot; truth = MISaligned &middot;
                score {shift['score']*100:.0f}% ({shift['n_aligned']}/{shift['n_total']})
                &middot; det≠vlm {shift['disagreements']}x</figcaption>
              <a href="{shift_img}"><img src="{shift_img}" loading="lazy"></a>
              <table class="ctl"><thead><tr><th>bind</th><th>kind</th><th>pres</th><th>off</th><th>det</th><th>vlm</th><th>votes</th><th>conf</th><th>combined</th></tr></thead>
              <tbody>{control_rows(shift)}</tbody></table>
            </figure>
          </div>
        </section>""")

    doc = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Align Grader — calibration report</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:#101015; color:#e7e7ee; font:15px/1.5 -apple-system,system-ui,Segoe UI,Roboto,sans-serif; }}
  .wrap {{ max-width: 1200px; margin: 0 auto; padding: clamp(12px,3vw,28px); }}
  h1 {{ font-size: clamp(20px,5vw,30px); margin:.2em 0; }}
  h2 {{ font-size: clamp(16px,3.5vw,22px); margin-top:1.6em; border-bottom:1px solid #2a2a36; padding-bottom:.3em; }}
  h3 {{ font-size: clamp(13px,3vw,17px); word-break: break-all; color:#9fd; }}
  .sub {{ color:#9a9aac; }}
  .headline {{ display:flex; flex-wrap:wrap; gap: clamp(8px,2vw,18px); margin:1em 0; }}
  .stat {{ flex:1 1 120px; background:#1a1a22; border:1px solid #2a2a36; border-radius:12px; padding:14px; text-align:center; }}
  .stat .v {{ font-size: clamp(22px,6vw,34px); font-weight:700; }}
  .stat .k {{ color:#9a9aac; font-size:12px; text-transform:uppercase; letter-spacing:.05em; }}
  .good {{ color:#5ee08a; }} .warn {{ color:#f0c850; }} .err {{ color:#eb6b6b; }}
  table {{ border-collapse: collapse; width:100%; font-size: clamp(11px,2.4vw,13px); }}
  .cm td, .cm th {{ border:1px solid #2a2a36; padding:8px 10px; text-align:center; }}
  .cm .lbl {{ background:#1a1a22; font-weight:600; }}
  .pair {{ display:flex; flex-wrap:wrap; gap: clamp(8px,2vw,18px); }}
  figure {{ flex:1 1 360px; margin:0; background:#16161d; border:1px solid #2a2a36; border-radius:12px; overflow:hidden; }}
  figcaption {{ padding:8px 12px; font-size:13px; color:#cfcfe0; background:#1c1c25; }}
  figure img {{ width:100%; height:auto; display:block; }}
  table.ctl {{ font-size:11px; }}
  table.ctl th, table.ctl td {{ border-bottom:1px solid #232330; padding:4px 6px; text-align:center; }}
  table.ctl tr.ok td:last-child {{ color:#5ee08a; }}
  table.ctl tr.bad td:last-child {{ color:#eb6b6b; }}
  .note {{ background:#1a1a22; border-left:3px solid #f0c850; border-radius:6px; padding:12px 14px; margin:1em 0; color:#d8d8e6; }}
  code {{ background:#222; padding:1px 5px; border-radius:4px; }}
</style></head>
<body><div class="wrap">
<h1>Button-alignment grader — calibration</h1>
<p class="sub">3 finalized skins &times; (as-is = aligned positives, shift 0.35 = misaligned negatives).
Combine rule: <b>aligned = det.aligned AND vlm.aligned</b> (either signal can veto).</p>

<h2>Accuracy (primary: clean 0.35-shift negatives)</h2>
<div class="headline">
  <div class="stat"><div class="v {'good' if cm['acc']>=0.9 else 'warn'}">{cm['acc']*100:.0f}%</div><div class="k">accuracy</div></div>
  <div class="stat"><div class="v {'good' if cm['prec']>=0.95 else 'warn'}">{cm['prec']*100:.0f}%</div><div class="k">precision</div></div>
  <div class="stat"><div class="v {'good' if cm['rec']>=0.9 else 'warn'}">{cm['rec']*100:.0f}%</div><div class="k">recall</div></div>
  <div class="stat"><div class="v">{cm['agree']*100:.0f}%</div><div class="k">det↔vlm agree</div></div>
  <div class="stat"><div class="v">{cm['unan']*100:.0f}%</div><div class="k">vlm vote unanimity</div></div>
</div>

<table class="cm"><tr><td class="lbl"></td><td class="lbl">pred aligned</td><td class="lbl">pred MIS</td></tr>
<tr><td class="lbl">truth aligned</td><td class="good">TP {cm['TP']}</td><td class="err">FN {cm['FN']}</td></tr>
<tr><td class="lbl">truth MIS</td><td class="err">FP {cm['FP']}</td><td class="good">TN {cm['TN']}</td></tr>
</table>
<p class="sub">N = {cm['N']} controls.</p>

<div class="note">
<b>Honest reading.</b> Zero false positives — the grader never passes a misaligned control.
The {cm['FN']} errors are all <b>false-negatives on truly-aligned controls</b>: 2&times; <code>stop</code>
(VLM voted 2:1 misaligned on a button det correctly accepts at presence&gt;1.8 — a VLM error the AND
rule lets veto) and 1&times; <code>seek</code> on the frog (det presence 0.31 on a low-contrast painted
slider the VLM correctly accepts 3:0 — a det error). The two halves are complementary; the AND rule is
deliberately conservative (precision over recall), so a single wrong veto costs a true positive.
We did <b>not</b> loosen the veto to chase recall, because that would re-introduce false positives —
for a grader, "never pass a bad skin" (precision 1.0) is the property worth keeping.
</div>

<div class="note">
<b>Ground-truth construction caveat.</b> A small shift (<code>--shift 0.18</code>) is an
<i>unreliable negative generator on dense skins</i>: the box slides onto a neighboring real well, so
both det and vlm correctly call it "on a control" — the negative <i>label</i> is wrong, not the grader.
With 0.18 negatives the matrix degrades to
acc {cm18['acc']*100:.0f}% / prec {cm18['prec']*100:.0f}% / rec {cm18['rec']*100:.0f}%
(4 FPs, all on the dense lime-green skin where 0.18 just shuffled boxes between wells).
The 0.35 shift pushes every box off the device onto blank body — an unambiguous negative — which is why
it is the primary calibration. This is a property of the synthetic-negative trick, not the grader.
</div>

<h2>Per-skin overlays (combined verdict: green=aligned, red=MIS)</h2>
{''.join(skin_blocks)}

<h2>How to run</h2>
<p><code>python tools/align-grader/grade.py &lt;skin-id&gt; [--shift S] [--no-vlm]</code><br>
Writes <code>.proof/grade-&lt;id&gt;[-shiftS].jpg</code> (tinted overlay + score header) and
<code>tools/align-grader/last-&lt;id&gt;.json</code>.</p>
</div></body></html>"""

    out = os.path.join(PROOF, "grader-report.html")
    with open(out, "w") as f:
        f.write(doc)
    print("wrote", out)


if __name__ == "__main__":
    main()
