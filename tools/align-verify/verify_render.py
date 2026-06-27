#!/usr/bin/env python3
"""Gemini judge of a LIVE-RENDERED skin screenshot (what the user actually sees).

The transport buttons are BAKED into the device art (transparent overlay), so the only
honest check is the final render, not a hit-region overlay. Pass a screenshot of the
running player; Gemini 2.5 Pro scores whether the controls read as correctly-placed real
hardware. Focus: BUTTONS.

Usage: python3 verify_render.py <image.png> [<label>]
"""
import json, os, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL = "google/gemini-2.5-pro"
VISION = "https://queue.fal.run/openrouter/router/vision"


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


PROMPT = (
    "This is a FINAL RENDER of a skeuomorphic music-player skin — exactly what the end user sees. "
    "Judge CONTROL ALIGNMENT/placement only (ignore art style, colors, the disc art). For the transport "
    "BUTTONS (play, stop, previous/rewind, next/forward) and any knobs and sliders, decide if each reads as a "
    "correctly-placed, real-looking control: it sits cleanly in/on its hardware seat, not floating on blank "
    "body, not half-off its socket, not overlapping a neighbour, not duplicated, the right size. Be strict but "
    "judge ONLY what is visibly wrong in this render.\n\n"
    "Return ONLY strict JSON, no prose:\n"
    '{\"controls\":[{\"name\":\"play|stop|prev|next|knob|seek|...\",\"ok\":true|false,\"issue\":\"<short>\"}],'
    '\"buttons_perfect\":true|false,\"score\":<0-100>}'
)


def judge(path):
    payload = {"model": MODEL, "reasoning": True, "max_tokens": 4000, "temperature": 0,
               "image_urls": [upload(path)], "prompt": PROMPT}
    sub = _req(VISION, json.dumps(payload).encode(), {"Authorization": f"Key {FAL}", "Content-Type": "application/json"})
    t0 = time.time()
    while True:
        st = _req(sub["status_url"], headers={"Authorization": f"Key {FAL}"})
        if st.get("status") == "COMPLETED": break
        if st.get("status") in ("FAILED", "ERROR") or time.time() - t0 > 180: raise SystemExit(f"vision failed: {st}")
        time.sleep(2)
    out = _req(sub["response_url"], headers={"Authorization": f"Key {FAL}"}).get("output", "")
    s, e = out.find("{"), out.rfind("}")
    return json.loads(out[s:e + 1]) if s >= 0 else {"raw": out}


if __name__ == "__main__":
    if not FAL: raise SystemExit("FAL_KEY not found")
    path = sys.argv[1]; label = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(path)
    v = judge(path)
    bad = [c for c in v.get("controls", []) if not c.get("ok")]
    print(f"[{label}] score={v.get('score')} buttons_perfect={v.get('buttons_perfect')} "
          f"({len(v.get('controls',[]))-len(bad)}/{len(v.get('controls',[]))} ok)")
    for c in bad:
        print(f"    BAD {c.get('name'):10} {c.get('issue','')}")
    print("JSON:", json.dumps(v))
