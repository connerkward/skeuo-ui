#!/usr/bin/env python3
"""observe12 — the [[skin-observation-rule]] pass, scripted. For one skin:
  1. drives the REAL served player headlessly (playwright): full screenshot, then
     interactions (seek jump, toggle click, knob pointer-drag, playpause click) and an
     after-interaction screenshot;
  2. cuts per-control close-up crops (3x upscaled) from the rendered screenshots using
     regions.json device rects — the crops ARE the observation, a full frame can't show
     ±px seating;
  3. (--vlm) sends frame + verdict prompt to a SOTA eye (Gemini via fal
     openrouter/router/vision, ~$0.01-0.03/call) per [[sota-eye-review-rule]] and writes
     observe.json {model, verdict, raw} next to the crops.
Output: <assets>/observe/{full.png, after.png, crop-<control>.png, observe.json}
Usage: python3 observe12.py <assets-dir> [--vlm] [--url http://host:port/assets-x/player.html]
"""
import os, re, sys, json, time, base64

OUT = os.path.abspath(sys.argv[1])
HERE = os.path.dirname(os.path.abspath(__file__))
SID = os.path.basename(OUT).replace("assets-", "")
OBS = os.path.join(OUT, "observe")
os.makedirs(OBS, exist_ok=True)
VLM = "--vlm" in sys.argv
URL = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--url=")), None)
if not URL:
    su = open(os.path.join(HERE, ".serve-url")).read().strip().rstrip("/")
    URL = f"{su}/assets-{SID}/player.html"

regs = json.load(open(os.path.join(OUT, "regions.json")))
ROLES = regs.get("roles", {})
DEVF = regs.get("devFrac", 1.0)

# browser driving lives in observe_drive.mjs (repo's node playwright — python playwright
# isn't installed here; the node dep already exists, don't add a second browser stack)
import subprocess
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
subprocess.run(["node", os.path.join(HERE, "observe_drive.mjs"), URL, OBS],
               cwd=REPO, check=True, timeout=120)

# per-control close-up crops (from BOTH frames for stateful controls)
from PIL import Image
full = Image.open(os.path.join(OBS, "full.png"))
after = Image.open(os.path.join(OBS, "after.png"))
W, H = full.size
def crop(img, dev, pad=0.35):
    x, y, w, h = dev
    y, h = y / DEVF, h / DEVF          # device-frac -> phone-frac (phone bg is width-fit)
    px, py = w * pad, h * pad
    box = (max(0, (x - px)) * W, max(0, (y - py)) * H,
           min(1, (x + w + px)) * W, min(1, (y + h + py)) * H)
    c = img.crop(tuple(int(v) for v in box))
    return c.resize((c.width * 3, c.height * 3), Image.LANCZOS)

names = []
for k, r in regs["regions"].items():
    if not r.get("device"): continue
    crop(full, r["device"]).save(os.path.join(OBS, f"crop-{k}.png"))
    if ROLES.get(k) in ("toggle", "knob", "slider"):
        crop(after, r["device"]).save(os.path.join(OBS, f"crop-{k}-after.png"))
    names.append(k)
print(f"[observe] {SID}: full+after frames, {len(names)} control crops -> {OBS}")

if VLM:
    import requests
    KEY = None
    for line in open(os.path.expanduser("~/dev/central/.env")):
        m = re.match(r"\s*FAL_KEY\s*=\s*(.+)", line)
        if m: KEY = m.group(1).strip().strip('"').strip("'")
    ctrls = ", ".join(f"{k} ({ROLES.get(k, '?')})" for k in names)
    prompt = (
        f"This is a rendered skeuomorphic music-player skin ('{SID}'). Controls and roles: {ctrls}. "
        "For EACH named control report SEATED-CORRECTLY or BROKEN (what's wrong: missing sprite, "
        "misplaced, wrong scale, exposure blowout, baked text label). Designed asymmetries are OK: "
        "toggle OFF/ON states may legitimately differ in silhouette (creative switch mechanisms), "
        "sprites are theme-styled so unusual shapes are fine if seated in a plausible socket. "
        "Also flag any visible text/words baked into the device (it must be wordless). "
        "End with exactly one line: VERDICT: PASS or VERDICT: FAIL."
    )
    def b64(p):
        return "data:image/png;base64," + base64.b64encode(open(p, "rb").read()).decode()
    body = {"prompt": prompt, "model": "google/gemini-2.5-pro", "reasoning": True,
            "image_urls": [b64(os.path.join(OBS, "full.png")), b64(os.path.join(OBS, "after.png"))]}
    q = requests.post("https://queue.fal.run/openrouter/router/vision",
                      headers={"Authorization": f"Key {KEY}", "Content-Type": "application/json"},
                      json=body).json()
    t0 = time.time()
    while True:
        s = requests.get(q["status_url"], headers={"Authorization": f"Key {KEY}"}).json().get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR") or time.time() - t0 > 180: raise RuntimeError(f"vlm {s}")
        time.sleep(3)
    r = requests.get(q["response_url"], headers={"Authorization": f"Key {KEY}"}).json()
    text = r.get("output") or r.get("text") or json.dumps(r)[:2000]
    verdict = "PASS" if re.search(r"VERDICT:\s*PASS", str(text)) else \
              "FAIL" if re.search(r"VERDICT:\s*FAIL", str(text)) else "UNPARSED"
    rec = {"skin": SID, "eye": "fal openrouter/router/vision (google/gemini-2.5-pro)",
           "verdict": verdict, "raw": text, "frames": ["full.png", "after.png"],
           "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    json.dump(rec, open(os.path.join(OBS, "observe.json"), "w"), indent=2)
    print(f"[observe] {SID}: VLM verdict {verdict} (google/gemini-2.5-pro via fal)")
