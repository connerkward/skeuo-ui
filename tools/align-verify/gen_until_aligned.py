#!/usr/bin/env python3
"""Generate skins whose BUTTON alignment Gemini approves — by construction.

The painter's bank is usually even but unreliable on hard bodies. So: generate, have
Gemini 2.5 Pro (consensus) judge the transport bank, and RE-ROLL the paint until it
passes (or max tries). The painter's own variance + the even-spacing prompt converge to a
clean bank; Gemini is the gate (not my eyes, not SAM). Prints the winning id per prompt.

Usage: python3 gen_until_aligned.py --tries 4 --runs 2 "<prompt1>" "<prompt2>" ...
"""
import json, os, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEN = os.path.join(ROOT, "public", "generated")
OUT = "/tmp/gen-aligned"; os.makedirs(OUT, exist_ok=True)
MODEL = "google/gemini-2.5-pro"
VISION = "https://queue.fal.run/openrouter/router/vision"
GENAPI = "http://localhost:5180/api/generate"


def _key(name):
    for p in (os.path.join(ROOT, ".dev.vars"), "/Users/conner/dev/central/.env"):
        if os.path.exists(p):
            for line in open(p):
                if line.startswith(name + "="): return line.split("=", 1)[1].strip()
    return os.environ.get(name)


FAL = _key("FAL_KEY")


def _req(url, data=None, headers=None, method=None, timeout=240):
    r = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.read().decode()


def generate(prompt):
    body = json.dumps({"prompt": prompt, "variant": "simple",
                       "model": "fal-ai/gemini-3.1-flash-image-preview/edit"}).encode()
    raw = _req(GENAPI, body, {"Content-Type": "application/json"}, "POST", timeout=240)
    last = [l for l in raw.strip().splitlines() if l.strip()][-1]
    return json.loads(last).get("id")


def upload(path):
    init = json.loads(_req("https://rest.alpha.fal.ai/storage/upload/initiate",
                       json.dumps({"file_name": os.path.basename(path), "content_type": "image/png"}).encode(),
                       {"Authorization": f"Key {FAL}", "Content-Type": "application/json"}))
    urllib.request.urlopen(urllib.request.Request(init["upload_url"], data=open(path, "rb").read(),
                           headers={"Content-Type": "image/png"}, method="PUT"), timeout=180)
    return init["file_url"]


def device_png(skin):
    from PIL import Image
    lay = json.load(open(os.path.join(GEN, f"{skin}-layout.json")))
    df = lay.get("devFrac", 0.84)
    im = Image.open(os.path.join(GEN, f"{skin}-paint.png")).convert("RGB"); W, H = im.size
    p = os.path.join(OUT, f"{skin}.png"); im.crop((0, 0, W, int(H * df))).save(p); return p


PROMPT = (
    "This is the PAINTED hardware of a music player. Judge ONLY the transport BUTTON cluster "
    "(play/stop/previous/next). Are the buttons EVENLY SPACED with identical gaps, consistently sized (play may "
    "be bigger), cleanly formed, undistorted, and seated in one tidy row — like real manufactured hardware? Any "
    "uneven gap, crowded/merged/drifting/tilted key = FAIL. Ignore knobs, screens, colors, art.\n"
    'Return ONLY JSON: {\"buttons_perfect\":true|false,\"issue\":\"<short>\"}'
)


def judge_once(url):
    payload = {"model": MODEL, "reasoning": True, "max_tokens": 3500, "temperature": 0,
               "image_urls": [url], "prompt": PROMPT}
    sub = json.loads(_req(VISION, json.dumps(payload).encode(), {"Authorization": f"Key {FAL}", "Content-Type": "application/json"}, "POST"))
    t0 = time.time()
    while True:
        st = json.loads(_req(sub["status_url"], headers={"Authorization": f"Key {FAL}"}))
        if st.get("status") == "COMPLETED": break
        if st.get("status") in ("FAILED", "ERROR") or time.time() - t0 > 180: return {"buttons_perfect": False, "issue": "timeout"}
        time.sleep(2)
    out = json.loads(_req(sub["response_url"], headers={"Authorization": f"Key {FAL}"})).get("output", "")
    s, e = out.find("{"), out.rfind("}")
    return json.loads(out[s:e + 1]) if s >= 0 else {"buttons_perfect": False, "issue": "no-json"}


def passes(skin, runs):
    url = upload(device_png(skin))
    ok = 0; issue = ""
    for _ in range(runs):
        r = judge_once(url)
        if r.get("buttons_perfect"): ok += 1
        elif not issue: issue = r.get("issue", "")
    return ok > runs / 2, ok, runs, issue


def run(prompt, tries, runs):
    print(f"\n### {prompt[:60]}")
    for t in range(1, tries + 1):
        sid = generate(prompt)
        if not sid:
            print(f"  try {t}: gen failed"); continue
        ok, p, n, issue = passes(sid, runs)
        print(f"  try {t}: {sid[-4:]}  {'PASS' if ok else 'FAIL'} ({p}/{n})" + (f"  {issue}" if not ok else ""))
        if ok:
            return sid
    print("  -> NO PASS within tries")
    return None


if __name__ == "__main__":
    if not FAL: raise SystemExit("FAL_KEY not found")
    args = sys.argv[1:]
    tries = 4; runs = 2
    if "--tries" in args: i = args.index("--tries"); tries = int(args[i + 1]); args = args[:i] + args[i + 2:]
    if "--runs" in args: i = args.index("--runs"); runs = int(args[i + 1]); args = args[:i] + args[i + 2:]
    won = {}
    for pr in args:
        won[pr] = run(pr, tries, runs)
    print("\n=== WINNERS ===")
    for pr, sid in won.items():
        print(f"  {'OK ' if sid else 'XX '} {sid or '(none)'}  {pr[:50]}")
    print(f"ALL_PASS={all(won.values())}")
    sys.exit(0 if all(won.values()) else 1)
