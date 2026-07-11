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
# [[sota-eye-review-rule]] crop discipline: pad = 0.5 -> crop box is (1 + 2*0.5) = 2x the
# control's own extent per axis. Anchor is `r["device"]` — extract12.py's DETECTED/aligned
# rect from regions.json, never a template-expected position. Wide pad makes mis-anchoring
# (layout drift) visible instead of silently framing garbage the VLM would judge as real.
CROP_PAD = 0.5

def crop(img, dev, pad=CROP_PAD):
    x, y, w, h = dev
    y, h = y / DEVF, h / DEVF          # device-frac -> phone-frac (phone bg is width-fit)
    px, py = w * pad, h * pad
    box = (max(0, (x - px)) * W, max(0, (y - py)) * H,
           min(1, (x + w + px)) * W, min(1, (y + h + py)) * H)
    c = img.crop(tuple(int(v) for v in box))
    return c.resize((c.width * 3, c.height * 3), Image.LANCZOS)

names = []
crop_files = []  # (label, path) — supplements sent to the VLM alongside the mandatory full frame
for k, r in regs["regions"].items():
    if not r.get("device"): continue
    p = os.path.join(OBS, f"crop-{k}.png")
    crop(full, r["device"]).save(p)
    crop_files.append((k, p))
    if ROLES.get(k) in ("toggle", "knob", "slider"):
        pa = os.path.join(OBS, f"crop-{k}-after.png")
        crop(after, r["device"]).save(pa)
        crop_files.append((f"{k}-after", pa))
    names.append(k)
print(f"[observe] {SID}: full+after frames, {len(names)} control crops -> {OBS}")

if VLM:
    import requests
    KEY = None
    for line in open(os.path.expanduser("~/dev/central/.env")):
        m = re.match(r"\s*FAL_KEY\s*=\s*(.+)", line)
        if m: KEY = m.group(1).strip().strip('"').strip("'")
    ctrls = ", ".join(f"{k} ({ROLES.get(k, '?')})" for k in names)
    # [[sota-eye-review-rule]] crop discipline: images 1-2 are ALWAYS the full frame (before,
    # after) — the ground truth. Images 3+ are per-control crop SUPPLEMENTS, wide-padded
    # (2x extent) and anchored on detected regions.json rects, never template-expected ones.
    # The model must say CROP-MISS on a crop rather than judge whatever filled the frame.
    crop_order = ", ".join(f"[{i+3}]={label}" for i, (label, _) in enumerate(crop_files))
    prompt = (
        f"This is a rendered skeuomorphic music-player skin ('{SID}'). Controls and roles: {ctrls}. "
        "Image [1] is the FULL rendered frame before interaction; image [2] is the FULL frame "
        "after interaction (toggle/knob/seek exercised) — these two are the primary evidence and "
        "always show the whole device. "
        + (f"Images [3..] are wide-padded close-up crops of individual controls, in this order: "
           f"{crop_order}. Each crop is a SUPPLEMENT for precision, not independent evidence — "
           "if a crop does not clearly contain the named control (wrong content fills the frame, "
           "control absent, or ambiguous), say CROP-MISS for that control and judge it from the "
           "full frame instead. Do not judge what isn't there. " if crop_files else "")
        + "For EACH named control report SEATED-CORRECTLY, BROKEN, or CROP-MISS (what's wrong: "
        "missing sprite, misplaced, wrong scale, exposure blowout, baked text label). Designed "
        "asymmetries are OK: toggle OFF/ON states may legitimately differ in silhouette (creative "
        "switch mechanisms), sprites are theme-styled so unusual shapes are fine if seated in a "
        "plausible socket. Also flag any visible text/words baked into the device (it must be "
        "wordless). End with exactly one line: VERDICT: PASS or VERDICT: FAIL."
    )
    def b64(p):
        return "data:image/png;base64," + base64.b64encode(open(p, "rb").read()).decode()
    image_urls = [b64(os.path.join(OBS, "full.png")), b64(os.path.join(OBS, "after.png"))]
    image_urls += [b64(p) for _, p in crop_files]
    body = {"prompt": prompt, "model": "google/gemini-2.5-pro", "reasoning": True,
            "image_urls": image_urls}
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
    # a control the model flags CROP-MISS on is UNMEASURED, not a fail of the control itself —
    # it's a harness anchoring miss, not evidence anything is broken. Scan per named control for
    # "<name> ... CROP-MISS" on the same line/near it in the raw text.
    unmeasured = sorted({k for k in names
                          if re.search(rf"\b{re.escape(k)}\b[^\n]{{0,80}}CROP-MISS", str(text), re.I)})
    rec = {"skin": SID, "eye": "fal openrouter/router/vision (google/gemini-2.5-pro)",
           "verdict": verdict, "raw": text,
           "frames": ["full.png", "after.png"] + [f"crop-{label}.png" for label, _ in crop_files],
           "unmeasured_crop_miss": unmeasured,
           "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    json.dump(rec, open(os.path.join(OBS, "observe.json"), "w"), indent=2)
    print(f"[observe] {SID}: VLM verdict {verdict} (google/gemini-2.5-pro via fal)")
