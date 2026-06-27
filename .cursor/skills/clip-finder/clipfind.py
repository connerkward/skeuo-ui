#!/usr/bin/env python3
"""clip-finder (local backend) — find + extract a SHOT from a video by text query.

PySceneDetect cuts shots → CLIP (muser embedders) ranks keyframes → ffmpeg cuts clips.
Free, local, no API. The similarity score is a confidence gate (low top-sim ⇒ the
queried shot probably isn't in the video).

Run in an env with scenedetect + muser + ffmpeg — easiest from the muser repo:
    cd ~/dev/Muser && uv pip install "scenedetect[opencv]"      # one-time
    uv run python <this> VIDEO "robot welding sparks" -k 5 --out .scratch/clip
"""
import argparse, os, subprocess, json, numpy as np
from scenedetect import detect, AdaptiveDetector
from muser.registry import _REGISTRY

DEVNULL = subprocess.DEVNULL
def ff(*args): subprocess.run(["ffmpeg", "-y", *args], stdout=DEVNULL, stderr=DEVNULL)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("query")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--out", default="/tmp/clipfind")
    ap.add_argument("--model", default="siglip2-b")
    ap.add_argument("--min-sim", type=float, default=0.0, help="drop shots below this similarity")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)

    scenes = detect(a.video, AdaptiveDetector())
    if not scenes: print("no shots detected"); return
    kf = []
    for i, (s, e) in enumerate(scenes):
        mid = (s.get_seconds() + e.get_seconds()) / 2
        p = f"{a.out}/_kf{i:03d}.jpg"
        ff("-ss", str(mid), "-i", a.video, "-frames:v", "1", "-q:v", "2", p)
        kf.append((s.get_seconds(), e.get_seconds(), p))

    emb = _REGISTRY[a.model][1]()
    img = np.asarray(emb.embed_images([k[2] for k in kf]), dtype=np.float32)
    q = np.asarray(emb.embed_queries([a.query])[0], dtype=np.float32)
    img /= np.linalg.norm(img, axis=1, keepdims=True) + 1e-9
    q /= np.linalg.norm(q) + 1e-9
    sims = img @ q
    order = np.argsort(-sims)[:a.k]

    results = []
    for rank, idx in enumerate(order, 1):
        st, en, _ = kf[idx]; sim = float(sims[idx])
        if sim < a.min_sim: continue
        clip = f"{a.out}/{rank:02d}_t{int(st)}_sim{sim:.3f}.mp4"
        ff("-ss", str(st), "-i", a.video, "-t", str(max(1.5, en - st)),
           "-c:v", "libx264", "-c:a", "aac", clip)
        results.append({"rank": rank, "start": round(st, 1), "end": round(en, 1),
                        "sim": round(sim, 3), "clip": os.path.basename(clip)})
        print(f"  #{rank} {st:.1f}-{en:.1f}s sim={sim:.3f} -> {os.path.basename(clip)}")
    for k in kf:                       # tidy keyframes
        try: os.remove(k[2])
        except OSError: pass
    json.dump(results, open(f"{a.out}/results.json", "w"), indent=1)
    if results and results[0]["sim"] < 0.12:
        print("  ⚠ low top similarity — the queried shot likely isn't in this video")

if __name__ == "__main__": main()
