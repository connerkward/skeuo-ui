#!/usr/bin/env python3
"""Consensus button-alignment judge over a batch of generated skins.

Gemini's verdict varies run-to-run, so judge each skin N times and take the MAJORITY.
Crops the painted DEVICE region (top devFrac) from the paint — the baked transport bank
lives there — and asks Gemini 2.5 Pro per run. Prints a pass/fail per skin and an overall
"all buttons perfect" gate. Uses the cut frame if present (cleaner), else the paint crop.

Usage: python3 judge_batch.py <id> [<id> ...] [--runs N]
"""
import json, os, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEN = os.path.join(ROOT, "public", "generated")
OUT = "/tmp/judge-batch"; os.makedirs(OUT, exist_ok=True)
MODEL = "google/gemini-2.5-pro"
VISION = "https://queue.fal.run/openrouter/router/vision"


def _key(name):
    for p in (os.path.join(ROOT, ".dev.vars"), "/Users/conner/dev/central/.env"):
        if os.path.exists(p):
            for line in open(p):
                if line.startswith(name + "="): return line.split("=", 1)[1].strip()
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
    "This is the PAINTED hardware of a skeuomorphic music player. Judge ONLY the transport BUTTON cluster "
    "(play / stop / previous-rewind / next-forward). Are the buttons EVENLY SPACED, consistently sized (play "
    "may be bigger), cleanly formed and seated in one tidy row/housing — like real manufactured hardware? "
    "Uneven gaps, crowded/drifting keys, tilted/distorted/merged buttons, or a missing button = FAIL. Ignore "
    "knobs, screens, colors, and art style.\n\n"
    'Return ONLY strict JSON: {\"buttons_perfect\":true|false,\"issue\":\"<short, or empty>\",\"score\":<0-100>}'
)


def image_for(skin):
    from PIL import Image
    frame = os.path.join(GEN, f"{skin}-frame.png")
    if os.path.exists(frame):
        im = Image.open(frame).convert("RGBA"); bg = Image.new("RGBA", im.size, (26, 26, 28, 255))
        bg.alpha_composite(im); out = bg.convert("RGB")
    else:
        paint = os.path.join(GEN, f"{skin}-paint.png")
        lay = json.load(open(os.path.join(GEN, f"{skin}-layout.json")))
        df = lay.get("devFrac", 0.84)
        im = Image.open(paint).convert("RGB"); W, H = im.size
        out = im.crop((0, 0, W, int(H * df)))
    p = os.path.join(OUT, f"{skin}.png"); out.save(p); return p


def judge_once(url):
    payload = {"model": MODEL, "reasoning": True, "max_tokens": 3500, "temperature": 0,
               "image_urls": [url], "prompt": PROMPT}
    sub = _req(VISION, json.dumps(payload).encode(), {"Authorization": f"Key {FAL}", "Content-Type": "application/json"})
    t0 = time.time()
    while True:
        st = _req(sub["status_url"], headers={"Authorization": f"Key {FAL}"})
        if st.get("status") == "COMPLETED": break
        if st.get("status") in ("FAILED", "ERROR") or time.time() - t0 > 180: raise RuntimeError(st)
        time.sleep(2)
    out = _req(sub["response_url"], headers={"Authorization": f"Key {FAL}"}).get("output", "")
    s, e = out.find("{"), out.rfind("}")
    return json.loads(out[s:e + 1]) if s >= 0 else {"buttons_perfect": False, "issue": "no-json", "score": 0}


def judge(skin, runs):
    url = upload(image_for(skin))
    res = []
    for _ in range(runs):
        try: res.append(judge_once(url))
        except Exception as ex: res.append({"buttons_perfect": False, "issue": str(ex)[:40], "score": 0})
    passes = sum(1 for r in res if r.get("buttons_perfect"))
    scores = [r.get("score", 0) for r in res]
    ok = passes > runs / 2
    issues = [r.get("issue", "") for r in res if not r.get("buttons_perfect") and r.get("issue")]
    print(f"[{skin[:40]:40}] {'PASS' if ok else 'FAIL'}  {passes}/{runs} perfect  scores={scores}"
          + (f"  e.g. {issues[0]}" if issues else ""))
    return ok


if __name__ == "__main__":
    if not FAL: raise SystemExit("FAL_KEY not found")
    runs = 3
    args = sys.argv[1:]
    if "--runs" in args: i = args.index("--runs"); runs = int(args[i + 1]); args = args[:i] + args[i + 2:]
    results = {s: judge(s, runs) for s in args}
    allok = all(results.values())
    print(f"\n=== {sum(results.values())}/{len(results)} skins pass · ALL_BUTTONS_PERFECT={allok} ===")
    sys.exit(0 if allok else 1)
