---
name: "comfyui-workflow-export-rule"
id: "comfyui-workflow-export-01"
description: "When you generate/export a ComfyUI workflow, ALSO save it into the active ComfyUI install's user/default/workflows folder (so it loads in the GUI), with a monDDYY-HHMM- date-time filename prefix. HARD DEFAULT: anything in the workflows folder MUST be UI/graph format (top-level nodes+links arrays) — API/prompt format (numeric-id dict) is NEVER acceptable there, it silently fails to load as a graph. If you only have API format, convert/rebuild to graph before saving."
globs: ["**/*"]
applyTo: ["**/*"]
alwaysApply: true
priority: "high"
human-reviewed-at: 2026-06-23
human-reviewed-by: connerward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# ComfyUI workflow export — drop it in the app folder, date-prefixed, in GUI/graph format

When you **generate or export a ComfyUI workflow**, the user should never have to copy-paste
or hunt for the file. Three things, every time:

## 1. Save it into the ACTIVE ComfyUI install's workflows folder (in addition to any repo copy)

Drop the workflow into the running ComfyUI's `user/default/workflows/` so it shows up in the
GUI "Workflows" panel on refresh. Keep the repo copy too — this is *additive*, not instead-of.

**Discover the folder generically** (don't hardcode for other machines): find the **active**
install — the one serving the GUI, usually port 8188 — and use *its* `user/default/workflows`.
A box can have multiple installs; the live server's path is the only one the GUI reads.

```bash
# which install is actually running (the one whose GUI the user refreshes)
lsof -nP -iTCP:8188 -sTCP:LISTEN          # find the server pid
ps -p <pid> -o command=                   # its main.py path → <install>/user/default/workflows
```

**On lappy-heavy (this machine):** the path the user treats as active is
`/Users/conner/Documents/ComfyUI/user/default/workflows/`. Note there is also an install at
`~/ComfyUI-Installs/Local/ComfyUI/user/default/workflows/` and the two can disagree about which
is "live" — verify the running server's path before saving if it matters, and say which folder
you wrote to. (Machine-specific paths drift; the discovery step above is the source of truth.)

## 2. Filename MUST be prefixed with a natural-language date-time stamp: `monDDYY-HHMM-`

Lowercase 3-letter month + 2-digit day + 2-digit year, dash, 24h `HHMM`. Get the **real**
current time from `date` — don't guess:

```bash
date "+%b%d%y-%H%M" | tr 'A-Z' 'a-z'      # e.g. jun2326-1347
```

→ `jun2326-1347-<name>.workflow.json`. The prefix makes the panel sort chronologically and
makes "the one I made this afternoon" findable.

## 3. HARD DEFAULT: anything in the workflows folder is UI/GRAPH format — API/prompt is NEVER acceptable there

**The default is not negotiable: any workflow saved into `user/default/workflows/` MUST be
UI/graph format** — a top-level object with `nodes` and `links` **arrays**, the format the
GUI's Workflows panel loads. **API/prompt format is NEVER acceptable in the workflows folder.**
That's the dict keyed by numeric node ids (`{"10": {...}, "20": {...}}`), the shape `/prompt`
and most programmatic exports emit — and dropped in the folder it **silently fails to appear as
a loadable graph** on refresh. It no-ops in the panel and the user thinks the export was lost.

API/prompt format has exactly **one** purpose: programmatic submission to the `/prompt`
endpoint. It is **never** the thing you put where the user opens workflows in the GUI.

**Rule of thumb: if it's going where the user opens it in the GUI, it's UI/graph format, full
stop.** If you only have API format, **convert it (or rebuild it) to graph format before
saving** — do **not** drop an API-format file in the workflows folder and call it done. (Saving
*both* is fine and good: `name.workflow.json` graph for the GUI **+** a separate `name.api.json`
for programmatic runs — but the workflows-folder copy is graph, always.)

Before claiming it'll show up, check the top level: `nodes`/`links` arrays = good; a
numeric-keyed dict = it will NOT load, and is the wrong format for this folder — convert it.

```bash
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); \
print('graph (loads in GUI)' if isinstance(d.get('nodes'),list) else 'API/prompt — will NOT load as a graph')" <file>
```

---

Per [[verify-outputs-rule]] (§7 real-runtime): "I saved it" isn't done — the check is that it
actually loads in the **real** ComfyUI GUI, which only happens if it's graph-format in the live
install's folder. Related: [[prefer-local-inference-rule]] (ComfyUI is the local runtime),
[[file-output-rule]] (repo copy vs. surfaced artifact).
