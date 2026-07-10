#!/usr/bin/env python3
"""FREEFORM → TEMPLATE → RESKIN.

1. Generate a media-player UI FREEFORM with gpt-image-2 (no blueprint).
2. EXTRACT a template (region boxes + kinds) from that image with Gemini 3.1 Pro
   via Vertex AI — the extracted layout becomes the new source of truth.
3. (reskin step lives in generate.py once template.json is swapped.)

Outputs to generation/freeform/:
  donor.png            the freeform-generated design
  template.json        extracted, schema-compatible template
  overlay.png          extracted boxes drawn over the donor (for verification)
"""
import base64, json, os, subprocess, time, urllib.request
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "freeform"); os.makedirs(OUT, exist_ok=True)

def key(name):
    for l in open("/Users/conner/dev/central/.env"):
        if l.startswith(name + "="): return l.split("=", 1)[1].strip()
FAL = key("FAL_KEY")

# extract() below is Gemini 3.1 Pro via VERTEX AI (gcloud user-auth access token) —
# ZERO OpenAI/gpt-4o. Same project + auth pattern proven working by
# tools/mask-align-exp/gen12/genskin.py's edit_vertex() (this machine is already
# `gcloud auth login`-ed against muser-2605300220).
VERTEX_PROJECT = os.environ.get("VERTEX_PROJECT", "muser-2605300220")
VERTEX_MODEL = "gemini-3.1-pro-preview"
VERTEX_URL = (f"https://aiplatform.googleapis.com/v1/projects/{VERTEX_PROJECT}/locations/global/"
              f"publishers/google/models/{VERTEX_MODEL}:generateContent")

def fpost(u, b):
    r = urllib.request.Request(u, data=json.dumps(b).encode(),
        headers={"Authorization": f"Key {FAL}", "Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(r, timeout=180).read())
def fget(u):
    r = urllib.request.Request(u, headers={"Authorization": f"Key {FAL}"})
    return json.loads(urllib.request.urlopen(r, timeout=180).read())

W, H = 1024, 1536

DONOR_PROMPT = (
    "A clean flat front-on screenshot of a SKEUOMORPHIC desktop MUSIC PLAYER application window, "
    "portrait orientation, on a plain neutral background. It clearly shows distinct physical controls: "
    "a row of round transport buttons (previous, play, pause, stop, next), one or two large rotary "
    "KNOBS, several vertical EQ slider faders in a row, a horizontal progress slider, a couple of "
    "rectangular toggle buttons, a small segmented switch, a wide dark rectangular DISPLAY screen at "
    "the top, and a large rectangular PLAYLIST area below. Every control is a clearly separated, "
    "well-spaced rectangle or circle. Realistic materials, soft shadows, high detail, no text content "
    "inside the screens. Straight-on orthographic, no perspective."
)

def generate_donor():
    job = fpost("https://queue.fal.run/openai/gpt-image-2", {
        "prompt": DONOR_PROMPT, "image_size": {"width": W, "height": H},
        "quality": "high", "output_format": "png"})
    t0 = time.time()
    while True:
        s = fget(job["status_url"]).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): raise SystemExit("donor gen failed")
        if time.time() - t0 > 400: raise SystemExit("donor timeout")
        time.sleep(4)
    url = fget(job["response_url"])["images"][0]["url"]
    urllib.request.urlretrieve(url, os.path.join(OUT, "donor.png"))
    print("donor ->", os.path.join(OUT, "donor.png"), "url", url, flush=True)
    return url

EXTRACT_SYS = (
    "You are a precise UI layout parser. Given a screenshot of a music-player UI, return STRICT JSON "
    "describing every interactive control and screen as bounding boxes. JSON shape: "
    '{"regions":[{"id":"snake_case","kind":"...","label":"...","x":0.0,"y":0.0,"w":0.0,"h":0.0}]}. '
    "Coordinates are NORMALISED 0..1 with x,y = TOP-LEFT corner, w,h = width/height fraction of the image. "
    "kind must be one of: button, toggle, slider-h, slider-v, knob, segmented, xy, display. "
    "Use 'display' for screens/LCDs/playlist areas. Use 'slider-v' for vertical EQ faders, 'slider-h' for "
    "horizontal progress/volume bars, 'knob' for round rotary dials. Identify EVERY distinct control. "
    "Return ONLY the JSON object."
)

def extract(donor_url):
    """Vision-locate every region in the freeform donor image. Ported 2026-07 from
    OpenAI gpt-4o (api.openai.com) to Gemini 3.1 Pro via Vertex AI — same gcloud
    user-auth access-token pattern as genskin.py:edit_vertex(). No OpenAI key needed."""
    tok = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    img_bytes = urllib.request.urlopen(donor_url, timeout=60).read()
    b64 = base64.b64encode(img_bytes).decode()
    body = {
        "contents": [{"role": "user", "parts": [
            {"inline_data": {"mime_type": "image/png", "data": b64}},
            {"text": "Parse this music-player UI into normalized region boxes."},
        ]}],
        "systemInstruction": {"role": "system", "parts": [{"text": EXTRACT_SYS}]},
        # thinkingLevel "low": gemini-3.1-pro-preview defaults to "high" thinking, which
        # (verified live 2026-07-10) burns the ENTIRE maxOutputTokens budget on internal
        # thought tokens before emitting any JSON (finishReason MAX_TOKENS, zero content)
        # for a short structured-extraction call like this one.
        "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 4000,
                              "thinkingConfig": {"thinkingLevel": "low"}},
    }
    r = urllib.request.Request(VERTEX_URL, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}, method="POST")
    resp = json.loads(urllib.request.urlopen(r, timeout=180).read())
    content = "".join(p.get("text", "") for p in resp["candidates"][0]["content"]["parts"])
    data = json.loads(content)
    regs = data.get("regions", [])
    print(f"extracted {len(regs)} regions", flush=True)
    return regs

LAYER = {"display": "screen"}
def to_template(regs):
    out = []
    for i, r in enumerate(regs):
        kind = r.get("kind", "button")
        content = "dynamic" if kind == "display" else "sprite"
        layer = "screen" if kind == "display" else "components"
        out.append({
            "id": r.get("id") or f"r{i}", "kind": kind, "content": content, "layer": layer,
            "rect": {"x": float(r["x"]), "y": float(r["y"]), "w": float(r["w"]), "h": float(r["h"])},
            "label": r.get("label", ""),
        })
    return {"id": "freeform", "name": "Freeform-extracted", "canvas": {"w": W, "h": H}, "regions": out}

COLOR = {"button": (59,130,246), "toggle": (34,197,94), "slider-h": (245,158,11),
         "slider-v": (168,85,247), "knob": (236,72,153), "segmented": (20,184,166),
         "xy": (139,92,246), "display": (14,165,233)}
def overlay(tpl):
    im = Image.open(os.path.join(OUT, "donor.png")).convert("RGB")
    d = ImageDraw.Draw(im, "RGBA")
    try: f = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 20)
    except: f = ImageFont.load_default()
    for r in tpl["regions"]:
        x0 = r["rect"]["x"]*W; y0 = r["rect"]["y"]*H
        x1 = x0 + r["rect"]["w"]*W; y1 = y0 + r["rect"]["h"]*H
        c = COLOR.get(r["kind"], (255,255,255))
        d.rectangle([x0,y0,x1,y1], outline=c+(255,), width=4)
        d.rectangle([x0,y0-20,x0+len(r["kind"])*11+6,y0], fill=c+(220,))
        d.text((x0+3,y0-20), r["kind"], fill=(0,0,0), font=f)
    im.save(os.path.join(OUT, "overlay.png"))
    print("overlay ->", os.path.join(OUT, "overlay.png"), flush=True)

if __name__ == "__main__":
    url = generate_donor()
    regs = extract(url)
    tpl = to_template(regs)
    json.dump(tpl, open(os.path.join(OUT, "template.json"), "w"), indent=2)
    overlay(tpl)
    print("DONE — review freeform/overlay.png")
