#!/usr/bin/env python3
"""pbrtest step 2 — derive OpenGL-style normal maps from the flat albedo.

Two paths (both local, $0):
  sobel    — classical baseline: height-from-luminance + Sobel gradients (numpy).
             Runs under any python3 with numpy+PIL.
  marigold — prs-eth/marigold-normals-v1-1 via diffusers on MPS (weights already
             in the HF cache). Run with the ComfyUI venv python + PYTHONPATH=pydeps:
             PYTHONPATH=pydeps /Users/conner/ComfyUI-Installs/Local/ComfyUI/.venv/bin/python \
                 make_normals.py marigold albedo.png normal-marigold.png

Output encoding: RGB8, OpenGL convention (R=+X right, G=+Y up, B=+Z out of surface).
"""
import sys
import numpy as np
from PIL import Image


def sobel_normals(albedo_path, out_path, strength=2.0, blur=2):
    img = Image.open(albedo_path).convert("L")
    h = np.asarray(img, dtype=np.float32) / 255.0
    # mild blur so JPEG-ish noise doesn't become high-frequency bumps
    if blur:
        from PIL import ImageFilter
        h = np.asarray(Image.fromarray((h * 255).astype(np.uint8))
                       .filter(ImageFilter.GaussianBlur(blur)), dtype=np.float32) / 255.0
    gx = np.zeros_like(h); gy = np.zeros_like(h)
    gx[:, 1:-1] = (h[:, 2:] - h[:, :-2]) * 0.5
    gy[1:-1, :] = (h[2:, :] - h[:-2, :]) * 0.5
    # OpenGL: G = +Y up; image y grows downward, so ny = +gy_img after negating slope
    nx = -gx * strength * h.shape[1] / 512.0
    ny = gy * strength * h.shape[0] / 512.0
    nz = np.ones_like(h)
    n = np.stack([nx, ny, nz], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    rgb = ((n * 0.5 + 0.5) * 255).astype(np.uint8)
    Image.fromarray(rgb).save(out_path)
    print(f"[sobel] {out_path} {rgb.shape[1]}x{rgb.shape[0]}")


def marigold_normals(albedo_path, out_path):
    import torch
    from diffusers import MarigoldNormalsPipeline
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    pipe = MarigoldNormalsPipeline.from_pretrained(
        "prs-eth/marigold-normals-v1-1", torch_dtype=torch.float32).to(device)
    img = Image.open(albedo_path).convert("RGB")
    out = pipe(img, num_inference_steps=4, ensemble_size=1, processing_resolution=768)
    normals = out.prediction[0]  # (H,W,3) in [-1,1], Marigold = OpenGL screen space
    if hasattr(normals, "cpu"):
        normals = normals.cpu().numpy()
    normals = np.asarray(normals)
    if normals.ndim == 4:
        normals = normals[0]
    if normals.shape[0] == 3 and normals.ndim == 3:
        normals = np.moveaxis(normals, 0, -1)
    rgb = ((normals * 0.5 + 0.5).clip(0, 1) * 255).astype(np.uint8)
    Image.fromarray(rgb).resize(img.size, Image.LANCZOS).save(out_path)
    print(f"[marigold] {out_path} {img.size[0]}x{img.size[1]} (device={device})")


if __name__ == "__main__":
    mode, src, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    if mode == "sobel":
        sobel_normals(src, dst)
    elif mode == "marigold":
        marigold_normals(src, dst)
    else:
        raise SystemExit(f"unknown mode {mode}")
