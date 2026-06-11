#!/usr/bin/env python3
"""Per-style freeform skins: for EACH style, gpt-image-2 designs a player with a
DISTINCT layout, OpenAI vision extracts a template, and Nano Banana reskins the
blueprint in that style. Each becomes a live skin with its OWN unique layout.

Publishes to public/skins/ff-<style>/{frame.png,template.json}.
"""
import json, os, subprocess, time, urllib.request, concurrent.futures
import generate as G
import freeform as F   # reuse extract() + EXTRACT_SYS + to_template()

HERE = G.HERE
ROOT = os.path.dirname(HERE)
TMP = os.path.join(HERE, "freeform")
os.makedirs(TMP, exist_ok=True)
W, H = 1024, 1536

BASE = (
    "A clean flat front-on screenshot of a SKEUOMORPHIC desktop MUSIC PLAYER application window, "
    "portrait, on a plain neutral background. Distinct, clearly-separated, well-spaced physical "
    "controls (each a clear rectangle or circle): transport buttons, knobs, vertical EQ faders, a "
    "horizontal slider, toggle buttons, a segmented switch, one or more dark rectangular DISPLAY "
    "screens, and a large PLAYLIST area. Realistic materials, soft shadows, high detail, no text "
    "inside the screens. Straight-on orthographic, no perspective. "
)
# a distinct LAYOUT per style so the six extracted templates differ
LAYOUTS = {
    "winamp":     "Layout: a wide top display, a single horizontal row of five round transport buttons, ten thin vertical EQ faders in a row, two small knobs at top-right, playlist filling the bottom third.",
    "fallout":    "Layout: two LARGE round dials dominate the top corners, a chunky rectangular screen between them, a column of stacked rocker buttons down the left, EQ faders across the middle, a wide playlist at the bottom.",
    "fantasy":    "Layout: symmetric and ornate — a tall central display flanked by two round gem-like knobs, transport buttons in a curved row beneath, EQ faders fanned in the middle, a framed playlist scroll at the bottom.",
    "aqua":       "Layout: wide and minimal — a long horizontal display across the top, a single row of pill buttons, a horizontal scrubber, three knobs on the right, a clean list below. Lots of whitespace.",
    "hifi":       "Layout: a wide receiver — one big tuning dial on the right, several rectangular push-buttons in two rows on the left, horizontal slider faders stacked in the middle, two long thin VU display strips at top.",
    "papercraft": "Layout: playful and slightly asymmetric — a square display top-left, a cluster of round buttons, knobs scattered, short EQ faders, a torn-edge playlist at the bottom.",
}
STYLES = list(LAYOUTS.keys())

def gen_donor(style):
    job = G.post("https://queue.fal.run/openai/gpt-image-2", {
        "prompt": BASE + LAYOUTS[style], "image_size": {"width": W, "height": H},
        "quality": "high", "output_format": "png"})
    t0 = time.time()
    while True:
        s = G.get(job["status_url"]).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): print(f"[{style}] donor FAIL"); return None
        if time.time() - t0 > 500: print(f"[{style}] donor timeout"); return None
        time.sleep(4)
    url = G.get(job["response_url"])["images"][0]["url"]
    urllib.request.urlretrieve(url, os.path.join(TMP, f"ff-{style}-donor.png"))
    print(f"[{style}] donor {time.time()-t0:.0f}s", flush=True)
    return url

# ---- behaviour binding inference (from publish_freeform) ----
def bind_for(label):
    l = (label or "").lower()
    if "prev" in l or "back" in l: return "prev"
    if "playlist" in l: return None
    if "play" in l: return "play"
    if "pause" in l: return "pause"
    if "stop" in l: return "stop"
    if "next" in l or "forward" in l or "skip" in l: return "next"
    if "eject" in l: return "eject"
    if "shuffle" in l: return "shuffle"
    return None

def enrich(tpl):
    knob_i = seg_i = vs_i = 0
    disp = [r for r in tpl["regions"] if r["kind"] == "display"]
    disp_s = sorted(disp, key=lambda r: r["rect"]["w"] * r["rect"]["h"], reverse=True)
    assign = {}
    if disp_s: assign[id(disp_s[0])] = "playlist"
    tops = sorted(disp_s[1:], key=lambda r: r["rect"]["y"])
    if tops: assign[id(tops[0])] = "marquee"
    if len(tops) > 1: assign[id(tops[1])] = "time"
    for r in tpl["regions"]:
        k = r["kind"]
        if k in ("button", "toggle"):
            b = bind_for(r.get("label"));
            if b: r["bind"] = b
        elif k == "knob":
            r["bind"] = ["volume", "balance"][min(knob_i, 1)]; knob_i += 1
        elif k == "segmented":
            r["bind"] = ["repeatMode", "eqPreset"][min(seg_i, 1)]
            r.setdefault("options", ["OFF", "1", "ALL"] if seg_i == 0 else ["FLAT", "ROCK", "POP", "JAZZ"]); seg_i += 1
        elif k == "slider-h":
            r["bind"] = "seek"
        elif k == "slider-v":
            r["bind"] = "eqBand"; r["group"] = "eq-bands"; r["index"] = vs_i; vs_i += 1
        elif k == "display":
            dt = assign.get(id(r))
            if dt: r["content"] = "dynamic"; r["layer"] = "screen"; r["dynamicType"] = dt
            else: r["content"] = "sprite"; r["layer"] = "screen"
    return tpl

def build_template(style, url):
    regs = F.extract(url)
    tpl = enrich(F.to_template(regs))
    dest = os.path.join(ROOT, "public", "skins", f"ff-{style}")
    os.makedirs(dest, exist_ok=True)
    tj = os.path.join(dest, "template.json")
    json.dump(tpl, open(tj, "w"), indent=2)
    # blueprint from this template
    ctrl = os.path.join(TMP, f"ff-{style}-control.png")
    subprocess.run(["python3", os.path.join(HERE, "render_control.py")],
                   env=dict(os.environ, TEMPLATE_JSON=tj, CONTROL_OUT=ctrl), check=True)
    print(f"[{style}] template {len(tpl['regions'])} regions", flush=True)
    return ctrl

def reskin(style, ctrl):
    cu = G.upload(ctrl)
    job = G.submit(cu, G.SKINS[style])
    t0 = time.time()
    while True:
        s = G.get(job["status_url"]).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): print(f"[{style}] reskin FAIL"); return
        if time.time() - t0 > 500: print(f"[{style}] reskin timeout"); return
        time.sleep(4)
    u = G.get(job["response_url"])["images"][0]["url"]
    out = os.path.join(ROOT, "public", "skins", f"ff-{style}", "frame.png")
    urllib.request.urlretrieve(u, out)
    print(f"[{style}] reskin {time.time()-t0:.0f}s -> {out}", flush=True)

def main():
    only = os.environ.get("ONLY")
    styles = [s for s in STYLES if (not only or s in only.split(","))]
    print("phase 1: donors", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        urls = dict(zip(styles, ex.map(gen_donor, styles)))
    print("phase 2: extract + blueprint", flush=True)
    ctrls = {}
    for s in styles:
        if urls.get(s): ctrls[s] = build_template(s, urls[s])
    print("phase 3: reskin", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(lambda s: reskin(s, ctrls[s]), [s for s in styles if s in ctrls]))
    print("ALL DONE", flush=True)

if __name__ == "__main__":
    main()
