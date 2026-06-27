---
name: muser
description: Local-first semantic image search — index folders of images and search them by natural-language description (SigLIP/CLIP embeddings + LanceDB, fully offline, no API keys). Use when the user wants to FIND images by what's in them across one or more folders (e.g. "search all the mercedes + bmw asset folders for car-interior / research-buck images"), dedupe a photo library, or reverse-image-search local files.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Muser — semantic image search

**Repo:** `~/dev/Muser` (`https://github.com/connerkward/Muser`)

Embeds images with a SigLIP/CLIP vision encoder, text queries with the matching text
encoder, into one shared space; stores vectors in an embedded **LanceDB** at
`~/.muser/db` (one global index, one table per model). On-device (MPS on Apple
Silicon), no API keys. **Python 3.12 + uv.** Default model `siglip2-b`.

If `~/dev/Muser` is missing: `git clone https://github.com/connerkward/Muser ~/dev/Muser`.
Read `~/dev/Muser/CLAUDE.md` for architecture (embedders, registry, index, service, eval).

## Run it — CLI + embedded service

Always `cd ~/dev/Muser` and prefix with `uv run` (editable install lives in its `.venv`).

```bash
# Warm service: loads the model once, serves a JSON API + web UI on :7777.
# (If it prints "address already in use", it's already running — reuse it.)
uv run muser serve            # http://127.0.0.1:7777

uv run muser models           # list models; siglip2-b is the default
uv run muser index <folder>   # index/re-index (recursive, incremental by mtime)
uv run muser search "a login screen with a blue button" -k 12   # rich CLI output
```

JSON API (preferred when scripting / parsing results):

```bash
curl -s "http://127.0.0.1:7777/api/status"                       # {model, indexed, db}
curl -s "http://127.0.0.1:7777/api/index" -X POST -H 'content-type: application/json' \
     -d '{"folder":"/abs/path","recursive":true}'
curl -s "http://127.0.0.1:7777/api/search?q=<urlenc query>&k=24" # {results:[{path,name,score}]}
```

No daemon? add `--local` to `index`/`search` to run in-process (loads the model each
call — fine for one-offs, slow for many).

## Search WITHIN a specific folder (the common ask)

The index is **global** (one table per model, all folders pooled), but search is
**folder-scoped natively** — pass a directory and only images under it (any depth) are
ranked. Scoping is a LanceDB `prefilter` range on `path`, so the vector `limit` is applied
*after* the folder cut (you get the folder's true top-k, not "globally-top-k that happen
to be in the folder").

```bash
cd ~/dev/Muser
uv run muser index /abs/folder                                   # ensure it's indexed
uv run muser search "car interior research buck" -k 12 --in /abs/folder
# Top 12 … in /abs/folder:   1. 16.2% seat-buck.jpg   2. 13.0% driving-sim.jpg …
```

JSON API — add `&folder=<urlenc abs dir>`; every result path is under that dir:

```bash
curl -s "http://127.0.0.1:7777/api/search?q=car%20interior&k=12&folder=/abs/folder"
curl -s "http://127.0.0.1:7777/api/folders"   # indexed dirs + image counts (for a picker)
```

Web UI: a **scope** box under the search bar (free-text + datalist of indexed dirs w/
counts). MCP: `search_images(query, k, folder="/abs/dir")`.

Notes:
- Scope to **multiple** folders: run one scoped query per folder and merge, or scope to a
  common parent prefix that covers them all.
- siglip2 absolute scores look low (~10–20%); **relative order within the folder** is
  what matters.
- Reveal a hit in Finder: `curl "http://127.0.0.1:7777/api/reveal?path=<abs>"` (open -R).

## MCP (Claude Desktop only)

`mcp-ts/` is an MCP ext-app that renders matches in an interactive gallery inside Claude
Desktop (thin HTTP client of `muser serve`). For Claude Code, prefer the CLI/HTTP above —
headless and parseable. To wire the MCP into Desktop:
`{"mcpServers":{"muser":{"command":"bun","args":["~/dev/Muser/mcp-ts/...","--http"]}}}`
(see `~/dev/Muser/mcp-ts/` and its README for the exact entry).
