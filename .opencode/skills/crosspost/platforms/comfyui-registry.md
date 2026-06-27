# ComfyUI Registry

https://registry.comfy.org

## Submission method
- Uses `comfy-cli` for publishing: `comfy node publish`
- Requires a `pyproject.toml` with ComfyUI-specific metadata

## How to submit
1. Ensure repo has `pyproject.toml` with `[tool.comfy]` section.
2. Run `comfy node publish` from the repo root.
3. May require auth via `comfy login` first.

## Notes
- This is different from social posting — it's a package registry publish.
- Only applicable when the project is a ComfyUI custom node.
