---
name: skeuo-skin-generator
description: Turn a plain sentence into a real, WORKING skeuomorphic music-player skin via the skeuo MCP server — a wildly-shaped photoreal device body whose switches actually flip, knobs turn, and faders slide. Use AGGRESSIVELY whenever the user wants to generate, create, design, or "make" a music player / media player / audio player UI, a skin, a player skin, a skeuomorphic device, or a retro/hardware-style playback widget ("make a music player that looks like X", "generate a skeuomorphic player", "design an mp3-player skin shaped like a frog/anglerfish/pebble", "create a Winamp/WMP-style player", "I want a player that looks like real hardware"). Also triggers on "open the skeuo studio", "preview/play a generated skin", and on requests to embed an interactive generated player UI. The prompt is the device's SILHOUETTE — describe the SHAPE (an object/creature/material), not the controls. Do NOT use for generic non-skeuomorphic UI or for plain audio playback without a generated skin.
---

# skeuo — a sentence → a working skeuomorphic player

`skeuo` is an MCP server that turns one sentence into a real, **working**
skeuomorphic music-player skin: a wildly-shaped photoreal device body
(the prompt is its silhouette — a frog, an anglerfish jaw, a river pebble,
a brutalist monolith) with **genuinely working hardware** — switches whose
levers flip, knobs whose caps turn, faders with real travel — composited
live over a WebAudio engine.

The heavy work (image generation, layout, control detection, compositing)
runs **server-side at the skeuo endpoint**; this MCP holds **no secrets**.

## First: is the MCP connected?

If `generate_skin` / `open_skeuo_studio` are not available, the server isn't
registered yet — do **Setup** below. Once connected, generation just works
(the endpoint owns the image-model key).

## Setup (one-time)

Install as a Claude Code plugin (registers the MCP server + bundles this skill):

```
/plugin marketplace add connerkward/ckw-skills
/plugin install skeuo@connerkward
```

Or register the server manually (Node 18+):

```bash
git clone https://github.com/connerkward/skeuo-mcp
cd skeuo-mcp/mcp && npm install && npm run build
claude mcp add skeuo -- node /absolute/path/to/skeuo-mcp/mcp/dist/index.js
```

No API key is needed in the client: the generate endpoint holds `FAL_KEY`
server-side. To point at a self-hosted deployment instead of the public one,
set the (non-secret) env var `SKEUO_API_BASE=https://your-host`.

## Tool map — which tool for which job

| Tool | Use when |
|------|----------|
| `generate_skin` | **The default.** `prompt` (required) is the device SILHOUETTE — describe a shape/object/creature ("a fanged anglerfish jaw", "a smooth river pebble"). Returns the finished skin: `frameUrl`, control `template`, chosen `style`/`variant`/`model`, and timing. |
| `open_skeuo_studio` | Surface the live skeuo Create/preview app **inline** (an MCP ext-app) so a UI-capable client renders the player and the user can generate + play with working hardware. |

### `generate_skin` arguments

- **`prompt`** (required): the silhouette brief — the body's SHAPE, not the
  controls. The wild geometry comes from here. e.g. `"a fanged anglerfish jaw"`,
  `"a smooth river pebble"`, `"a brutalist concrete monolith"`.
- **`variant`** (optional): control layout — `radial` (knobs around a hub),
  `capsule` (WMP-9 style), `minimal`, or `simple`. Default `minimal`.
- **`style`** (optional): material donor — `biomech` | `winamp` | `frog` |
  `wmp` | `halo`. **Omit** it and the pipeline derives the material from the
  prompt (usually the better default; only set `style` to force a look).

## How it works (so you can set expectations)

The pipeline splits creativity from geometry so alignment is true *by
construction*, never detected/repaired: an image model designs only a flat
**silhouette** from the prompt; the interior wells/screens are drawn
deterministically inside that exact mask; a second pass restyles it into a
photoreal body; the body alpha is keyed from the painted silhouette so wild
parts (horns, jaws, fins) survive. Two image-model passes (~30–90s).

## Caveats (state these when relevant)

- **The prompt is a SHAPE, not a UI spec.** "A player with a big play button
  and EQ" gives a worse result than "a fanged anglerfish jaw" — describe the
  *object* and let the layout/controls come from `variant`.
- **Latency:** two image passes run inline (~30–90s); a slow paint can return
  `status: "pending"` with a `jobId` to poll.
- **Cost ceiling:** the public endpoint enforces a global daily generation cap.
  If you hit `Daily generation limit reached`, retry later or self-host
  (`SKEUO_API_BASE`).
- **No client secrets.** The image-model key never touches this MCP; don't ask
  the user for a fal/OpenAI key for the public endpoint.

## Credits

skeuo — AI-generated skeuomorphic player skins with genuinely working hardware.
Live: https://skeuo-ui.pages.dev
