#!/usr/bin/env python3
"""WILD Y2K bodies with EMPTY MOUNTING WELLS — the full layered stack:

  layer 1: gpt-image-2 designs a wildly-shaped 90s/Y2K player body (pod, blob,
           creature) with EMPTY screens and EMPTY recessed mounting wells
           (sockets where controls mount). BiRefNet cuts the silhouette.
  layer 2: the per-style AI control SPRITES (switch states, knob, button,
           thumb) mount into the wells at runtime — real reactive parts.
  layer 3: live screens (spectrum, playlist...) into CV-detected screen rects.

Wells are extracted by a vision pass tuned to EMPTY sockets (shape → kind),
then bound: button wells by x → transport, round wells → vol/bal, vertical
slots → EQ bands, the long groove → seek, small rect wells → switches.

Usage: python3 wild_y2k.py            # all variants
       python3 wild_y2k.py pod        # one
"""
import base64, json, os, subprocess, sys, time, urllib.request, concurrent.futures
import generate as G
import detect_screens as DS

ROOT = os.path.dirname(G.HERE)
W, H = 1024, 1536

# extract_wells() below is Gemini 3.1 Pro via VERTEX AI (gcloud user-auth access
# token) — ZERO OpenAI/gpt-4o. Same project + auth pattern proven working by
# tools/mask-align-exp/gen12/genskin.py's edit_vertex().
VERTEX_PROJECT = os.environ.get("VERTEX_PROJECT", "muser-2605300220")
VERTEX_MODEL = "gemini-3.1-pro-preview"
VERTEX_URL = (f"https://aiplatform.googleapis.com/v1/projects/{VERTEX_PROJECT}/locations/global/"
              f"publishers/google/models/{VERTEX_MODEL}:generateContent")

BODY = (
    "Design a WILDLY NON-RECTANGULAR skeuomorphic MP3-player device in late-90s Winamp-skin / Y2K style: "
    "an irregular asymmetric silhouette — {shape}. Front-on orthographic, centered on a FLAT pure-white "
    "background, no shadow outside the device, high detail. The device has: ONE wide rectangular DISPLAY "
    "screen in the upper half and ONE large rectangular PLAYLIST screen in the lower half — both "
    "COMPLETELY EMPTY switched-off dark glass (no text, no graphics). Plus EMPTY RECESSED MOUNTING WELLS "
    "(bare empty sockets — NO controls mounted in them, nothing inside): a neat row of FIVE small "
    "rounded-square wells (for transport buttons), TWO round circular wells (for knobs), a row of SIX "
    "short VERTICAL slot channels (for EQ faders), ONE long thin HORIZONTAL groove (for the seek "
    "slider), and TWO small rectangular wells (for flip switches). Every well is clearly visible, "
    "clearly empty, recessed into the body. MATERIAL: {mat}"
)

VARIANTS = {
    "pod":    {"style": "winamp",  "name": "Y2K Pod ✦",     "shape": "a swooping chrome alien pod with two horn-like fins, asymmetric bulges and little feet",
               "mat": "polished chrome and brushed gunmetal with dark plastic inserts, green LED accents — classic Winamp-skin hardware."},
    "wasp":   {"style": "fallout", "name": "Rust Wasp ✦",   "shape": "an insectoid rounded body with an antenna stalk, a side pod and stubby legs",
               "mat": "scuffed olive-drab riveted metal, retro-industrial RobCo style with amber-green accents."},
    "splash": {"style": "aqua",    "name": "Aqua Splash ✦", "shape": "a melting liquid splash / amoeba outline with rounded lobes and a tail drip",
               "mat": "glossy translucent white and candy-blue Aqua gel over brushed aluminium, bright highlights."},
}

EXTRACT_WELLS = (
    "You are a precise UI layout parser. The image shows a custom-shaped music-player DEVICE with EMPTY "
    "recessed mounting WELLS (empty sockets) and two dark SCREENS. Return STRICT JSON "
    '{"regions":[{"kind":"...","x":0..1,"y":0..1,"w":0..1,"h":0..1}]} with x,y = TOP-LEFT, normalized to '
    "the FULL image. Classify each EMPTY well by its shape: small rounded-square or rectangular wells in "
    "a horizontal row → kind=button (one region PER well); round circular wells → kind=knob; short "
    "vertical slot channels → kind=slider-v (one per slot); one long thin horizontal groove → "
    "kind=slider-h; small standalone rectangular wells (not in the button row) → kind=toggle. Do NOT "
    "include the dark screens. Find EVERY well. Return ONLY the JSON."
)

def gen_body(key):
    v = VARIANTS[key]
    job = G.post("https://queue.fal.run/openai/gpt-image-2", {
        "prompt": BODY.format(shape=v["shape"], mat=v["mat"]),
        "image_size": {"width": W, "height": H}, "quality": "high", "output_format": "png"})
    t0 = time.time()
    while True:
        s = G.get(job["status_url"]).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): raise SystemExit(f"{key} body FAIL")
        if time.time() - t0 > 520: raise SystemExit(f"{key} timeout")
        time.sleep(4)
    url = G.get(job["response_url"])["images"][0]["url"]
    print(f"[{key}] body {time.time()-t0:.0f}s", flush=True)
    return url

def cutout(url):
    job = G.post("https://queue.fal.run/fal-ai/birefnet/v2", {
        "image_url": url, "model": "General Use (Heavy)",
        "operating_resolution": "2048x2048", "refine_foreground": True, "output_format": "png"})
    t0 = time.time()
    while True:
        s = G.get(job["status_url"]).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): raise SystemExit("cutout FAIL")
        if time.time() - t0 > 300: raise SystemExit("cutout timeout")
        time.sleep(3)
    return G.get(job["response_url"])["image"]["url"]

def extract_wells(image_url):
    """Vision-locate empty mounting wells. Ported 2026-07 from OpenAI gpt-4o
    (api.openai.com) to Gemini 3.1 Pro via Vertex AI — same gcloud user-auth
    access-token pattern as genskin.py:edit_vertex(). No OpenAI key needed."""
    tok = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    img_bytes = urllib.request.urlopen(image_url, timeout=60).read()
    b64 = base64.b64encode(img_bytes).decode()
    body = {
        "contents": [{"role": "user", "parts": [
            {"inline_data": {"mime_type": "image/png", "data": b64}},
            {"text": "Find every empty mounting well."},
        ]}],
        "systemInstruction": {"role": "system", "parts": [{"text": EXTRACT_WELLS}]},
        # thinkingLevel "low": gemini-3.1-pro-preview defaults to "high" thinking, which
        # (verified live 2026-07-10) burns the ENTIRE maxOutputTokens budget on internal
        # thought tokens before emitting any JSON (finishReason MAX_TOKENS, zero content)
        # for a short structured-extraction call like this one.
        "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 4000,
                              "thinkingConfig": {"thinkingLevel": "low"}},
    }
    req = urllib.request.Request(VERTEX_URL, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}, method="POST")
    resp = json.loads(urllib.request.urlopen(req, timeout=180).read())
    content = "".join(p.get("text", "") for p in resp["candidates"][0]["content"]["parts"])
    return json.loads(content).get("regions", [])

TRANSPORT = ["prev", "play", "pause", "stop", "next", "eject"]
def build_template(dirpath, wells):
    frame = os.path.join(dirpath, "frame.png")
    Wf, Hf, boxes = DS.detect(frame)
    regions = []
    for (x0, y0, bw, bh, _), role in DS.assign(boxes):
        regions.append({"id": role, "kind": "display", "content": "dynamic", "layer": "screen",
                        "dynamicType": role, "rect": {"x": x0/Wf, "y": y0/Hf, "w": bw/Wf, "h": bh/Hf}})
    btns = sorted([w for w in wells if w["kind"] == "button"], key=lambda w: (round(w["y"],2), w["x"]))
    knobs = sorted([w for w in wells if w["kind"] == "knob"], key=lambda w: w["x"])
    slvs = sorted([w for w in wells if w["kind"] == "slider-v"], key=lambda w: w["x"])
    slhs = [w for w in wells if w["kind"] == "slider-h"]
    togs = sorted([w for w in wells if w["kind"] == "toggle"], key=lambda w: w["x"])
    def rect(w): return {"x": float(w["x"]), "y": float(w["y"]), "w": float(w["w"]), "h": float(w["h"])}
    for i, w in enumerate(btns[:6]):
        b = TRANSPORT[i] if i < len(TRANSPORT) else "presetNext"
        regions.append({"id": b, "kind": "button", "content": "sprite", "layer": "components",
                        "bind": b, "label": b, "rect": rect(w)})
    for i, w in enumerate(knobs[:2]):
        regions.append({"id": f"knob{i}", "kind": "knob", "content": "sprite", "layer": "components",
                        "bind": ["volume", "balance"][i], "label": ["VOL", "BAL"][i], "rect": rect(w)})
    for i, w in enumerate(slvs):
        regions.append({"id": f"eq{i}", "kind": "slider-v", "content": "sprite", "layer": "components",
                        "bind": "eqBand", "group": "eq-bands", "index": i, "label": str(i), "rect": rect(w)})
    for w in slhs[:1]:
        regions.append({"id": "seek", "kind": "slider-h", "content": "sprite", "layer": "components",
                        "bind": "seek", "label": "Seek", "rect": rect(w)})
    for i, w in enumerate(togs[:3]):
        regions.append({"id": f"sw{i}", "kind": "toggle", "content": "sprite", "layer": "components",
                        "bind": ["shuffle", "eqOn", "mute"][i], "label": ["SHUF", "EQ", "MUTE"][i], "rect": rect(w)})
    tpl = {"id": os.path.basename(dirpath), "name": "wild-y2k", "canvas": {"w": Wf, "h": Hf}, "regions": regions}
    json.dump(tpl, open(os.path.join(dirpath, "template.json"), "w"), indent=2)
    return len(regions)

def do(key):
    url = gen_body(key)
    cut = cutout(url)
    dest = os.path.join(ROOT, "public", "skins", f"y2k-{key}")
    os.makedirs(dest, exist_ok=True)
    urllib.request.urlretrieve(cut, os.path.join(dest, "frame.png"))
    urllib.request.urlretrieve(url, os.path.join(G.HERE, "freeform", f"y2k-{key}-raw.png"))
    wells = extract_wells(url)
    n = build_template(dest, wells)
    print(f"[{key}] saved ({len(wells)} wells → {n} regions)", flush=True)

if __name__ == "__main__":
    keys = sys.argv[1:] or list(VARIANTS.keys())
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(do, keys))
    print("ALL DONE", flush=True)
