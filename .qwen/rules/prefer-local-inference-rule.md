---
name: "prefer-local-inference-rule"
id: "prefer-local-inference-01"
description: "Before any paid/hosted model API call (fal, OpenAI, Replicate, Gemini), check whether it can run locally on MPS/GPU first — local is default, hosted only when no pragmatic local path exists."
globs: ["**/*"]
applyTo: ["**/*"]
alwaysApply: false
priority: "high"
human-reviewed-at: 2026-06-26
human-reviewed-by: connerward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Prefer local inference — check local FIRST, reach for hosted/API only when local is impractical

Before sending a task to a **paid/hosted model API** (fal, OpenAI, Replicate, Gemini,
any cloud inference), **pragmatically check whether it can run locally first** — on this
machine's GPU/MPS, via a local model (Ollama, an HF `transformers`/`diffusers` pipeline, a
cloned repo, ComfyUI, llama.cpp). Local is the default; hosted is the fallback you justify,
not the reflex you start with.

**Why:** local inference is free, private (no data leaves the machine), offline-capable, and
has no rate limits — and this machine is an Apple-Silicon box with working MPS and the disk
for multi-GB weights. The cost of a hosted call is recurring; the cost of standing up a local
model is usually one-time. For anything you'll run **more than once or iterate on**, local
almost always wins. (Set as a rule 2026-06-18 during the extrusion-lookdev depth-engine build:
DA2/DA3 run locally on MPS; fal/OpenAI were reserved for models with no practical local path.)

## The reflex — before any hosted-inference call

Ask: *can this model (or an equivalent) run locally, pragmatically?*
- **Yes, and setup is reasonable** (pip/HF pull, a clone, a few GB of weights, runs in
  seconds-to-minutes on MPS) → **run it locally.** This is the default.
- **No / not pragmatically** → use hosted, and say why local was ruled out (below).

## "Pragmatically" — when hosted IS the right call

Local-first is a bias, not dogma. Hosted is correct when:
- **No local path exists** — the model is closed/proprietary (Nano Banana / Gemini Image,
  GPT-Image, Sora, Veo, Midjourney) with no open weights.
- **Local is impractical here** — needs more VRAM than the machine has, CUDA-only kernels
  that don't run on MPS, or weights/runtime that would take hours to stand up for a one-off.
- **True one-shot throwaway** — a single image you'll never regenerate, where a 5-second API
  call beats 20 minutes of local setup. (If you'll run it again, set local up instead.)
- **Hosted is materially better for the job** and quality is the point — then use it, and
  ideally *also* keep a local baseline for comparison.

## How to apply

- **Look before you call.** Check for an existing local runtime (Ollama models, a project
  `.venv` with torch, ComfyUI, a cloned repo) before reaching for an MCP/API tool. The
  fal/OpenAI/etc. MCPs being *available* is not a reason to use them.
- **State the choice.** When you do go hosted, name the reason ("closed model, no local
  weights" / "CUDA-only, won't run on MPS"). When you go local, just do it.
- **Mixed pipelines are fine and good** — run what you can locally, send only the genuinely
  hosted-only parts out, and label which is which (esp. when comparing engines).

Related: [[software-engineering-rule]] (don't waste my time / run it yourself), [[restraint-rule]]
(smallest thing that works), `fal` / `gcloud` skills (the hosted fallbacks). On any conflict
about local vs hosted, bias local.
