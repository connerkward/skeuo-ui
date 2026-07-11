#!/usr/bin/env python3
"""imgjson experiment — can gemini-3-pro-image-preview (the IMAGE model) emit usable
TEXT/JSON alongside or instead of its image output, and how does its spatial JSON
compare to gemini-3.1-pro-preview (the TEXT/director model)?

Ground truth: assets-wc-goldshield/regions.json "device" bboxes, verified by crop
(see docs/experiments write-up) to be normalized [x,y,w,h] over paint.png's own
pixel dimensions (2304x3712) — NOT the joint/mask/blueprint frame.

Three calls, same source image (paint.png, read-only) + same control roster:
  A. TEXT-only ask to the IMAGE model     (responseModalities: ["TEXT"])
  B. Interleaved ask to the IMAGE model   (responseModalities: ["TEXT","IMAGE"])
  C. Same JSON ask to the TEXT model      (gemini-3.1-pro-preview, responseMimeType
                                            application/json — the director's own
                                            proven pattern, ported from src/generate/director.ts)

Usage: python3 run_tests.py
Writes imgjson/out/{a,b,c}_raw.json (full Vertex response) + imgjson/out/results.json
(scored) + imgjson/out/*.png (any returned image parts, test B only).
"""
import os, sys, json, base64, subprocess, time
import requests
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GEN12 = os.path.dirname(HERE)
# paint.png/regions.json are gitignored (assets-*/paint.png) so a fresh worktree
# doesn't have them checked out — read them from the main shared checkout instead.
# Read-only reuse, never written to (git-worktree-rule: isolate WRITES, reads of
# untracked assets from the main tree are fine).
MAIN_GEN12 = "/Users/conner/dev/skeuo-ui/tools/mask-align-exp/gen12"
ASSET = os.path.join(MAIN_GEN12 if os.path.isdir(os.path.join(MAIN_GEN12, "assets-wc-goldshield"))
                      else GEN12, "assets-wc-goldshield")
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

VERTEX_PROJECT = os.environ.get("VERTEX_PROJECT", "muser-2605300220")
IMAGE_MODEL = "gemini-3-pro-image-preview"
TEXT_MODEL = "gemini-3.1-pro-preview"

def endpoint(model):
    return (f"https://aiplatform.googleapis.com/v1/projects/{VERTEX_PROJECT}/locations/global/"
            f"publishers/google/models/{model}:generateContent")

def token():
    return subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()

REGIONS = json.load(open(os.path.join(ASSET, "regions.json")))
ROSTER = list(REGIONS["regions"].keys())
ROLES = REGIONS["roles"]

PROMPT = (
    "This image is a top-down skeuomorphic media-player skin. It contains exactly these "
    "10 controls, each present exactly once: " + ", ".join(f"{n} ({ROLES[n]})" for n in ROSTER) + ".\n\n"
    "Return STRICT JSON ONLY — no markdown fence, no prose before or after — an array of "
    "objects, one per control, each shaped exactly:\n"
    '  {"name": "<one of the 10 names above>", "x": <float>, "y": <float>, '
    '"w": <float>, "h": <float>}\n'
    "x,y is the TOP-LEFT corner of a tight bounding box around that control's visible "
    "housing, and w,h its width/height — ALL FOUR normalized 0..1 against this image's own "
    "width and height (x+w<=1, y+h<=1). Do not include any control not in the list. Do not "
    "omit any control in the list."
)

INTERLEAVED_PROMPT = (
    PROMPT + "\n\nSeparately, also lightly re-render this exact image (same layout, same "
    "controls, same camera) with a subtle warmer color-grade pass. Return the JSON array as "
    "a TEXT part and the re-rendered image as an IMAGE part in the same response."
)


def _post_with_retry(url, body, tag):
    """429 retry (ported from genskin.py:edit_vertex_multi — same project has hit
    per-minute Vertex quota on this account before)."""
    r = None
    for attempt in range(5):
        r = requests.post(url, headers={
            "Authorization": f"Bearer {token()}", "Content-Type": "application/json"},
            json=body, timeout=300)
        if r.status_code == 429 and attempt < 4:
            wait = 20 * (attempt + 1)
            print(f"[{tag}] 429 rate-limited, retry {attempt+1}/5 in {wait}s", flush=True)
            time.sleep(wait)
            continue
        break
    if r.status_code != 200:
        raise RuntimeError(f"vertex({tag}) HTTP {r.status_code}: {r.text[:800]}")
    return r.json()


def call_image_model(prompt, modalities, seed=71):
    b64 = base64.b64encode(open(os.path.join(ASSET, "paint.png"), "rb").read()).decode()
    body = {
        "contents": [{"role": "user", "parts": [
            {"inline_data": {"mime_type": "image/png", "data": b64}},
            {"text": prompt},
        ]}],
        "generationConfig": {
            "responseModalities": modalities,
            "seed": seed,
            "candidateCount": 1,
        },
    }
    return _post_with_retry(endpoint(IMAGE_MODEL), body, "image")


def call_text_model(prompt, image_path):
    b64 = base64.b64encode(open(image_path, "rb").read()).decode()
    body = {
        "contents": [{"role": "user", "parts": [
            {"inline_data": {"mime_type": "image/png", "data": b64}},
            {"text": prompt},
        ]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingLevel": "low"},
        },
    }
    return _post_with_retry(endpoint(TEXT_MODEL), body, "text")


def extract_parts(resp):
    """Return (text_parts:list[str], image_bytes_list:list[bytes], finish_reason)."""
    cand = resp.get("candidates", [{}])[0]
    parts = cand.get("content", {}).get("parts", [])
    texts, imgs = [], []
    for p in parts:
        if p.get("text"):
            texts.append(p["text"])
        d = p.get("inlineData") or p.get("inline_data")
        if d and d.get("data"):
            if d["data"].startswith("<"):  # stripped-for-commit placeholder (see score.py)
                continue
            imgs.append(base64.b64decode(d["data"]))
    return texts, imgs, cand.get("finishReason")


def try_parse_json(text):
    """Extract usable JSON from a text blob that may carry markdown fences and/or
    "thinking"-style prose BEFORE the JSON (observed: the image model emits several
    paragraphs of chain-of-thought-style narration ahead of the actual JSON array
    even when asked for "STRICT JSON ONLY, no prose"). Strategy: strip fences, then
    try json.JSONDecoder().raw_decode() at every '[' / '{' candidate start (in
    order) — the first one that parses to a non-empty list/dict wins. raw_decode
    tolerates trailing garbage after the JSON, which a plain json.loads() cannot.
    Returns (obj or None, error or None)."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
        if t.lstrip().startswith("json"):
            t = t.lstrip()[4:]
    t = t.strip()
    dec = json.JSONDecoder()
    starts = [i for i, c in enumerate(t) if c in "[{"]
    last_err = "no '[' or '{' found in text"
    for i in starts:
        try:
            obj, _end = dec.raw_decode(t, i)
        except Exception as e:
            last_err = str(e)
            continue
        if isinstance(obj, (list, dict)) and len(obj) > 0:
            return obj, None
    return None, last_err


def run_test(name, fn):
    print(f"[{name}] calling vertex...", flush=True)
    t0 = time.time()
    resp = fn()
    dt = time.time() - t0
    json.dump(resp, open(os.path.join(OUT, f"{name}_raw.json"), "w"), indent=2)
    texts, imgs, finish = extract_parts(resp)
    print(f"[{name}] {dt:.1f}s finish={finish} text_parts={len(texts)} image_parts={len(imgs)}")
    for i, im in enumerate(imgs):
        p = os.path.join(OUT, f"{name}_img{i}.png")
        open(p, "wb").write(im)
        print(f"[{name}]   wrote {p} ({Image.open(p).size})")
    parsed = None
    err = None
    if texts:
        # Join with "" NOT "\n": Vertex splits the model's text stream into many
        # `text` parts at arbitrary byte boundaries — observed mid-number splits
        # ("0." | "3597") — so injecting newlines corrupts the JSON. Concatenated
        # verbatim, the stream reassembles exactly.
        parsed, err = try_parse_json("".join(texts))
    return {"name": name, "seconds": round(dt, 1), "finishReason": finish,
            "n_text_parts": len(texts), "n_image_parts": len(imgs),
            "raw_text": "".join(texts)[:6000], "parsed": parsed, "parse_error": err}


def probe_modalities():
    """Cheap capability probes, recorded for the docs write-up: what does the image
    model actually do for responseModalities=["TEXT"] alone, and ["IMAGE"] alone with
    a text-only-shaped prompt? Both fail fast (no polling loop), so cost is trivial."""
    out = {}
    try:
        call_image_model(PROMPT, ["TEXT"], seed=71)
        out["text_only_modalities"] = {"ok": True}
    except RuntimeError as e:
        out["text_only_modalities"] = {"ok": False, "error": str(e)[:400]}
    r = call_image_model(PROMPT, ["IMAGE"], seed=71)
    texts, imgs, finish = extract_parts(r)
    out["image_only_modalities_textprompt"] = {
        "finishReason": finish, "n_text_parts": len(texts), "n_image_parts": len(imgs),
        "usageMetadata": r.get("usageMetadata", {}),
    }
    json.dump(out, open(os.path.join(OUT, "modality_probes.json"), "w"), indent=2)
    print("[probe]", json.dumps(out, indent=2))
    return out


def main():
    print("=== capability probes ===")
    probe_modalities()
    time.sleep(15)
    print("=== scored tests ===")
    results = {}
    # EMPIRICAL FINDING (see docs/experiments write-up): responseModalities:["TEXT"]
    # alone is REJECTED by this model with HTTP 400 "The request is not supported by
    # this model" — the image model requires "IMAGE" present in the modalities list
    # even for a text/JSON-only ask. responseModalities:["IMAGE"] alone, given a
    # prompt that doesn't ask for an image, returns finishReason NO_IMAGE with ZERO
    # content (burns ~3100 thought tokens trying, then gives up). So the only modality
    # config that actually returns text for a JSON-only ask is ["TEXT","IMAGE"] combined
    # — it will emit text-only parts (no image) when the prompt doesn't request a re-render.
    results["a_text_only"] = run_test("a_text_only",
        lambda: call_image_model(PROMPT, ["TEXT", "IMAGE"]))
    time.sleep(15)
    results["b_interleaved"] = run_test("b_interleaved",
        lambda: call_image_model(INTERLEAVED_PROMPT, ["TEXT", "IMAGE"]))
    time.sleep(15)
    results["c_text_model"] = run_test("c_text_model",
        lambda: call_text_model(PROMPT, os.path.join(ASSET, "paint.png")))
    json.dump(results, open(os.path.join(OUT, "results_raw.json"), "w"), indent=2)
    print("\nwrote", os.path.join(OUT, "results_raw.json"))


if __name__ == "__main__":
    main()
