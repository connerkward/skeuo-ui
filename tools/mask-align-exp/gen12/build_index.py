#!/usr/bin/env python3
"""build_index — the canonical, queryable INDEX of every skin the gen12 pipeline has ever
generated. Scans assets-* the same way build_dashboard.py does, adds a few derived fields
(baked_slider detection, human verdict binding, status), and writes:
  - skins-index.json  (the derived source-of-truth manifest; JSON, git-diffable, regenerable)
  - skins-gallery.html (a responsive filterable gallery rendered FROM the index)

This exists so "sweep the roster to find skins with X defect" is NEVER a manual grep-and-look
task again — every future generation re-runs this (wired into orchestrate12.py) and the
gallery's filters answer it instantly. See tools/mask-align-exp/gen12/placement-invariants-rule
etc. for why baked-slider detection must be computed, not hand-swept.

Usage: python3 build_index.py
"""
import os, json, glob, re, datetime, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))


def jload(path, default=None):
    try:
        return json.load(open(path))
    except Exception:
        return default if default is not None else {}


def rel(path):
    """repo-relative path from gen12/ (the served root), or None if it doesn't exist."""
    return os.path.relpath(path, HERE) if os.path.exists(path) else None


# ---------------------------------------------------------------------------
# human-labeled verdict store: pick the most-recently-modified review*.json
# (review.json is the live /save target from review_server.py; review-YYYY-MM-DD*.json
# are dated snapshots). Never the "-archived" ones. We only READ this — never mutate it,
# per human-labeled-data-rule; it is the authoritative human-judgment store.
review_candidates = [f for f in glob.glob(os.path.join(HERE, "review*.json"))
                      if "-archived" not in os.path.basename(f)]
review_source = max(review_candidates, key=os.path.getmtime) if review_candidates else None
HUMAN = jload(review_source, {}) if review_source else {}
review_source_rel = os.path.basename(review_source) if review_source else None

# bad-examples manifest — may not exist yet (another agent may be creating it concurrently).
# Defensive loader: try dict-keyed-by-id and list-of-objects shapes.
BAD_EXAMPLES = {}
bad_ex_path = os.path.join(HERE, "bad-examples-manifest.json")
bad_ex_source = None
if os.path.exists(bad_ex_path):
    bad_ex_source = "bad-examples-manifest.json"
    raw = jload(bad_ex_path, {})
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(v, dict):
                BAD_EXAMPLES[k] = v.get("drive_link") or v.get("driveLink") or v.get("url")
            else:
                BAD_EXAMPLES[k] = v
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("id"):
                BAD_EXAMPLES[item["id"]] = (item.get("drive_link") or item.get("driveLink")
                                             or item.get("url"))

GEN_MODEL = "fal-ai/gemini-3-pro-image-preview/edit"
MATTE_MODEL_LOCAL = "birefnet-v2 (local MPS)"
DR_MODEL = "vertex:gemini-3.1-pro-preview"


def detect_baked_slider(regions, erase_log_path, human_note):
    """baked_slider is the field the old manual sweep existed to answer: does this skin
    have (or has it ever had, per the erase-repair log) a baked-in slider/knob thumb that
    should be an empty socket? Three independent signals, any one is sufficient evidence:
      1. regions.json's live gate.baked_thumb (extract12.py's own detector)
      2. an erase12-log.json record (erase12.py only logs when it found+attempted a repair)
      3. the human reviewer's own note literally saying "baked" (their judgment overrides
         a detector miss — this is exactly why claymation/steam-porthole show baked_slider
         true here even though the CURRENT regions.json gate doesn't flag them: the human
         saw it on the rendered player, which is the ground truth per skin-observation-rule)
    """
    evidence = []
    gate = (regions or {}).get("gate", {})
    baked_thumb = gate.get("baked_thumb") or []
    if baked_thumb:
        evidence.append(f"gate.baked_thumb={baked_thumb}")
    log = jload(erase_log_path, None)
    if log:
        controls = sorted({e.get("control") for e in log if e.get("control")})
        if controls:
            evidence.append(f"erase12-log:{','.join(controls)}")
    if human_note and "baked" in human_note.lower():
        evidence.append("human-note-mentions-baked")
    return (len(evidence) > 0), evidence


def cost_estimate(orch, dr):
    rolls = orch.get("rolls")
    rolls = rolls if isinstance(rolls, int) else 1
    lo = rolls * (0.15 + 0.005)
    hi = rolls * (0.15 + 0.005) * 1.15
    dr_lo = dr_hi = 0.0
    if dr:
        est = str(dr.get("cost_estimate_usd") or "")
        m = re.match(r"([\d.]+)\s*-\s*([\d.]+)", est)
        if m:
            dr_lo, dr_hi = float(m.group(1)), float(m.group(2))
    return round(lo + dr_lo, 3), round(hi + dr_hi, 3), rolls


skins = []
for d in sorted(glob.glob(os.path.join(HERE, "assets-*"))):
    base = os.path.basename(d)
    if base.endswith("_biref") or base.endswith("_pbr"):
        continue
    if not os.path.isdir(d):
        continue
    sid = base.replace("assets-", "", 1)
    orch = jload(os.path.join(d, "orch.json"))
    results = jload(os.path.join(d, "results.json"))
    regions = jload(os.path.join(d, "regions.json"))
    dr = jload(os.path.join(d, "director-review.json"), None)

    theme = re.sub(r"-toggletrack\d+$", "", sid)
    mode = results.get("mode") or orch.get("mode") or "?"
    seed = orch.get("final_seed", results.get("seed", "?"))
    model = results.get("model", GEN_MODEL)

    paint_path = os.path.join(d, "paint.png")
    paint_mtime = os.path.getmtime(paint_path) if os.path.exists(paint_path) else None
    paint_iso = (datetime.datetime.fromtimestamp(paint_mtime).isoformat(timespec="seconds")
                 if paint_mtime else None)
    paint_sha = (hashlib.sha256(open(paint_path, "rb").read()).hexdigest()[:12]
                 if os.path.exists(paint_path) else None)

    biref_dir = os.path.join(HERE, f"assets-{sid}_biref")
    paths = {
        "paint": rel(paint_path),
        "mask": rel(os.path.join(d, "mask.png")),
        "regions": rel(os.path.join(d, "regions.json")),
        "player": rel(os.path.join(d, "player.html")),
        "player_pbr": rel(os.path.join(d, "player-pbr.html")),
        "joint4k": rel(os.path.join(d, "joint-4k.png")),
        "blueprint": rel(os.path.join(d, "blueprint.png")),
        "overlay": rel(os.path.join(d, "overlay.png")),
        "biref_device": rel(os.path.join(biref_dir, "device.png")),
        "orch": rel(os.path.join(d, "orch.json")),
        "results": rel(os.path.join(d, "results.json")),
        "director_review": rel(os.path.join(d, "director-review.json")),
    }
    paths = {k: v for k, v in paths.items() if v}

    # subcomponent crops for the gallery's per-control breakdown: prefer director/ (final,
    # theme-graded crops) then observe/ (geometry/defect crops) then raw biref cut sprites.
    crop_dir = None
    for cand in ("director", "observe"):
        p = os.path.join(d, cand)
        if os.path.isdir(p) and glob.glob(os.path.join(p, "crop-*.png")):
            crop_dir = cand
            break
    crops = []
    if crop_dir:
        for f in sorted(glob.glob(os.path.join(d, crop_dir, "crop-*.png"))):
            name = os.path.basename(f)[len("crop-"):-len(".png")]
            if name.endswith("-after"):
                continue  # after-shots are secondary; keep the primary crop only
            crops.append({"control": name, "path": rel(f)})
    elif os.path.isdir(biref_dir):
        for f in sorted(glob.glob(os.path.join(biref_dir, "*.png"))):
            name = os.path.basename(f)[:-4]
            if name in ("global-matte",):
                continue
            crops.append({"control": name, "path": rel(f)})

    orch_gate = orch.get("gate") or {}
    live_gate = regions.get("gate") or {}
    orch_pass = orch.get("passed")
    live_pass = live_gate.get("PASS")
    auto_pass = live_pass if live_pass is not None else orch_pass
    reasons = live_gate.get("reasons") or orch_gate.get("reasons") or []

    hv = HUMAN.get(sid, {})
    human_verdict = hv.get("gate") if hv.get("gate") in ("pass", "fail") else None
    human_note = hv.get("notes") or None

    baked, baked_evidence = detect_baked_slider(
        regions, os.path.join(d, "erase12-log.json"), human_note)

    cost_lo, cost_hi, rolls = cost_estimate(orch, dr)

    if sid in BAD_EXAMPLES:
        status = "bad-example"
    elif human_verdict == "pass":
        status = "pass"
    elif human_verdict == "fail":
        status = "fail"
    else:
        status = "ungraded"

    skins.append({
        "id": sid,
        "theme": theme,
        "mode": mode,
        "seed": seed,
        "model": model,
        "director_model": (dr or {}).get("model"),
        "paths": paths,
        "crops": crops,
        "paint_mtime": paint_iso,
        "paint_sha": paint_sha,
        "gate_results": {
            "auto_pass": auto_pass,
            "orch_passed": orch_pass,
            "live_pass": live_pass,
            "reasons": reasons,
            "orch_gate": orch_gate or None,
            "live_gate": live_gate or None,
            "director_verdict": (dr or {}).get("verdict"),
            "director_score_0_10": (dr or {}).get("score_0_10"),
        },
        "baked_slider": baked,
        "baked_slider_evidence": baked_evidence,
        "human_verdict": human_verdict,
        "human_note": human_note,
        "status": status,
        "bad_example_drive_link": BAD_EXAMPLES.get(sid),
        "rolls": rolls,
        "cost_estimate_usd": [cost_lo, cost_hi],
    })

n = len(skins)
n_pass = sum(1 for s in skins if s["status"] == "pass")
n_fail = sum(1 for s in skins if s["status"] == "fail")
n_ungraded = sum(1 for s in skins if s["status"] == "ungraded")
n_bad = sum(1 for s in skins if s["status"] == "bad-example")
n_baked = sum(1 for s in skins if s["baked_slider"])
total_cost_lo = round(sum(s["cost_estimate_usd"][0] for s in skins), 2)
total_cost_hi = round(sum(s["cost_estimate_usd"][1] for s in skins), 2)
themes = sorted({s["theme"] for s in skins})
modes = sorted({s["mode"] for s in skins if s["mode"] != "?"})

index = {
    "schema_version": 1,
    "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
    "review_source": review_source_rel,
    "bad_examples_source": bad_ex_source,
    "counts": {"total": n, "pass": n_pass, "fail": n_fail, "ungraded": n_ungraded,
               "bad_example": n_bad, "baked_slider": n_baked},
    "cost_estimate_usd": [total_cost_lo, total_cost_hi],
    "models": {"generation": GEN_MODEL, "matte": MATTE_MODEL_LOCAL, "director": DR_MODEL},
    "themes": themes,
    "modes": modes,
    "skins": skins,
}
json.dump(index, open(os.path.join(HERE, "skins-index.json"), "w"), indent=2)
print(f"[build_index] {n} skins indexed -> skins-index.json "
      f"(pass {n_pass} · fail {n_fail} · ungraded {n_ungraded} · bad-example {n_bad} · "
      f"baked-slider {n_baked}) · review source: {review_source_rel} · "
      f"bad-examples source: {bad_ex_source or 'none (not created yet)'}")

# ---------------------------------------------------------------------------
# GALLERY — a single self-contained HTML page rendered FROM the index above. All filtering
# happens client-side against the embedded JSON; no server templating needed beyond this
# build step (responsive-web-rule; served on the existing pinned :8899 static server).

GALLERY_HTML = f'''<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>gen12 — skin index &amp; gallery</title><style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}
body{{margin:0;background:#0a0b0e;color:#cdd3dd;font:14px/1.5 system-ui,sans-serif;padding:20px;max-width:1400px;margin:auto}}
h1{{font-size:21px;margin:0 0 4px}}
.sub{{color:#8a90a0;font:12px ui-monospace,monospace;margin:2px 0}}
a{{color:#7ab7ff;text-decoration:none}}a:hover{{text-decoration:underline}}
.bar{{position:sticky;top:0;z-index:20;background:#0a0b0eee;backdrop-filter:blur(6px);
  padding:10px 0 12px;border-bottom:1px solid #ffffff14;margin-bottom:16px;
  display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.stat{{background:#12161d;border:1px solid #ffffff14;border-radius:8px;padding:6px 12px;font:12px ui-monospace,monospace}}
.fgroup{{display:flex;gap:5px;align-items:center;flex-wrap:wrap;background:#12161d;border:1px solid #ffffff14;
  border-radius:8px;padding:5px 9px}}
.fgroup label{{font:11px ui-monospace,monospace;color:#8a90a0;margin-right:2px}}
select,.chip-btn{{background:#161a22;border:1px solid #ffffff22;color:#cdd3dd;border-radius:6px;
  padding:5px 9px;font:12px ui-monospace,monospace;cursor:pointer}}
.chip-btn.on{{background:#1b3a5c;border-color:#3a7cffaa;color:#cfe6ff}}
.chip-btn.baked.on{{background:#5c2a1b;border-color:#ff7c3aaa;color:#ffd2b0}}
#count{{font:12px ui-monospace,monospace;color:#9ab;margin-left:auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}
.card{{background:#0e1116;border:1px solid #ffffff14;border-radius:12px;overflow:hidden;display:flex;flex-direction:column}}
.card.st-pass{{border-color:#2a6}}.card.st-fail{{border-color:#a33}}.card.st-bad-example{{border-color:#666;opacity:.55}}
.thumbwrap{{position:relative;aspect-ratio:3/4;background:#000;overflow:hidden}}
.thumbwrap img{{width:100%;height:100%;object-fit:cover;display:block}}
.badge{{position:absolute;top:7px;left:7px;font:700 10px ui-monospace,monospace;padding:2px 7px;border-radius:5px}}
.badge.pass{{background:#6f9;color:#052}}.badge.fail{{background:#f88;color:#400}}
.badge.ungraded{{background:#556;color:#dde}}.badge.bad-example{{background:#333;color:#aaa}}
.badge.baked{{position:absolute;top:7px;right:7px;background:#ff7c3a;color:#2a0e00;left:auto}}
.cbody{{padding:11px 12px;display:flex;flex-direction:column;gap:6px;flex:1}}
.ctitle{{display:flex;justify-content:space-between;align-items:baseline;gap:6px}}
.ctitle b{{font-size:14px}}
.tag{{font:10px ui-monospace,monospace;color:#8a90a0;border:1px solid #ffffff20;border-radius:5px;padding:1px 6px}}
.hnote{{font:12px ui-monospace,monospace;color:#dde;background:#0b0d12;border:1px solid #ffffff14;
  border-radius:6px;padding:6px 8px;min-height:34px}}
.hnote.empty{{color:#666;font-style:italic}}
.meta{{font:10.5px ui-monospace,monospace;color:#7a8090}}
.evid{{font:10px ui-monospace,monospace;color:#ff9;opacity:.85}}
.crops{{display:flex;gap:5px;overflow-x:auto;padding-top:3px}}
.crops img{{width:48px;height:48px;object-fit:cover;border-radius:5px;border:1px solid #ffffff1c;background:#000;flex:0 0 auto}}
.crops span{{font:9px ui-monospace,monospace;color:#666;display:block;text-align:center}}
.links{{display:flex;gap:10px;font:11px ui-monospace,monospace;margin-top:auto;padding-top:4px}}
.thumbwrap[data-player]{{cursor:pointer}}
.thumbwrap[data-player]:focus-visible{{outline:2px solid #7ab7ff;outline-offset:-2px}}
.thumbwrap.no-player{{opacity:.5;cursor:default}}
.playhint{{position:absolute;bottom:7px;left:7px;font:10px ui-monospace,monospace;
  background:#0009;color:#dde;padding:2px 7px;border-radius:5px;pointer-events:none}}
.thumbwrap[data-player]:hover .playhint{{background:#3a7cffcc;color:#fff}}
.badge.nolink{{position:absolute;bottom:7px;left:7px;background:#333;color:#999;
  font:10px ui-monospace,monospace;padding:2px 7px;border-radius:5px}}
a.playerlink{{cursor:pointer}}
.modal-overlay{{position:fixed;inset:0;background:#000c;backdrop-filter:blur(3px);display:none;
  align-items:center;justify-content:center;z-index:100;padding:14px}}
.modal-overlay.open{{display:flex}}
.modal-box{{background:#0e1116;border:1px solid #ffffff22;border-radius:12px;overflow:hidden;
  width:min(96vw,760px);height:min(94vh,880px);display:flex;flex-direction:column;box-shadow:0 20px 60px #000a}}
.modal-bar{{display:flex;justify-content:space-between;align-items:center;padding:8px 8px 8px 14px;
  border-bottom:1px solid #ffffff14;gap:10px;flex:0 0 auto}}
.modal-bar b{{font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.modal-actions{{display:flex;gap:14px;align-items:center;font:11px ui-monospace,monospace;flex:0 0 auto}}
.modal-close{{background:#1b1e26;border:1px solid #ffffff22;color:#cdd3dd;border-radius:6px;
  width:28px;height:28px;cursor:pointer;font-size:14px;line-height:1}}
.modal-close:hover{{background:#2a2f3a}}
.modal-hint{{font:10px ui-monospace,monospace;color:#6b7180;padding:4px 14px;border-bottom:1px solid #ffffff10;flex:0 0 auto}}
.modal-iframe{{flex:1;width:100%;border:0;background:#050608;display:block}}
@media (max-width:520px){{
  .modal-box{{width:100vw;height:100vh;height:100dvh;border-radius:0}}
}}
@media (prefers-color-scheme:light){{
  body{{background:#f6f7f9;color:#1a1d22}}
  .card,.stat,.fgroup,select,.chip-btn,.hnote,.modal-box{{background:#fff;border-color:#00000018}}
  .bar{{background:#f6f7f9ee}}
  .modal-overlay{{background:#000000aa}}
  .modal-iframe{{background:#fff}}
}}
</style></head><body>
<h1>gen12 — skin index &amp; gallery</h1>
<div class=sub id=genline></div>
<div class=sub>models: <b>{GEN_MODEL}</b> (paint+mask) · <b>{MATTE_MODEL_LOCAL}</b> (matte, $0) · <b>{DR_MODEL}</b> (director review) ·
  extraction/player = local $0 · est. total spend across indexed skins ≈ <b>${total_cost_lo:.2f}-${total_cost_hi:.2f}</b></div>
<div class=sub>click any thumbnail to open its LIVE player inline — drag the seek/knob, flip switches, press buttons — right here in the gallery.</div>
<div class=bar>
  <span class=stat id=statline></span>
  <div class=fgroup><label>status</label>
    <button class="chip-btn on" data-status="">all</button>
    <button class="chip-btn" data-status="pass">pass</button>
    <button class="chip-btn" data-status="fail">fail</button>
    <button class="chip-btn" data-status="ungraded">ungraded</button>
    <button class="chip-btn" data-status="bad-example">bad-example</button>
  </div>
  <div class=fgroup><label>theme</label><select id=fTheme><option value="">all</option></select></div>
  <div class=fgroup><label>mode</label><select id=fMode><option value="">all</option></select></div>
  <div class=fgroup><button class="chip-btn baked" id=fBaked>🍞 baked slider only</button></div>
  <span id=count></span>
</div>
<div class=grid id=grid></div>
<div class=modal-overlay id=modalOverlay>
  <div class=modal-box role=dialog aria-modal=true aria-labelledby=modalTitle>
    <div class=modal-bar>
      <b id=modalTitle>—</b>
      <div class=modal-actions>
        <a id=modalOpenNew href="#" target=_blank rel=noopener>open in new tab ↗</a>
        <button class=modal-close id=modalClose aria-label="Close live player" title="Close (Esc)">✕</button>
      </div>
    </div>
    <div class=modal-hint>interactive — drag the seek/knob, flip the switch, click the buttons</div>
    <iframe class=modal-iframe id=modalFrame title="live interactive player" loading=lazy></iframe>
  </div>
</div>
<script id=skins-data type=application/json>{{DATA_JSON}}</script>
<script>
const IDX = JSON.parse(document.getElementById('skins-data').textContent);
document.getElementById('genline').textContent =
  'generated ' + IDX.generated_at + ' · review source: ' + (IDX.review_source||'none') +
  ' · bad-examples source: ' + (IDX.bad_examples_source||'none (not created yet)');
document.getElementById('statline').textContent =
  IDX.counts.total+' skins · '+IDX.counts.pass+' pass · '+IDX.counts.fail+' fail · '+
  IDX.counts.ungraded+' ungraded · '+IDX.counts.bad_example+' bad-example · '+
  IDX.counts.baked_slider+' baked-slider';
const fThemeSel = document.getElementById('fTheme'), fModeSel = document.getElementById('fMode');
IDX.themes.forEach(t=>{{const o=document.createElement('option');o.value=t;o.textContent=t;fThemeSel.appendChild(o);}});
IDX.modes.forEach(m=>{{const o=document.createElement('option');o.value=m;o.textContent=m;fModeSel.appendChild(o);}});

let state = {{status:'', theme:'', mode:'', baked:false}};

function esc(s){{ return (s==null?'':String(s)).replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c])); }}

function card(s){{
  const thumb = s.paths.paint || s.paths.blueprint || '';
  const link = s.paths.player || '';
  const hasPlayer = !!link;
  const note = s.human_note ? esc(s.human_note) : 'no human note yet';
  const bakedBadge = s.baked_slider ? `<span class="badge baked" title="${{esc((s.baked_slider_evidence||[]).join(' · '))}}">baked slider</span>` : '';
  const evid = (s.baked_slider_evidence||[]).length ? `<div class=evid>baked evidence: ${{esc(s.baked_slider_evidence.join(' · '))}}</div>` : '';
  const crops = (s.crops||[]).slice(0,10).map(c=>
    `<div><img src="${{esc(c.path)}}" loading=lazy title="${{esc(c.control)}}"><span>${{esc(c.control)}}</span></div>`).join('');
  const dr = s.gate_results.director_verdict ? ` · director ${{esc(s.gate_results.director_verdict)}} ${{esc(s.gate_results.director_score_0_10)}}/10` : '';
  const cost = '$'+s.cost_estimate_usd[0].toFixed(2)+'-'+s.cost_estimate_usd[1].toFixed(2);
  const playerAttrs = hasPlayer
    ? `data-player="${{esc(link)}}" data-title="${{esc(s.id)}}" tabindex="0" role="button" aria-label="Open live interactive player for ${{esc(s.id)}}"`
    : '';
  return `<div class="card st-${{s.status}}" data-status="${{s.status}}" data-theme="${{esc(s.theme)}}" data-mode="${{esc(s.mode)}}" data-baked="${{s.baked_slider}}">
    <div class="thumbwrap${{hasPlayer?'':' no-player'}}" ${{playerAttrs}}>
      ${{thumb?`<img src="${{esc(thumb)}}" loading=lazy>`:''}}
      <span class="badge ${{s.status}}">${{esc(s.status)}}</span>
      ${{bakedBadge}}
      ${{hasPlayer?'<span class=playhint>&#9654; open live player</span>':'<span class="badge nolink">no player</span>'}}
    </div>
    <div class=cbody>
      <div class=ctitle><b>${{esc(s.id)}}</b><span class=tag>${{esc(s.mode)}}</span></div>
      <div class=meta>theme ${{esc(s.theme)}} · seed ${{esc(s.seed)}} · model ${{esc(s.model)}} · ${{s.rolls}} roll(s) · ~${{cost}}${{dr}}</div>
      <div class="hnote ${{s.human_note?'':'empty'}}">${{note}}</div>
      ${{evid}}
      ${{crops?`<div class=crops>${{crops}}</div>`:''}}
      <div class=links>
        ${{hasPlayer?`<a href="${{esc(link)}}" target=_blank class=playerlink data-player="${{esc(link)}}" data-title="${{esc(s.id)}}">live player ▶</a>`:'<span class=tag>no player</span>'}}
        ${{s.paths.regions?`<a href="${{esc(s.paths.regions)}}" target=_blank>regions.json</a>`:''}}
        ${{s.paths.orch?`<a href="${{esc(s.paths.orch)}}" target=_blank>orch.json</a>`:''}}
      </div>
    </div>
  </div>`;
}}

// ---- interactive live-player modal ------------------------------------------------
const modalOverlay = document.getElementById('modalOverlay');
const modalFrame = document.getElementById('modalFrame');
const modalTitle = document.getElementById('modalTitle');
const modalOpenNew = document.getElementById('modalOpenNew');
function openPlayer(url, title){{
  if(!url) return;
  modalTitle.textContent = title || url;
  modalOpenNew.href = url;
  modalFrame.src = url;
  modalOverlay.classList.add('open');
  document.body.style.overflow = 'hidden';
  modalClose.focus();
}}
function closePlayer(){{
  modalOverlay.classList.remove('open');
  modalFrame.src = 'about:blank';
  document.body.style.overflow = '';
}}
const modalClose = document.getElementById('modalClose');
modalClose.onclick = closePlayer;
modalOverlay.addEventListener('click', e=>{{ if(e.target===modalOverlay) closePlayer(); }});
document.addEventListener('keydown', e=>{{ if(e.key==='Escape' && modalOverlay.classList.contains('open')) closePlayer(); }});
// keydown inside the iframe doesn't bubble to this document (separate browsing context) —
// attach Esc-to-close on the embedded player's own document too, so it works while the
// user is actively interacting with the live player (same-origin: assets served from this host).
modalFrame.addEventListener('load', ()=>{{
  try {{
    const fd = modalFrame.contentDocument;
    if (fd) fd.addEventListener('keydown', e=>{{ if(e.key==='Escape') closePlayer(); }});
  }} catch(err) {{}}
}});
document.getElementById('grid').addEventListener('click', e=>{{
  const el = e.target.closest('[data-player]');
  if(!el) return;
  e.preventDefault();
  openPlayer(el.dataset.player, el.dataset.title);
}});
document.getElementById('grid').addEventListener('keydown', e=>{{
  if(e.key!=='Enter' && e.key!==' ') return;
  const el = e.target.closest && e.target.closest('.thumbwrap[data-player]');
  if(el){{ e.preventDefault(); openPlayer(el.dataset.player, el.dataset.title); }}
}});

function render(){{
  const list = IDX.skins.filter(s=>
    (!state.status || s.status===state.status) &&
    (!state.theme || s.theme===state.theme) &&
    (!state.mode || s.mode===state.mode) &&
    (!state.baked || s.baked_slider===true));
  document.getElementById('grid').innerHTML = list.map(card).join('');
  document.getElementById('count').textContent = list.length + ' / ' + IDX.skins.length + ' shown';
}}
document.querySelectorAll('.chip-btn[data-status]').forEach(b=>{{
  b.onclick=()=>{{ document.querySelectorAll('.chip-btn[data-status]').forEach(x=>x.classList.remove('on'));
    b.classList.add('on'); state.status=b.dataset.status; render(); }};
}});
document.getElementById('fBaked').onclick=(e)=>{{ state.baked=!state.baked; e.target.classList.toggle('on', state.baked); render(); }};
fThemeSel.onchange=()=>{{ state.theme=fThemeSel.value; render(); }};
fModeSel.onchange=()=>{{ state.mode=fModeSel.value; render(); }};
render();
</script>
</body></html>'''

data_json = json.dumps(index)
open(os.path.join(HERE, "skins-gallery.html"), "w").write(
    GALLERY_HTML.replace("{DATA_JSON}", data_json))
print(f"[build_index] gallery -> skins-gallery.html "
      f"(open http://localhost:8899/skins-gallery.html)")
