# skeuo

**skeuo is an MCP server that turns one sentence into a real, _working_ skeuomorphic music-player skin** — a wildly-shaped photoreal device whose switches actually flip, knobs turn, and faders slide.

![Four skins playing](https://skeuo-ui.pages.dev/og.png)

Say *"a fanged anglerfish jaw"* and get back a finished player: a body shaped like that jaw, with genuinely working hardware composited live over a WebAudio engine. The prompt is the device's **silhouette** — describe the *shape*, not the controls.

**Live demo:** https://skeuo-ui.pages.dev

## Install

Tell your coding agent to add it — one line:

```
/plugin marketplace add connerkward/ckw-skills
/plugin install skeuo@connerkward
```

That registers the MCP server **and** bundles the `skeuo-skin-generator` agent skill. No API key needed in the client — the image-model key lives server-side at the generate endpoint.

(Manual MCP registration, self-hosting, and internals → [`docs/INSTALL.md`](docs/INSTALL.md).)

## What you get

- **`generate_skin(prompt, variant?, style?)`** — a sentence → a finished skin (frame image + working-control template). `prompt` is the silhouette (a shape/object/creature); `variant` picks the control layout; `style` is an optional material donor.
- **`open_skeuo_studio()`** — the live Create/preview app surfaced **inline** as an MCP ext-app, so a UI-capable client renders the player and you generate + play right there.

## How it works

The pipeline splits **creativity from geometry** so control alignment is true *by construction* — never detected or repaired. An image model designs only a flat silhouette from your prompt; the interior wells and screens are drawn deterministically inside that exact mask; a second pass restyles it into a photoreal body; the alpha is keyed from the painted silhouette so wild parts (horns, jaws, fins) survive. The result composites live in the browser with real, manipulable hardware.

## FAQ

**What do I put in the prompt?** A *shape* — "a smooth river pebble", "a brutalist concrete monolith", "a fanged anglerfish jaw". Not a UI spec. The controls come from `variant`.

**Do I need a fal / OpenAI key?** No. The public endpoint holds the image-model key server-side. Set `SKEUO_API_BASE` only if you self-host.

**How long does it take?** Two image-model passes run inline, ~30–90s.

## License

MIT — see [`LICENSE`](LICENSE).
