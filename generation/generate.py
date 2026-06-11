#!/usr/bin/env python3
"""Generate styled skin layers from the neutral control blueprint via fal
gpt-image-1.5/edit. Uploads the control once, submits one edit job per skin in
parallel, polls the queue, and downloads each result to public/skins/<id>/frame.png.

The prompt asks the model to restyle the blueprint IN PLACE (preserving layout)
and to keep the recessed screens EMPTY so live React content shows through.
"""
import base64, json, os, sys, time, urllib.request, urllib.error, concurrent.futures

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def fal_key():
    for line in open("/Users/conner/dev/central/.env"):
        if line.startswith("FAL_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("no FAL_KEY")

KEY = fal_key()
H = {"Authorization": f"Key {KEY}", "Content-Type": "application/json"}

def post(url, body, headers=H):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())

def get(url):
    req = urllib.request.Request(url, headers={"Authorization": f"Key {KEY}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())

def upload(path):
    """Upload a local file to fal storage, return CDN url."""
    name = os.path.basename(path)
    init = post("https://rest.alpha.fal.ai/storage/upload/initiate",
                {"file_name": name, "content_type": "image/png"})
    upload_url = init["upload_url"]
    data = open(path, "rb").read()
    req = urllib.request.Request(upload_url, data=data, method="PUT",
                                 headers={"Content-Type": "image/png"})
    urllib.request.urlopen(req, timeout=120)
    return init["file_url"]

BASE = (
    "Photorealistic 3D-rendered skeuomorphic media-player skin, front-on orthographic "
    "view, no perspective, even studio lighting, crisp and high detail, fills the frame. "
    "Restyle this UI blueprint EXACTLY as laid out: every button, slider and screen keeps "
    "its exact position, size and shape. The rounded rectangular buttons are RAISED, "
    "physically pressable, with bevelled edges and their text labels kept legible and "
    "embossed. The thin horizontal and vertical slider tracks are RECESSED EMPTY grooves "
    "with NO knob or handle (the handle is added separately). The large flat dark "
    "rectangles are INSET GLASS SCREENS — keep them COMPLETELY DARK and EMPTY: no text, "
    "no numbers, no letters, no graphics, a switched-off black-glass look. Do not add "
    "extra decoration that covers the controls. "
)

SKINS = {
    "winamp": BASE + (
        "MATERIAL: late-1990s Winamp player — brushed gunmetal and dark charcoal plastic "
        "casing with a subtle metallic sheen, thin polished chrome bevels and tiny philips "
        "screws in the corners. Buttons are dark grey plastic with bright specular "
        "highlights; the EQ slider knobs are small chrome caps; the toggle buttons glow a "
        "faint LED green. Screens are near-black glass."
    ),
    "fallout": BASE + (
        "MATERIAL: Fallout Pip-Boy 3000 retro-futuristic device — scuffed dark olive-green "
        "metal casing with rivets and worn paint, the whole unit tinted monochrome amber-"
        "green phosphor. Buttons are chunky industrial bakelite knobs and toggles. Slider "
        "tracks are metal channels. Screens are dark curved CRT glass with a faint green "
        "phosphor vignette, empty and switched off."
    ),
    "warcraft": BASE + (
        "MATERIAL: Warcraft III fantasy game interface — a carved dark grey stone panel "
        "bordered by ornate engraved bronze and gold filigree with gemstone accents and "
        "rivets. Buttons are polished stone tiles rimmed in gold; toggle buttons are glowing "
        "amber gems; slider knobs are faceted gold gems in stone channels. Screens are "
        "obsidian black glass framed by engraved bronze, empty and dark."
    ),
}

def submit(control_url, prompt):
    return post("https://queue.fal.run/fal-ai/gpt-image-1.5/edit", {
        "prompt": prompt,
        "image_urls": [control_url],
        "image_size": "1024x1536",
        "quality": "high",
        "input_fidelity": "high",
        "background": "opaque",
        "output_format": "png",
    })

def poll_and_download(skin, job):
    status_url = job["status_url"]
    response_url = job["response_url"]
    t0 = time.time()
    while True:
        st = get(status_url)
        s = st.get("status")
        if s == "COMPLETED":
            break
        if s in ("FAILED", "ERROR"):
            print(f"[{skin}] FAILED: {st}", flush=True)
            return None
        if time.time() - t0 > 600:
            print(f"[{skin}] timeout", flush=True)
            return None
        time.sleep(4)
    res = get(response_url)
    url = res["images"][0]["url"]
    outdir = os.path.join(ROOT, "public", "skins", skin)
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "frame.png")
    urllib.request.urlretrieve(url, out)
    print(f"[{skin}] done in {time.time()-t0:.0f}s -> {out}", flush=True)
    return out

def main():
    print("uploading control...", flush=True)
    control_url = upload(os.path.join(HERE, "control.png"))
    print("control:", control_url, flush=True)
    jobs = {}
    for skin, prompt in SKINS.items():
        jobs[skin] = submit(control_url, prompt)
        print(f"[{skin}] submitted {jobs[skin]['request_id']}", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(poll_and_download, s, j): s for s, j in jobs.items()}
        for f in concurrent.futures.as_completed(futs):
            f.result()
    print("ALL DONE", flush=True)

if __name__ == "__main__":
    main()
