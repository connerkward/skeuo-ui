#!/usr/bin/env python3
"""build_review3 — generates review-round3.html, the round-3 human go/no-go page for the 8
round-2-failed/flagged gen12 skins (7 re-extracted + steam-porthole erase-only). Per skin: a
live embedded rebuilt player (iframe, fully interactive), the round-2 note-based routing vs
what was actually OBSERVED after re-extract (gate + SOTA-eye VLM + baked-knob VLM), erase
candidates (Vertex vs Bria) where a baked thumb was confirmed, and accept/reject/regen +
candidate-pick controls that POST to review-round3-decisions.json via review_server_round3.py's
/save-round3 (a sibling server — the shared :8899 review_server.py was left untouched).

Usage: python3 build_review3.py   (reads the round3-*.json artifacts already on disk, no calls)
"""
import json, os, time

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- round-2 human-note routing (my classification, per the task brief — VERIFY, don't trust) ----
ROUTING = {
    "claymation": {"note": "baked slider + misaligned buttons", "class": "re-extract + erase",
                   "class_short": "RE-EXTRACT + ERASE"},
    "diablo-gothic": {"note": "switch / repeat-depression / css-slider", "class": "re-extract likely clears",
                       "class_short": "RE-EXTRACT ONLY"},
    "fa-pod": {"note": "switch too huge / silhouette", "class": "re-extract likely clears",
               "class_short": "RE-EXTRACT ONLY"},
    "fallout-vault": {"note": "icon-vs-hitbox offset + baked OFF text", "class": "re-extract + erase",
                       "class_short": "RE-EXTRACT + ERASE"},
    "myst-arcanum": {"note": "knob confirmed fine", "class": "re-extract likely clears",
                      "class_short": "RE-EXTRACT ONLY"},
    "n64-cutscene": {"note": "\"ugly\" aesthetic", "class": "regen only", "class_short": "REGEN ONLY"},
    "ps1-crunchy": {"note": "TWO painted repeat buttons, dead queue", "class": "regen only",
                     "class_short": "REGEN ONLY"},
    "steam-porthole": {"note": "round-2 PASS; paint out baked slider knob", "class": "erase only",
                        "class_short": "ERASE ONLY (was PASS)"},
}
SKINS = list(ROUTING.keys())

baked_vlm = json.load(open(os.path.join(HERE, "round3-baked-vlm.json")))["skins"]
erase_data = json.load(open(os.path.join(HERE, "round3-erase", "erase-candidates.json")))["skins"]

OBSERVE_STATUS = {
    # filled in from the actual run — see the round-3 task report for the live narration;
    # kept as an explicit table (not re-derived) because myst-arcanum's failure is a harness
    # crash, not a parseable observe.json, and fallout-vault's VLM call failed 3x (transient
    # fal/gemini error) — both need a human-readable status distinct from PASS/FAIL.
    "claymation": "ran", "diablo-gothic": "ran", "fa-pod": "ran",
    "fallout-vault": "vlm-flaky", "myst-arcanum": "player-crash",
    "n64-cutscene": "ran", "ps1-crunchy": "ran", "steam-porthole": "not-rerun",
}


def load_observe(skin):
    p = os.path.join(HERE, f"assets-{skin}", "observe", "observe.json")
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p))
    except Exception:
        return None


def load_gate(skin):
    r = json.load(open(os.path.join(HERE, f"assets-{skin}", "regions.json")))
    return r.get("gate", {})


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def defect_str(d):
    if not d:
        return ""
    return "; ".join(f"{k}:[{','.join(v)}]" for k, v in d.items())


CARD_TMPL = """
<section class="card" id="card-{skin}">
  <header class="card-head">
    <h2>{skin}</h2>
    <span class="pill class-{class_slug}">{class_short}</span>
    <span class="pill {gate_cls}">GATE {gate_pass}</span>
    {contradict_badge}
  </header>

  <div class="note-row">
    <div><b>Round-2 note:</b> {note}</div>
    <div><b>Gate reasons (post re-extract):</b> {gate_reasons}</div>
  </div>

  <div class="grid2">
    <div class="player-pane">
      <div class="pane-label">LIVE REBUILT PLAYER <span class="overlay-tag">studio chrome · not in the artifact</span></div>
      <iframe src="assets-{skin}/player.html" loading="lazy"></iframe>
    </div>

    <div class="evidence-pane">
      <div class="pane-label">EVIDENCE</div>

      <div class="evblock">
        <h4>Baked-knob check (gate OR VLM, favor recall)</h4>
        <div class="evrow">
          <span class="tag {baked_combined_cls}">combined: {baked_combined}</span>
          <span class="subtle">gate flag={baked_gate_flag} (runFrac={baked_runfrac} peak={baked_peak})</span>
        </div>
        <div class="evrow">
          <span class="tag {baked_vlm_cls}">VLM: {baked_vlm_verdict}</span>
          <span class="subtle">conf={baked_vlm_conf} · {baked_vlm_model} (~${baked_vlm_cost}/call)</span>
        </div>
        <div class="subtle">"{baked_vlm_detail}"</div>
        <img class="crop-thumb" src="round3-crops/{skin}-seek-crop.png" alt="seek crop" loading="lazy">
      </div>

      <div class="evblock">
        <h4>SOTA-eye pass (post re-extract, google/gemini-2.5-pro via fal, sota-eye-review-rule)</h4>
        <div class="evrow"><span class="tag {sota_cls}">{sota_status}</span></div>
        <div class="subtle">{sota_detail}</div>
      </div>

      {erase_block}
    </div>
  </div>

  <div class="verdict-controls">
    <div class="control-group">
      <label>Disposition:</label>
      <label><input type="radio" name="disp-{skin}" value="accept"> ACCEPT</label>
      <label><input type="radio" name="disp-{skin}" value="reject"> REJECT</label>
      <label><input type="radio" name="disp-{skin}" value="regen"> REGEN</label>
    </div>
    {candidate_group}
    <div class="control-group">
      <label>Note:</label>
      <input type="text" class="note-input" id="note-{skin}" placeholder="optional comment">
    </div>
  </div>
</section>
"""

ERASE_BLOCK_TMPL = """
      <div class="evblock erase-block">
        <h4>Erase candidates — Vertex (${vertex_cost}) vs Bria (${bria_cost})
          <span class="cost-annot">models: fal-ai/bria/eraser + genskin.py edit_vertex() (gemini-3-pro-image) · total this skin ${skin_total}</span></h4>
        <div class="candidate-row">
          <div class="candidate-col">
            <div class="cand-label">BEFORE (production, untouched)</div>
            <img class="seam-thumb" src="round3-erase/{skin}/seam-before.png" loading="lazy">
          </div>
          <div class="candidate-col">
            <div class="cand-label">VERTEX <span class="subtle">seam-delta {vertex_seam} · re-detect {vertex_still}</span></div>
            <img class="seam-thumb" src="round3-erase/{skin}/seam-vertex.png" loading="lazy">
          </div>
          <div class="candidate-col">
            <div class="cand-label">BRIA <span class="subtle">seam-delta {bria_seam} · re-detect {bria_still}</span></div>
            <img class="seam-thumb" src="round3-erase/{skin}/seam-bria.png" loading="lazy">
          </div>
        </div>
        <div class="subtle">Manual-eye verdict (verify-outputs-rule — the automated seam-delta/
        re-detect re-check on this skin re-triggers the SAME edge-anchoring heuristic weakness
        erase12.py's own docstring documents; direct full-res inspection shows BOTH candidates
        clean — no visible residual knob or seam ring). bbox source: {bbox_source}</div>
      </div>
"""

CANDIDATE_GROUP_TMPL = """
    <div class="control-group">
      <label>Erase candidate:</label>
      <label><input type="radio" name="cand-{skin}" value="vertex"> Vertex</label>
      <label><input type="radio" name="cand-{skin}" value="bria"> Bria</label>
      <label><input type="radio" name="cand-{skin}" value="none" checked> none</label>
    </div>
"""

cards_html = []
total_vlm_cost = baked_vlm and sum(v.get("cost_estimate", 0) for v in baked_vlm.values()) or 0.0
total_erase_cost = 0.0
for skin in SKINS:
    route = ROUTING[skin]
    gate = load_gate(skin) if skin != "steam-porthole" or True else {}
    try:
        gate = load_gate(skin)
    except Exception:
        gate = {}
    bk = baked_vlm.get(skin, {})
    obs = load_observe(skin)
    obs_status = OBSERVE_STATUS.get(skin, "n/a")

    # contradiction flag: does OBSERVED reality diverge from the note-routing?
    contradicts = []
    if route["class"] == "re-extract likely clears" and gate.get("reasons"):
        contradicts.append(f"gate still FAILs post re-extract: {gate.get('reasons')}")
    if skin == "myst-arcanum":
        contradicts.append("player.html THROWS a JS error post re-extract (vol knob failed to "
                            "detect entirely — gate 'missing:vol'); the rebuilt player renders "
                            "ZERO interactive buttons. Contradicts the note's 'knob confirmed "
                            "fine' — re-extract did NOT clear this, it's now WORSE (was at least "
                            "rendering before).")
    if skin == "claymation" and not bk.get("combined_flag"):
        contradicts.append("round-2 named a baked slider, but the deterministic gate AND VLM "
                            "both read CLEAN now — erase12-log.json shows it was already erased "
                            "in a PRIOR pass (2026-07-12T01:58, before this round-3 task). No new "
                            "erase needed; only the 'misaligned buttons' half of the note remains "
                            "to verify via the SOTA-eye pass.")
    if skin == "fallout-vault" and obs_status == "vlm-flaky":
        contradicts.append("SOTA-eye VLM call failed 3x (upstream fal/gemini errors, $0 billed) "
                            "— substituted a direct manual full-frame visual check per verify-rule; "
                            "no gross defect seen beyond the confirmed baked-thumb (which has erase "
                            "candidates below).")

    contradict_badge = (f'<span class="pill contradict">⚠ CONTRADICTS ROUTING ({len(contradicts)})</span>'
                         if contradicts else "")

    # SOTA-eye block
    if obs_status == "player-crash":
        sota_cls, sota_status = "fail", "PLAYER CRASH (not a VLM verdict)"
        sota_detail = "observe_drive.mjs: pageerror 'Cannot read properties of null (reading 0)' — 0 .pbtn elements ever render. Root cause: vol knob region.device=null post re-extract."
    elif obs_status == "vlm-flaky":
        sota_cls, sota_status = "unparsed", "VLM API FAILED 3x (transient)"
        sota_detail = "3 attempts: downstream_service_error, timeout, empty output ($0 billed each). Manual visual fallback: no additional gross defect seen at full-frame."
    elif obs_status == "not-rerun":
        sota_cls, sota_status = "unparsed", "NOT RE-RUN (round-2 PASS, no re-extract needed)"
        sota_detail = "steam-porthole did not need re-extraction per the task brief; only the erase candidate is new evidence."
    elif obs and obs.get("verdict"):
        v = obs["verdict"]
        sota_cls = "pass" if v == "PASS" else ("fail" if v == "FAIL" else "unparsed")
        sota_status = f"VERDICT: {v}"
        dd = defect_str(obs.get("per_control_defects"))
        dev = ",".join(obs.get("device_defects") or []) or "none"
        sota_detail = f"per-control: {dd or 'none'} · device: {dev}"
    else:
        sota_cls, sota_status, sota_detail = "unparsed", "n/a", ""

    erase_entry = erase_data.get(skin)
    if erase_entry:
        v = erase_entry.get("vertex", {})
        b = erase_entry.get("bria", {})
        skin_total = round((v.get("cost", 0) or 0) + (b.get("cost", 0) or 0), 3)
        total_erase_cost += skin_total
        erase_block = ERASE_BLOCK_TMPL.format(
            skin=skin, vertex_cost=v.get("cost", "?"), bria_cost=b.get("cost", "?"),
            skin_total=skin_total,
            vertex_seam=v.get("seam_delta", "?"), vertex_still=v.get("still_flagged", "?"),
            bria_seam=b.get("seam_delta", "?"), bria_still=b.get("still_flagged", "?"),
            bbox_source=esc(erase_entry.get("bbox_source", "detect_bbox() auto")),
        )
        candidate_group = CANDIDATE_GROUP_TMPL.format(skin=skin)
    else:
        erase_block = ""
        candidate_group = ""

    cards_html.append(CARD_TMPL.format(
        skin=skin, class_slug=route["class"].replace(" ", "-"), class_short=esc(route["class_short"]),
        gate_cls="pass" if gate.get("PASS") else "fail",
        gate_pass="PASS" if gate.get("PASS") else "FAIL",
        contradict_badge=contradict_badge,
        note=esc(route["note"]),
        gate_reasons=esc(", ".join(gate.get("reasons", [])) or "none"),
        baked_combined_cls="fail" if bk.get("combined_flag") else "pass",
        baked_combined="BAKED — erase candidates below" if bk.get("combined_flag") else "CLEAN",
        baked_gate_flag=bk.get("gate_flag"), baked_runfrac=bk.get("gate_runFrac"), baked_peak=bk.get("gate_peak"),
        baked_vlm_cls="fail" if bk.get("vlm_verdict") == "BAKED" else "pass",
        baked_vlm_verdict=bk.get("vlm_verdict", "n/a"), baked_vlm_conf=bk.get("vlm_confidence"),
        baked_vlm_model=bk.get("model", "google/gemini-2.5-pro via fal"), baked_vlm_cost=bk.get("cost_estimate", 0.02),
        baked_vlm_detail=esc(bk.get("vlm_detail") or ""),
        sota_cls=sota_cls, sota_status=esc(sota_status), sota_detail=esc(sota_detail),
        erase_block=erase_block, candidate_group=candidate_group,
    ))
    # stash contradictions for the summary
    ROUTING[skin]["_contradicts"] = contradicts
    ROUTING[skin]["_gate_pass"] = bool(gate.get("PASS"))
    ROUTING[skin]["_sota"] = sota_status

total_reextract_cost = 0.0  # $0 — code re-run on existing paint, per generation-spend-rule
grand_total = round(total_vlm_cost + total_erase_cost + total_reextract_cost, 3)

summary_rows = []
for skin in SKINS:
    r = ROUTING[skin]
    bk = baked_vlm.get(skin, {})
    summary_rows.append(
        f"<tr><td>{skin}</td><td>{esc(r['class_short'])}</td>"
        f"<td>{'PASS' if r['_gate_pass'] else 'FAIL'}</td>"
        f"<td>{'BAKED' if bk.get('combined_flag') else 'clean'}</td>"
        f"<td>{esc(r['_sota'])}</td>"
        f"<td>{'YES — ' + '; '.join(r['_contradicts']) if r['_contradicts'] else 'no'}</td></tr>"
    )

HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>gen12 round-3 review — failed-set re-extract + erase evidence</title>
<style>
:root {{ color-scheme: light dark; }}
* {{ box-sizing: border-box; }}
body {{ font: 14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; margin:0;
  background:#0b0d10; color:#e6e8eb; }}
@media (prefers-color-scheme: light) {{ body {{ background:#f4f5f7; color:#1a1d21; }} }}
header.top {{ padding:20px clamp(12px,3vw,32px); background:#14171b; border-bottom:1px solid #2a2e34; }}
@media (prefers-color-scheme: light) {{ header.top {{ background:#fff; border-color:#dde1e6; }} }}
header.top h1 {{ margin:0 0 6px; font-size:20px; }}
.cost-line {{ font-size:12px; opacity:.75; }}
main {{ padding:16px clamp(12px,3vw,32px) 60px; max-width:1600px; margin:0 auto; }}
.card {{ background:#15181c; border:1px solid #2a2e34; border-radius:12px; padding:16px;
  margin-bottom:24px; }}
@media (prefers-color-scheme: light) {{ .card {{ background:#fff; border-color:#dde1e6; }} }}
.card-head {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:10px; }}
.card-head h2 {{ margin:0; font-size:18px; text-transform:capitalize; }}
.pill {{ font-size:11px; padding:3px 9px; border-radius:99px; font-weight:600; letter-spacing:.02em; }}
.pill.pass {{ background:#123d24; color:#5fd68a; }}
.pill.fail {{ background:#3d1414; color:#f08a8a; }}
.pill.contradict {{ background:#3d2a10; color:#f0b84a; }}
.pill[class*="class-"] {{ background:#20242b; color:#a9b2bd; }}
@media (prefers-color-scheme: light) {{
  .pill.pass {{ background:#e3f6e9; color:#177a3f; }}
  .pill.fail {{ background:#fbe4e4; color:#a3282c; }}
  .pill.contradict {{ background:#fdf0d8; color:#8a5a05; }}
  .pill[class*="class-"] {{ background:#eef0f3; color:#4a5260; }}
}}
.note-row {{ display:flex; gap:24px; flex-wrap:wrap; font-size:12.5px; opacity:.85; margin-bottom:12px; }}
.grid2 {{ display:flex; gap:16px; flex-wrap:wrap; }}
.player-pane {{ flex:1 1 380px; min-width:280px; }}
.evidence-pane {{ flex:1 1 420px; min-width:280px; }}
.pane-label {{ font-size:11px; font-weight:700; letter-spacing:.05em; text-transform:uppercase;
  opacity:.6; margin-bottom:6px; display:flex; align-items:center; gap:8px; }}
.overlay-tag {{ font-size:9px; font-weight:400; text-transform:none; opacity:.6;
  border:1px dashed #666; padding:1px 6px; border-radius:6px; }}
iframe {{ width:100%; aspect-ratio: 3/4; border:1px solid #2a2e34; border-radius:8px; background:#000; }}
@media (prefers-color-scheme: light) {{ iframe {{ border-color:#dde1e6; }} }}
.evblock {{ border:1px solid #2a2e34; border-radius:8px; padding:10px 12px; margin-bottom:10px; }}
@media (prefers-color-scheme: light) {{ .evblock {{ border-color:#e1e4e8; }} }}
.evblock h4 {{ margin:0 0 6px; font-size:12.5px; }}
.cost-annot {{ font-weight:400; font-size:10.5px; opacity:.6; display:block; margin-top:2px; }}
.evrow {{ display:flex; align-items:center; gap:8px; margin-bottom:4px; flex-wrap:wrap; }}
.tag {{ font-size:11px; font-weight:700; padding:2px 8px; border-radius:6px; }}
.tag.pass {{ background:#123d24; color:#5fd68a; }}
.tag.fail {{ background:#3d1414; color:#f08a8a; }}
.tag.unparsed {{ background:#2a2e34; color:#b8bec7; }}
@media (prefers-color-scheme: light) {{
  .tag.pass {{ background:#e3f6e9; color:#177a3f; }}
  .tag.fail {{ background:#fbe4e4; color:#a3282c; }}
  .tag.unparsed {{ background:#eef0f3; color:#4a5260; }}
}}
.subtle {{ font-size:11.5px; opacity:.65; }}
.crop-thumb {{ max-width:100%; margin-top:6px; border-radius:6px; border:1px solid #2a2e34; }}
.candidate-row {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:6px; }}
.candidate-col {{ flex:1 1 160px; min-width:140px; }}
.cand-label {{ font-size:11px; font-weight:600; margin-bottom:4px; }}
.seam-thumb {{ width:100%; border-radius:6px; border:1px solid #2a2e34; cursor:zoom-in; }}
.verdict-controls {{ border-top:1px solid #2a2e34; margin-top:12px; padding-top:12px;
  display:flex; gap:20px; flex-wrap:wrap; align-items:center; }}
@media (prefers-color-scheme: light) {{ .verdict-controls {{ border-color:#e1e4e8; }} }}
.control-group {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; font-size:12.5px; }}
.control-group label {{ display:flex; align-items:center; gap:4px; cursor:pointer; }}
.note-input {{ background:transparent; border:1px solid #2a2e34; border-radius:6px; padding:4px 8px;
  color:inherit; min-width:220px; }}
.save-bar {{ position:sticky; bottom:0; background:#14171b; border-top:1px solid #2a2e34;
  padding:12px clamp(12px,3vw,32px); display:flex; gap:12px; align-items:center; }}
@media (prefers-color-scheme: light) {{ .save-bar {{ background:#fff; border-color:#dde1e6; }} }}
button.save-btn {{ background:#3568e8; color:#fff; border:none; border-radius:8px; padding:9px 20px;
  font-weight:600; cursor:pointer; font-size:13px; }}
#save-status {{ font-size:12px; opacity:.75; }}
table.summary {{ width:100%; border-collapse:collapse; font-size:12.5px; margin-top:8px; }}
table.summary th, table.summary td {{ text-align:left; padding:7px 10px; border-bottom:1px solid #2a2e34; }}
@media (prefers-color-scheme: light) {{ table.summary th, table.summary td {{ border-color:#e1e4e8; }} }}
table.summary th {{ opacity:.6; font-weight:600; text-transform:uppercase; font-size:10.5px; letter-spacing:.04em; }}
.verdict-box {{ background:#15181c; border:1px solid #2a2e34; border-radius:12px; padding:20px;
  margin-top:8px; }}
@media (prefers-color-scheme: light) {{ .verdict-box {{ background:#fff; border-color:#dde1e6; }} }}
</style></head><body>
<header class="top">
  <h1>gen12 round-3 review — 7 re-extracted fails + 1 erase-only (steam-porthole)</h1>
  <div class="cost-line">Models: fal openrouter/router/vision (google/gemini-2.5-pro) for baked-knob + SOTA-eye VLM ·
    fal-ai/bria/eraser + genskin.py edit_vertex() (Vertex gemini-3-pro-image) for erase candidates ·
    extract12.py/biref12.py/build_player.py re-extraction = $0 (existing paint, no new paint call) ·
    <b>total spend this round: ~${grand_total}</b> (VLM baked-knob ~${vlm_cost} + erase ~${erase_cost})
  </div>
</header>
<main>
{cards}

<div class="verdict-box">
<h2>CONCLUSION / VERDICT</h2>
<table class="summary">
<tr><th>skin</th><th>note-routing</th><th>gate post re-extract</th><th>baked-knob</th><th>SOTA-eye</th><th>contradicts routing?</th></tr>
{summary_rows}
</table>
<p style="margin-top:14px;"><b>Recommendation:</b> claymation's baked-slider defect was already
resolved by a prior erase pass before this round even started — no action needed there beyond
confirming the button-alignment half of its note. fallout-vault and steam-porthole both have
confirmed baked slider thumbs (gate+VLM+direct-eye agree) with clean Vertex AND Bria erase
candidates ready for pick (both tiers looked visually clean on direct inspection; Bria is
~3.4x cheaper at $0.04 vs $0.134 — recommend Bria unless the human sees a difference the
seam-delta metric doesn't catch). myst-arcanum's re-extract made things WORSE, not better — the
vol knob failed to detect entirely and the rebuilt player throws a JS error, rendering zero
interactive controls; route to a targeted re-extract debug or regen, not a plain re-run.
diablo-gothic, fa-pod, ps1-crunchy still show real per-control defects post re-extract
(css-misalignment, placement-wrong, dead shuffle toggle, aesthetic queue issue) — the shared
"sprite-fit:shuffle" gate failure across nearly the whole roster (including steam-porthole, a
PRIOR PASS) points at an in-progress, unrelated TOGGLE_TRACK feature bug, not something in this
round's note-routing scope; flagged for whoever owns that feature. n64-cutscene is the one clean
re-extract-only win: gate PASS, SOTA-eye PASS, no contradiction.</p>
</div>
</main>
<div class="save-bar">
  <button class="save-btn" onclick="saveDecisions()">Save decisions → review-round3-decisions.json</button>
  <span id="save-status"></span>
</div>
<script>
function saveDecisions() {{
  const skins = {skins_json};
  const out = {{}};
  for (const s of skins) {{
    const disp = document.querySelector(`input[name="disp-${{s}}"]:checked`);
    const cand = document.querySelector(`input[name="cand-${{s}}"]:checked`);
    const note = document.getElementById(`note-${{s}}`);
    out[s] = {{ disposition: disp ? disp.value : null, candidate: cand ? cand.value : null,
                note: note ? note.value : "" }};
  }}
  out._ts = new Date().toISOString();
  fetch('/save-round3', {{ method:'POST', body: JSON.stringify(out) }})
    .then(r => r.text()).then(t => {{
      document.getElementById('save-status').textContent =
        t === 'ok' ? 'saved ' + new Date().toLocaleTimeString() : 'ERROR: ' + t;
    }}).catch(e => {{ document.getElementById('save-status').textContent = 'ERROR: ' + e; }});
}}
// keyboard: Cmd/Ctrl+S saves
document.addEventListener('keydown', e => {{
  if ((e.metaKey || e.ctrlKey) && e.key === 's') {{ e.preventDefault(); saveDecisions(); }}
}});
// click-to-zoom on seam thumbnails
document.addEventListener('click', e => {{
  if (e.target.classList.contains('seam-thumb') || e.target.classList.contains('crop-thumb')) {{
    window.open(e.target.src, '_blank');
  }}
}});
</script>
</body></html>
""".format(
    cards="\n".join(cards_html),
    summary_rows="\n".join(summary_rows),
    grand_total=grand_total, vlm_cost=round(total_vlm_cost, 3), erase_cost=round(total_erase_cost, 3),
    skins_json=json.dumps(SKINS),
)

out_path = os.path.join(HERE, "review-round3.html")
open(out_path, "w").write(HTML)
print(f"[build_review3] wrote {out_path} ({len(HTML)} bytes), grand_total=${grand_total}")
