---
name: fal
description: fal.ai inference for image/video/audio/music generation. Hosted MCP at mcp.fal.ai gives access to 1,000+ models. Key in central/.env. Use when generating media or running model inference.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# fal.ai

fal hosts an inference platform for generative models — image (FLUX, SDXL, Recraft, Ideogram), video (Veo, Kling, Runway, Wan, Hunyuan, LTX), audio (MMAudio, F5-TTS, ElevenLabs), music (Stable Audio, MusicGen), and ~1,000 more. Access is via the hosted MCP server at `mcp.fal.ai`, the REST API at `fal.run`/`queue.fal.run`, or official SDKs.

## Layers (pick the right one)

| Need | Tool | Why |
|------|------|-----|
| Discover a model, check its schema, one-off generation | **fal MCP** (`mcp__fal-ai__*`) | Hosted MCP exposes search/schema/run/upload across all models. Fastest path from "what model fits" → "working call". |
| Programmatic batch generation, server-side integration | **REST API** (`fal.run`) + `FAL_KEY` | MCP is overhead for repeated calls. Use queue API for long-running jobs. |
| Local Python/Node project with type safety | **`fal-client` SDK** (`pip install fal-client` / `npm i @fal-ai/client`) | Handles auth, polling, file uploads. |
| Heavy local image work (ComfyUI graphs) | run ComfyUI yourself (no central skill) | Different surface — ComfyUI runs models locally with custom node graphs. fal is hosted inference. |

Default to the MCP for ad-hoc work. Move to REST/SDK when calls become repetitive or live in code.

## Cost discipline — fal is pay-per-use; do NOT burn the balance

fal bills per run and the **balance can run dry mid-task** → every call then 403s with
`User is locked. Reason: Exhausted balance` and the whole pipeline halts. Treat fal spend
as the user's real money and minimize it by default. (Burn: skeuo-ui 2026-06-23 — iterating
on sprite-cut geometry re-ran the paint + BiRefNet on fal every loop and exhausted the
balance; the cutting could have run **locally in ComfyUI for free**, and the geometry
iteration only needed the *already-saved* paint, not a new paid paint each time.)

Rules, in priority order:

1. **Local first — check [[prefer-local-inference-rule]] before any fal call.** Background
   removal (BiRefNet/rembg), SAM segmentation, SD/Flux img2img, upscale, depth — all run
   **locally and free in ComfyUI** or via a local model. Only send to fal what genuinely
   has no practical local path (closed models: Veo, Kling, Sora, Nano-Banana/Gemini-Image,
   gpt-image). Don't pay fal for what the machine can do.
2. **Never re-pay to iterate.** When tuning a *downstream* step (a cut, a crop, a composite,
   a prompt-parse), iterate against the **saved output** of the expensive step — do not
   re-run the paid generation each loop. Persist every fal result to disk and reuse it.
3. **Prove on the cheapest tier first.** Validate the approach on the smallest/cheapest
   model + lowest resolution + `n:1`; scale to the SOTA/large model only once it works.
4. **Batch & reuse.** Upload an input image **once** and reuse its `file_url` across calls;
   use multi-item endpoints (N boxes/prompts in one call) where the model supports it.
5. **Estimate before you spend.** `get_pricing` × the run count before any batch, video, or
   training job. Say the expected cost out loud for anything non-trivial.
6. **On `403 ... Exhausted balance`: STOP, don't retry-spam** (the account is locked, each
   retry is moot). Surface it with the top-up link (fal.ai/dashboard/billing) and switch
   remaining work to a local path if one exists.
7. **Topping up is the user's action** — never attempt to add balance / enter payment.

## Choosing a model — web-search the SOTA FIRST, don't just grep the catalog

`search_models` / `recommend_model` rank by keyword match and trending, **not by what is actually best for your task**. The top catalog hit is routinely *not* the SOTA model — and the catalog is a subset of what exists (Viggle, Sora, some Runway/Pika tiers aren't on fal at all). Picking the first plausible `search_models` result is the most common and most expensive mistake here.

**For any non-trivial "what model should I use for X" decision, do this in order:**

1. **WebSearch the current SOTA for the task** — e.g. `"best model for <task> <current year>"`, `"<task> model comparison"`. Read 1–2 comparison articles. Identify the *named* leading model(s) and which **model class** fits the job (these are different tools, not interchangeable):
   - *image-to-video* (animate from one still + prompt) — Veo, Kling i2v, Hailuo, Seedance.
   - *motion transfer* (drive a character image with a reference video's motion) — Viggle, Kling motion-control, Wan-Animate, One-to-All.
   - *video-to-video restyle* (repaint an existing clip's look) — Luma Ray Modify, Runway. **Restyle repaints the WHOLE frame** — it destroys a flat/transparent background and re-renders props. Wrong tool when you must preserve a clean matte or a specific object.
   - *reference-to-video* (multi-image character consistency) — Kling Elements, Happy Horse.
2. **Map the named SOTA to a fal endpoint** — `search_models` for that *specific* model by name, confirm the variant. If it's **not on fal**, say so and surface the off-fal option to the user (it may need their own account/key) rather than silently substituting a weaker catalog model.
3. **Read the schema and check the real constraint** before committing a paid run — e.g. Kling `motion-control` runs *human* pose detection and **rejects a cartoon/non-human driving video**; some models need a face element, specific aspect, or min subject size. The schema's field descriptions carry these gotchas.

This composes with [[verify-external-claims-rule]] (don't assert a model's capabilities from memory — check the live docs/schema) and `recommend_model` (use it as *one* input, not the decision).

**Burn that set this (skeuo-ui, 2026-06):** needed to animate a fixed stylized 3D character into an on-model run. Grabbed `wan-motion` (Wan-Animate) straight off a catalog `search_models` and shipped it as "SOTA." A WebSearch showed the recognized SOTA for character motion-fidelity is **Viggle** (off-fal) and **Kling 3.0** (on fal as `kling-video/v3/pro/motion-control`); Kling 3.0 — driven by a *generated human run* retargeted onto the character — produced a dramatically better, genuinely premium result. Also burned a full pass on `ray-2/modify` (restyle) before realizing the *class* was wrong: it greyed-out the black background and turned a knob into an eyeball. Research the class and the leader first; the catalog grep is the last step, not the first.

## Credentials

`~/dev/central/.env` (gitignored, mode 600):

```bash
set -a && source ~/dev/central/.env && set +a
```

- `FAL_KEY` — **admin key** (full account scope: inference, key management, billing). Created at https://fal.ai/dashboard/keys. Format: `<uuid>:<hex-secret>`.

Because it's an admin key, treat it like a root credential. For untrusted environments (CI runners, shared scripts) create a scoped inference-only key instead and use that.

Never pass the key as a literal in commands — always via `$FAL_KEY` so it doesn't land in shell history or process listings.

## MCP server

Wired as the `fal-ai` HTTP MCP (`type: http`, `https://mcp.fal.ai/mcp`, `Authorization: Bearer ${FAL_KEY}`). For how MCP servers are configured and synced across surfaces — including the Claude Desktop stdio-shim (`mcp-remote`) needed because Desktop silently ignores `type: http` — see the `mcp` skill; fal follows the standard HTTP-MCP pattern. fal-specific notes:

- **Header is `Bearer` for the MCP**, but `Key` for the REST API (below) — don't swap.
- `FAL_KEY` comes from the process env (`source ~/dev/central/.env`); **never** inline it into `headers`/`env`/synced MCP JSON (`sync-mcp-servers` copies those verbatim).
- Tools surface as `mcp__fal-ai__*` — deferred in Claude Code (fetch via `ToolSearch` before calling), eager in other agents.
- Re-add if missing: `claude mcp add -s user --transport http fal-ai https://mcp.fal.ai/mcp --header "Authorization: Bearer $FAL_KEY"` then `sync-mcp-servers`.

## REST API patterns

Models follow the pattern `fal-ai/<family>/<variant>` (e.g. `fal-ai/flux/dev`, `fal-ai/veo3`). Two endpoints:

**Synchronous (short jobs, <60s)** — `fal.run`:
```bash
curl -sS -X POST \
  -H "Authorization: Key $FAL_KEY" \
  -H "Content-Type: application/json" \
  "https://fal.run/fal-ai/flux/dev" \
  -d '{"prompt":"a cat","image_size":"square_hd"}'
```

**Queue (long jobs, video/large batches)** — `queue.fal.run`:
```bash
# submit
REQ=$(curl -sS -X POST \
  -H "Authorization: Key $FAL_KEY" \
  -H "Content-Type: application/json" \
  "https://queue.fal.run/fal-ai/veo3" \
  -d '{"prompt":"..."}')
ID=$(echo "$REQ" | jq -r .request_id)

# poll status — returns {status: IN_QUEUE|IN_PROGRESS|COMPLETED, queue_position, logs}
curl -sS -H "Authorization: Key $FAL_KEY" \
  "https://queue.fal.run/fal-ai/veo3/requests/$ID/status"

# fetch result when COMPLETED (either URL works)
curl -sS -H "Authorization: Key $FAL_KEY" \
  "https://queue.fal.run/fal-ai/veo3/requests/$ID/response"
```

**Webhook delivery (skip polling)**: append `?fal_webhook=https://your.endpoint/path` to the submit URL. fal POSTs the result there when `COMPLETED`. SDK equivalents: `webhook_url=` (Python), `webhookUrl:` (JS). Useful for serverless workers that shouldn't long-poll.

Status values: `IN_QUEUE`, `IN_PROGRESS`, `COMPLETED`. Cancellation adds `CANCELLATION_REQUESTED`, `ALREADY_COMPLETED`, `NOT_FOUND`.

Note: auth header is `Authorization: Key <FAL_KEY>` for the REST API (not `Bearer`). The MCP uses `Bearer`. This is per fal's docs — don't "fix" it.

## File uploads

fal accepts public URLs or fal-hosted files. To pass a local image/video as input:
- MCP: `mcp__fal-ai__upload_file` returns a fal-hosted URL.
- REST: `POST https://rest.alpha.fal.ai/storage/upload/initiate` → returns a presigned URL → PUT the file → use the returned `file_url` in subsequent calls.

## Pricing

Pay-per-inference, billed per second of compute or per output unit depending on model. Check pricing on each model's fal.ai page before running expensive jobs (video models can hit $1+ per generation). Admin key can view billing at https://fal.ai/dashboard/billing.

## ⚠️ Transparency must be real (alpha)

If an asset must be transparent (logo, icon, sticker, cut-out), the delivered file must actually carry alpha — the rendered result is the spec, not the model's promise. Many editors (notably **OpenAI gpt-image via fal**) return an opaque image with a baked background even when asked for transparency, and `sips -g hasAlpha` can report `yes` while pixels are solid. So: **check actual corner pixels**, and composite onto the real target bg to catch white/black halos.

If alpha is missing, re-matte: run through **`fal-ai/birefnet/v2`** (`model: "Matting"`, `refine_foreground: true`, `output_format: "png"`) — handles fur/hair edges; don't corner-flood-fill (white halos + misses interior white). Video has the same trap: export an alpha codec **and verify the output `pix_fmt` carries alpha** (silent fallback to `yuv420p` = none), or keep the opaque video and clip it on the page with CSS `mask-image` from a still's alpha. If real alpha can't be achieved, **say so** — never ship an opaque rectangle where a floating shape was intended.

Also: never trust a guessed CDN URL — use the exact `file_url` from `storage/upload/initiate` / the result JSON; `file <out>` after every download must report PNG/MP4, not "ASCII text".

## Common pitfalls

- **Wrong auth header.** REST uses `Authorization: Key <key>`, MCP uses `Authorization: Bearer <key>`. Don't swap.
- **Sync timeout on video.** Video models exceed `fal.run`'s sync window. Always use `queue.fal.run` for video/audio long-running models.
- **Stale model IDs.** fal renames/deprecates models periodically. If a model 404s, search the MCP or check https://fal.ai/models for the current ID.
- **Image size strings vs explicit dims.** Some models accept presets (`"square_hd"`, `"landscape_16_9"`), others want `{width, height}`. Check the model's schema via the MCP.

## See also

- `central/skills/web-media/SKILL.md` — source a real/archival asset instead of generating (often cheaper).
- `central/skills/mcp/SKILL.md` — MCP server inventory and adding/removing patterns.
