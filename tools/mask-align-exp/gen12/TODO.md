# gen12 TODO

## BIREF_LOCAL / PAINT_VERTEX flags

Both landed flag-gated OFF, then were flipped ON 2026-07-10 (user call, batch drained —
see `.claude/rules/generation-spend-rule.md` and `.claude/rules/feature-flag-rule.md`).
Flip only **between** batches, never while `orchestrate12.py` is mid-run.

### `biref12.py: BIREF_LOCAL` (now `True`)

- **What it does when `True`:** runs BiRefNet locally via `transformers`
  (`trust_remote_code=True`) on MPS instead of the fal
  `fal-ai/birefnet/v2` endpoint. $0/matte, no fal dependency.
- **Requires:** the `.venv-biref/` venv in this dir (torch/torchvision/transformers/
  huggingface-hub/accelerate/scipy/pillow/requests/numpy — already created + populated
  on this machine). `biref12.py` auto-re-execs itself under `.venv-biref/bin/python3`
  if the current interpreter lacks `torch`, so `orchestrate12.py`'s
  `["python3", "biref12.py", ASSETS]` call keeps working unmodified.
- **Checkpoint: `ZhengPeng7/BiRefNet_HR` @ 2048 input** (switched from general@1024
  after a bench, 2026-07-10). What fal's "General Use (Heavy)" actually is: fal's own
  schema maps it to `BiRefNet_lite`, but the same schema describes Heavy as "slower
  but more accurate" (lite is the 44M fast model) — the Light/Heavy rows are almost
  certainly swapped in fal's doc, and the bench can't discriminate. IoU vs the fal
  Heavy matte on fallout-vault: HR@2048 **0.9978**, general@2048 0.9979, lite@1024
  0.9976, general@1024 0.9973 — all within 0.0006 (noise). HR chosen: full 220.7M
  checkpoint TRAINED at the 2048 operating resolution the fal call uses, IoU ≥ the
  previously shipped general@1024.
- **Verified:** `True` — end-to-end via the real shipped biref12.py: IoU 0.9978,
  all 4 strip parts (vol/seek/shuffle off+on) matched at 98–100% mask-cell overlap,
  visually identical side-by-side. ~31s/matte at 2048 on MPS incl. model load
  (~5s inference once warm).

### `genskin.py: PAINT_VERTEX` (default `False`)

- **What it does when `True`:** calls the same `gemini-3-pro-image-preview` model
  direct via Vertex AI (`aiplatform.googleapis.com`, `gcloud auth print-access-token`
  — no ADC file needed, same pattern as `bproof/run_bproof_vertex.py`) instead of
  fal's `fal-ai/gemini-3-pro-image-preview/edit` wrapper.
- **Price (verified live, 2026-07-10):** fal is $0.15/image at 1K/2K but **$0.30/image
  at 4K** (genskin requests `resolution: "4K"` — fal's own pricing page states 4K is
  2x the base rate). Vertex direct at the same 4K tier is **$0.24/image** (2000 output
  tokens x $120/1M, per the Vertex AI generative-pricing page) + ~$0.001 input tokens.
  **Vertex is ~20% cheaper than fal for this exact call**, in addition to removing the
  fal-billing-lock dependency (fal 403'd the whole pipeline once already, per the
  generation-spend rule).
- **Requires:** `gcloud` CLI authenticated as a user with Vertex AI access on project
  `muser-2605300220` (or set `VERTEX_PROJECT` env var) — already working on this
  machine, no ADC file present or needed.
- **Verified:** `True` — one test generation (`steam-porthole` spec, shortened test
  prompt, not the full production prompt) returned a real, correctly-themed image in
  45s at 4608x3712 (aspect 1.241 vs requested 5:4=1.25). Full production-prompt
  parity not re-tested (contract — image in/out, aspect, seed — is what changed;
  prompt text is unchanged either way).
- `genskin.py:edit_vertex()` matches (diffed line-for-line, only cosmetic naming
  differs) `abshape/genskin_ab.py:edit_vertex()`, which already ran 4 real
  generations today on this same project/auth — independent convergence on the
  same proven call shape, not a fresh untested integration.
