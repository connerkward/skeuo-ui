"""skeuo_gen12 — ComfyUI custom nodes reproducing the skeuo-ui gen12 skin-generation
pipeline (blueprint -> nano-banana-pro edit -> split -> BiRefNet -> extract -> player).

Each node is a THIN WRAPPER that shells out to the REAL, unmodified gen12 python
(tools/mask-align-exp/gen12/{genskin,extract12,biref12,build_player}.py). Nothing in the
gen12 pipeline is reimplemented here — the nodes only marshal a shared working directory
and convert PNGs <-> ComfyUI IMAGE tensors. FAL_KEY is read by the gen12 scripts themselves
from ~/dev/central/.env at runtime; it is never read, logged, or stored by node code.
"""
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
