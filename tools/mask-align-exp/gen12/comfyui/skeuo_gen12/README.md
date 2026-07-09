# skeuo_gen12 — ComfyUI nodes for the skeuo-ui gen12 skin pipeline

Reproduces the gen12 skin-generation pipeline as a ComfyUI graph. Each node is a thin wrapper
that **subprocesses the real, unmodified gen12 scripts** in
`~/dev/skeuo-ui/tools/mask-align-exp/gen12/` — no pipeline logic is reimplemented here.

## Nodes
| Node | Wraps | In → Out |
|------|-------|----------|
| Skeuo Blueprint | `genskin.py` via `prompt_capture.py` (fal stubbed — free, no network) | spec → blueprint IMAGE, keys json, job, **prompt STRING** |
| Skeuo Nano-Banana Edit | `genskin.py` (fal gemini-3-pro-image edit) — ALT path | job → joint, paint, mask, job |
| Skeuo Split Joint | width//2 crop | joint → paint, mask, job |
| Skeuo Island Split (`SkeuoBiRefNet`) | `extract12.py` (pass-1) + `biref12.py` | job (+ optional **matte IMAGE**) → matte, job |
| Skeuo Extract Regions | `extract12.py` (pass-2, gate) | job → overlay, regions_json, gate, job |
| Skeuo Build Player | `build_player.py` | job → player.html path |

### Local / native paths (jul0926-1014-skeuo-gen12-local workflow)
- **Prompt output**: `prompt_capture.py` imports the unmodified `genskin.py`, stubs its fal
  helpers, and captures the verbatim structural prompt — so ComfyUI's **native**
  `GeminiImage2Node` ("Nano Banana Pro", `gemini-3-pro-image-preview`, comfy.org login +
  credits) can perform the edit: blueprint IMAGE + prompt STRING → joint. 5:4 / 4K / seed
  match the fal call.
- **Local matte**: paint → `ComfyUI_BiRefNet_ll` (`LoadRembgByBiRefNetModel` General.safetensors
  → `GetMaskByBiRefNet` → `MaskToImage`) → `SkeuoBiRefNet.matte`. The node composes
  paint+matte into `assets-<id>_biref/global-matte.png`; `biref12.py` detects the existing
  matte and **skips its fal call** ("reused existing matte"), running only the skeuo-specific
  island split. With `matte` unconnected the legacy fal path is used unchanged.

The `job` (SKEUO_JOB) edge carries the shared spec path + assets dir between stages — the same
on-disk `assets-<id>/` contract the standalone pipeline uses.

## Requirements
- **Node code**: numpy, Pillow, torch — all shipped with ComfyUI.
- **Wrapped scripts**: numpy, Pillow, scipy, requests — the package auto-selects the first
  interpreter that has them (`sys.executable`, then `python3` on PATH, then Homebrew python).
- **fal**: the Nano-Banana Edit and BiRefNet stages call fal.ai. `FAL_KEY` is read by the gen12
  scripts from `~/dev/central/.env` at runtime; the nodes never read, log, or store it.
- `gen12_dir` defaults to the skeuo-ui repo path and is overridable on the Blueprint node.

## Notes
- Generic ComfyUI BiRefNet nodes only produce a matte; gen12 additionally splits the matte into
  device + moving-part islands correlated to the mask strip cells, so the real `biref12.py` is
  wrapped instead.
- Nano-Banana Edit re-runs the full `genskin.py`, which redraws the (deterministic) blueprint and
  performs the fal edit — the Blueprint node upstream is a free preview of the same blueprint.
