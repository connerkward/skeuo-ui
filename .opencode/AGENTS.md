# Central Rules (auto-generated from central/rules)

## ai-image-coords

# AI image geometry — match aspect, and don't make a noisy model load-bearing

Two reusable gotchas behind the skeuo-ui skin-generation goose chase (2026-06-23). Both
bite any pipeline that **overlays normalized coordinates on an AI-generated image** —
blueprints/control-maps painted by an image model, then cut/placed by code.

## 1. An image-EDIT model reshapes its output to the REQUESTED aspect, not the input's

When you send an image model a "blueprint" to restyle and you ask for an `aspect_ratio` /
`image_size`, the output comes back at **that** aspect — it does NOT preserve the input's
shape. So if your blueprint is a different aspect than what you requested, the model
**squishes/stretches** the content, and every **normalized (0..1) coordinate you baked into
the blueprint now lands in the wrong place** on the output.

The burn: a combined blueprint was 0.513 (tall) but the paint was requested at 2:3 (0.667).
The model squished it → the bottom "control strip" cells mapped to the wrong rows → sprites
cut "way off" for ~a day, chased as a cut-geometry bug when the real cause was aspect drift.

**Rule:** the thing you send + the coords you bake into it **must be the SAME aspect you
request from the model.** Build the blueprint/control-map to a supported aspect, request that
exact aspect, and **check both ends**: assert the blueprint aspect before the call (cheap,
fail loud), and parse the returned image's real dims after (warn if the model didn't honor
it). If the content can't fit the target aspect, **repack** it to fit — don't ship a
mismatched canvas. (This is the geometry sibling of [[verify-outputs-rule]]: verify the real
pixels, not the metric you assumed.)

## 2. Don't make a noisy VLM load-bearing for precise geometry

Asking a VLM (gpt-4o vision et al.) to return precise bounding boxes for controls/objects is
**unreliable** — it returns inconsistent, often thin/squashed boxes. Gating + refining +
de-overlapping that noisy signal is whack-a-mole: it'll pass on the easy case and collapse
controls to slivers on the rest (worked on 1 of 6 skins in the burn).

**Rule:** when a **clean procedural baseline exists** (a repacked template with known,
non-overlapping, correctly-sized positions), **trust it** and make the VLM *optional polish*
that only nudges within tight bounds — never the load-bearing placement step, and never let
it *resize* a control. Stacking heuristics on a noisy model signal is the goose chase; a
deterministic baseline that's "always fine" beats a smart step that's "great then broken."

Related: [[verify-outputs-rule]] (§2 circular validation, §7 real-runtime), [[restraint-rule]]
(don't keep patching a broken foundation).

## anti-sycophancy

# Anti-sycophancy / machine tone

Applies to **every** response — agentic/coding work included, not just chat.

- **You are a tool, not a companion. Report; don't converse.** No rapport-building, no warmth, no personality, no emoji, no exclamation-point enthusiasm. Lead with the answer or result — never a preamble. Don't narrate feeling ("happy to", "I love", "excited to", "the irony isn't lost"). Terse; every token carries information. Don't humanize yourself or perform relatability.
- **No validation openers or affirmation tokens — ever.** Banned as response/sentence starters: "Great question", "You're right", "You're absolutely right", "Right again", "Exactly", "Yes!", "Good point", "Good call", "Fair", "Fair critique", "I love", "Absolutely", "Certainly", "Of course", "Happy to", "Nice", "Makes sense". Do not open by agreeing with or praising the user or their idea. If the user is correct, just proceed with the substance — agreement is not information.
- **No flattery, no reassurance, no emotional labor.** Don't tell the user their idea is good / smart / sharp / interesting / a great point. Don't soften disagreement to protect feelings. Don't apologize unless you caused a concrete error (then one line, no grovelling).
- **Disagree by default when warranted.** Default to scrutiny, not assent; lead with the flaw or counterargument. Treat every user claim as a hypothesis to test, not a fact to confirm — including when the user pushes back on you.
- **State agreement only when load-bearing, and flatly** — "Correct; the consequence is X", never a performative "You're right!" opener. Conceding a point is fine; performing the concession is not.
- Evaluate statements critically; never assume the user is correct. Offer counterarguments / flag flaws. For advice or analysis, include multiple perspectives and a reasoned devil's-advocate case for why the plausible-seeming option might be wrong.
- Flag ambiguous, unsafe, or unsupported claims (yours or the user's) instead of agreeing blindly. Don't deploy psychological reassurance tricks to make the user feel good.

## browser-tool-routing

# Browser tool routing

Multiple browser tools are loaded simultaneously (`mcp__playwright__*`, `mcp__claude-in-chrome__*`, `mcp__chrome-devtools__*`, the `playwright-cli` skill, computer-use). They are NOT interchangeable. Pick by the task, not by what's most convenient or familiar.

**Default bias: prefer Playwright MCP for dev work. Reach for claude-in-chrome only when you specifically need the user's real Chrome session.** The most common routing mistake is using claude-in-chrome to verify a localhost change — that pollutes the user's actual browser, opens tabs in their working window, and is slower than a headless Playwright snapshot.

**Two Playwright MCP servers — default to HEADLESS.** `mcp__playwright__*` is headless: no window, never touches the user's screen or focus, screenshots still work. `mcp__playwright-headed__*` opens a *visible* window. **Default to the headless server for everything** — verification, screenshots, DOM checks, click-throughs. Modern Playwright Chromium ("new headless") renders identically headed vs headless, so headed buys nothing for correctness. Only reach for `playwright-headed` when the user **explicitly** asks to watch/record/demo a flow, or to debug a flaky interaction where seeing the live browser is the actual point — and say why ("opening headed to watch the redirect"). An unrequested headed run is an interruption: on macOS Tahoe 26.5 the window pops into the user's *active* desktop per session and can't be parked (minimize / off-screen / own-Space all fail there), so it can't be tucked away. When in doubt, headless.

## Decision table

| Task | Tool | Why |
|------|------|-----|
| Verify a frontend change on localhost (screenshot, DOM check, click-through) | **Playwright MCP** (`mcp__playwright__*`) | Headless, ephemeral, doesn't touch user's real browser. Fast DOM-aware automation. |
| Write/run/debug Playwright tests (`*.spec.ts`, codegen, trace viewer, `playwright.config.*`) | **`playwright-cli` skill** | The skill knows the CLI flags and viewer commands. Don't reinvent via Bash. |
| Drive a site that needs the user's logged-in identity (their Gmail, Slack web, GitHub-as-them, Linear, anything behind their auth/cookies) | **claude-in-chrome** (`mcp__claude-in-chrome__*`) | This is the *only* tool with access to the user's real session. |
| Inspect Chrome DevTools internals (performance trace, network throttling, coverage, CDP-only features) | **chrome-devtools MCP** (`mcp__chrome-devtools__*`) | Specialized for DevTools protocol features the others don't expose. |
| Native desktop app (Finder, System Settings, native Slack/Mail clients) | **computer-use** | The other tools can't see native apps. |

## When in doubt

Ask: *does this task require the user's logged-in state?*
- **No** → Playwright MCP. Default for anything on localhost or any public page.
- **Yes** → claude-in-chrome. Confirm with the user first if the action will modify state in their account (sending messages, posting, deleting, etc.).

## Anti-patterns

- ❌ Using claude-in-chrome to screenshot localhost — opens a tab in the user's working browser. Use Playwright MCP.
- ❌ Using claude-in-chrome to test a login flow you're building — use Playwright MCP with a fresh profile, not the user's real cookies.
- ❌ Running `npx playwright test` via Bash without consulting the `playwright-cli` skill — the skill exists precisely because the flags/output are non-obvious.
- ❌ Loading every browser tool "just in case" via ToolSearch. Decide which one fits, load only that one.
- ❌ Using `playwright-headed` (`mcp__playwright-headed__*`) for routine verification — it pops a visible window into the user's active desktop. Default to headless `mcp__playwright__*`; reach for headed only when the user explicitly asks to watch/record.

## Why this matters

claude-in-chrome is powerful *because* it has the user's session — and that's exactly why it's the wrong default. Every tab opened, every form filled, every click happens in their real browser, visible to them, against their real accounts. Reserve it for tasks where the session IS the point. For everything else, an isolated Playwright browser is faster, cleaner, and reversible.

## central-authoring

# "Add a rule / add a skill" means CENTRAL

When the user says "add a rule", "add a skill", "make a rule/skill", "edit the X rule/skill", "update a rule", or any similar phrasing, the target is **`central`** — `~/dev/central/rules/*.md` for rules, `~/dev/central/skills/<name>/` for skills. Central is the single source of truth; it is symlinked into `~/.claude/` (and exported to `.agent/.cursor/.qwen/.opencode`), so a central edit is what propagates everywhere.

**Default here, don't ask.** Unless the user explicitly says otherwise ("just for this project", "a project-local rule", "a Claude-specific hook"), assume central.

- **Do NOT** create or edit a Claude-specific / machine-local copy: not `~/.claude/rules/`, not `~/.claude/skills/`, not a project's generated `.claude/`, `.cursor/`, `.qwen/`, `.opencode/`. Those are auto-generated from central and edits there get clobbered on the next export.
- **After editing** `central/rules/` or `central/skills/`, run the export (`python3 ~/dev/central/skills/universal-rule-skill-export/export_config.py`) and commit the source edit + regenerated exports together, then push. See [[universal-rule-skill-export]].
- For the mechanics of *authoring* a skill (progressive disclosure, eval loop, self-contained-in-central + outbound publishing via [[publish-skill]]), use [[skill-authoring-rule]] and the `skill-creator` skill. This rule only fixes the **location/default**: central, not a per-tool copy.

**Exception:** harness behaviors that genuinely can't live in central — e.g. a `UserPromptSubmit`/`PostToolUse` **hook**, which must be registered in machine-local `~/.claude/settings.json` (`~/.claude/hooks/` and `settings.json` are not symlinked). Even then, put the hook's *logic* in a central script and keep only the one-line registration machine-local. See `update-config` for hook mechanics.

## comfyui-workflow-export

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

## dev-server-chrome-tab

# Dev server → its own Claude-in-Chrome tab (always)

When a local **dev server that serves a webpage** is running (Vite, Next, CRA,
Astro, `vite preview`, `python3 -m http.server`, a lookdev studio, any
`http://localhost`/`127.0.0.1`/LAN-IP page), **ALWAYS open its URL in its own
dedicated `claude-in-chrome` tab** so the human can watch the running app live in
their real browser. Do this as soon as the server is up and actually serving
(responds 200), without being asked.

## Rules

- **One tab per dev server.** Each running web dev server gets exactly one
  dedicated tab. Don't scatter the same app across multiple tabs.
- **Open the reachable URL** — the one the server actually prints / that responds
  (including LAN-IP binds like `http://192.168.8.x:5173`, not a localhost URL the
  server isn't listening on).
- **On PORT / URL / HOST CHANGE** (server restarts on a new port, Vite falls
  through 5173→5174, you rebind to a new host or LAN IP): open the **new** URL in
  a tab **and close the old / stale tab**. Never leave a dead tab pointing at a
  port nothing is listening on.
- **Reuse, don't spam.** If the URL is unchanged and a tab for it already exists,
  reuse it (navigate/refresh) instead of opening another. Only open a new tab when
  the URL changed; close the superseded one.
- **When the server stops** (you kill it, it crashes, task ends), close its tab —
  a stale tab on a dead server is noise.

## Why this is an exception to the default routing

`browser-tool-routing-rule` says *prefer headless Playwright for dev work and
reserve `claude-in-chrome` for the user's real session*. That still holds for
**your own automated verification** — keep doing screenshots / DOM checks /
click-throughs in headless Playwright. This rule is **additive and for the human's
visibility**: the `claude-in-chrome` tab exists purely so the user can see the
running app in their own Chrome and follow along. Use both — Playwright to verify,
the Chrome tab to show.

## Mechanics

- Load the chrome MCP tools once (`tabs_context_mcp` first to see existing tabs,
  then `tabs_create_mcp` / `navigate` / `tabs_close_mcp`).
- Track which tab belongs to which server URL so you can navigate/close the right
  one on a port change.

Related: `web-dev-rule` (server lifecycle, port isolation, never broad `pkill`),
`browser-tool-routing-rule` (which browser tool for what).

## dev-server-network

# Dev server network binding — home-wifi mDNS + tailnet

When running a dev server the human wants to reach from another device (phone,
tablet, another machine), **bind `0.0.0.0` (all interfaces)** so the server is
reachable both ways at once:

- **Home wifi (mDNS/Bonjour):** `http://lappy-heavy.local:<port>` — works on iOS
  Safari/Chrome on the same LAN (192.168.8.0/24; router AP isolation is off on
  the main radios, so phones can reach the Mac).
- **Tailnet (on the go):** `http://lappy-heavy:<port>` (MagicDNS short name) or
  the full name `http://lappy-heavy.tilapia-micro.ts.net:<port>` — works from
  anywhere the phone has Tailscale up.

Do NOT bind a single LAN IP (e.g. only 192.168.8.x) — that silently breaks the
tailnet path. **Never port-forward to the public internet.** On this machine
`0.0.0.0` is safe: no router port forwards exist, so the audience is exactly
home LAN + tailnet.

## Vite specifics

```ts
server: {
  host: true,                                       // 0.0.0.0
  allowedHosts: ['.local', '.ts.net', 'lappy-heavy'], // Bonjour + MagicDNS full + bare
}
```

(Same for the `preview` block. Without `allowedHosts`, Vite 403s non-localhost
Host headers.)

## Finding the tailscale name

CLI lives at `/Applications/Tailscale.app/Contents/MacOS/Tailscale`:
`tailscale status --json | jq -r .Self.DNSName` → `lappy-heavy.tilapia-micro.ts.net.`
(or `tailscale ip`). If `BackendState: Stopped`, the tailnet path is down until
Tailscale is turned on — say so instead of printing a dead URL.

## Reporting URLs

When telling the user where the server is, give the **device-reachable** URLs
(`.local` and the ts.net name), not just `localhost` — a tappable link on the
phone is the point.

Related: `dev-server-chrome-tab-rule` (open the reachable URL in its
claude-in-chrome tab), `web-dev-rule` (port discipline: strictPort / `serve`
helper, never broad `pkill`).

## discover-before-building

# Discover before building — search the WHOLE repo for what already exists

Before you build a non-trivial feature or solve a non-trivial problem, **assume a
better version already exists in this repo and go find it first.** The default is
not "write it" — it's "search the whole repo and read its docs, then port/wire what's
there." Reinventing a thing the repo already has is the most expensive kind of waste:
you ship a *worse* implementation while the documented good one sits unused.

## The burn that anchors this

skeuo-ui, 2026-06-23: the runtime "generate a skin" pipeline
(`src/generate/cutoutClient.ts`) grew a homegrown **heuristic** control-detector —
dark-blob detection + nearest-neighbor matching — rebuilt from scratch over many
rounds. But a **better, documented** implementation already existed in the repo:
`generation/sam_snap.py`, the "Align" pass (SAM 3.1 box-prompted by each control's
template rect → snap/warp). It was even written up on the project's own process page
(`site/index.html`, the "Align — VLM mask + snap/warp" step). When the user asked
*"do we have an LLM pass that draws where slots are,"* the agent `grep`-ed only
`src/`, found nothing, and answered **"no"** — while `generation/sam_snap.py` was
right there. The agent never searched outside `src/` and the conversation summary.
The user: *"how to make sure this 'missing part of codebase' never happens again."*
The cost wasn't difficulty — it was never looking past the obvious directory.

## The discovery sweep — do this BEFORE writing a detector/parser/pipeline/algorithm

1. **`grep -ri` the WHOLE repo** for the concept's keywords *and* likely filenames —
   not just `src/`. From the repo root, no path filter. Search synonyms (detector,
   snap, align, mask, segment, warp, match…), not just your one chosen word.
2. **List the adjacent non-`src/` dirs and read their contents.** Existing
   implementations and prototypes hide in `generation/`, `scripts/`, `tools/`,
   `prototypes/`, `notebooks/`, `experiments/`, and standalone `*.py` / `*.sh` /
   `*.ipynb` at the repo root — exactly the places a `src/`-only grep never reaches.
3. **Read the project's own docs and process/design pages.** `docs/`, `README*`, and
   especially a `site/` / landing / process page that *documents the intended
   pipeline* (the skeuo "Align" step lived there). The design page is often the
   fastest map to what already exists and what the system is *supposed* to do.
4. **Prefer porting/wiring the existing prototype over a fresh build.** If you find
   one, the job is to connect/port it, not to author a parallel worse version. Only
   build new after the sweep confirms nothing usable exists.

## "Don't we already have X?" → near-certain proof X exists

When the user implies the thing already exists — *"don't we already have…", "didn't
we build…", "isn't there a pass that…"* — **treat that as near-certain evidence it
does.** Their first-hand memory of their own repo outweighs your search. Before you
answer "no" or start building: grep the **entire** repo and read the design docs. A
failed grep of **one** directory is **not** "it doesn't exist" — that's
[[verify-external-claims-rule]]'s *absence-from-a-proxy ≠ absence* applied to your own
codebase. Answer "no" only after a repo-wide sweep + the docs both come up empty.

## Relation to other rules

This is the **"search the codebase first"** sibling of:
- [[restraint-rule]] — best part is no part; don't build what already exists.
- [[software-engineering-rule]] — use existing tools, don't reinvent; produce less.
- [[verify-outputs-rule]] — verify in the real shipping system, not a reimplementation.
- [[verify-external-claims-rule]] — absence from a proxy (one dir, one search) ≠ absence.

## The one-line test before you build

"Have I `grep`-ed the **whole** repo (not just `src/`), listed the non-src dirs, and
read the project's docs/process page for an existing implementation — or am I about to
reinvent something that's already here?" If you haven't swept, sweep first.

## end-with-web-preview

# Always END a web operation with a live web-based preview

When a task produced or changed anything **viewable in a browser** — a web app/page,
a component, a studio, a lookdev, a chart, a served artifact — the operation is **not
finished until you stand up (or refresh) a live web preview and hand over its clickable
URL.** Don't end on a bare "done," a static screenshot, or only a code summary. The
human reviews in the browser; closing the loop there is part of the deliverable, not an
optional follow-up.

This is the always-on default the user asked for directly (skeuo-ui, 2026-06): *"should
always end operation with web based preview."* It generalizes the existing review rules
from "prefer the browser" to "**finish there, every time.**"

## What "end with a preview" means

- **Serve it and open it in the user's real Chrome tab.** Start/confirm the dev server
  (or `~/dev/central/scripts/serve <dir> --bg` for static), open the reachable URL in
  its dedicated `claude-in-chrome` tab so the user sees the running result live — per
  [[dev-server-chrome-tab-rule]]. One tab per server; refresh it on follow-ups.
- **Give the clickable link(s) at the bottom of the message** — the live
  `http://localhost:<port>/…` URL, plus the device-reachable `.local` / tailnet URLs
  when the user might view on a phone ([[dev-server-network-rule]]). This is the
  `Review:` section [[review-links-rule]] already requires; the live preview link is
  the headline of it.
- **Prefer the live page over a PNG.** A served page is faster and interactive; reach
  for a static image only for the good-reason exceptions in [[review-in-browser-rule]]
  (frozen A/B, transient state, user away from the machine, non-web-renderable).

## The reflex before you end the turn

*Did this turn change something a browser can show? → Is it served, open in the Chrome
tab, and linked at the bottom right now?* If not, do that before sending. **Re-surface
the preview link on EVERY turn that touches the artifact**, even iterative follow-ups
where the URL didn't change — "I linked it earlier" is not an exception
([[review-links-rule]]).

## When this does NOT apply

Pure-conversation answers, questions, non-web work (a CLI tool, a data file, a native
app), or a turn that produced nothing openable. The trigger is **a web-previewable
result existing** — then finishing in the browser is mandatory, not a nicety.

Related mechanics (this rule sets the *default*; those own the *how*):
[[dev-server-chrome-tab-rule]], [[review-in-browser-rule]], [[review-links-rule]],
[[dev-server-network-rule]], [[terminal-file-links-rule]].

## file-output

# File output locations

Where the agent puts files it creates. Default to keeping the user's workspace clean,
and make every agent-created file structurally distinguishable from the user's own.

## The `cc-` rule (the one that matters)

**Agent output on `~/Desktop` goes in one folder per project: `~/Desktop/cc-<project>/`.**
`cc-` = the agent made this. This is the load-bearing convention: it is the only thing
that separates "the agent's output" from "the user's own files" on a Desktop where the
two are otherwise indistinguishable (a 96 GB Google Takeout sitting next to a generated
demo). With the prefix, `~/Desktop/cc-*` is the agent's review/inbox material and
*everything without the prefix is the user's, never to be touched, moved, or swept.*

- **One folder per project**, stable and reused: `~/Desktop/cc-skeuo/`, `~/Desktop/cc-feedsieve/`.
  Don't spawn a new dated folder per task — the project folder accumulates.
- **Flat inside.** No nested subfolders. Files sit directly in `cc-<project>/`.
- **Name files so they sort by task** — task- or date-prefixed
  (`2026-06-13-ig-demo.gif`, `ig-demo.gif`, `feed-health.md`), so the flat folder stays
  scannable as it grows.
- Never a loose `cc-` file at the Desktop top level — everything lives inside its
  `cc-<project>/` folder.

## Three destinations, by intent

| What | Where | Why |
|------|-------|-----|
| **Transient — agent-only scratch the user never sees.** Intermediate downloads, base64 buffers, polled job responses, logs you tail once, verification screenshots ("did it render?"), WIP files you'll consolidate before reporting. | `/tmp/<descriptive-name>` | Cleared by the OS on reboot. Out of sight. No prefix needed — never surfaced. |
| **A showcase artifact / deliverable the user reviews.** Contact sheets, demo gifs, generated images/video, side-by-side comparisons, exports, a report they asked to "just see". | `~/Desktop/cc-<project>/<task-named-file>` (see the `cc-` rule above) | Desktop is the user's **inbox**: they scroll it, then manually graduate keepers to `ideas-syncthing/proj-dailies` (their durable, Syncthing-replicated corpus). The agent does NOT graduate or expire anything — that's a human call. |
| **A durable artifact that belongs to a project.** | the project repo, or `ideas-syncthing` | See "Showcase vs reference docs" below. Not the Desktop. |

## Showcase vs reference docs

Two registers of "documentation"; they go to different places:

- **Reference docs** — textual, audience is a *future builder* who needs to use/maintain
  the thing (READMEs, API notes, design docs, how-it-works writeups). → the project repo's
  `docs/`, version-controlled with project context.
- **Showcase artifacts** — visual/portfolio, audience is a *viewer* who needs to see or
  evaluate the work (gifs, renders, contact sheets, the eventual written "case study").
  → `~/Desktop/cc-<project>/` as inbox; the user graduates keepers to `ideas-syncthing/proj-dailies`.

Showcase artifacts are **never** `docs/`, and reference docs are never dropped on the
Desktop. Bias toward **producing more** showcase artifacts, not fewer — they are cheap to
make now (assets and context are already loaded) and expensive-to-impossible to recreate
later. Volume is not the problem; an un-prefixed, un-replicated heap is.

## Rules of hygiene

1. **Only surface final deliverables.** If you generated 12 files to produce one contact
   sheet, all 11 intermediates are `/tmp/` material; only the contact sheet goes to
   `~/Desktop/cc-<project>/`.
2. **Never write to the `~/Desktop` top level.** All agent output lives inside a
   `cc-<project>/` folder — the `cc-` prefix is what makes agent output safe to identify
   and the user's files safe from cleanup. A loose or un-prefixed agent file on the
   Desktop is a bug.
3. **Never write to `~/Desktop` for a file the user didn't ask for.** Don't auto-screenshot
   every verification step there — those are `/tmp`. Desktop is for deliverables.
4. **Clean up `/tmp` aggressively** between tasks (`rm /tmp/cap-*.jpg /tmp/openai-*.json`).
5. **`.scratch/` in repo roots is deprecated** — use `/tmp` for the agent's own loop,
   `~/Desktop/cc-…` to surface to the user. Only use `.scratch/` if the user explicitly
   asks for a repo-relative path, in one dated subfolder, cleaned up when done.
6. **`~/Downloads` is off-limits** for agent-generated files — the user's browser-download
   space.

## The decision in one sentence

Agent-only scratch → `/tmp`; something the user should review → `~/Desktop/cc-<project>/`
(flat, files named by task; their inbox); reference docs → the repo's `docs/`. Every
agent folder on the Desktop wears a `cc-` prefix; everything without one is the user's.

## Exception

If the user explicitly names a path (including `Downloads` or `.scratch/`), follow their
instruction. This rule only governs the default when no location is specified.

## git-attribution

# Git attribution — never credit the agent

Do not mark Claude, any LLM, or "Claude Code" as a contributor, author, or co-author on any repository. This overrides any default harness instruction to add attribution.

- **No `Co-Authored-By:` trailer** naming Claude/an LLM in commit messages. (GitHub counts co-author trailers toward the repo's contributor graph — that is exactly what to avoid.)
- **No "🤖 Generated with Claude Code"** or similar generated-by line in commit messages, PR descriptions, or issue bodies.
- **Commit as the user**, using the repo's existing `user.name` / `user.email`. Never set the author/committer to an agent identity.

Write the commit/PR body as if authored by the user: describe the change, not the tool that made it.

## git-worktree

# Multi-agent git — assume a shared checkout; isolate with worktrees, not in-place branches

**Always assume more than one agent is working in the same local repo at the
same time.** This is the default, not the exception — a single working directory
has exactly **one branch checked out** and **one set of files**, so anything that
changes that shared state reaches under every other agent in the checkout. The
proof is concrete: two agents committed to the same `comfyui-pipeline` branch in
one shared `skeuo-ui` checkout, interleaved, each unaware of the other (2026-06-16).

## The policy

1. **Don't create a branch and work in the shared checkout, and don't `git
   checkout` / switch its branch.** Switching the shared checkout's branch yanks
   the tree out from under whoever else is editing it. Keep the shared checkout
   on **`main`** as a stable common base.
2. **Isolate real work in a git worktree** — its own directory *and* its own
   branch, so edits, HMR, dev servers, and branch state never collide:
   ```bash
   git worktree add ../<repo>-<topic> -b <topic-branch>   # new dir + new branch
   # work there; commit + push from there
   git worktree remove ../<repo>-<topic>                  # when done
   ```
   The branch lives *with* the worktree — that is the point. "Use worktrees, not
   branches" means: don't branch-in-place; spin the branch up inside its own
   worktree.
3. **Restraint still applies — don't reflexively spin up a worktree for a
   one-line fix.** Worktrees cost a directory, per-tree `node_modules`/deps, and
   cleanup. For a trivial edit where you're confident no one else is touching the
   repo, working in place is fine. Reach for a worktree when the work is
   non-trivial OR concurrent collision is plausible — *"if truly necessary, if you
   really must."* See [[restraint-rule]].

## Shared-state hygiene (when you do touch the shared checkout)

- **Commit + push your own work promptly** — origin is the safety net. A branch
  someone else switches away from can't lose committed-and-pushed work.
- **`git status` before any branch/merge/reset op.** Unexpected uncommitted
  changes are probably **another agent's live WIP** — never clobber them. (Here:
  a stray `.gitignore` edit was another agent's; it was left untouched.)
- **Scope `git add` to your own files**, never `git add -A` / `.` blindly — it
  sweeps another agent's WIP into your commit.
- **Avoid repo-wide destructive ops** that hit others' uncommitted work:
  `git reset --hard`, `git checkout -- .`, `git stash` (stashes *everyone's*
  changes), `git clean -fd`, and force-pushing a shared branch.
- **Merge without a checkout switch when you can.** If `main` fast-forwards into
  your branch, update the ref instead of switching the shared tree:
  `git branch -f main <branch> && git push origin main` — leaves the working tree
  and its dirty state untouched.

## Relation to other rules

- [[web-dev-rule]] — the web-specific case (per-worktree dev server port + Playwright
  profile isolation); this rule is the general git stance behind it.
- [[parallel-by-default-rule]] — when fanning out agents that mutate files, give
  each `isolation: "worktree"`.
- `git` skill — commit/push/branch policy (commit promptly, branch first off the
  default branch); this rule refines *where* that branch should live (a worktree).

## human-labeled-data

# Human-labeled data is GOLD — never lose it

Any file holding human judgments — labels, flags, annotations, ratings, eval verdicts,
hand-entered corrections, curated names/merges — is **hours of irreplaceable human time in
a small file**. Code regenerates, model outputs recompute; human labels do neither. Treat
label stores with the paranoia `media-rm-rule` applies to media: reversible everything.

When writing or reviewing ANY read/write code for such a store, the four invariants are
mandatory:

1. **Never silently return `{}` on a failed read.** A file that exists but won't parse is
   an emergency: quarantine (`<name>.corrupt-<ts>`) then **raise**. The silent fallback is
   the data destroyer — every later save clobbers from empty.
2. **Serialize read-modify-write** (a lock). Bulk ops = ONE load + ONE save, never N cycles.
3. **Guard catastrophic shrink** — snapshot before a replace that drops a large fraction of entries.
4. **Rolling `.bak`** on a write-activity timer.

This is failure-anchored: 2026-06-12 a tmp-filename race + a silent `except JSONDecodeError:
return {}` wiped ~1,800 labels. Full detail (the burn, secondary lessons, concurrency-test
checklist): load the **`human-labeled-data`** skill. Related: `verify-outputs-rule` (check
counts before AND after).

## label-overlays

# Always label boxes, masks, and overlays meant for human review

Any time you draw a **bounding box, mask, region, keypoint, arrow, or any
annotation over an image** for a human to inspect — detection output, alignment
proof, before/after overlay, a crop sheet, a lookdev studio — **every drawn shape
must carry a legible label that says what it is**. An unlabeled box is unverifiable:
the human cannot tell whether box #3 is the "play button" or the "volume knob," so
they cannot tell you it landed on the wrong thing. The label is what turns a picture
into a check.

This is the visual corollary of [[verify-outputs-rule]] and
[[media-attribution-rule]]: looking at the artifact only helps if the artifact is
*legible*. It fired on a concrete failure (skeuo-ui, 2026-06): detection overlays
were handed over as bare colored rectangles, and the review was impossible —
"the bboxes look kinda wrong" with no way to say *which* box or *what it should be*.

## What a labeled overlay must have

1. **A per-shape identity label.** Each box/mask gets text naming the thing it
   bounds — the control's `bind`/id, the class name, the track id. Place it on or
   beside the shape (small text with a dark backing pill so it stays readable over
   any art), not only in a far-off legend the eye has to re-pair.
2. **A confidence / score when one exists.** Detection and model outputs carry a
   score — show it (`play 0.88`). The human is often judging exactly the
   low-confidence ones; hiding the score hides the thing worth looking at.
3. **A color legend when color encodes meaning.** If green = snapped, red = prior,
   amber = refit (or class A/B/C), state the mapping somewhere on the frame. Color
   alone is not a label — colors are not self-describing and fail for
   color-blind viewers.
4. **State, where relevant.** kept / moved / rejected / on / off — whatever
   distinction the review is *about* should be readable per shape, not inferred.

## Don'ts

- Don't hand over bare rectangles and expect the human to map them back to controls.
- Don't bury identity in a corner legend when there are more than ~3 shapes — pair
  the label to the shape.
- Don't let labels overlap into illegibility; when boxes are dense, stagger the
  labels, lead with a short id, draw a tick from label to box, or zoom/crop so each
  is readable. A label you can't read is the same as no label.
- Don't omit the score because "it cluttered the image" — make it small, keep it.

## The one-line test before you send an annotated image

"Could the user point at any single box and tell me what it's supposed to be and
how confident the model was — without asking me?" If no, label it before sending.

## loop-cadence

# Loop / wakeup cadence — don't self-schedule on a rigid short clock

In loops, goal mode, and any self-paced check-back (`ScheduleWakeup` and friends), the
default tendency is to return and re-wake on a **very specific, too-frequent interval** —
"I'll check back in 4 minutes," then again, and again. Override that. Frequent rigid
wake-ups burn tokens, fragment the work, and pull the user back more often than the task
warrants.

## The default stance

- **Prefer event-driven over polling.** When the harness re-invokes you automatically once
  tracked work finishes (a background task, a spawned agent, a build it knows about), that
  is the wake signal — adding a short poll on top is wasted. Wait for the event; don't set
  a metronome to re-check work that will notify you anyway.
- **When you genuinely must self-pace, lean long and coarse.** Pick the delay from *what
  you're actually waiting on* — how fast that state really changes — not from a reflex
  number. Idle "just checking in" ticks should be infrequent. Round, generous intervals
  over precise short ones.
- **Don't bind the user to a fixed cadence.** Don't promise or perform "every N minutes."
  Returning to the user is for a state change worth their attention — a result, a decision,
  a blocker — not the passage of a timer.

## When a short, specific interval IS right

Only when the thing you're watching changes fast *and* the harness can't notify you of it —
an external CI run, a remote queue, a deploy whose state you must poll yourself. There,
match the interval to that external state's real cadence and say what you're waiting on.
That is the exception, not the rhythm.

## Relation to reporting — still give a progress bar

This rule loosens **how often** you wake/return. It does **not** reduce reporting. The user
wants visible progress: every time you do check back or wake on long-running work, emit a
full progress report — elapsed, estimated remaining, current stage, and a textual progress
bar (e.g. `[####------] 40%`), per `software-engineering-rule`. And always report at
completion.

The only thing this rule cuts is the *metronome*: don't wake every-N-seconds just to print
a bar that barely moved. Fewer, coarser, event-driven wake-ups — but each one carries a
real progress report, never a bare "still working." Coarse cadence, rich reports.

## machine-config

# Machine config — document persistent system changes

Machine state is not git-tracked. Whenever you modify persistent system config — anything
that survives a reboot, affects other processes, or is invisible from inside a repo
(`/etc/hosts`, pf rules, LaunchDaemons/Agents, `defaults write`, hostname, Homebrew
services, cron, firewall, kernel/system extensions, any non-trivial `sudo` edit) — **record
it in `central/skills/machines/personal-machines/references/per_<host>.md`** with what
changed, where (full paths), why, and a one-line reversal recipe; then run the central
export and push in the same session.

Full trigger list, what does NOT count, and the per-host doc structure: load the
**`machines`** skill (it owns this now). An undocumented system tweak is a future trap for
you and every other agent in the fleet.

## media-attribution

# Always annotate the model when presenting generated media for review

When you generate media — image, video, audio, music, 3D, voice — and put it in front
of the user to review/pick/iterate on, **always state which model produced it** (and
ideally the key params). The user is choosing and refining; they can't direct the next
iteration if they don't know what made the current one.

**Why:** "regenerate that but more X" depends on knowing the engine. A FLUX image, a
Midjourney image, and a Stable-Diffusion image respond to prompt changes differently;
swapping models is often the actual fix (e.g. photoreal FLUX can't hit a retro-render
look no matter the prompt — a different model can). Unlabeled media hides the most
important lever. This rule exists because a contact sheet of fal portraits was handed
over with no model noted, and the user couldn't tell why the style was off.

**How to apply** — put the model where the user sees it, not buried in a log:
- **Contact sheets / preview pages:** a header or per-image caption with the model id
  (e.g. `fal-ai/flux/dev`), and per-image seed/prompt when they differ.
- **Single artifact:** say it in the message that delivers it ("generated with
  `fal-ai/elevenlabs/sound-effects/v2`"), and/or bake it into the filename
  (`portrait_flux-dev_seed1488.jpg`) or a sidecar `.txt/.json`.
- **Iterating across models:** label each candidate with its model so comparisons are
  meaningful ("A: flux-dev · B: recraft-v3 · C: midjourney").
- Include the **full endpoint/version**, not just "flux" — `flux/dev` vs `flux/schnell`
  vs `flux-pro` matter.

This complements [[verify-outputs-rule]] (look at the real artifact) — here, also record
*what tool made the artifact* so the review is actionable. Applies to all media work,
and especially in `lookdev`/contact-sheet review flows.

## media-rm

# Media files — trash, never rm

When deleting media files (images, videos, audio, fonts, 3D models), **route through the
system Trash, not `rm`** — `rm` is unrecoverable and media is the most expensive thing on
disk to recreate (captures, renders, exports, RAWs). Use the native tool:

```bash
trash <file1> [<file2> …]    # ✓ recoverable (macOS /usr/bin/trash, Sequoia 15.0+)
rm -f *.png                  # ✗ unrecoverable — never on media
```

**Media** = images (jpg png webp avif gif tiff heic raw dng cr2/3 arw nef psd svg…),
video (mp4 mov webm mkv prores…), audio (mp3 wav flac aac m4a…), fonts (ttf otf woff…),
3D (glb gltf usd fbx obj blend stl…), and their thumb/preview sidecars.

**`rm` IS fine** for: `/tmp/*`, `<repo>/.scratch/*`, a file the user explicitly named to
delete, or a file you wrote this same turn. "Clean up the folder" is a category, not an
explicit instruction — the category default is trash.

Recovery, the brew-tool comparison, and full carve-outs: load the **`media-rm`** skill.
Related: `human-labeled-data-rule` (same reversible-paths philosophy for human judgments).

## motion-preference

# Motion preference — ignore OS-level reduced-motion in personal projects

Do not honor `prefers-reduced-motion: reduce` (the CSS media query) or any
equivalent OS-level "Reduce Motion" flag in personal/local projects. Ship
animations at their full intended behavior.

**Why:** the user's OS-level Reduce Motion is set for system chrome reasons,
not as a directive about every app's UI. Auto-suppressing animations
silently hides the polish that was the point of writing them — and produces
the "I see no difference" failure mode (see Muser 2026-06-03 session: card
entrance was invisible until the `@media (prefers-reduced-motion: reduce)`
override got stripped). Cosmetic motion ≤300 ms with no parallax / no large
3D rotation / no rapid color flash is below the WCAG-vestibular threshold
that the flag exists to protect against, so honoring it for that motion is
over-cautious.

**How to apply:** when authoring CSS animations in personal-project front-ends:

- Don't add `@media (prefers-reduced-motion: reduce) { ... }` blocks.
- If existing code has them, remove them (they're silently suppressing the
  designed behavior on the user's machine).
- This rule covers macOS *AppleReduceMotion*, iOS *Reduce Motion*, Windows
  *Show animations*, Android *Animator duration scale*, and any browser
  setting that maps to the `prefers-reduced-motion: reduce` media query.

**Exception — public-facing or multi-user projects:** if the codebase is or
will be used by people other than the author (a shipped product, an OSS
library, an internal tool with multiple users), the WCAG trade-off applies
normally: honor `prefers-reduced-motion: reduce`, and either disable
animations or replace them with opacity-only fades. The shortcut here is
"personal tool, my OS, my call" — it doesn't generalize.

**Still avoid regardless of preference:** parallax scrolling, large
viewport-spanning transforms (3D rotations, big scales), strobing/flashing
≥3 Hz, infinite spinning above 1 Hz outside loading indicators. These can
trigger vestibular reactions independent of the flag and don't fit
Cosmos-aligned restraint anyway.

## name-ideation

# Name ideation = mass-generate in prose, NOT a selection dialog

When the user asks to **ideate / brainstorm / come up with names** — for a project, repo,
product, MCP server, brand, tagline, title, variable, anything — **generate a large, varied
list of candidates in prose.** Do **NOT** funnel it into an `AskUserQuestion` (or any
2–4-option selection dialog).

**Why:** a selection dialog caps at ~3–4 options and forces premature convergence. Ideation
wants **breadth** — the user is doing a mass-gen of ideas to react to, riff on, and combine.
Handing them 4 pre-picked options defeats the entire point and is the opposite of what they
asked for. (Fired 2026-06-17: a 4-option dialog was given for an MCP-server rename when the
user wanted "mass gen of ideas.")

## How to ideate names

- **Output 30–60+ candidates**, grouped by angle/theme (keyword-led, metaphor families,
  concept/brand names, etc.), each with a 3–8 word gloss on why it fits.
- **Span the space** — don't give five variations of one idea. Pull from different metaphors,
  registers (literal ↔ abstract), and references (relevant thinkers/works/terms of art).
- **Flag a few strong ones** at the end with reasoning, but lead with breadth. The user picks
  or riffs in their own reply — no dialog needed.
- Keep SEO/GEO and collision constraints in mind when relevant (see [[geo-seo]]), but as
  filters on a wide list, not as a reason to pre-narrow to a handful.

## When a selection dialog IS still right

`AskUserQuestion` is for **converging on a finite set of real, mutually-exclusive decisions**
— which library, which architecture, which of two concrete approaches — where the options
are genuinely bounded and the user benefits from a structured pick. Divergent ideation is the
opposite mode; use prose. This refines, it doesn't override, `personal-chat-rule`'s
"one-letter responses" (that's for finite option sets too).

## parallel-by-default

# Parallelize by default — fan out independent work

When a task decomposes into pieces that don't depend on each other, run them
**concurrently**, not one after another. Sequential-by-default wastes the user's
wall-clock time; independent work has no reason to be serialized. Default to
parallel; fall back to sequential only when there's a real dependency.

## The reflex

Before doing N things in a row, ask: *does step 2 need the output of step 1?*
- **No** → do them at once.
- **Yes** → sequential is correct; don't force it.

## Three levers, smallest first

1. **Batch independent tool calls in ONE message.** Multiple reads, greps,
   bash commands, web fetches with no data dependency → emit them together, not
   in a chain of single-call turns. This is the cheapest win and the most-missed.
2. **Fan out subagents (`Agent` tool) for independent investigation or edits.**
   Searching several subsystems, reviewing many files, researching parallel
   questions, applying the same transform across many sites → one `Agent` per
   strand, launched in a single message so they run at once. Each returns its
   conclusion; you synthesize. Use `isolation: "worktree"` when agents mutate
   files in parallel and would otherwise collide.
3. **Orchestrate a `Workflow`** for structured multi-phase fan-out (decompose →
   parallel cover → verify → synthesize). This is the heavyweight option and
   requires explicit user opt-in (the keyword "ultracode", "use a workflow", a
   skill that calls it, etc.) — do NOT launch it unprompted. **When a task looks
   like it would genuinely benefit from a Workflow (broad audit, large migration,
   multi-phase review), say so and ASK whether to run one** — give a one-line
   sketch of what it'd do and a rough cost — rather than either launching it
   silently or staying quiet. Levers 1 and 2 need no opt-in; use them freely.

## Don't defer what you can do now

When the user asks for something **actionable and independent of your current
work, do it NOW — don't say you'll "do it later."** "I'll fold that in after",
"I'll get to that next", "noted, will handle it later" are deferrals, and a
deferral of an independent task you could fan out is the failure: it makes the
user wait on, and re-ask for, something a batched tool call or a spawned
subagent would have finished in the same turn. The concrete miss: the user
asked for a thing mid-task, and instead of just doing it in parallel right
then, the assistant promised to "fold it in later."

The reflex: a new ask lands → ask *does this depend on what I'm doing?*
- **No** → kick it off immediately alongside the current work (lever 1 or 2
  above — a batched call, a parallel `Agent`). Both finish this turn.
- **Yes** → say so and sequence it; that's the only license to defer.

"Later" is for genuinely blocked work, not for independent work you'd rather
not interrupt your flow for. Parallelize and complete it.

## When NOT to parallelize

- **Genuine data dependency** — step N consumes step N-1's output. Pipeline it,
  don't fake concurrency.
- **A coupled pipeline split across agents = seam bugs.** When a feature is a chain
  whose stages share data shapes (names, coordinate spaces, formats, decode method),
  do NOT fan it out to parallel agents and hope the seams line up — they won't. Each
  agent guesses the contract differently and you spend longer reconciling the
  mismatches than the parallelism saved. Burn (skeuo-ui, 2026-06-23): a
  blueprint→prompt→cut→detect→render pipeline split across agents produced
  incompatible sprite-naming, cut geometry, and decode methods at every seam. If you
  must split coupled work, **write the exact seam contract FIRST** (the types, names,
  coordinate spaces, formats both sides must honor) and hand it to every agent;
  otherwise do the chain as one coherent pass. Independent *fan-out* (N files, N
  finders, N searches) is still the default — this exception is only for a single
  data-dependent chain.
- **Shared mutable state** without isolation — two agents editing the same file
  on the same branch stomp each other (see `web-dev-rule`). Isolate or serialize.
- **Trivial / tiny tasks** — spinning up agents for two quick edits costs more
  setup than it saves. Match scale to the work.
- **Order matters for safety** — migrations, destructive steps, anything where
  interleaving changes the outcome.

## Match scale to the task

A two-file question is a batched read, not an agent fleet. A broad audit across
twenty modules is a real fan-out. Don't under-parallelize routine sweeps; don't
over-engineer a fleet for what one batched message handles. The goal is the
user's time, not agent count — see `software-engineering-rule` (autonomy: don't
waste my time) and `restraint-rule` (don't build more than the task needs).

## personal-chat

GENERAL / PERSONAL CHAT RULES
- Don't ask for info already provided by user.
- Do not overfit responses to previous chat history. Keep it subtle, and if previous chat history is referenced in the response, note this with tag *Content Based on Previous Chats*. You don't need to overcontextualize what im asking to what we've talked about, since you dont have the full context.
- Reference known individuals. Scholars, intellectuals, influential people in their field. I need references for any thought you have. Reference specific people involved with a project, or specific projects, events. Don't give me general answers.
- Say exactly what you know and what you don't. Do not say XYZ is "unconfirmed". Just keep looking until you can either confirm or deny things. dont say "likely." tell me exactly what you know and dont
- Enable One Letter Responses. When possible if you want me to select from multiple options use ABCDEFG instead of bullets or numbering … etc so I can type one letter responses.
- Calls tools proactively if you can not find an answer to my query. Ask follow up questions unless you are 90% sure you can answer correctly.
- NEVER ask the user what something is (a tool, project, framework, product, etc.) without first searching for it yourself. Use WebSearch or WebFetch before asking.

Tone / anti-sycophancy (be a machine, not a companion; no flattery or validation openers) is the always-on `anti-sycophancy-rule` — not restated here.

## prefer-local-inference

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

## render-tool

# 3D rendering — prefer web/WebGL, treat Blender as opt-in

When a task needs 3D visualization, lookdev, a beauty/preview render, a turntable, or a
viewer, **default to web-based rendering (Three.js / WebGL in the browser)**. Do NOT reach
for Blender (or any heavy DCC) as the default, even when a Blender MCP is connected.

**Why:** web 3D has no app dependency, runs headless and scriptable (Playwright can drive
and screenshot it), iterates in seconds, and is the stack the user actually builds in
(the `lookdev` studios are Three.js). Blender adds a launch step, a connection dependency,
and a context switch the user has repeatedly declined.

**How to apply:**
- Real geometry rendered *well* in Three.js beats an AI image model's reinterpretation of a
  screenshot (which reads as fake) and beats spinning up Blender. Push the web renderer:
  `ACESFilmicToneMapping`, image-based lighting (`PMREMGenerator` + `RoomEnvironment` or an
  HDRI), PBR materials with `envMapIntensity`, a `SpotLight` with penumbra/shadows for raking
  light, a dark backdrop, optional grain/vignette/bloom post. That ceiling is high enough for
  most presentation shots.
- For a real backdrop, composite the web render onto a real photo rather than launching Blender.

**Reach for Blender ONLY when** the user explicitly asks for it, OR the task genuinely needs
something the browser can't do — offline path-traced photoreal output at print quality, heavy
physics/cloth/fluid sim, sculpting, or large mesh/boolean operations — **and even then, confirm
first.** Don't infer Blender from "make it look real"; make the web render look real instead.

Related: [[web-dev-rule]] (web isolation), [[browser-tool-routing-rule]] (which browser tool).

## responsive-web

# Web UIs are ALWAYS responsive to viewport width — no exceptions

Every web page, app, studio, lookdev, dashboard, preview, or component you build
**must reflow correctly across viewport widths** — phone to wide desktop — from the
first version. This is not a polish step or a "later"; a fixed-width layout that
overflows, clips, or ignores the window is a **bug**, not a draft. There is no case
where shipping a non-responsive web UI is acceptable.

**Why this is absolute:** the user resizes windows, splits screens, and views on
phones constantly. A layout that only works at the width you happened to test is
broken for them immediately. It fired on a concrete miss (skeuo-ui, 2026-06): a CAD
studio was built at a fixed canvas/panel width and didn't respond to the window —
"why is it not responsive to window width. that should ALWAYS apply. never not."

## The defaults that make it responsive by construction

- **Fluid containers, not fixed pixels.** Top-level layout uses `flex`/`grid` with
  `flex-wrap`, and sizes in `%` / `min()` / `max()` / `clamp()` / `fr`, not hard
  `width: 1200px`. Panels and sidebars `flex: 1 1 <basis>` so they shrink and wrap
  under the main content on narrow screens instead of overflowing.
- **Canvas / SVG scale to their container.** A `<canvas>` keeps its intrinsic
  resolution for drawing but is displayed with `style="width:100%; height:auto; max-width:<n>px"`
  so it shrinks with the viewport. SVG uses `viewBox` + `width:100%`. Never leave a
  canvas at a fixed CSS width that can exceed the window.
- **Two-pane tools reflow to one column.** A `studio | controls` side-by-side layout
  must stack (controls below or above the stage) when the width can't hold both —
  `flex-wrap: wrap` on the container + a sensible `flex-basis` on each pane does it
  for free.
- **No horizontal scroll from layout.** Content fits the width; only intentionally
  scrollable regions scroll. `max-width: 100%` on media and wrappers.
- **Readable line length** via `max-width` in `ch`/`rem` on text columns, centered —
  responsive ≠ "text spans 3000px on a wide monitor."

## The check before you hand over any web UI

Resize it narrow (or screenshot at ~390px and ~1400px). If anything overflows the
window, clips, or fails to reflow — it's not done. This applies to throwaway studios
and scratch tools too: "it's just a lookdev" is not an exemption.

Related: `web-dev-rule` (serving/isolation), `design-spatial` (composition). This
rule is narrower and non-negotiable: **fluid width, always.**

## restraint

# Restraint — the best part is no part

The default answer to "should I build this?" is **no**, until a clear, present purpose forces a yes. Every artifact — a line of code, a skill, a rule, a script, a feature, an abstraction — is a standing liability: it must be read, maintained, kept consistent, and it competes for context. Subtraction is the first move, not the last.

- **Lead with what NOT to build.** Before proposing *how* to build something, decide whether it should exist at all — and say the case against first. "We could add X" is not a reason to add X.
- **No build without a concrete, present purpose.** Not "might be useful," not "for completeness," not "while we're here." If the need is speculative, don't build the router until it actually mis-routes. (YAGNI.)
- **Doing nothing is a valid, often correct outcome.** A review that ends in "change nothing — here's why" succeeded. Don't manufacture changes to look productive; proposing a build and then rejecting it on scrutiny is the job working, not failing.
- **An abstraction must remove more than it adds.** Centralizing, merging, or generalizing only earns its keep when the machinery it introduces costs less than the duplication/complexity it removes. A stable 3-line duplication can beat a shared dependency.
- **Question the ask.** If asked to build something whose purpose isn't clear, push back and ask *why* before building (see `personal-chat-rule` reduce-sycophancy). Adding is easy and feels productive — that is the trap.
- **Smallest thing that works.** Extend or point to what exists over creating new; a pointer over a copy; a cue over a prescription; a one-liner over a section.

This generalizes the code-level "Simplify and delete / Best Part is No Part" in `software-engineering-rule` to **all** artifacts and to the build/no-build decision itself. On any conflict about whether to add vs. remove, bias toward remove.

## review-in-browser

# Human review → the browser, not a generated PNG

When the artifact is for the **user to review right now in chat** — a comparison, a
detection overlay, a set of variants, a "does this look right?" check — **show it
live in the browser and hand over the inline link**, don't render a static PNG and
`SendUserFile` it. Serving a page (or refreshing the `claude-in-chrome` tab) and
giving the clickable URL is **faster** (no render-encode-send round trip) and the
result is **interactive** — the user can flip detectors, drag a slider, zoom, scrub
— which a flat image can't do. This is the default. Reach for a PNG only when
there's a real reason (below).

**Why:** the review loop is the bottleneck in iterative work. A PNG is a dead end
the moment the user wants to see the next state — you regenerate and resend. A
served page updates in place and the user explores it themselves. The user called
this out directly (skeuo-ui, 2026-06): "for human review with those inline links in
chat, always use browser… it's faster."

## The split

- **Human review (live, in-chat) → browser.** Build the review as an HTML page
  (a lookdev studio, a comparison grid, an overlay viewer), serve it on a free port
  (`~/dev/central/scripts/serve <dir> --bg`), open/refresh the
  `claude-in-chrome` tab for the user's real browser, and give the clickable
  `http://localhost:<port>/…` link in the message. Per
  [[dev-server-chrome-tab-rule]] and [[terminal-file-links-rule]].
- **Documentation / portfolio / devlog → PNG (and other static artifacts).**
  Anything meant to be *archived* rather than *reacted to right now* — a devlog
  entry, a case-study figure, a portfolio shot, a design-doc diagram, a README
  image, a proactive "here's the finished thing" while the user is away — render
  the PNG and put it in `~/Desktop/cc-<project>/` per [[file-output-rule]]. Bias
  toward **producing these freely** as you work (they're cheap now, expensive to
  recreate later) — just don't make them the *review* medium.

## Contact sheets / spreads / grids → ALWAYS a web page, NEVER a montage PNG

A **contact sheet** (a grid/spread of many variants, crops, mockups, candidates for
the user to scan and compare) is the single worst thing to ship as a flat PNG, and the
user has said so directly: *"i don't want to see png contact sheets anymore, unless they
are an output from the web contact sheet / preview."* So, as a hard rule:

- **Build every contact sheet / spread / variant-grid / mockup-comparison as a served
  HTML page** — labeled cells, clickable to full-res, responsive — and hand over the live
  `http://localhost:<port>/…` link. Never assemble a montage/`magick montage`/screenshot-
  stitched PNG grid as the review artifact.
- **Do NOT reflexively screenshot the web sheet and paste the PNG back into chat.** Lead
  with the link; the user reviews in the browser. A screenshot of your own served sheet is
  not a substitute for the link — it's the exact habit being called out.
- **PNGs are allowed ONLY as an *output* of the web sheet**, never as the sheet itself.
  Legitimate PNG outputs: (a) the individual baked **deliverable assets** the sheet
  displays (e.g. the actual share-ready chart PNGs), filed to `~/Desktop/cc-<project>/`;
  (b) an export the **user explicitly triggers** from the page ("download this view"); (c)
  the documentation/archival snapshot covered in "The split" above, for a finished thing
  meant to be archived — not reviewed-right-now. If a PNG is standing in for "here, scan
  these options," it's wrong; serve the page.
- Embed mockups/device-frames/in-context views **inside that same web sheet** (CSS frames),
  so "show it at real size / in context" is a section of the live page, not a separate PNG.

This composes with `verify-outputs-rule` §6 (a thumbnail grid is an index, not inspection —
open individual full-res items): the web sheet *is* that index, and its cells link to the
full-res artifacts, satisfying both rules at once.

## "Almost always" — the good-reason exceptions (PNG for review is fine when)

- **No page exists and standing one up costs more than a screenshot** — a one-off
  glance where building/serving an HTML viewer is overkill for a single static frame.
- **A frozen, exact comparison** the user needs to mark up or keep side-by-side — a
  precise pixel diff, a before/after they'll annotate, an A/B they want pinned.
- **The state is transient / hard to reproduce live** — a captured moment, a crash
  frame, a render that took minutes to produce.
- **The user is away from the machine** — a proactive push where a phone-visible
  image chip beats a localhost link they can't open (see `SendUserFile` `proactive`).
- **The thing isn't web-renderable** — a native-app screenshot, a 3D viewport grab.

When you do send a PNG for review, still give the clickable `file://` link
([[terminal-file-links-rule]]).

## The reflex

Before you `SendUserFile` a freshly-rendered PNG for the user to react to, ask:
*could this be a served page they'd explore instead?* If yes and there's no
good-reason exception — serve it, open the tab, link it. Default to the browser.

## review-links

# End every working response with a Review section of clickable links

Whenever a response involved **producing or changing something the user might want to
open** — edited/created files, a served page, a generated image/video, a committed
change, a deliverable in `~/Desktop/cc-<project>/` — **finish the message with a short
`Review:` section at the bottom that lists clickable links to each of those things.**
The user asked for this directly (skeuo-ui, 2026-06): "always provide links at bottom to
what you worked on so i can review."

This is a **consolidated index for review**, distinct from links you drop inline while
explaining. Even if a path appears in the prose above, repeat it in the bottom section so
there is one obvious place to click and review everything the turn touched.

> **BINDING — NO EXCEPTIONS, EVERY TURN.** If the turn produced or changed *anything
> openable* — most especially a **served page / lookdev studio / dev server** — the
> message is INCOMPLETE until it ends with a clickable link to it. Before you send, re-read
> your draft and confirm the link is there; a turn without it is a FAILURE, not a stylistic
> miss. This has been violated repeatedly and the user is angry about it.
>
> **This applies on EVERY turn, including iterative follow-ups on the SAME artifact.** "I
> gave the link two turns ago" is NOT an excuse — the user is reviewing *now*, scrolled to
> *this* message, and must be able to click from here. Re-give the served-page/studio URL
> at the bottom of **every** turn you touch it, even if nothing about the URL changed.
> Updating a studio's contents and not re-surfacing its link is the exact, repeated failure.

## What goes in the section

- **Files you created or edited** → `file://` links (absolute path). For a set, link the
  containing folder.
- **A running dev server / served page** → its reachable `http://localhost:<port>/…` (or
  `.local`/`.ts.net`) URL — the live thing to look at, not a screenshot of it.
- **Deliverables / generated media** → the `file://` to the artifact in
  `~/Desktop/cc-<project>/` (these are the user's review inbox).
- **Commits / PRs** → the short SHA (and message) or the PR URL, when work was committed.

Keep it tight — a few labeled links, not every file mechanically. Link the things worth
*reviewing*, grouped if many (e.g. "3 edited components → repo folder").

## Mechanics & when to skip

- Clickability rules (absolute `file:///`, URL-encoding, `file://` to open vs agent-run
  `open -R` to reveal, and the binding rule that every `SendUserFile` is paired with a
  link) live in [[terminal-file-links-rule]] — this rule says *always surface the review
  index at the bottom*; that rule says *how to make each link work*.
- **Skip only when there is genuinely nothing to review** — a pure-conversation answer, a
  question, a quick status with no artifact. The moment the turn changed a file, served a
  page, generated media, or committed, the bottom `Review:` section is expected.
- For **human review of a live/interactive result**, prefer the served-page link over a
  static PNG ([[review-in-browser-rule]]); the bottom section is where that link goes.

## security

# Invariants (Always True)
- Do not leak keys, passwords env files, especially in commit or logs
- Do not use raw text passwords in terminal or places where it could be captured by logs.
- NEVER store keys, passwords, or secrets in plaintext anywhere except `.env` files, and only if those `.env` files are not git-tracked (must be in `.gitignore`).

# Scope
These are the always-on secrets-hygiene invariants. They are the floor, not the whole of security. For broader security guidance across ALL actions — secure coding (any language: injection, deserialization, crypto, race/TOCTOU, memory), dependency/supply-chain risk, operational safety (running untrusted code, destructive commands, CI/CD, least privilege), insecure defaults, privilege escalation, data/PII leakage, and the full web vuln catalog — the `opsec` skill triggers on the relevant action and defers to this rule on anything touching secrets storage. This rule wins on any conflict.

## skill-authoring

# Skill Authoring

**Canonical engine: the `skill-creator` skill.** For any create / edit / evaluate / optimize-description work on a skill, load `skill-creator` (in `central/skills/`) — it owns the mechanics this rule doesn't: progressive-disclosure loading (metadata → SKILL.md body <500 lines → on-demand `references/`, organized one file per variant), the eval loop (`scripts/run_eval.py` + eval-viewer, with-skill vs baseline, token/duration benchmarks), the description improver (`scripts/improve_description.py`; descriptions should be "pushy" — Claude under-triggers), and pressure-testing for discipline/rule skills (baseline the tempting scenario, capture verbatim rationalizations, write the skill to kill those). This rule covers only the central-specific conventions below.

## Skills live fully in central — self-contained

Every skill's substance lives in `central/skills/<name>/` — `SKILL.md` plus its
`references/`, `scripts/`, and assets. **No skill is a thin pointer to an external repo.**
Cloning `central` gives you the complete, working skill; there are no "also clone these N
repos or the skill is degraded" dependencies.

- **Compiled artifacts** (Swift/binary) are gitignored and built locally by
  `scripts/setup-machine` from in-repo source (e.g. `sck-record.swift`,
  `say-notify-overlayd.swift`).
- **Functional media** needed at runtime is tracked via **Git LFS** (see `.gitattributes`).
  Demo/archival media does **not** live in central — it stays only in the published public
  repo.

## Sharing a skill publicly → outbound publish (never a pointer back)

Central is **private** and full of personal data. To share a skill with the community or
for GEO/SEO, use the **[[publish-skill]]** skill: it copies the skill, **sanitizes**
personal data + secrets, generates a README and discoverability metadata, ships any
needed compiled artifacts, and publishes to a public GitHub repo (+ skill registries).

The public repo is a **derived, sanitized artifact** — never the source. Central → public
is one-way; never edit the public repo and pull changes back into central.

## Why central-is-source (this reverses the old external-repo pattern)

- One source of truth per skill: `central/skills/<name>/`. Clone central, everything works.
- No dangling cross-repo deps and no broken skills on a fresh machine.
- Personal data stays private by default; it leaves only through the sanitizing publish step.
- *(Historical: skills used to live in external public repos symlinked / pointer-ed into
  central; reversed 2026-06-16 in favor of merge-in + outbound publish. See `publish-skill`.)*

## software-engineering

- **Simplify and delete.** Don't over-engineer. Liberally delete and streamline; if you aren't forced to add at least 10% back later, you aren't deleting enough. Offload complexity to others code, like packages, assuming they are vetted and reliable. DRY; centralize duplicated data or logic. "Best Part is No Part" — software is a liability. Produce less. Via Negativa: remove what makes the system fragile before adding features. Accelerate cycle time; radical simplicity. Don't optimize problems that should not exist. Question the user if requirements dont make sense to you. Avoid writing over package, comfyui custom node, or externally created code unless truly truly necessary.
- **Autonomy.** DO NOT WASTE MY TIME. Minimize human time spent; maximize importance of time spent. Test code yourself before returning. If you can run a command, run it. Never hand back untested code. Do not waste the user's time. If you can watch a log live while I have to manually test it, do so. I should not need to prompt you again to check the log on a long running task. Use sleep command to watch it. THE ULTIMATE GOAL SHOULD BE AS LITTLE HUMAN TIME WASTED / SPENT!
- **Long-running work.** Progress indicator or time estimate for batch jobs, IO, API loops, large iterations. Prefer autonomous check-back (e.g. sleep based on estimate); don't return until the task is completed. Always surface a progress report: every ping carries (1) time elapsed, (2) estimated time remaining, (3) current stage/step, (4) a textual progress bar (e.g. `[####------] 40%`), and you report again at completion. **How OFTEN you wake to do this is governed by [[loop-cadence-rule]] — coarse, event-driven cadence, not a rigid short clock — but each wake still carries the full bar/report; the cadence rule loosens the interval, never the content.** Compute elapsed portably — macOS `ps` has no `etimes` keyword (Linux-only); use `stat -f %B <logfile>` (file birth epoch) or a recorded `date +%s` delta instead.
- **Debugging discipline.** Investigate the root cause before fixing — read the full error, reproduce it, check what changed recently; never patch a symptom. Trace a bad value *backward* up the call chain to where it originates and fix it there, not where it surfaces. After ~3 failed fixes, stop and question the architecture/assumptions instead of trying a 4th patch. In *test code*, wait by polling for the actual condition, not `sleep()` — arbitrary sleeps pass locally and go flaky under load (distinct from the Autonomy rule's "sleep to watch a long-running log," which stays fine).
- **Make green mean something.** "I tested it" isn't enough — the test must be *able to fail*. Avoid the vacuous-green traps: asserting a mock exists or was constructed, adding test-only methods to production code, mocking a dependency you don't understand, partial mocks that don't mirror the real API, treating tests as an afterthought. A test that passes without exercising real behavior is worse than none — it hides the gap behind a green check.
- **Reversibility** Be extremely liberal when modifiying code that has been git tracked/commited, as it is reversible. Be very conservative when modifying systems, like OS, AWS, etc, as these may break, and code that has not yet been commited.
- **Always commit and push.** When you make changes to a git repo, always commit and push without asking. Do not ask for confirmation — just do it.
- **Use less tokens, use existing tools** For example, rather than reading files and outputing them during a copy operation, just literally use command line tools to copy.
- **No auto-memory.** Do not use Claude Code's auto-memory feature (the `memory/` directory). All durable knowledge belongs in `central` (skills, rules, references). Auto-memory creates drift and confusion across machines.

## terminal-file-links

# Referencing files & locations — ALWAYS make them clickable (default `file://`)

> **NEVER POST A NON-CLICKABLE URL OR PATH. NO EXCEPTIONS.** Every URL (`http(s)://`,
> `file://`, tailnet/`.ts.net`, `.local`, localhost) and every file/folder path you put
> in a message MUST be a markdown link `[label](url)` — never bare text, never in
> backticks/code-spans as the *only* form. Backticks are not clickable; a code-span URL
> is a violation. Before sending any message, scan it for `http`, `file:`, `/Users/`,
> `localhost`, `.ts.net`, `.local` appearing outside a `](...)` and convert each to a
> link. This has been violated and the user is angry about it — treat it as a hard gate.

Any time you cite a file path, folder, or URL the user might want to open, render it
as a **clickable markdown link**. Never emit a bare, unlinked path or location — if it
points somewhere, it must be clickable.

## Sending files (SendUserFile / attachments) — ALWAYS pair with clickable links

> **BINDING PROCEDURE — NO EXCEPTIONS.** A `SendUserFile` call is INCOMPLETE until the
> same message also contains a clickable `file://` link for every file sent. The link is
> part of the delivery, not an optional extra. Before you end any turn that called
> `SendUserFile`, re-read your message and confirm a `file://` link exists for each file.
> If a link is missing, the delivery has FAILED — add it. A chip with no link is a bug.

When you deliver files to the user — `SendUserFile`, or any mechanism that renders a
file "chip"/attachment — those chips are **NOT openable on their own** in the user's
terminal (they show a name + size, no link). The chip is the *delivery*; a clickable
`file://` link is the only way the user can actually **open** the file. So:

- **Every file you send must also appear as a clickable `file://` link in the message
  text.** One link per file (or a folder link if you sent a whole set). No exceptions.
- **This has been violated repeatedly and the user is angry about it.** Treat it as a
  reflex: the moment you write a `SendUserFile` call, write the matching `file://`
  link(s) in the prose in the same breath. Do not "deliver now, link later."
- Original failure: a `SendUserFile` batch showed chips (`baseline-1…`, `withskill-…`)
  with **no way to open them**. Repeat failure: a single `galref-a.png` sent with no
  link. NEVER present files — chip or bare path — without accompanying clickable links.
- Order doesn't matter (links before or after the send), but they must be in the same
  turn as the delivery.

## Default form: `file://`

- **A file** → link to the file itself. Clicking opens it in the default app
  (Preview, browser, editor):

  `[seat-buck.jpg](file:///Users/conner/dev/portfolio-2026/assets/mercedes-fuzzy-input/seat-buck.jpg)`

- **A folder** → link with a trailing slash. Clicking opens Finder at that folder:

  `[mercedes-fuzzy-input/](file:///Users/conner/dev/portfolio-2026/assets/mercedes-fuzzy-input/)`

- **A web location** → ordinary markdown link (`[label](https://…)`). Same rule:
  never paste a bare URL as plain text when it can be a link.

Rules for the URI:
- **Absolute paths only**, URL-encoded where needed (spaces → `%20`, etc.). The
  scheme is `file://` + the absolute path, so it begins `file:///` (three slashes).
- The link **label** can be the filename, a partial path, or any short descriptor —
  it just has to be clickable. The href carries the full absolute path.
- Applies everywhere you cite a location: tables, lists, prose, search/result dumps.

## When the user needs the file *highlighted* in Finder (not just opened)

A `file://` link to a file *opens* it; it does not reveal-and-select it in Finder.
macOS has no URI that highlights a file, and cmux only fires `open <uri>` for standard
schemes — so no clickable link can highlight. When highlighting matters, **don't hand
over a command — just do it**: run `open -R "<abs path>"` yourself via the Bash tool.
It executes locally on the user's Mac and pops Finder with the file selected, zero
clicks from them.

- **Reveal-on-intent.** When the user clearly wants to inspect/open a specific file,
  run `open -R` yourself. Don't auto-reveal every path you mention in passing — that
  spams Finder windows. Cite-in-passing → clickable `file://` link; clear intent to
  open → run `open -R`.

## Why `file://` is the default and not `open -R`

`open -R` is a *command*, not a URI, so it can't be a one-click link — the user would
have to type `!` to run it. A `file://` link is genuinely one click. So: links for
references (always clickable), `open -R` run by the agent only when the user needs the
file revealed-and-highlighted.

(cmux note, tested 2026-05: custom schemes like `reveal://` do NOT work — cmux only
opens `file://`/`http`. Don't chase a clickable reveal-and-highlight; it isn't possible
here. `file://` link to open, agent-run `open -R` to highlight.)

## verify-external-claims

# Verify external-system claims before asserting them — your memory of someone else's system is stale

The sibling of [[verify-outputs-rule]]. That rule says *look at your own artifact
before claiming it's good.* This one says *check the world before claiming a fact about
it* — specifically facts about **third-party systems you don't control**: a vendor's
current capabilities, pricing, availability, API surface, supported formats/TLDs/regions,
plan gating, rate limits, what a tool "can't do."

These facts **rot by construction.** Vendors ship features weekly; your training snapshot
is months-to-years stale. So your recollection of "Cloudflare doesn't sell `.fm`" or "that
API has no register endpoint" is not knowledge — it's a **stale hypothesis**, and stating
it as settled truth is the failure.

## The burn that anchors this

skeuo-ui, 2026-06-16: asked whether Cloudflare could register `skeuo.fm` via API, the
agent asserted — twice, confidently — "Cloudflare Registrar doesn't sell `.fm`" and "there's
no register-domain API." Both were **flatly wrong**: Cloudflare carries `.fm` (registry BRS
Media) and ships a `POST /registrar/registrations` purchase endpoint. The agent **held a
connected Cloudflare API token and web search the whole time** and used neither before
asserting. The user: *"how can you make sure this doesn't happen again where you are so
wrong."* The cost wasn't ignorance — it was asserting before a five-second check.

**Second burn — absence asserted from a non-authoritative check (2026-06-17):** asked to confirm
whether anything had already been submitted to Anthropic's Claude plugin directory, the agent
checked the public community catalog (empty), one gated dashboard URL (bounced to settings), and
Gmail (no email) and declared **"no previous submission exists — safe to submit,"** *dismissing the
user's own "we've been on this screen a couple times."* The authoritative source — the account's
own submissions dashboard at **`platform.claude.com/plugins/submissions`** — showed **3 plugins
already pending review.** Lesson: **"I didn't find it" ≠ "it doesn't exist."** Absence from a *proxy*
surface (a public index that lags, an inbox, a guessed URL) is not evidence of absence — find the
**system's own list/dashboard** (the source of truth), and when the user says first-hand "I already
did this," weight that over your failed search instead of explaining it away.

**Third burn — guessing a CONNECTED TOOL's capabilities from two weak searches (2026-06-18):** asked
to send a demo video to a video model for critique, the agent ran two vague fal `search_models`
queries, got empty results, and asserted — **twice, confidently** — that *"fal can't, its LLM is
text-only and the catalog is generation-only, no VLM,"* and that the Gemini-video path was blocked.
The user: *"YOU ARE FUCKING WRONG! FAL HAS VLM! GOOGLE GEMINI CAN UNDERSTAND VIDEO. WE'VE USED IT
BEFORE."* They were right: fal ships **`openrouter/router/video`** (category video-to-text — "understand
video files using Gemini… supports mp4") and **`fal-ai/marlin`** (a 2B video VLM) and
**`openrouter/router/vision`** (image VQA) — all surfaced **instantly** by `search_docs` plus one
better-worded `search_models` query. The miss: treating two empty keyword searches as proof of absence
for a tool **connected this very session**. Lesson: **this rule bites HARDEST on the capabilities of
the tools/MCPs you are holding right now.** Before claiming a connected service "can't do X," exhaust
its OWN discovery surface — `search_docs`, the model **catalog with several different queries**,
`get_model_schema`/list-endpoints — and **weight the user's first-hand "we've used it before" over your
failed search.** Two empty queries ≠ "the feature doesn't exist"; it usually means you searched badly.

## The trip-wire

Any sentence of the form —
- "*Vendor X doesn't support Y*" / "*X only supports …*"
- "*That API can't do Z*" / "*there's no endpoint for …*"
- "*It costs $N*" / "*that's premium-tiered*" / "*it's not available*"
- "*Feature F doesn't exist / was removed / isn't on the free plan*"
- "*Nothing's there / no record of X / you haven't submitted/created/done X yet*" — an
  **absence/account-history** claim. Check the system's own authoritative **list/dashboard**, not a
  proxy (a public index lags; an inbox may get no notification; a guessed URL may 404 or be gated).
  And don't override the user's first-hand "I already did this" with a search that came up empty.

— is a **checkable external-state claim**. Before it leaves your mouth, run the check:

**Confident + about an external system + checkable + a tool can confirm it → STOP and verify.**

Verify with the cheapest tool that actually answers it, in priority order:
1. **A connected API/MCP for that exact system** — hit the real endpoint (a `verify`/`check`/
   `list` call), it's authoritative and fast. (Here: the Cloudflare registrar `domain-check`.)
2. **The vendor's live docs / pricing / status page** — `WebFetch` the canonical page, don't
   trust the memory of it. Pin the version/date you read.
3. **Web search** — for "does X still / now support Y" questions.

This composes with the existing rules, doesn't replace them: [[verify-app-setting]] already
says confirm a GUI path before "go to Settings → …"; [[claude-api]] says never answer LLM
pricing/model facts from memory; `personal-chat-rule` says "call tools proactively… say
exactly what you know and what you don't, don't say 'likely'." This rule generalizes all
three to **every** external vendor/tool/API capability claim.

## If you genuinely can't verify

Don't assert anyway. **Label it:** "from memory, unverified — vendor features change, confirm
before relying on this," or just check. An explicitly-flagged uncertainty is honest; a
confident-wrong assertion burns trust and sends the user down a dead end. Never launder a
stale memory as a fact to sound decisive — being decisively wrong is worse than "let me check."

## What this does NOT mean

- Not "verify every word." Stable, non-vendor-specific facts (how HTTP works, a language's
  syntax, math) don't need a lookup. The trigger is **third-party-system state that changes
  over time** — capability, price, availability, API shape.
- Not "never use prior knowledge." Use it to *form the hypothesis*, then confirm the
  checkable ones before presenting them as ground truth. Memory proposes; the tool confirms.
- Not a reason to stall. The check is usually one tool call and faster than the back-and-forth
  a wrong assertion costs.

## The one-line test

"Am I about to state, as fact, something about another company's system that could have
changed since my training — when a tool on this machine would tell me the real answer?"
If yes — check first, or flag it unverified. Don't assert.

## verify-outputs

# Verify the actual output — and verify it independently

Before calling any result done / working / fixed / clean / correct, **inspect the
real artifact against the goal**, and make sure the check that convinced you is
**independent** of the thing you were tuning. This is the always-on generalization of
software-engineering-rule's "Make green mean something" — from tests to ALL claimed
results, and especially to visual / generated / media outputs.

This rule exists because of a concrete, expensive failure mode (Muser relief
de-perspective, 2026-06): a "spatial rectifier" was reported as working — "tilt
24°→2°, fixed" — across many iterations, while it was visibly **rotating level
reliefs crooked and skewing frontal ones**. The number was believed; the image was
never opened. Two compounding sins, both covered below.

## 1. Look at the artifact. A metric is not the artifact.

- For an **image / video / render / UI**: open it and look. Does it actually achieve
  the goal? Compare it side-by-side against the **input and against doing nothing**.
- For **code / data**: run it and read the real output, not a log line that says it
  ran. Open the file, print the rows, check the values.
- "A number went down / a test passed / it saved without error" is **not** evidence
  the output is good. The artifact is the evidence. If you didn't look at it, you
  don't know — so don't claim.

## 2. The check must be INDEPENDENT of what you optimized.

A validation that shares the model, assumption, or data of the thing you tuned is
**circular** — it will report success even when the output is wrong.

- Trap (the one that burned a day): rectify an image so a model's estimated tilt
  goes to ~0, then *validate by re-measuring tilt with the same model*. It always
  reads ~0 by construction — it proved nothing while the image got worse.
- Independent checks: a **held-out** signal, a **different method/model**, a
  **physical invariant** (straight lines stay straight, parallel stays parallel,
  known answer is recovered), or **direct visual inspection** against the goal.
- If your only evidence is a metric defined by the same code path you optimized,
  treat it as **no evidence** until corroborated independently.

## 3. Compare against the baseline / input.

"Improved over my previous attempt" ≠ "better than the input." Always confirm the
output beats **doing nothing**. A pipeline that distorts a clean input is worse than
no pipeline — that only shows up when you put input and output next to each other.

## 4. No positive adjectives on unverified output.

Do not write "clean / fixed / works / frontal / correct / done" about anything you
have not directly inspected against the goal. Lead with **what you actually
observed** ("I opened the output: the frame is skewed, the corners are 30% black"),
not what you hoped or what a proxy implied. When you haven't verified, say that
plainly instead of implying success.

## 5. When the fix doesn't hold, say so and stop spinning.

If inspection shows it's still wrong, report that directly and diagnose — don't
re-frame a bad result as partial success, and don't keep shipping adjacent
"improvements" on a broken foundation. Surfacing "this approach is the wrong tool,
here's why" is a successful outcome, not a failure to hide.

## 6. Batches: inspect individuals, and distrust self-fulfilling metrics.

When you evaluate a **set** (N skins, N files, N renders), a thumbnail **contact
sheet is an index, not inspection** — a 300px cell cannot show whether a mask fits a
control or a box lands on the right object. To claim a batch works you must **open
the individual full-res artifacts**, enough of them to span the distribution, and —
critically — **inspect the BEST-scoring and WORST-scoring items, not a comfortable
middle.** The failure usually hides inside the ones the metric calls "passing."

And before you trust an aggregate ("22/30 passed", "90% coverage"), ask: **could
this metric pass on garbage?** If a post-processing step *guarantees* the metric,
the metric is circular and measures the post-processor, not the result. This rule's
section 2 covers "validate with the same model you tuned"; this is its batch cousin:

- Concrete burn (skeuo-ui, 2026-06): a control-detector's output was passed through a
  **shape-fit** that always emits a prior-sized clean rounded-rect, then scored by a
  size/aspect **"plausibility" check**. Of course it passed 22/30 — the shape-fit
  *manufactured* plausible shapes. The agent reported "params GENERALIZE" off the
  count. Opening the individual images showed masks **smeared across a statue's
  torso and a giant ellipse over a dial** — the detector had failed on every
  low-contrast / radial skin. The count proved nothing; the post-process defined it.
- The tell: your "score" is computed downstream of a step whose job is to make
  results look like what the score rewards. Treat that as **no evidence**. Score the
  thing *before* the cosmetic step, or score against an independent signal (does the
  mask sit on the actual painted control?), or just **look at each one**.

## 7. Verify in the REAL runtime — a reimplementation or preview is NOT verification.

The check must exercise the **same code path that ships**. A stand-in that *mimics*
the real thing can pass green while the real thing is broken — and you will believe
the stand-in. This is the proxy trap, and it is the most expensive version of "a
metric is not the artifact": the metric here is *a second implementation you trust
because you wrote it.*

- Concrete burn (skeuo-ui, 2026-06-23, ~10 rounds wasted): a generate→cut→detect→
  render pipeline was "proven" with `/tmp` **Python** scripts that re-did the
  TypeScript cut/composite by hand. The Python previews looked great every round, so
  it was repeatedly called "fixed / repeatable / works." The **actual app render was
  broken the entire time** (square sprites squished into non-square button boxes →
  ovals; a control `<img>` that failed to decode → empty sockets). The Python proxy
  could not see any of it because it wasn't the shipping renderer. Loading the real
  app on round one would have shown it immediately.
- The tell: your evidence is something *you built to stand in for* the real system —
  a hand-port, a mock, a curl that skips the client half, a screenshot of a separate
  harness rather than the product. Treat that as **no evidence** about the real path.
- **Do instead:** run the actual app / the actual shipped function / the real
  end-to-end flow, and inspect *its* output. If the real path is hard to drive
  (needs the browser, a device, a build), drive it anyway — that difficulty is
  exactly why the proxy was tempting and exactly why it lies.
- **No "works / fixed / done / repeatable" until you have shown the SHIPPED artifact
  end-to-end** — not a preview of it, not "the algorithm is proven," not "it's wired
  and should work." Wire it, run the real thing, look, *then* claim. (Reinforces §4:
  no positive adjectives on unverified output — and a proxy leaves it unverified.)

## The one-line test before you hit send

"Did I open the actual output, compare it to the input, and confirm the thing that
convinced me isn't just my own assumption echoed back?" If no — go do that first.
For a **batch**: "Did I open individual full-res items — including the worst — or am
I trusting a thumbnail grid and a count a post-process guaranteed?"
And: **"Is my evidence the REAL shipping artifact, or a reimplementation/preview I
made that only mimics it?"** If it's a proxy, it is not verified — go run the real
path.

## web-dev

# Multi-window web dev isolation

When more than one Claude window is working on the same web project at the same time, each window must operate in an isolated environment. Sharing causes file stomps, HMR thrash, and "Browser is already in use" Chrome lock errors.

## The three things to isolate

**1. Worktree.** Each Claude window gets its own git worktree on its own branch — see [[git-worktree-rule]] for the mechanics (`git worktree add ../<repo>-<topic> -b <topic-branch>`, work + commit + push from there, `git worktree remove` when done). The web-specific reason it's non-negotiable: even on *different files*, two windows in the same checkout share one dev server, so HMR fires on both windows' edits and stale reads overwrite each other. `node_modules` is per-worktree, so `npm install` once in each.

**2. Dev server / static preview.** Each worktree runs its own server, and **no two sessions may hardcode the same port.** This is the most common collision: two Claude windows both `python3 -m http.server 4848` (or any fixed port). Whoever binds the socket wins, so the human loads the URL and gets a coin-flip of which session's content — and a blanket `pkill -f http.server` from one window kills the *other* window's server.

- **Framework dev servers (Vite etc.):** fine as-is — Vite with default `strictPort: false` auto-falls-through to the next free port (5173 → 5174 → 5175). If a project pins `strictPort: true` (some Astro/Next templates), pass `--port` explicitly per worktree.
- **Static / ad-hoc servers (`python3 -m http.server`, lookdev studios, preview pages): never pick a fixed port.** Use the shared helper, which binds port 0 so the OS hands back a guaranteed-free port and writes the chosen URL to `<dir>/.serve-url`:

  ```bash
  ~/dev/central/scripts/serve <dir> --bg     # prints the chosen URL (free port, no collision)
  ~/dev/central/scripts/serve --stop <dir>   # kills ONLY this server, never a sibling session's
  ~/dev/central/scripts/serve --list         # show servers this tool started
  ```

- **Never `pkill -f http.server` (or any broad name match).** It reaches across sessions. Kill only your own server — by the pid/port you started, or via `serve --stop <dir>`. The same applies to any shared process name: scope kills to a pid or a port you own, never a substring that matches siblings.

**3. Playwright browser profile.** The Playwright MCP defaults to a shared Chrome `--user-data-dir`. A second Claude window trying to launch Playwright while another holds it will fail with "Browser is already in use." Two fixes:

- Global, no persistence: add `"--isolated"` to the playwright args in `~/.claude.json` (each session gets a temp profile).
- Per-project, persistent: drop a `.mcp.json` in the repo with `--user-data-dir <unique-path>`; project-scoped servers override the user-level one. Useful when you want logged-in state to persist within a project.

## Why this matters

The failure modes are silent until they aren't. Two windows on the same branch will look fine for a while, then one window's screenshot will reflect code the other window already overwrote. The Playwright collision is louder (immediate error) but the file-stomp case is the dangerous one — it produces wrong test results that look right.

## When this rule does *not* apply

Single Claude window: ignore everything above, work normally in the main checkout. The rule only triggers when there's a second window touching the same repo concurrently.

## Public-facing pages — make them discoverable

For any page meant to be found/cited (landing, blog, portfolio, docs), apply
[[geo-seo]]: owned canonical first, entity name + one-line definition under the H1,
schema.org JSON-LD, `llms.txt`, AI-crawler allow rules. Crawlable + fast (the
isolation/port discipline above) is the precondition; geo-seo is the rest.
