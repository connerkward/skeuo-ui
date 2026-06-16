#!/usr/bin/env python3
"""Run a ComfyUI API-format workflow against the local Comfy Desktop server and
save every output image. This is the headless equivalent of hitting "Queue" in
the GUI — POST /prompt, watch the websocket for completion, pull the result.

These workflows mirror the skeuo wild_sculpt pipeline using ComfyUI's cloud
API NODES (the same models the fal pipeline uses):
  - OpenAIGPTImage1   (gpt-image-2)              -> the flat silhouette
  - GeminiNanoBanana2 (Nano Banana / Gemini img) -> the layout-preserving paint
API nodes bill comfy.org credits and require being signed in inside Comfy
Desktop. A failed call (auth/credit) returns an execution error, not a charge.

Usage: python3 run.py <workflow.json> [out_prefix]
"""
import json, os, sys, time, uuid, urllib.request, urllib.error

SERVER = os.environ.get("COMFY_SERVER", "127.0.0.1:8188")
OUTDIR = "/Users/conner/Desktop/cc-skeuo"
os.makedirs(OUTDIR, exist_ok=True)


def _comfy_api_key():
    """Comfy API key for the cloud API nodes (gpt-image / Nano Banana). Read
    from COMFY_API_KEY, else from central/.env — never hardcode the secret.
    Passed to /prompt as extra_data.api_key_comfy_org (execution.py reads it)."""
    k = os.environ.get("COMFY_API_KEY")
    if k:
        return k.strip()
    env = os.path.expanduser("~/dev/central/.env")
    if os.path.exists(env):
        for line in open(env):
            if line.startswith("COMFY_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _comfy_auth_token():
    """Short-lived comfy.org login token (auth_token_comfy_org). Lets a headless
    run reuse an already-signed-in Comfy Desktop session without an API key.
    From COMFY_AUTH_TOKEN, else the ephemeral /tmp/_comfy_tok. Expires ~1h; the
    API key (above) is the durable path. Never committed — secret stays out of git."""
    t = os.environ.get("COMFY_AUTH_TOKEN")
    if t:
        return t.strip()
    p = "/tmp/_comfy_tok"
    if os.path.exists(p):
        return open(p).read().strip()
    return None


def _req(path, data=None):
    url = f"http://{SERVER}{path}"
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(url, data=body,
                               headers={"Content-Type": "application/json"} if body else {})
    with urllib.request.urlopen(r, timeout=120) as resp:
        return json.loads(resp.read())


def run(wf_path, out_prefix=None):
    wf = json.load(open(wf_path))
    prompt = wf["prompt"] if "prompt" in wf else wf
    cid = uuid.uuid4().hex
    payload = {"prompt": prompt, "client_id": cid}
    key = _comfy_api_key()
    tok = _comfy_auth_token()
    if key:
        payload["extra_data"] = {"api_key_comfy_org": key}
        print("auth: COMFY_API_KEY present", flush=True)
    elif tok:
        payload["extra_data"] = {"auth_token_comfy_org": tok}
        print("auth: desktop login token present (may expire ~1h)", flush=True)
    else:
        print("auth: none — cloud API nodes will return Unauthorized", flush=True)
    print(f"queue {os.path.basename(wf_path)} (client {cid[:8]})", flush=True)
    try:
        res = _req("/prompt", payload)
    except urllib.error.HTTPError as e:
        print("PROMPT REJECTED:", e.read().decode()[:1500]); sys.exit(2)
    pid = res["prompt_id"]
    print("prompt_id", pid, "— polling /history", flush=True)

    t0 = time.time()
    while True:
        time.sleep(2)
        hist = _req(f"/history/{pid}")
        if pid in hist:
            h = hist[pid]
            status = h.get("status", {})
            if status.get("status_str") == "error" or not status.get("completed", True) is True and status.get("status_str"):
                pass
            # check for messages / errors
            msgs = status.get("messages", [])
            for m in msgs:
                if m and m[0] == "execution_error":
                    print("EXECUTION ERROR:", json.dumps(m[1], indent=2)[:2000]); return None
            outputs = h.get("outputs", {})
            saved = []
            for nid, out in outputs.items():
                for img in out.get("images", []):
                    fn, sub, typ = img["filename"], img.get("subfolder", ""), img.get("type", "output")
                    from urllib.parse import urlencode
                    data = _get_bytes(f"/view?{urlencode({'filename': fn, 'subfolder': sub, 'type': typ})}")
                    pre = out_prefix or os.path.splitext(os.path.basename(wf_path))[0]
                    dst = os.path.join(OUTDIR, f"{pre}_{nid}_{fn}")
                    open(dst, "wb").write(data)
                    saved.append(dst)
            if outputs:
                print(f"DONE in {time.time()-t0:.0f}s, {len(saved)} image(s):", flush=True)
                for s in saved:
                    print("  ", s, f"({os.path.getsize(s)} bytes)")
                return saved
        if time.time() - t0 > 300:
            print("TIMEOUT after 300s"); return None
        print(f"  ...{time.time()-t0:.0f}s", flush=True)


def _get_bytes(path):
    with urllib.request.urlopen(f"http://{SERVER}{path}", timeout=120) as r:
        return r.read()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
