#!/usr/bin/env python3
"""_lama_worker — run local LaMa (simple-lama-inpainting, big-lama weights, MPS) on one
crop+mask pair. Invoked as a subprocess from run_bakeoff.py using the .venv-biref
interpreter (has torch+MPS already set up for BiRefNet). $0 marginal cost, no prompt input —
pure pixel-statistics texture continuation (see docs/design/2026-07-12-inpaint-pricing.md §3).

Usage: python3 _lama_worker.py <crop.png> <mask.png> <out.png>
"""
import sys
from PIL import Image

crop_path, mask_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

from simple_lama_inpainting import SimpleLama

image = Image.open(crop_path).convert("RGB")
mask = Image.open(mask_path).convert("L")

lama = SimpleLama()
result = lama(image, mask)
result.save(out_path)
