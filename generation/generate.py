#!/usr/bin/env python3
"""Generate styled skin layers from the neutral control blueprint via fal
gpt-image-1.5/edit. Uploads the control once, submits one edit job per skin in
parallel (transparent background so each skin keeps its OWN silhouette), polls,
and downloads to public/skins/<id>/frame.png.

Each prompt describes a distinct physical OBJECT (not a recolor) and tells the
model to richly ornament the decorative zones (corners, side rails, header
crest, bottom nameplate) while keeping the controls on their blueprint boxes,
screens empty, and slider channels knob-free.
"""
import json, os, time, urllib.request, concurrent.futures

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def fal_key():
    for line in open("/Users/conner/dev/central/.env"):
        if line.startswith("FAL_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("no FAL_KEY")

KEY = fal_key()
H = {"Authorization": f"Key {KEY}", "Content-Type": "application/json"}

def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=H, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r: return json.loads(r.read())
def get(url):
    req = urllib.request.Request(url, headers={"Authorization": f"Key {KEY}"})
    with urllib.request.urlopen(req, timeout=120) as r: return json.loads(r.read())

def upload(path):
    init = post("https://rest.alpha.fal.ai/storage/upload/initiate",
                {"file_name": os.path.basename(path), "content_type": "image/png"})
    req = urllib.request.Request(init["upload_url"], data=open(path, "rb").read(),
                                 method="PUT", headers={"Content-Type": "image/png"})
    urllib.request.urlopen(req, timeout=120)
    return init["file_url"]

COMMON = (
    "Photorealistic 3D-rendered skeuomorphic media-player SKIN, front-on orthographic view, "
    "no perspective, even soft studio lighting, crisp and high detail. Restyle this UI blueprint "
    "IN PLACE: every button, knob, slider, segmented switch and screen keeps its EXACT position, "
    "size and shape from the blueprint. The round circles are physical rotary KNOBS (body only, no "
    "pointer). The wide divided bars are SEGMENTED switches with their labels legible. The square "
    "dark pad is an inset control surface. The thin grooves are RECESSED EMPTY slider channels with "
    "NO handle. The flat rectangles are INSET SCREENS — keep them EMPTY (no text, no numbers, no "
    "graphics); give the LARGE lower playlist screen the SAME glass treatment as the small upper "
    "screens (do NOT render it plain white unless this skin's screens are explicitly white/paper). "
    "The small diamond-marked inset zones at the CORNERS, "
    "the two narrow vertical SIDE RAILS, the top-center CREST panel and the bottom NAMEPLATE are "
    "DECORATIVE — fill them with rich skin-appropriate ORNAMENT (not controls). Buttons carry their "
    "embossed labels. "
)

SKINS = {
    "winamp": COMMON + (
        "OBJECT: a late-1990s Winamp hardware player as a sleek rectangular brushed-gunmetal and "
        "dark-charcoal slab with crisp polished chrome bevels and tiny phillips screws at each corner. "
        "Knobs are knurled chrome; buttons are dark grey plastic with bright specular highlights; "
        "segmented switches are chrome rocker strips. Corner zones = chrome screw bosses; side rails = "
        "thin brushed-chrome strips; crest = an etched 'lightning bolt' chrome badge; nameplate = an "
        "engraved chrome plate. Screens are near-black glass. Cool grey + chrome palette."
    ),
    "fallout": COMMON + (
        "OBJECT: a Fallout Pip-Boy / RobCo industrial handheld — a chunky rounded olive-drab metal "
        "device with scuffed worn paint, exposed rivets and hex bolts, the whole casing tinted "
        "monochrome amber-green. Knobs are heavy ribbed bakelite dials; buttons are stubby industrial "
        "toggles; segmented switches are riveted metal selectors. Corner zones = riveted bolt plates; "
        "side rails = ribbed rubber grips; crest = a stencilled VAULT-TEC roundel; nameplate = a "
        "stamped serial-number plate. Screens are dark curved CRT glass. Olive-green + amber palette."
    ),
    "fantasy": COMMON + (
        "OBJECT: an ornate Baldur's-Gate / Warcraft-III fantasy console carved from cool gray-green "
        "dungeon stone, framed in bright gold filigree with mirror-symmetric scrollwork. Knobs are "
        "faceted amber gems set in brass; buttons are gold-inlaid icon tiles seated in chiselled stone "
        "wells; segmented switches are runed brass plaques. Corner zones = carved dragon-head / curling-"
        "vine gold ornaments; side rails = twisted gold rope with gem nodes; crest = a heraldic gold "
        "crest with a faceted red gem; nameplate = an engraved brass banner. Screens are obsidian glass "
        "rimmed in gold. Gray-green stone + brass-gold + gem palette. Hand-painted, weathered, gilded."
    ),
    "aqua": COMMON + (
        "OBJECT: an early-2000s Apple Mac OS X 'Aqua' application window — a glossy brushed-aluminium "
        "frame with faint horizontal pinstripes and a bright white top highlight. Knobs and buttons are "
        "glossy translucent 'lickable' aqua-gel lozenges (clear glass with a white top reflection and a "
        "soft blue tint); segmented switches are glossy gel pill toggles. Corner zones = subtle brushed-"
        "metal rivets; side rails = pinstriped aluminium strips; crest = a glossy aqua-blue badge; "
        "nameplate = an embossed aluminium label. Screens are pale glossy light-blue glass. Clean white, "
        "silver and candy-blue palette — bright and LIGHT, not dark."
    ),
    "hifi": COMMON + (
        "OBJECT: a 1970s wood-and-aluminium hi-fi stereo receiver — a wide brushed-aluminium faceplate "
        "framed by warm walnut-veneer wood end-caps. Knobs are big knurled silver dials with black "
        "pointers; buttons are rectangular brushed-aluminium push-keys; segmented switches are aluminium "
        "rocker banks; tiny amber pilot lamps glow. Corner zones = hex-screw aluminium corners; side "
        "rails = walnut wood strips with grain; crest = a brushed-metal logo plate; nameplate = an "
        "engraved model-number strip. Screens are warm fluorescent teal-green tuner glass. Silver "
        "aluminium + walnut brown + amber palette."
    ),
    "papercraft": COMMON + (
        "OBJECT: a hand-made papercraft / cardboard music player — built from folded kraft cardboard and "
        "layered cut-paper with visible fold creases, glue tabs, corrugated edges and soft matte paper "
        "drop-shadows (NO gloss, NO glow, NO metal). Knobs are paper discs; buttons are cut-paper tabs "
        "with little drop shadows and hand-drawn marker labels; segmented switches are folded paper "
        "strips. Corner zones = folded paper triangles; side rails = corrugated cardboard strips; crest "
        "= a cut-paper badge; nameplate = a strip of masking tape with marker writing. Screens are plain "
        "white paper. Warm kraft-tan + cream + red/teal marker palette. Tactile, low-tech, charming."
    ),
}

# GPT Image 2 (OpenAI's newest) — strongest prompt adherence + reference
# following; Gemini kept ignoring the brief and the reference character. Opaque
# output (the device fills the frame); the caller applies its own mask as alpha.
ENDPOINT = "openai/gpt-image-2/edit"
def submit(control_url, prompt, ref_urls=None):
    # The blueprint is the FIRST image (layout authority); any reference-style
    # images follow so the model borrows their shape/material/color/detail
    # vocabulary while keeping the blueprint's exact wells and silhouette.
    urls = [control_url] + list(ref_urls or [])
    return post(f"https://queue.fal.run/{ENDPOINT}", {
        "prompt": prompt, "image_urls": urls,
        "image_size": {"width": 1024, "height": 1536}, "quality": "high", "output_format": "png",
    })

def run(skin, job):
    su, ru = job["status_url"], job["response_url"]
    t0 = time.time()
    while True:
        s = get(su).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): print(f"[{skin}] FAILED", flush=True); return
        if time.time() - t0 > 600: print(f"[{skin}] timeout", flush=True); return
        time.sleep(4)
    url = get(ru)["images"][0]["url"]
    outdir = os.path.join(ROOT, "public", "skins", skin); os.makedirs(outdir, exist_ok=True)
    urllib.request.urlretrieve(url, os.path.join(outdir, "frame.png"))
    print(f"[{skin}] done {time.time()-t0:.0f}s", flush=True)

def main():
    only = os.environ.get("ONLY")
    skins = {k: v for k, v in SKINS.items() if (not only or k in only.split(","))}
    print("uploading control...", flush=True)
    cu = upload(os.path.join(HERE, "control.png"))
    print("control:", cu, flush=True)
    jobs = {s: submit(cu, p) for s, p in skins.items()}
    for s in jobs: print(f"[{s}] submitted", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(lambda kv: run(kv[0], kv[1]), jobs.items()))
    print("ALL DONE", flush=True)

if __name__ == "__main__":
    main()
