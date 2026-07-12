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
     observe.json {model, verdict, raw, per_control_defects, device_defects} next to crops.
Output: <assets>/observe/{full.png, after.png, crop-<control>.png, observe.json}
Usage: python3 observe12.py <assets-dir> [--vlm] [--url http://host:port/assets-x/player.html]

PROMPT RECALIBRATED 2026-07-11 (docs/experiments/2026-07-11-verification-recalibration.md):
the human review round (review-2026-07-11-round1.json) failed 0/15 skins the old
SEATED-CORRECTLY/BROKEN prompt had mostly passed — the old prompt only asked "is it seated",
never "does it FIT its slot", "is the slider thumb baked into the static art", "is the whole
device even right-side-up", "are there two of the same button". DEFECT_TAGS below is the fixed
taxonomy (also used to code the human's notes for eval scoring — see human_defects.json /
score_verification.py); the prompt now interrogates each tag explicitly per control PLUS one
device-level check (orientation/duplicates/phantoms aren't tied to a single control key).
"""
import os, re, sys, json, time, base64

# canonical defect vocabulary — kept in sync with human_defects.json's "_meta.taxonomy" and
# director_review.py's DEFECT_TAGS (independently duplicated there on purpose: director_review
# owns its own OpenAPI schema and this file is not a module director_review imports, same
# reasoning already used for crop() in that file's docstring).
PER_CONTROL_TAGS = ["baked-thumb", "sprite-slot-mismatch", "css-misalignment",
                     "silhouette-mismatch", "dead-control", "duplicate-control",
                     "phantom-control", "placement-wrong", "aesthetic"]
DEVICE_TAGS = ["orientation", "duplicate-control", "phantom-control", "aesthetic"]

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
    # a region entry can be a bare `null` when extract12 failed to detect that control at
    # all (e.g. n64-prerender-character's "repeat") — skip it rather than crash; it's a
    # missing-control signal, not something this pass fixes.
    if not r or not r.get("device"): continue
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
    tag_list = ", ".join(PER_CONTROL_TAGS)
    device_tag_list = ", ".join(DEVICE_TAGS)
    prompt = (
        f"This is a rendered skeuomorphic music-player skin ('{SID}'). Controls and roles: {ctrls}. "
        "Image [1] is the FULL rendered frame before interaction; image [2] is the FULL frame "
        "after interaction (toggle/knob/seek exercised) — these two are the primary evidence and "
        "always show the whole device. "
        + (f"Images [3..] are wide-padded close-up crops of individual controls, in this order: "
           f"{crop_order}. Some controls (toggle/knob/slider) have BOTH a plain crop and a "
           "'-after' crop of the SAME control post-interaction — compare that pair directly: if "
           "the two crops look visually identical despite the interaction script having dragged/"
           "clicked/toggled it, the control did not actually respond (tag dead-control). Each crop "
           "is a SUPPLEMENT for precision, not independent evidence — if a crop does not clearly "
           "contain the named control (wrong content fills the frame, control absent, or "
           "ambiguous), say CROP-MISS for that control and judge it from the full frame instead. "
           "Do not judge what isn't there. " if crop_files else "")
        + "Check EACH named control against this exact defect checklist, then report ONE line per "
        f"control in the EXACT format '<key>: OK' or '<key>: DEFECT[tag1,tag2] - <short detail>' "
        f"or '<key>: CROP-MISS' (tags MUST be chosen only from: {tag_list}). Checklist per control: "
        "(a) baked-thumb — for a slider specifically: is the moving thumb/handle actually a static "
        "part of the painted background art (never moves, or a second handle-shaped mark visibly "
        "duplicates the CSS-drawn one)? (b) sprite-slot-mismatch — does the moving/interactive "
        "sprite (thumb, switch lever/cap, knob cap) match its socket's SIZE and SHAPE — flag if "
        "visibly smaller/larger than the socket or a different shape than the cutout it sits in? "
        "(c) css-misalignment — for slider/seek specifically: does the CSS-drawn fill/track/thumb "
        "line up with the painted groove art, or does it look offset, clipped, or run past the "
        "groove's painted ends? (d) silhouette-mismatch — for a button with a pressed/depression "
        "look: does the depression shape match the button's OWN outline (a round button needs a "
        "round depression, a non-round button needs a matching non-round depression — a mismatched "
        "shape reads as a defect even though 'has a depression' alone is correct)? (e) dead-control "
        "— per the before/after crop comparison above. (f) placement-wrong — is the control "
        "rendered in a position/location that doesn't match a sane device layout for its role? "
        "(g) aesthetic — anything that reads as broken/confusing/illegible at a glance that isn't "
        "covered above (e.g. an indicator whose current state is ambiguous). Designed asymmetries "
        "are OK: toggle OFF/ON states may legitimately differ in silhouette (creative switch "
        "mechanisms), sprites are theme-styled so unusual shapes are fine IF seated correctly in a "
        "plausible, correctly-sized socket. Also flag any visible text/words baked into the device "
        "(it must be wordless) — tag that as aesthetic and describe it. "
        "\n\nAfter the per-control lines, output exactly one DEVICE-level line covering things not "
        f"tied to a single control, format 'DEVICE: [tag1,tag2] - <detail>' or 'DEVICE: none' (tags "
        f"only from: {device_tag_list}): (h) orientation — is the WHOLE device rendered upright and "
        "in a usable orientation (not rotated, not sideways, not upside-down, not viewed from a "
        "bizarre/unusable angle)? (i) duplicate-control — are there two or more copies of what "
        "should be a single control (e.g. two play buttons)? (j) phantom-control — is there a "
        "control-shaped decorative element in the art with NO corresponding named/functional "
        "control (a fake button that does nothing)? "
        "\n\nFinally, output exactly one line: VERDICT: PASS or VERDICT: FAIL. The verdict MUST be "
        "FAIL if ANY per-control line has a DEFECT tag, or the DEVICE line has any tag other than "
        "none — do not average defects away against an otherwise-nice render."
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
    # structured per-control / device defect tags, parsed from the model's own required line
    # format ('<key>: DEFECT[tag1,tag2] - detail' / 'DEVICE: [tag1,tag2] - detail') so
    # downstream scoring (score_verification.py) and any future dashboard consumer get an
    # exact tag match instead of having to re-guess keywords out of freeform prose.
    per_control_defects = {}
    for k in names:
        m = re.search(rf"^\s*{re.escape(k)}\s*:\s*DEFECT\[([^\]]*)\]", str(text), re.I | re.M)
        if m:
            tags = [t.strip() for t in m.group(1).split(",") if t.strip()]
            per_control_defects[k] = [t for t in tags if t in PER_CONTROL_TAGS]
    # tolerant of the model omitting the brackets (seen in practice, e.g. "DEVICE: aesthetic -
    # ..." instead of "DEVICE: [aesthetic] - ..."): capture up to " - " or end of line either way.
    dm = re.search(r"^\s*DEVICE\s*:\s*\[?([^\]\n]*?)\]?(?:\s*-.*)?$", str(text), re.I | re.M)
    device_defects = [t.strip() for t in dm.group(1).split(",") if t.strip() in DEVICE_TAGS] if dm else []
    rec = {"skin": SID, "eye": "fal openrouter/router/vision (google/gemini-2.5-pro)",
           "verdict": verdict, "raw": text,
           "frames": ["full.png", "after.png"] + [f"crop-{label}.png" for label, _ in crop_files],
           "unmeasured_crop_miss": unmeasured,
           "per_control_defects": per_control_defects, "device_defects": device_defects,
           "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    json.dump(rec, open(os.path.join(OBS, "observe.json"), "w"), indent=2)
    print(f"[observe] {SID}: VLM verdict {verdict} (google/gemini-2.5-pro via fal)")
