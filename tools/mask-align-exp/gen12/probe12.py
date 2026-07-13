#!/usr/bin/env python3
"""probe12 — deterministic scripted JS-state probe.

Spec: docs/experiments/2026-07-11-verification-recalibration.md, "Residual gaps" section.
Vision (observe12.py's VLM pass) cannot reliably tell a DEAD control from a merely-static
one — two screenshots are the wrong evidence for an interaction-testing question:
  - `ps1-crunchy` "visualizer not working" (human review round1) turned out to be a control
    that WAS drawing every frame, just not visibly different enough between two static
    screenshots to read as "animating" to a VLM (idle wobbles gently by design).
  - `fallout-vault` "prev button, shuffle button, failed to work" (same round) is the anchor
    case for a hitbox/z-order defect: a static screenshot pair can't distinguish "the handler
    is broken" from "the click never reached this element because a sibling control overlaps
    it" — both just look like "nothing changed."

This script replaces "does it look right" with "did the interaction actually change the
player's own state" — deterministic, $0, no VLM call, ~10-20s/skin. For each control the
shipped player exposes (per regions.json `roles`), it clicks/drags it via a REAL
`page.mouse` interaction at the control's own `getBoundingClientRect()` center on a
throwaway, isolated Playwright chromium instance (own `chromium.launch()` — no shared
profile with any other driver), then asserts the player's own DOM/JS state changed:
  - buttons (playpause/prev/next/repeat/queue/...): the hint line / dataset / queue overlay
    the player's own click handler writes (build_player.py, read-only reference — not
    touched by this script).
  - toggle (shuffle): a generic style diff (background-image / left / top / transform) for
    the `.ptog` sprite-swap/lever renderings, OR — since shuffle can also render as a plain
    icon `.pbtn` (build_player.py STATEFUL_LIT_ICON, commit a1a95228; role stays "toggle" in
    regions.json) — a classList 'on' flip for that mode. probe_drive.mjs tries `.ptog` first,
    falls back to `.pbtn[title=<key>]` by title, so this stays correct for whichever
    architecture actually shipped without a regions.json mode flag.
  - knob (vol): the cap's rotation transform after a drag.
  - slider (seek): thumb position changes AND clamps identically on a second overshoot at
    BOTH ends (drag-past-max twice, drag-past-min twice).
  - visualizer: playing-state canvas pixel activity over 600ms, well above THIS skin's own
    idle-wobble baseline (the ps1-crunchy lesson — idle already wobbles gently by design, so
    a bare non-zero diff is not proof of anything).

The actual browser driving lives in probe_drive.mjs (repo's Node Playwright — python
playwright isn't installed here, same reasoning observe12.py/observe_drive.mjs already
established: don't add a second browser stack).

Output: <assets-dir>/observe/probe.json
  {skin, url, load_ok, page_errors, controls: {<key>: {alive, evidence}}, dead_controls,
   elapsed_s, ts}

Usage: python3 probe12.py <assets-dir> [--url=http://host:port/assets-x/player.html]
"""
import os, sys, json, time, subprocess

if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
    print(__doc__)
    sys.exit(1)

OUT = os.path.abspath(sys.argv[1])
HERE = os.path.dirname(os.path.abspath(__file__))
SID = os.path.basename(OUT).replace("assets-", "")
OBS = os.path.join(OUT, "observe")
os.makedirs(OBS, exist_ok=True)

URL = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--url=")), None)
if not URL:
    su = open(os.path.join(HERE, ".serve-url")).read().strip().rstrip("/")
    URL = f"{su}/assets-{SID}/player.html"

REGIONS = os.path.join(OUT, "regions.json")
if not os.path.exists(REGIONS):
    print(f"[probe12] {SID}: no regions.json at {REGIONS} — nothing to probe", file=sys.stderr)
    sys.exit(1)

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
NODE_OUT = os.path.join(OBS, "probe_raw.json")

t0 = time.time()
try:
    subprocess.run(
        ["node", os.path.join(HERE, "probe_drive.mjs"), URL, REGIONS, NODE_OUT],
        cwd=REPO, check=True, timeout=90,
    )
except subprocess.CalledProcessError as e:
    print(f"[probe12] {SID}: probe_drive.mjs failed (exit {e.returncode}) — see stderr above", file=sys.stderr)
    sys.exit(1)
except subprocess.TimeoutExpired:
    print(f"[probe12] {SID}: probe_drive.mjs timed out after 90s", file=sys.stderr)
    sys.exit(1)
dt = time.time() - t0

raw = json.load(open(NODE_OUT))
controls = raw.get("results", {})
dead = sorted(k for k, v in controls.items() if not v.get("alive", False))

rec = {
    "skin": SID,
    "url": URL,
    "load_ok": raw.get("loadOk", True),
    "load_err": raw.get("loadErr", ""),
    "page_errors": raw.get("pageErrors", []),
    "controls": controls,
    "dead_controls": dead,
    "elapsed_s": round(dt, 1),
    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
}
json.dump(rec, open(os.path.join(OBS, "probe.json"), "w"), indent=2)
os.remove(NODE_OUT)

status = "ALL ALIVE" if not dead else f"DEAD: {', '.join(dead)}"
print(f"[probe12] {SID}: {len(controls)} controls probed in {dt:.1f}s -- {status}")
for k, v in sorted(controls.items()):
    mark = "alive" if v.get("alive") else "DEAD "
    print(f"    [{mark}] {k}: {v.get('evidence', '')}")
