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
        break

run(["python3", "build_player.py", ASSETS])
# ✨ PBR/emissive dynamic-lighting pass (pbr_pass.py + player-pbr.html) — feature-flagged
# OFF until proven across the roster: it adds ~$0.02-0.03/skin hosted patina spend and
# ~1min per roll. Flip here to enable; per-skin kill switch: spec "lighting.enabled": false.
# Details: WIRE-pbr.md.
PBR_PASS_ENABLED = False
if PBR_PASS_ENABLED:
    run(["python3", "pbr_pass.py", ASSETS])
    run(["python3", "build_player_pbr.py", ASSETS])
# DIRECTOR FINAL REVIEW — aesthetic/thematic judgment of the FINISHED render against its
# own theme brief (director_review.py), distinct from observe12.py's geometry/defect pass.
# User-requested stage; default OFF until proven across the roster (~$0.02-0.05/skin,
# unverified at scale) — flip here to enable.
DIRECTOR_REVIEW_ENABLED = False
if DIRECTOR_REVIEW_ENABLED:
    run(["python3", "director_review.py", ASSETS])
final = history[-1] if history else {}
result = {"id": sid, "title": spec.get("title", sid), "mode": spec["mode"],
          "passed": bool(final.get("PASS")), "rolls": len(history), "final_seed": final.get("seed"),
          "gate": final, "history": history, "elapsed_s": round(time.time() - t0, 1),
          "player": f"assets-{sid}/player.html"}
json.dump(result, open(os.path.join(ASSETS, "orch.json"), "w"), indent=2)
print(f"[orch:{sid}] DONE passed={result['passed']} rolls={result['rolls']} "
      f"seed={result['final_seed']} in {result['elapsed_s']}s")
