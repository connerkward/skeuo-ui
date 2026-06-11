#!/usr/bin/env python3
"""Close the freeform loop: render a blueprint from the EXTRACTED template and
reskin it into a couple of styles via Nano Banana Pro. Proves freeform → template
→ reskin. Outputs to generation/freeform/."""
import os, subprocess, urllib.request, time
import generate as G

FF = os.path.join(G.HERE, "freeform")

def render_blueprint():
    env = dict(os.environ, TEMPLATE_JSON=os.path.join(FF, "template.json"),
               CONTROL_OUT=os.path.join(FF, "control.png"))
    subprocess.run(["python3", os.path.join(G.HERE, "render_control.py")], env=env, check=True)

def reskin(styles=("fantasy", "winamp")):
    cu = G.upload(os.path.join(FF, "control.png"))
    print("blueprint", cu, flush=True)
    for s in styles:
        job = G.submit(cu, G.SKINS[s])
        su, ru = job["status_url"], job["response_url"]
        t0 = time.time()
        while True:
            st = G.get(su).get("status")
            if st == "COMPLETED": break
            if st in ("FAILED", "ERROR"): print(s, "FAIL"); break
            if time.time() - t0 > 400: print(s, "timeout"); break
            time.sleep(4)
        else:
            continue
        if st != "COMPLETED": continue
        url = G.get(ru)["images"][0]["url"]
        out = os.path.join(FF, f"reskin-{s}.png")
        urllib.request.urlretrieve(url, out)
        print(f"reskin-{s} -> {out}", flush=True)

if __name__ == "__main__":
    render_blueprint()
    reskin()
    print("DONE")
