#!/usr/bin/env python3
"""Gemini-gated BUTTON-alignment verifier.

For each skin: draw the template's interactive control rects (labelled) over the cut
frame.png, send to Gemini 2.5 Pro (the strongest vision model reachable via fal's
OpenRouter), and ask — per control — whether the app's rect sits PRECISELY on the
painted control/socket. Returns a strict JSON verdict so the result drives an automated
loop (NOT my own eyes). Buttons are the focus, but all interactive kinds are checked.

Usage: python3 verify.py <id> [<id> ...]
       (ids are filenames in public/generated/, without the -frame.png suffix)
"""
import json, os, sys, time, urllib.request, base64

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEN = os.path.join(ROOT, "public", "generated")
OUTDIR = "/tmp/align-verify"
os.makedirs(OUTDIR, exist_ok=True)
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


def overlay(skin):
    from PIL import Image, ImageDraw, ImageFont
    fr = Image.open(os.path.join(GEN, f"{skin}-frame.png")).convert("RGBA")
    bg = Image.new("RGBA", fr.size, (24, 24,27, 255)); bg.alpha_composite(fr)
    im = bg.convert("RGB"); W, H = im.size; d = ImageDraw.Draw(im)
    try: font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", max(16, W // 48))
    except: font = ImageFont.load_default()
    tpl = json.load(open(os.path.join(GEN, f"{skin}-template.json")))
    labels = []
    for r in tpl["regions"]:
        if r["kind"] not in CTRL: continue
        rc = r["rect"]; x0, y0 = rc["x"] * W, rc["y"] * H; x1, y1 = (rc["x"] + rc["w"]) * W, (rc["y"] + rc["h"]) * H
        name = r.get("bind") or r.get("id") or r["kind"]
        d.rectangle([x0, y0, x1, y1], outline=(0, 229, 255), width=max(3, W // 340))
        tb = d.textbbox((0, 0), name, font=font); tw = tb[2] - tb[0]
        ly = max(0, y0 - (tb[3] - tb[1]) - 4)
        d.rectangle([x0, ly, x0 + tw + 6, ly + (tb[3] - tb[1]) + 6], fill=(0, 0, 0))
        d.text((x0 + 3, ly + 2), name, fill=(0, 229, 255), font=font)
        labels.append(name)
    p = os.path.join(OUTDIR, f"{skin}-overlay.png"); im.save(p)
    return p, labels


PROMPT = (
    "This image shows a skeuomorphic music-player's PAINTED hardware with CYAN labelled boxes overlaid. "
    "Each cyan box is where the APP will place that control; it must sit PRECISELY on the matching painted "
    "control/socket (a painted button, knob, or slider groove). Judge ALIGNMENT ONLY — ignore art quality. "
    "For EACH labelled box decide if it is correctly aligned (centered on, and roughly the same size as, the "
    "painted control it names) or misaligned (offset in a direction, wrong size, on blank body, or on the wrong "
    "control). Be strict: a clearly visible offset is a FAIL.\n\n"
    "Return ONLY strict JSON, no prose:\n"
    '{\"controls\":[{\"name\":\"<label>\",\"aligned\":true|false,\"issue\":\"<short, or empty>\"}],'
    '\"buttons_all_aligned\":true|false,\"score\":<0-100 alignment score>}'
)


def gemini(url):
    payload = {"model": MODEL, "reasoning": True, "max_tokens": 4000, "temperature": 0,
               "image_urls": [url], "prompt": PROMPT}
    sub = _req(VISION, json.dumps(payload).encode(), {"Authorization": f"Key {FAL}", "Content-Type": "application/json"})
    t0 = time.time()
    while True:
        st = _req(sub["status_url"], headers={"Authorization": f"Key {FAL}"})
        if st.get("status") == "COMPLETED": break
        if st.get("status") in ("FAILED", "ERROR") or time.time() - t0 > 180: raise SystemExit(f"vision failed: {st}")
        time.sleep(2)
    res = _req(sub["response_url"], headers={"Authorization": f"Key {FAL}"})
    out = res.get("output", "")
    s = out.find("{"); e = out.rfind("}")
    return json.loads(out[s:e + 1]) if s >= 0 else {"raw": out}


def run(skin):
    p, labels = overlay(skin)
    v = gemini(upload(p))
    ctrls = v.get("controls", [])
    bad = [c for c in ctrls if not c.get("aligned")]
    print(f"\n[{skin}] score={v.get('score')} buttons_all_aligned={v.get('buttons_all_aligned')} "
          f"({len(ctrls)-len(bad)}/{len(ctrls)} aligned)  overlay={p}")
    for c in bad:
        print(f"    MISALIGNED {c.get('name'):10} {c.get('issue','')}")
    return v


if __name__ == "__main__":
    if not FAL: raise SystemExit("FAL_KEY not found")
    for sid in sys.argv[1:]:
        run(sid)
