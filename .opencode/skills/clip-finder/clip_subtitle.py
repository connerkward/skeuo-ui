#!/usr/bin/env python3
"""clip-finder (subtitle backend) — locate a moment by DIALOGUE.

Match a line in a film's subtitles → timestamp → preview frame + cut clip.
Subtitles come from either a local file (--subs) or OpenSubtitles (--fetch TITLE).
You always supply the VIDEO (your copy) — there's no API for frames of films you
don't hold. ffmpeg required; stdlib only.

    # local subtitle file
    clip_subtitle.py VIDEO.mp4 "I'll be back" --subs SUBS.srt -k 5 --out .scratch/clip-sub
    # fetch subtitles from OpenSubtitles by title
    clip_subtitle.py VIDEO.mp4 "I'll be back" --fetch "Terminator 2" --lang en

OpenSubtitles creds in central/.env: OPENSUBTITLES_API_KEY, OPENSUBTITLES_USERNAME,
OPENSUBTITLES_PASSWORD. Note: a fetched .srt is timed to *some* release — if it's off
from your copy, pick another result or apply an offset (sub-sync isn't guaranteed).
"""
import argparse, os, re, subprocess, json, urllib.request, urllib.parse

DEVNULL = subprocess.DEVNULL
def ff(*a): subprocess.run(["ffmpeg", "-y", *a], stdout=DEVNULL, stderr=DEVNULL)

# ---- OpenSubtitles (opensubtitles.com REST v1) --------------------------
OS_BASE = "https://api.opensubtitles.com/api/v1"
OS_UA = "central-clip-finder/0.1"

def _os(path, method="GET", body=None, token=None):
    key = os.environ.get("OPENSUBTITLES_API_KEY")
    if not key:
        raise SystemExit("set OPENSUBTITLES_API_KEY (+ _USERNAME/_PASSWORD) in central/.env")
    h = {"Api-Key": key, "User-Agent": OS_UA, "Accept": "application/json"}
    if body is not None: h["Content-Type"] = "application/json"
    if token: h["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(OS_BASE + path, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)

def os_fetch_srt(query, lang, out_dir):
    # OpenSubtitles 301-redirects non-canonical query strings — params MUST be sorted.
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in sorted(
        {"languages": lang, "order_by": "download_count", "query": query}.items()))
    res = _os(f"/subtitles?{qs}")
    data = res.get("data", [])
    if not data: raise SystemExit(f"no subtitles found for {query!r}")
    attrs = data[0].get("attributes", {}) or {}
    files = attrs.get("files", [])
    if not files: raise SystemExit("top subtitle result has no files")
    user = os.environ.get("OPENSUBTITLES_USERNAME"); pw = os.environ.get("OPENSUBTITLES_PASSWORD")
    token = _os("/login", "POST", {"username": user, "password": pw}).get("token")
    dl = _os("/download", "POST", {"file_id": files[0]["file_id"]}, token=token)
    link = dl.get("link")
    path = os.path.join(out_dir, "fetched.srt")
    req = urllib.request.Request(link, headers={"User-Agent": OS_UA})
    with urllib.request.urlopen(req, timeout=30) as r, open(path, "wb") as f:
        f.write(r.read())
    print(f"  fetched subs for {query!r}  [{attrs.get('release','')[:50]}]  "
          f"(downloads left today: {dl.get('remaining','?')})")
    return path

# ---- subtitle parsing + matching ----------------------------------------
def parse_time(t):
    h, m, s = t.strip().replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)

def parse_subs(path):
    raw = open(path, encoding="utf-8-sig", errors="ignore").read()
    cues = []
    for block in re.split(r"\n\s*\n", raw):
        m = re.search(r"(\d{1,2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{3})", block)
        if not m: continue
        lines = block.split("\n")
        ti = next((i for i, l in enumerate(lines) if "-->" in l), 0)
        text = re.sub(r"<[^>]+>", "", " ".join(lines[ti + 1:])).strip()
        if text: cues.append((parse_time(m.group(1)), parse_time(m.group(2)), text))
    return cues

def score(q, text):
    ql, tl = q.lower(), text.lower()
    if ql in tl: return 1.0
    qw = set(re.findall(r"\w+", ql))
    if not qw: return 0.0
    return len(qw & set(re.findall(r"\w+", tl))) / len(qw) * 0.8

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("query")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--subs", help="local .srt/.vtt file")
    g.add_argument("--fetch", help="movie title — pull subtitles from OpenSubtitles")
    ap.add_argument("--lang", default="en")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--out", default="/tmp/clip-sub")
    ap.add_argument("--pad", type=float, default=0.4)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)

    subs = a.subs or os_fetch_srt(a.fetch, a.lang, a.out)
    cues = parse_subs(subs)
    if not cues: print("no cues parsed from", subs); return
    hits = [c for c in sorted(((score(a.query, t), s, e, t) for s, e, t in cues),
                              key=lambda x: -x[0]) if c[0] > 0][:a.k]
    if not hits: print("no dialogue match for", repr(a.query)); return

    results = []
    for rank, (sc, s, e, txt) in enumerate(hits, 1):
        mid = (s + e) / 2
        frame = f"{a.out}/{rank:02d}_t{int(s)}.jpg"
        ff("-ss", str(mid), "-i", a.video, "-frames:v", "1", "-q:v", "2", frame)
        st = max(0, s - a.pad)
        clip = f"{a.out}/{rank:02d}_t{int(s)}.mp4"
        ff("-ss", str(st), "-i", a.video, "-t", str(e - s + 2 * a.pad),
           "-c:v", "libx264", "-c:a", "aac", clip)
        results.append({"rank": rank, "score": round(sc, 2), "start": round(s, 1),
                        "end": round(e, 1), "text": txt[:140],
                        "frame": os.path.basename(frame), "clip": os.path.basename(clip)})
        print(f'  #{rank} [{sc:.2f}] {s:.1f}-{e:.1f}s  "{txt[:60]}"')
    json.dump(results, open(f"{a.out}/results.json", "w"), indent=1)

if __name__ == "__main__": main()
