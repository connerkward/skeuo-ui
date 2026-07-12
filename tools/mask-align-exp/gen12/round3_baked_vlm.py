#!/usr/bin/env python3
"""round3_baked_vlm — VLM baked-knob (slider thumb) cross-check for the round-3 review page.

For each skin: crop paint.png around its "seek" slider's device rect (regions.json), padded
wide (2x extent, not a tight patch — the surrounding empty-vs-occupied groove is the signal),
send to Gemini via fal openrouter/router/vision with a prompt stating design intent (empty
groove is correct; a bright rounded blob/knob mid-groove is a defect; a flat fill-line/detent/
end-cap is not). Combines with the deterministic extract12.py `bakedThumb.flag` gate signal by
OR (favor recall — erase is cheap+idempotent+self-checking per generation-spend-rule, so
over-flagging costs ~$0.04-0.13 of erase compute, not a re-paint).

Writes round3-baked-vlm.json: {skin: {gate_flag, vlm_verdict, vlm_confidence, vlm_detail,
combined_flag, crop_path}}. Usage: python3 round3_baked_vlm.py
"""
import base64, json, os, re, time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
SKINS = ["claymation", "diablo-gothic", "fa-pod", "fallout-vault", "myst-arcanum",
          "n64-cutscene", "ps1-crunchy", "steam-porthole"]
PAD = 1.75  # crop = seek device rect expanded to (1+2*PAD)x... i.e. generous surrounding context
OUT_JSON = os.path.join(HERE, "round3-baked-vlm.json")
CROP_DIR = os.path.join(HERE, "round3-crops")
os.makedirs(CROP_DIR, exist_ok=True)

KEY = None
for line in open(os.path.expanduser("~/dev/central/.env")):
    m = re.match(r"\s*FAL_KEY\s*=\s*(.+)", line)
    if m:
        KEY = m.group(1).strip().strip('"').strip("'")

MODEL = "google/gemini-2.5-pro"
ENDPOINT = "https://queue.fal.run/openrouter/router/vision"
COST_PER_CALL = 0.02  # estimate, per media-attribution-rule / dev-facing-cost-annotation-rule


def crop_seek(skin):
    from PIL import Image
    assets = os.path.join(HERE, f"assets-{skin}")
    regs = json.load(open(os.path.join(assets, "regions.json")))
    dev = regs["regions"]["seek"]["device"]
    paint = Image.open(os.path.join(assets, "paint.png")).convert("RGB")
    W, H = paint.size
    x, y, w, h = dev
    px, py = w * PAD, h * PAD
    box = (max(0, (x - px)) * W, max(0, (y - py)) * H,
           min(1, (x + w + px)) * W, min(1, (y + h + py)) * H)
    box = tuple(int(v) for v in box)
    c = paint.crop(box)
    scale = max(1, min(4, 900 // max(1, c.width)))
    c = c.resize((c.width * scale, c.height * scale), Image.LANCZOS)
    p = os.path.join(CROP_DIR, f"{skin}-seek-crop.png")
    c.save(p)
    return p, regs["regions"]["seek"].get("bakedThumb", {})


def b64(p):
    return "data:image/png;base64," + base64.b64encode(open(p, "rb").read()).decode()


def call_vlm(skin, crop_path):
    prompt = (
        f"This is a padded crop of a skeuomorphic music-player skin's ('{skin}') SEEK/SCRUB "
        "slider groove, cropped from the raw PAINTED artwork (not the rendered UI). Design "
        "intent: after this pipeline's erase step, this slider's TRACK/GROOVE must be "
        "completely EMPTY — the app renders its OWN CSS-positioned thumb sprite on top at "
        "runtime, so any thumb/knob/handle graphic baked into this painted groove is a DEFECT "
        "(the shipped render would show two thumbs). "
        "A bright, rounded, raised-looking blob/knob/handle sitting mid-groove (not at the very "
        "outer end caps) = BAKED (defect). A flat horizontal fill-line, a subtle detent mark, "
        "rounded END CAPS of the housing itself, or a smooth ambient-light gradient spanning "
        "nearly the WHOLE channel = NOT a defect (CLEAN). "
        "Report in EXACTLY this format:\nVERDICT: BAKED or CLEAN\nCONFIDENCE: 0-100\n"
        "LOCATION: <where in the crop, e.g. 'left third of groove' or 'none'>\n"
        "DETAIL: <one sentence>"
    )
    body = {"prompt": prompt, "model": MODEL, "reasoning": True, "image_urls": [b64(crop_path)]}
    q = requests.post(ENDPOINT, headers={"Authorization": f"Key {KEY}", "Content-Type": "application/json"},
                       json=body).json()
    t0 = time.time()
    while True:
        s = requests.get(q["status_url"], headers={"Authorization": f"Key {KEY}"}).json().get("status")
        if s == "COMPLETED":
            break
        if s in ("FAILED", "ERROR") or time.time() - t0 > 180:
            raise RuntimeError(f"vlm {s} for {skin}")
        time.sleep(3)
    r = requests.get(q["response_url"], headers={"Authorization": f"Key {KEY}"}).json()
    text = str(r.get("output") or r.get("text") or json.dumps(r)[:2000])
    verdict = "BAKED" if re.search(r"VERDICT:\s*BAKED", text, re.I) else \
              "CLEAN" if re.search(r"VERDICT:\s*CLEAN", text, re.I) else "UNPARSED"
    cm = re.search(r"CONFIDENCE:\s*(\d+)", text, re.I)
    lm = re.search(r"LOCATION:\s*(.+)", text, re.I)
    dm = re.search(r"DETAIL:\s*(.+)", text, re.I)
    return {"verdict": verdict, "confidence": int(cm.group(1)) if cm else None,
            "location": lm.group(1).strip() if lm else None,
            "detail": dm.group(1).strip() if dm else None, "raw": text}


def main():
    if not KEY:
        raise SystemExit("FAL_KEY not found in central/.env")
    results = {}
    total_cost = 0.0
    for skin in SKINS:
        crop_path, gate = crop_seek(skin)
        gate_flag = bool(gate.get("flag"))
        print(f"[round3-vlm] {skin}: gate_flag={gate_flag} (runFrac={gate.get('runFrac')} "
              f"peak={gate.get('peak')}) -> calling VLM...", flush=True)
        vlm = call_vlm(skin, crop_path)
        total_cost += COST_PER_CALL
        combined = gate_flag or (vlm["verdict"] == "BAKED")
        results[skin] = {
            "gate_flag": gate_flag, "gate_runFrac": gate.get("runFrac"), "gate_peak": gate.get("peak"),
            "vlm_verdict": vlm["verdict"], "vlm_confidence": vlm["confidence"],
            "vlm_location": vlm["location"], "vlm_detail": vlm["detail"],
            "combined_flag": combined,
            "crop_path": os.path.relpath(crop_path, HERE),
            "model": MODEL, "cost_estimate": COST_PER_CALL,
        }
        print(f"[round3-vlm] {skin}: VLM={vlm['verdict']} (conf={vlm['confidence']}) "
              f"combined_flag={combined}", flush=True)
    json.dump({"skins": results, "total_cost_estimate": round(total_cost, 3),
                "model": MODEL, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")},
               open(OUT_JSON, "w"), indent=2)
    print(f"[round3-vlm] DONE -> {OUT_JSON}  total_cost~${total_cost:.3f}")


if __name__ == "__main__":
    main()
