#!/usr/bin/env python3
"""clip-finder (cloud backend) — Twelve Labs marengo3.0 semantic moment retrieval.

Indexes a video, runs a natural-language query, returns rank-ordered timecoded
moments, and cuts each to a clip. Video-native (visual + audio + on-screen text).

Needs TWELVELABS_API_KEY in central/.env and `pip install twelvelabs`.
    python clip_twelvelabs.py VIDEO "robot welding sparks" -k 5 --out .scratch/clip-tl

Note: marengo3.0 'visual' search includes on-screen TEXT (OCR) — for purely visual
shots, results may include title/intertitle cards. Drop audio from search_options or
post-filter if you need visual-only. Free tier ≈ 600 indexing minutes. Video ≥480x360.
"""
import argparse, os, json, subprocess
from twelvelabs import TwelveLabs

DEVNULL = subprocess.DEVNULL
def ff(*a): subprocess.run(["ffmpeg", "-y", *a], stdout=DEVNULL, stderr=DEVNULL)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("query")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--out", default="/tmp/clip-tl")
    ap.add_argument("--env", default=os.path.expanduser("~/dev/central/.env"))
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    key = [l.split("=", 1)[1].strip() for l in open(a.env)
           if l.startswith("TWELVELABS_API_KEY=")][0]
    log = lambda *x: print(*x, flush=True)
    c = TwelveLabs(api_key=key)

    idx = c.indexes.create(index_name=f"clipfind-{os.path.basename(a.video)[:20]}",
                           models=[{"model_name": "marengo3.0", "model_options": ["visual", "audio"]}])
    with open(a.video, "rb") as f:
        task = c.tasks.create(index_id=idx.id, video_file=f)
    log("indexing…", task.id)
    c.tasks.wait_for_done(task_id=task.id, sleep_interval=6,
                          callback=lambda t: log(" ", getattr(t, "status", "?")))
    res = c.search.query(index_id=idx.id, search_options=["visual"],
                         query_text=a.query, group_by="clip", page_limit=a.k)
    rows = []
    for it in res:
        d = it.model_dump() if hasattr(it, "model_dump") else it.__dict__
        s, e = d.get("start"), d.get("end")
        if s is None or len(rows) >= a.k: continue
        clip = f"{a.out}/{len(rows)+1:02d}_t{int(s)}.mp4"
        ff("-ss", str(s), "-i", a.video, "-t", str(e - s), "-c:v", "libx264", "-c:a", "aac", clip)
        rows.append({"rank": len(rows)+1, "start": round(s, 1), "end": round(e, 1),
                     "clip": os.path.basename(clip)})
        log(f"  #{rows[-1]['rank']} {s:.1f}-{e:.1f}s -> {os.path.basename(clip)}")
    json.dump(rows, open(f"{a.out}/results.json", "w"), indent=1)

if __name__ == "__main__": main()
