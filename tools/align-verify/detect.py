#!/usr/bin/env python3
"""Gemini-grounded control DETECTION → align the template rects to the actual paint.

The painter drifts controls off the blueprint sockets (verified). Instead of SAM (rejected)
or my own vision, ask Gemini 2.5 Pro for the precise bounding box of each painted control on
the device frame, then move the template rect onto it. Conservative: only move when Gemini
returns a sane box near the prior; keep the blueprint rect otherwise. Writes a
<id>-template.snap.json sidecar (NOT overwriting) unless --apply.

Usage: python3 detect.py <id> [--apply]
"""
import json, os, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEN = os.path.join(ROOT, "public", "generated")
MODEL = "google/gemini-2.5-pro"
VISION = "https://queue.fal.run/openrouter/router/vision"
CTRL = {"button", "toggle", "knob", "slider-h", "slider-v", "slider-arc", "slider-path"}


def _key(name):
    for p in (os.path.join(ROOT, ".dev.vars"), "/Users/conner/dev/central/.env"):
        if os.path.exists(p):
            for line in open(p):
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip()
    return os.environ.get(name)


FAL = _key("FAL_KEY")


def _req(url, data=None, headers=None, method=None):
    r = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(r, timeout=180) as resp:
        return json.loads(resp.read().decode() or "{}")


def upload(path):
    init = _req("https://rest.alpha.fal.ai/storage/upload/initiate",
                json.dumps({"file_name": os.path.basename(path), "content_type": "image/png"}).encode(),
                {"Authorization": f"Key {FAL}", "Content-Type": "application/json"})
    urllib.request.urlopen(urllib.request.Request(init["upload_url"], data=open(path, "rb").read(),
                           headers={"Content-Type": "image/png"}, method="PUT"), timeout=180)
    return init["file_url"]


# words to describe each control to Gemini
ROLE = {"play": "the PLAY button", "pause": "the PAUSE button", "stop": "the STOP button",
        "prev": "the PREVIOUS/REWIND button", "next": "the NEXT/FAST-FORWARD button",
        "seek": "the horizontal SEEK/position slider groove", "volume": "the VOLUME knob",
        "balance": "the BALANCE knob", "shuffle": "the SHUFFLE toggle", "eqBand": "an EQ slider"}


def desc(r):
    b = r.get("bind") or r.get("id") or ""
    if b in ROLE: return ROLE[b]
    k = r["kind"]
    return {"button": "a push button", "knob": "a rotary knob", "toggle": "a toggle switch",
            "slider-h": "a horizontal slider groove", "slider-v": "a vertical EQ slider",
            "slider-arc": "an arc slider", "slider-path": "a slider"}.get(k, "a control")


def detect(url, ctrl):
    lines = "\n".join(f"- {r['_name']}: {desc(r)} (currently near x={r['rect']['x']+r['rect']['w']/2:.2f}, "
                      f"y={r['rect']['y']+r['rect']['h']/2:.2f})" for r in ctrl)
    prompt = (
        "This is a music player's painted hardware (no UI overlay). Locate each PAINTED control listed below "
        "and return its TIGHT bounding box. The 'currently near' hint is only a rough prior — the real painted "
        "control may be offset from it; report where the control ACTUALLY is.\n\n"
        f"Controls:\n{lines}\n\n"
        "Return ONLY strict JSON mapping each name to a normalized box [x_min, y_min, x_max, y_max] with values "
        "in 0..1 (x to the right, y downward, relative to the FULL image). If a control is genuinely not visible, "
        'use null. Example: {\"play\":[0.31,0.62,0.40,0.71],\"volume\":null}'
    )
    payload = {"model": MODEL, "reasoning": True, "max_tokens": 4000, "temperature": 0,
               "image_urls": [url], "prompt": prompt}
    sub = _req(VISION, json.dumps(payload).encode(), {"Authorization": f"Key {FAL}", "Content-Type": "application/json"})
    t0 = time.time()
    while True:
        st = _req(sub["status_url"], headers={"Authorization": f"Key {FAL}"})
        if st.get("status") == "COMPLETED": break
        if st.get("status") in ("FAILED", "ERROR") or time.time() - t0 > 180: raise SystemExit(f"vision failed: {st}")
        time.sleep(2)
    out = _req(sub["response_url"], headers={"Authorization": f"Key {FAL}"}).get("output", "")
    s, e = out.find("{"), out.rfind("}")
    return json.loads(out[s:e + 1]) if s >= 0 else {}


def plausible(rc, box):
    """box = [x0,y0,x1,y1] norm. Accept only a sane-sized box not absurdly far from the prior."""
    if not box or len(box) != 4: return None
    x0, y0, x1, y1 = box
    if not (0 <= x0 < x1 <= 1.001 and 0 <= y0 < y1 <= 1.001): return None
    w, h = x1 - x0, y1 - y0
    if w < 0.01 or h < 0.01 or w > 0.95 or h > 0.95: return None
    aw, ah = w / rc["w"], h / rc["h"]
    if not (0.3 < aw < 3.2 and 0.3 < ah < 3.2): return None      # size sanity vs blueprint
    pcx, pcy = rc["x"] + rc["w"] / 2, rc["y"] + rc["h"] / 2
    ncx, ncy = (x0 + x1) / 2, (y0 + y1) / 2
    if ((ncx - pcx) ** 2 + (ncy - pcy) ** 2) ** 0.5 > 0.30: return None  # didn't wander across the device
    return {"x": round(x0, 4), "y": round(y0, 4), "w": round(w, 4), "h": round(h, 4)}


def run(skin, apply=False):
    tpl = json.load(open(os.path.join(GEN, f"{skin}-template.json")))
    ctrl = []
    for r in tpl["regions"]:
        if r["kind"] in CTRL:
            r["_name"] = r.get("bind") or r.get("id") or r["kind"]; ctrl.append(r)
    # de-dup names (eqBand×N) → name by id for the prompt
    seen = {}
    for r in ctrl:
        if r["_name"] in seen: r["_name"] = r.get("id") or f"{r['_name']}{seen[r['_name']]}"
        seen[r.get('bind') or r.get('id')] = seen.get(r.get('bind') or r.get('id'), 0) + 1
    boxes = detect(upload(os.path.join(GEN, f"{skin}-frame.png")), ctrl)
    moved = 0
    out_regs = []
    for r in tpl["regions"]:
        r2 = dict(r); r2.pop("_name", None)
        if r["kind"] in CTRL:
            nm = r.get("bind") or r.get("id") or r["kind"]
            # match the (possibly renamed) detection key
            key = next((c["_name"] for c in ctrl if c is r), nm)
            nb = plausible(r["rect"], boxes.get(key) or boxes.get(nm))
            if nb: r2["rect"] = nb; moved += 1
        out_regs.append(r2)
    tpl["regions"] = out_regs
    out_path = os.path.join(GEN, f"{skin}-template.{'json' if apply else 'snap.json'}")
    json.dump(tpl, open(out_path, "w"))
    print(f"[{skin}] gemini-detect: moved {moved}/{len(ctrl)} controls → {out_path}")
    return moved


if __name__ == "__main__":
    if not FAL: raise SystemExit("FAL_KEY not found")
    apply = "--apply" in sys.argv
    for sid in [a for a in sys.argv[1:] if not a.startswith("--")]:
        run(sid, apply)
