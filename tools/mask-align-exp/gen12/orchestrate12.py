#!/usr/bin/env python3
"""orchestrate12 — the auto-regen GATE LOOP for one skin. Rolls seeds until the extractor's
GATE passes (or max tries), running the full pipeline each roll, then builds the player.
Writes a result summary to <assets>/orch.json. Usage: python3 orchestrate12.py <spec.json> [max_tries]

A roll = genskin -> extract12 -> biref12 -> extract12(pass2) -> read regions.json['gate'].
GATE PASS requires: empty sockets, 10/10 controls detected, seek covers groove, biref parts cut,
leak <= 0.30%. On the first PASS we stop and keep that generation; else we keep the LAST roll
and report FAIL with reasons (a genuinely hard skin the human can inspect via the dashboard)."""
import os, sys, json, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.abspath(sys.argv[1])
# AUTO-REROLL DISABLED 2026-07-10 (user call): default is ONE roll — a gate FAIL surfaces on the
# dashboard for human triage instead of burning seeds. Pass an explicit max_tries argv to re-enable
# per-run (e.g. `orchestrate12.py spec.json 4`); spend discipline: generation-spend-rule.
MAX = int(sys.argv[2]) if len(sys.argv) > 2 else 1
# FREEZE_ON_PASS: snapshot the paid roll's non-git-tracked joint-4k.png to Drive the moment
# it first gate-PASSes — closes the gap the drift bisect exposed (892bf045): every June
# baseline paint was re-rolled before ever being preserved, so the bytes are gone for good.
# See freeze_baseline.py's docstring for exactly what is/isn't frozen and why.
FREEZE_ON_PASS = True
spec = json.load(open(SPEC))
sid = spec["id"]; base = spec.get("seed", 71)
ASSETS = os.path.join(HERE, f"assets-{sid}")


def run(cmd):
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, timeout=600)
    return r.returncode, r.stdout + r.stderr


history = []
t0 = time.time()
for i in range(MAX):
    seed = base + i * 13
    spec["seed"] = seed
    json.dump(spec, open(SPEC, "w"), indent=2)
    print(f"[orch:{sid}] roll {i+1}/{MAX} seed={seed}", flush=True)
    rc, out = run(["python3", "genskin.py", SPEC])
    if rc != 0:
        history.append({"seed": seed, "error": "genskin", "log": out[-400:]}); continue
    run(["python3", "extract12.py", ASSETS])
    run(["python3", "biref12.py", ASSETS])
    rc, out = run(["python3", "extract12.py", ASSETS])
    try:
        gate = json.load(open(os.path.join(ASSETS, "regions.json"))).get("gate", {})
    except Exception as e:
        gate = {"PASS": False, "reasons": [f"regions-read:{e}"]}
    leak = json.load(open(os.path.join(ASSETS, "results.json"))).get("leak")
    history.append({"seed": seed, "PASS": gate.get("PASS"), "controls": gate.get("controls"),
                    "seek_cov": gate.get("seek_cov"), "reasons": gate.get("reasons"), "leak": leak})
    print(f"[orch:{sid}] roll {i+1} -> {'PASS' if gate.get('PASS') else 'FAIL'} {gate.get('reasons')}", flush=True)
    if gate.get("PASS"):
        # FREEZE_ON_PASS: preserve the paid roll the moment it first passes — the June
        # baseline-paint burn (892bf045 drift bisect) re-rolled every early paint before it
        # was ever snapshotted, making it unrecoverable and blocking a $0 experiment later.
        if FREEZE_ON_PASS:
            run(["python3", "freeze_baseline.py", ASSETS])
        break

run(["python3", "build_player.py", ASSETS])
final = history[-1] if history else {}
# gate_reasons drives the "erase" candidate below — read the LIVE regions.json gate (same
# "regions.json IS the live gate" convention build_dashboard.py already uses), not just this
# invocation's own roll history, so a re-run with MAX=0 against an already-gated skin still
# sees a real, current baked-thumb defect instead of an empty history[-1].
try:
    live_gate = json.load(open(os.path.join(ASSETS, "regions.json"))).get("gate", {})
except Exception:
    live_gate = {}
gate_reasons = live_gate.get("reasons") or final.get("reasons") or []

# ✨ PBR/emissive dynamic-lighting pass (pbr_pass.py + player-pbr.html) — feature-flagged
# OFF until proven across the roster: it adds ~$0.02-0.03/skin hosted patina spend and
# ~1min per roll. Flip here to enable; per-skin kill switch: spec "lighting.enabled": false.
# Details: WIRE-pbr.md. PARKED for skeuo v2 (TODO.md) — deliberately NOT wired into the
# DIRECTOR_GATES_OPTIONAL_STAGES pattern below; pick this back up only if/when v2 resumes it.
PBR_PASS_ENABLED = False
if PBR_PASS_ENABLED:
    run(["python3", "pbr_pass.py", ASSETS])
    run(["python3", "build_player_pbr.py", ASSETS])

# --- OPTIONAL STAGE CANDIDATES + DIRECTOR GATING (2026-07-12) -----------------------------
# TODO.md "Let the DIRECTOR decide whether optional pipeline stages are worth running per
# skin" (2026-07-11 user directive): every flag-gated optional stage used to be a global
# on/off — flip it True and it runs for EVERY skin, False and it runs for NONE. That's the
# wrong granularity (a matte-clay theme has no business paying for an AI repair pass a
# glossy-metal theme clearly wants). The fix: each *_ENABLED flag below stays a master
# PERMISSION (globally False -> always off, no gate call, matches the old semantics exactly),
# and when True it becomes a PERMISSION the director MAY exercise per-skin rather than a
# command — director_gate.py reads the theme spec (+ any live context, e.g. gate reasons) and
# returns {"run": bool, "why": str} per candidate stage, recorded into orch.json's
# "director_decisions" key so a skipped stage is auditable without re-running anything.
#
# ERASE_ENABLED: master permission for erase12.py's auto-repair pass (baked-thumb defect ->
# classical/generative inpaint). NEW here — erase12.py itself is proven manually (4/6
# review-flagged skins, TODO.md "DETECT+ERASE for baked slider thumbs") but has never been
# wired into the auto-loop. Default OFF per feature-flag-rule: unproven live inside the loop.
ERASE_ENABLED = os.environ.get("ERASE_ENABLED", "0") == "1"
# DIRECTOR_REVIEW_ENABLED: master permission for director_review.py's full aesthetic sign-off
# pass. Mainlined at True 2026-07-11 (proven on diablo-gothic — caught the guide-ring-residue
# defect the geometry gate missed). Unchanged by this task: when DIRECTOR_GATES_OPTIONAL_STAGES
# is False (default), this flag alone still means "always run", exactly as before.
DIRECTOR_REVIEW_ENABLED = True
# DIRECTOR_GATES_OPTIONAL_STAGES: master switch for the per-skin gating behavior itself. False
# means every *_ENABLED flag above keeps its ORIGINAL "always run when True" meaning — this
# task changes nothing for the mainline default. Default OFF per feature-flag-rule: the TODO's
# own cost-logic section says this only pays for itself once a real fraction of the roster's
# theme_specs would actually skip a stage, which hasn't been measured yet. Env-var override
# (not a CLI flag) so a single verification run doesn't require editing this file.
DIRECTOR_GATES_OPTIONAL_STAGES = os.environ.get("DIRECTOR_GATES_OPTIONAL_STAGES", "0") == "1"

# Build the candidate set from what's globally permitted AND actually relevant to THIS skin —
# e.g. "erase" is only a real question when extract12's gate already flagged a baked-thumb
# defect; asking the director to judge repairing a defect that doesn't exist is nonsensical.
candidate_stages = {}
if ERASE_ENABLED and any(r.startswith("baked-thumb:") for r in gate_reasons):
    candidate_stages["erase"] = {"gate_reasons": gate_reasons}
if DIRECTOR_REVIEW_ENABLED:
    candidate_stages["director_review"] = {}

director_decisions = {}
if candidate_stages and DIRECTOR_GATES_OPTIONAL_STAGES:
    rc, out = run(["python3", "director_gate.py", ASSETS, "--stages", ",".join(candidate_stages),
                   "--context", json.dumps(candidate_stages)])
    try:
        director_decisions = json.load(open(os.path.join(ASSETS, "director-gate.json"))).get("decisions", {})
    except Exception as e:
        print(f"[orch:{sid}] WARN director_gate.py failed/unreadable ({e}); "
              f"treating gating as unavailable this run", flush=True)
if candidate_stages and not director_decisions:
    # Gating disabled (or the gate call failed/produced nothing) -> the global *_ENABLED flag
    # alone permits, unconditionally, exactly as it did before this task (fail-open, never
    # fail-closed: a broken gate must never silently withhold a stage the flag already allows).
    director_decisions = {k: {"run": True, "why": "director gating disabled or gate call "
                                                    "unavailable; global flag permits unconditionally"}
                          for k in candidate_stages}

if "erase" in candidate_stages and director_decisions.get("erase", {}).get("run", True):
    run(["python3", "erase12.py", ASSETS])
    run(["python3", "extract12.py", ASSETS])          # refresh the gate post-erase
    try:
        gate_reasons = json.load(open(os.path.join(ASSETS, "regions.json"))).get("gate", {}).get("reasons", [])
        final = {**final, "reasons": gate_reasons}
    except Exception:
        pass
elif "erase" in candidate_stages:
    print(f"[orch:{sid}] director SKIPPED erase: {director_decisions['erase'].get('why')}", flush=True)

# DIRECTOR FINAL REVIEW — aesthetic/thematic judgment of the FINISHED render against its own
# theme brief (director_review.py), distinct from observe12.py's geometry/defect pass. Proven
# on diablo-gothic (2026-07-11): caught the guide-ring-residue defect (neon borders around
# every control) that the geometry/emptiness gate missed entirely.
if "director_review" in candidate_stages and director_decisions.get("director_review", {}).get("run", True):
    run(["python3", "director_review.py", ASSETS])
elif "director_review" in candidate_stages:
    print(f"[orch:{sid}] director SKIPPED director_review: "
          f"{director_decisions['director_review'].get('why')}", flush=True)

result = {"id": sid, "title": spec.get("title", sid), "mode": spec["mode"],
          "passed": bool(final.get("PASS")), "rolls": len(history), "final_seed": final.get("seed"),
          "gate": final, "history": history, "elapsed_s": round(time.time() - t0, 1),
          "player": f"assets-{sid}/player.html",
          "director_decisions": director_decisions}
json.dump(result, open(os.path.join(ASSETS, "orch.json"), "w"), indent=2)
print(f"[orch:{sid}] DONE passed={result['passed']} rolls={result['rolls']} "
      f"seed={result['final_seed']} in {result['elapsed_s']}s")
# INDEX AUTO-APPEND (skins-index.json + skins-gallery.html): every run keeps the canonical
# roster index current so "sweep to find skins with X defect" is never a manual task again —
# see build_index.py's docstring. The index is cheap ($0, local, sub-second) to fully rebuild,
# so this just reruns it rather than patching one row. Wrapped so an index bug never fails a
# real (paid) generation run.
try:
    run(["python3", "build_index.py"])
except Exception as e:
    print(f"[orch:{sid}] WARN build_index.py failed (non-fatal): {e}")
