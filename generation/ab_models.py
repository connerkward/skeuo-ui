#!/usr/bin/env python3
"""A/B the same blueprint through several editors at 2K, opaque, to compare
chrome quality + layout adherence. Saves to /tmp/skeuo-ab/."""
import json, os, time, urllib.request, concurrent.futures
HERE = os.path.dirname(os.path.abspath(__file__))

def fal_key():
    for l in open("/Users/conner/dev/central/.env"):
        if l.startswith("FAL_KEY="): return l.split("=",1)[1].strip()
KEY = fal_key()
H = {"Authorization": f"Key {KEY}", "Content-Type": "application/json"}
def post(u,b):
    r=urllib.request.Request(u,data=json.dumps(b).encode(),headers=H,method="POST")
    return json.loads(urllib.request.urlopen(r,timeout=180).read())
def get(u):
    r=urllib.request.Request(u,headers={"Authorization":f"Key {KEY}"})
    return json.loads(urllib.request.urlopen(r,timeout=180).read())
def upload(p):
    i=post("https://rest.alpha.fal.ai/storage/upload/initiate",{"file_name":os.path.basename(p),"content_type":"image/png"})
    urllib.request.urlopen(urllib.request.Request(i["upload_url"],data=open(p,"rb").read(),method="PUT",headers={"Content-Type":"image/png"}),timeout=180)
    return i["file_url"]

PROMPT = (
    "Restyle this UI blueprint into a richly detailed PHOTOREAL skeuomorphic media-player skin: a "
    "late-1990s Winamp hardware unit in brushed gunmetal and dark charcoal with crisp polished chrome "
    "bevels, knurled chrome knobs, tiny corner screws, dark plastic buttons with bright specular "
    "highlights, near-black glass screens. CRITICAL: keep EVERY button, knob, slider, segmented switch "
    "and screen in its EXACT original position, size and shape from the blueprint — do not move, add, "
    "remove or resize anything. Keep the dark screens EMPTY (no text). Buttons keep their labels. Sharp, "
    "high detail, even studio lighting, front-on, fills the frame."
)

def queue(ep, body):
    return post(f"https://queue.fal.run/{ep}", body)
def wait(job, name):
    t0=time.time()
    while True:
        s=get(job["status_url"]).get("status")
        if s=="COMPLETED": break
        if s in ("FAILED","ERROR"): print(name,"FAIL",get(job["status_url"])); return None
        if time.time()-t0>300: print(name,"timeout"); return None
        time.sleep(4)
    return get(job["response_url"])

def main():
    out="/tmp/skeuo-ab"; os.makedirs(out,exist_ok=True)
    cu=upload(os.path.join(HERE,"control.png"))
    print("control",cu,flush=True)
    jobs={}
    jobs["seedream45"]=("fal-ai/bytedance/seedream/v4.5/edit", queue("fal-ai/bytedance/seedream/v4.5/edit",
        {"prompt":PROMPT,"image_urls":[cu],"image_size":{"width":1408,"height":2112}}))
    jobs["nanobanana_pro"]=("fal-ai/gemini-3-pro-image-preview/edit", queue("fal-ai/gemini-3-pro-image-preview/edit",
        {"prompt":PROMPT,"image_urls":[cu],"resolution":"2K","aspect_ratio":"2:3","output_format":"png"}))
    for name,(ep,job) in jobs.items():
        res=wait(job,name)
        if not res: continue
        try:
            url=res["images"][0]["url"]
        except Exception:
            print(name,"no image, keys:",list(res.keys())); print(json.dumps(res)[:400]); continue
        urllib.request.urlretrieve(url, f"{out}/{name}.png")
        print(name,"->",f"{out}/{name}.png",flush=True)
    print("DONE")

if __name__=="__main__": main()
