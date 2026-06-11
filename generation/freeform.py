#!/usr/bin/env python3
"""FREEFORM → TEMPLATE → RESKIN.

1. Generate a media-player UI FREEFORM with gpt-image-2 (no blueprint).
2. EXTRACT a template (region boxes + kinds) from that image with an OpenAI
   vision model — the extracted layout becomes the new source of truth.
3. (reskin step lives in generate.py once template.json is swapped.)

Outputs to generation/freeform/:
  donor.png            the freeform-generated design
  template.json        extracted, schema-compatible template
  overlay.png          extracted boxes drawn over the donor (for verification)
"""
import base64, json, os, time, urllib.request
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "freeform"); os.makedirs(OUT, exist_ok=True)

def key(name):
    for l in open("/Users/conner/dev/central/.env"):
        if l.startswith(name + "="): return l.split("=", 1)[1].strip()
FAL = key("FAL_KEY"); OPENAI = key("OPENAI_API_KEY")

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
    body = {
        "model": "gpt-4o",
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": EXTRACT_SYS},
            {"role": "user", "content": [
                {"type": "text", "text": "Parse this music-player UI into normalized region boxes."},
                {"type": "image_url", "image_url": {"url": donor_url, "detail": "high"}},
            ]},
        ],
        "max_tokens": 4000,
    }
    r = urllib.request.Request("https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {OPENAI}", "Content-Type": "application/json"}, method="POST")
    resp = json.loads(urllib.request.urlopen(r, timeout=180).read())
    content = resp["choices"][0]["message"]["content"]
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
