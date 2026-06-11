#!/usr/bin/env python3
"""Generate all 6 skins via openai/gpt-image-2/edit for an A/B vs Nano Banana
Pro. Saves to /tmp/skeuo-gpt2/<skin>.png. Reuses prompts from generate.py."""
import os, time, urllib.request, concurrent.futures
import generate as G  # reuse SKINS, upload, post, get, KEY

def queue(body):
    return G.post("https://queue.fal.run/openai/gpt-image-2/edit", body)

def run(skin, prompt, control_url, out):
    job = queue({"prompt": prompt, "image_urls": [control_url],
                 "image_size": {"width": 1024, "height": 1536}, "quality": "high", "output_format": "png"})
    su, ru = job["status_url"], job["response_url"]
    t0 = time.time()
    while True:
        s = G.get(su).get("status")
        if s == "COMPLETED": break
        if s in ("FAILED", "ERROR"): print(f"[{skin}] FAIL", flush=True); return
        if time.time()-t0 > 400: print(f"[{skin}] timeout", flush=True); return
        time.sleep(4)
    url = G.get(ru)["images"][0]["url"]
    urllib.request.urlretrieve(url, f"{out}/{skin}.png")
    print(f"[{skin}] done {time.time()-t0:.0f}s", flush=True)

def main():
    out = "/tmp/skeuo-gpt2"; os.makedirs(out, exist_ok=True)
    cu = G.upload(os.path.join(G.HERE, "control.png"))
    print("control", cu, flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(lambda kv: run(kv[0], kv[1], cu, out), G.SKINS.items()))
    print("ALL DONE", flush=True)

if __name__ == "__main__":
    main()
