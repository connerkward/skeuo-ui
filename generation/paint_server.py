"""
Local REAL-TIME paint sidecar for the skeuo-ui diffuse template editor.

Sub-3-second, in-software paint of the editor's combined blueprint using the proven
real-time ControlNet stack — SD1.5 + LCM-LoRA (few-step, CFG-free) + a ControlNet
(canny) + TAESD tiny-VAE for near-instant decode — resident on Apple-Silicon MPS.
No ComfyUI, no cloud. (Same stack as HF's Real-Time-LCM-ControlNet-Lora-SD1.5 demo.)

  POST /generate  { prompt, control_image (dataURL/b64 PNG), steps, guidance,
                    controlnet_conditioning_scale, seed, width, height,
                    negative_prompt, canny_low, canny_high }
                -> { image (dataURL PNG), control_preview (dataURL PNG),
                     seed, timing_ms, size }
  GET  /health    -> { ready, loading, device, dtype, base, controlnet, error }

Run:  generation/.venv-zimage/bin/python generation/paint_server.py
      (PAINT_PORT=8788 · PAINT_BASE=Lykon/dreamshaper-8 · PAINT_CONTROLNET=...canny)
"""
from __future__ import annotations

import base64
import io
import os
import threading
import time
import traceback

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel

BASE_MODEL = os.environ.get("PAINT_BASE", "Lykon/dreamshaper-8")            # SD1.5 finetune
CN_MODEL = os.environ.get("PAINT_CONTROLNET", "lllyasviel/control_v11p_sd15_canny")
LCM_LORA = os.environ.get("PAINT_LCM", "latent-consistency/lcm-lora-sdv1-5")
TAESD = os.environ.get("PAINT_TAESD", "madebyollin/taesd")
PORT = int(os.environ.get("PAINT_PORT", "8788"))

_state = {"pipe": None, "device": None, "dtype": None, "loading": False, "ready": False, "error": None}
_load_lock = threading.Lock()
_gen_lock = threading.Lock()          # MPS is single-stream — serialize generations


def _pick_device_dtype():
    import torch
    if torch.backends.mps.is_available():
        return "mps", torch.float16   # TAESD keeps fp16 VAE safe (no NaN like SD's own VAE)
    if torch.cuda.is_available():
        return "cuda", torch.float16
    return "cpu", torch.float32


def _load():
    if _state["ready"] or _state["error"]:
        return
    with _load_lock:
        if _state["ready"] or _state["error"]:
            return
        _state["loading"] = True
        try:
            import torch
            from diffusers import (AutoencoderTiny, ControlNetModel, LCMScheduler,
                                   StableDiffusionControlNetPipeline)

            device, dtype = _pick_device_dtype()
            t0 = time.time()
            print(f"[paint] controlnet {CN_MODEL}", flush=True)
            controlnet = ControlNetModel.from_pretrained(CN_MODEL, torch_dtype=dtype)
            print(f"[paint] base {BASE_MODEL}", flush=True)
            pipe = StableDiffusionControlNetPipeline.from_pretrained(
                BASE_MODEL, controlnet=controlnet, torch_dtype=dtype,
                safety_checker=None, feature_extractor=None, requires_safety_checker=False,
            )
            print(f"[paint] taesd {TAESD}", flush=True)
            pipe.vae = AutoencoderTiny.from_pretrained(TAESD, torch_dtype=dtype)
            print(f"[paint] lcm-lora {LCM_LORA}", flush=True)
            pipe.load_lora_weights(LCM_LORA)
            pipe.fuse_lora()
            pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)
            pipe = pipe.to(device)
            try:
                pipe.set_progress_bar_config(disable=True)
            except Exception:
                pass
            _state.update(pipe=pipe, device=device, dtype=str(dtype).replace("torch.", ""))

            # WARM-UP: compile MPS kernels so the first real paint is fast, not a 10-20s stall.
            print("[paint] warming up (compiling MPS kernels)…", flush=True)
            warm = Image.new("RGB", (448, 800), (0, 0, 0))
            _run(pipe, "warmup", None, warm, 0.8, 4, 1.0, 448, 800, torch.Generator("cpu").manual_seed(0))
            _state.update(ready=True, loading=False)
            print(f"[paint] READY on {device} ({_state['dtype']}) in {time.time()-t0:.1f}s", flush=True)
        except Exception as e:  # noqa: BLE001
            _state.update(error=f"{type(e).__name__}: {e}", loading=False)
            print("[paint] LOAD FAILED\n" + traceback.format_exc(), flush=True)


def _run(pipe, prompt, neg, control, scale, steps, guidance, w, h, gen):
    return pipe(
        prompt=prompt, negative_prompt=neg, image=control,
        controlnet_conditioning_scale=float(scale),
        num_inference_steps=max(1, int(steps)), guidance_scale=float(guidance),
        width=w, height=h, generator=gen, output_type="pil",
    ).images[0]


# ---- image helpers ----------------------------------------------------------
def _decode_image(data: str) -> Image.Image:
    if "," in data and data.strip().startswith("data:"):
        data = data.split(",", 1)[1]
    return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")


def _encode_image(img: Image.Image) -> str:
    buf = io.BytesIO(); img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _round8(n: int) -> int:
    return max(8, int(round(n / 8.0)) * 8)


def _canny(img: Image.Image, w: int, h: int, lo: int, hi: int) -> Image.Image:
    import cv2
    img = img.resize((w, h), Image.LANCZOS)
    edges = cv2.Canny(np.array(img), lo, hi)
    return Image.fromarray(np.stack([edges, edges, edges], axis=-1))


class GenReq(BaseModel):
    prompt: str = ""
    control_image: str
    steps: int = 4                      # LCM few-step
    guidance: float = 1.0               # LCM: ~1, CFG-free (single UNet forward)
    controlnet_conditioning_scale: float = 0.8
    seed: int | None = None
    width: int = 448                    # 9:16-ish at a real-time size; raise for quality
    height: int = 800
    negative_prompt: str | None = None
    canny_low: int = 80
    canny_high: int = 180


app = FastAPI(title="skeuo real-time paint sidecar")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"ready": _state["ready"], "loading": _state["loading"], "device": _state["device"],
            "dtype": _state["dtype"], "base": BASE_MODEL, "controlnet": CN_MODEL, "error": _state["error"]}


@app.post("/load")
def load():
    if not _state["ready"] and not _state["loading"] and not _state["error"]:
        threading.Thread(target=_load, daemon=True).start()
    return health()


@app.post("/generate")
def generate(req: GenReq):
    if _state["error"]:
        return {"error": _state["error"]}
    if not _state["ready"]:
        threading.Thread(target=_load, daemon=True).start()
        return {"error": "model still loading — retry shortly", "loading": True}

    import torch
    w, h = _round8(req.width), _round8(req.height)
    try:
        blueprint = _decode_image(req.control_image)
    except Exception as e:  # noqa: BLE001
        return {"error": f"bad control_image: {e}"}
    control = _canny(blueprint, w, h, req.canny_low, req.canny_high)
    seed = req.seed if req.seed is not None else int.from_bytes(os.urandom(4), "big")
    gen = torch.Generator("cpu").manual_seed(seed)

    with _gen_lock:
        t0 = time.time()
        try:
            img = _run(_state["pipe"], req.prompt, req.negative_prompt, control,
                       req.controlnet_conditioning_scale, req.steps, req.guidance, w, h, gen)
        except Exception as e:  # noqa: BLE001
            print("[paint] GENERATE FAILED\n" + traceback.format_exc(), flush=True)
            return {"error": f"{type(e).__name__}: {e}"}
        dt = int((time.time() - t0) * 1000)

    return {"image": _encode_image(img), "control_preview": _encode_image(control),
            "seed": seed, "timing_ms": dt, "size": [w, h]}


if __name__ == "__main__":
    import uvicorn
    threading.Thread(target=_load, daemon=True).start()
    print(f"[paint] serving on http://0.0.0.0:{PORT}  (base={BASE_MODEL} · lcm+controlnet+taesd)", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
