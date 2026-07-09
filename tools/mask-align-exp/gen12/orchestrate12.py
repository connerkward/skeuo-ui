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
MAX = int(sys.argv[2]) if len(sys.argv) > 2 else 4
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
final = history[-1] if history else {}
result = {"id": sid, "title": spec.get("title", sid), "mode": spec["mode"],
          "passed": bool(final.get("PASS")), "rolls": len(history), "final_seed": final.get("seed"),
          "gate": final, "history": history, "elapsed_s": round(time.time() - t0, 1),
          "player": f"assets-{sid}/player.html"}
json.dump(result, open(os.path.join(ASSETS, "orch.json"), "w"), indent=2)
print(f"[orch:{sid}] DONE passed={result['passed']} rolls={result['rolls']} "
      f"seed={result['final_seed']} in {result['elapsed_s']}s")
