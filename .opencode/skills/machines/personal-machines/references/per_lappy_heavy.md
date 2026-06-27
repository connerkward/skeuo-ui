# Lappy Heavy

- **Hostname:** conner@lappy-heavy (tailscale), conner@lappy-heavy.local (home-lan)
- **Role:** Personal high-power laptop. M1 Max. Not always on.
- **Hardware:** macOS 26.5 (Tahoe), Apple M1 Max, 64 GB RAM. MacBookPro18,2.
- **SSH:** Key-based (`~/.ssh/id_ed25519`). `ssh desky` configured in `~/.ssh/config` → `conner@192.168.8.244`.
- **Storage:** —
- **Tools → MCP:** `davinci-resolve` (user-scope, 2026-06-13) — see [DaVinci Resolve MCP](#davinci-resolve-mcp-2026-06-13) below.
- **Shells:** zsh (default) with man-page-derived tab completion via `umlx5h/zsh-manpage-completion-generator` (brew tap `umlx5h/tap`). Fish 4.6.0 at `/opt/homebrew/bin/fish` is used only as the man-page parser backend. `~/.zshrc` adds `~/.local/share/zsh/generated_man_completions` to `fpath` before `compinit`.
- **LaunchAgents:** `~/Library/LaunchAgents/com.conner.fish-completions.plist` — daily at 03:00 runs `fish_update_completions` then `zsh-manpage-completion-generator` to refresh ~1000 man-derived completions. Logs: `/tmp/fish-completions.{log,err}`.
- **Manual completion refresh:** `refresh-zsh-man-completions` alias in `~/.zshrc` triggers the launchd job on demand (use after `brew install/upgrade`).
- **LaunchAgent — graph-studio (always-on):** `~/Library/LaunchAgents/com.graph-studio.serve.plist` runs `~/dev/exp-notes-indexing/.venv/bin/python studio.py` (knowledge-graph layers tuning studio) at login with `KeepAlive`, `STUDIO_PORT=60606`. Caddy proxies **http://tune.notes.localhost / http://tune.notes.local** → 127.0.0.1:60606. Logs: `~/.local-local/graph-studio.{log,err.log}`. Must run under the repo venv — system/homebrew python lacks deps and hangs listener-less.
  - **Reversal:** `launchctl bootout gui/$(id -u)/com.graph-studio.serve`; `rm ~/Library/LaunchAgents/com.graph-studio.serve.plist`; remove the tune.notes block from /opt/homebrew/etc/Caddyfile + `caddy reload`.
- **LaunchAgent — notes web UI (always-on):** `~/Library/LaunchAgents/com.notes.serve.plist` runs `~/.bun/bin/bun ~/dev/mcp-apple-notes/index.ts` (Apple Notes search/map/synthesize/bridges/entities web app + HTTP MCP endpoint, port 3741) with `KeepAlive`. Caddy proxies **http://notes.localhost / http://notes.local / http://notes** → 127.0.0.1:3741. /etc/hosts lines for the .local/bare names pending (sudo): `127.0.0.1 notes.local notes tune.notes.local` + same for `::1`. Logs: `~/.local-local/notes-serve.{log,err.log}`. Coexists with the Claude-Desktop-spawned stdio MCP instance (LanceDB handles multi-process).
  - **Reversal:** `launchctl bootout gui/$(id -u)/com.notes.serve`; `rm ~/Library/LaunchAgents/com.notes.serve.plist`; remove the notes block from Caddyfile + `caddy reload`; delete the /etc/hosts lines if added.
- **LaunchAgent — muser serve (always-on):** `~/Library/LaunchAgents/com.muser.serve.plist` runs `~/dev/Muser/.venv/bin/muser serve --host 127.0.0.1 --port 7777` at login with `KeepAlive` (auto-restarts on crash). The embedded semantic-image-search service warms `siglip2-b` into RAM (~14 s) and holds it resident. `PATH` in the plist is `/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin` so the service can reach `c2patool` (C2PA scan) and `/usr/bin/open` (reveal-in-Finder). Logs: `~/.muser/serve.{log,err.log}`. URL: http://127.0.0.1:7777. Also on PATH: `~/.local/bin/muser` → symlink to the same venv binary, for running `muser …` by hand. **`ProcessType=Interactive`** (NOT `Background`) + `LowPriorityIO=false`: Background QoS throttles the model's GPU/MPS work onto efficiency cores and App-Naps the idle GPU context, which made the first query after idle 7.7 s and steady-state 1.2 s; Interactive gives first-query 0.14 s / steady 0.035 s. Don't switch it back to Background.
  - **Reversal:** `launchctl bootout gui/$(id -u)/com.muser.serve` then `rm ~/Library/LaunchAgents/com.muser.serve.plist` (and `rm ~/.local/bin/muser` to drop the PATH symlink).
- **LaunchAgent — feed-demon daily digest:** `~/Library/LaunchAgents/com.feed-demon.daily.plist` runs `~/dev/feed-demon/daily-digest.sh` daily at **05:00** (`StartCalendarInterval`; moved 08:00→05:00 on 2026-06-18 for a fresher morning digest — on a sleeping Mac launchd fires it on next wake, run-on-wake, no power-wake scheduled). The runner does `uv run python -m feed_demon.pipeline`: pulls the RSS feeds in `~/dev/feed-demon/config.toml` via the `reader` lib (SQLite unread-state at `~/dev/feed-demon/feed-demon.sqlite`), ranks new items against the `interests` block with one headless `claude -p --output-format json` call, and writes a markdown digest to `~/dev/feed-demon/digests/`. Logs: `/tmp/feed-demon.{out,err}`. The plist + `daily-digest.sh` are git-tracked in the repo (`deploy/com.feed-demon.daily.plist`); only the `~/Library/LaunchAgents` copy is machine-local. **Auth:** `claude -p` reads the subscription OAuth token from the Keychain item `Claude Code-credentials` — verified accessible to a launchd job (no `ANTHROPIC_API_KEY` needed). `daily-digest.sh` hardcodes `PATH=/opt/homebrew/bin:...` so launchd's minimal env finds `uv` and `/opt/homebrew/bin/claude`.
  - **Reversal:** `launchctl bootout gui/$(id -u)/com.feed-demon.daily` then `rm ~/Library/LaunchAgents/com.feed-demon.daily.plist`.
- **LaunchAgent — feed-demon reader UI (always-on):** `~/Library/LaunchAgents/com.feed-demon.serve.plist` runs `~/dev/feed-demon/.venv/bin/python -m feed_demon.reader_ui 7778` at login with `KeepAlive`. The Feedly-style three-pane RSS reader on the `reader` SQLite backend. Behind Caddy at `http://feed-demon.local` / `feed-demon.localhost` / `feed-demon` (→ 7778). Logs: `~/.feed-demon/serve.{log,err.log}`. plist git-tracked at `~/dev/feed-demon/deploy/com.feed-demon.serve.plist`.
- **feed-demon MCP server (2026-06-18):** `~/dev/feed-demon/.venv/bin/python -m feed_demon.mcp_server` (stdio, FastMCP) exposes the reader to agents — tools `digest/search/recent/feeds/read_article/mark_read`. Registered in `~/.claude.json` (user scope, via `claude mcp add feed-demon -s user -e PYTHONPATH=/Users/conner/dev/feed-demon -- …`; needs `PYTHONPATH=repo` since `feed_demon` isn't pip-installed in the venv) and in the **Claude Desktop** config `~/Library/Application Support/Claude/claude_desktop_config.json`. Propagated to Cursor/Qwen/OpenCode/Gemini by `central/scripts/sync-mcp-servers`. **Reversal:** `claude mcp remove feed-demon -s user`; delete the `feed-demon` block from the Claude Desktop config; re-run `sync-mcp-servers`.
  - **Reversal:** `launchctl bootout gui/$(id -u)/com.feed-demon.serve` then `rm ~/Library/LaunchAgents/com.feed-demon.serve.plist`.
- **LaunchAgent — local.local dashboard (always-on):** `~/Library/LaunchAgents/com.local.serve.plist` runs `/usr/bin/python3 ~/dev/local-local/dashboard.py 7779` at login with `KeepAlive` (stdlib-only, no venv). A status grid of every local service (parses the Caddyfile + `launchctl list` + port probes). Behind Caddy at `http://local.local` / `local.localhost` / `local` (→ 7779). Logs: `~/.local-local/serve.{log,err.log}`. **Own repo `~/dev/local-local`** (moved out of feed-demon 2026-06-11); plist git-tracked at `~/dev/local-local/deploy/com.local.serve.plist`. **To add a service:** see `~/dev/local-local/CLAUDE.md` (or the `local-local` central skill) — UI apps auto-discovered from a Caddy block; non-UI daemons added to `AGENTS`/`INFRA` in `dashboard.py`.
  - **Reversal:** `launchctl bootout gui/$(id -u)/com.local.serve` then `rm ~/Library/LaunchAgents/com.local.serve.plist`.
- **LaunchAgent — muser PERSONAL serve (hidden Google-Photos triage, 2026-06-11):** `~/Library/LaunchAgents/com.muser-personal.serve.plist` runs `~/dev/Muser/.venv/bin/muser personal serve --host 127.0.0.1 --port 7780` with `KeepAlive` and `EnvironmentVariables MUSER_HOME=/Users/conner/.muser-personal` (the isolated data root — its own LanceDB/scores/facets, completely separate from the aesthetic `~/.muser`). Same `Interactive`/`LowPriorityIO=false` warm-GPU treatment as the main muser agent. Behind Caddy at `http://personal.muser.local` (→ 7780). Logs: `~/.muser-personal/serve.{log,err.log}`. The "personal" feature is hidden — the Triage tab only appears because `/api/status` returns `personal:true` under this root. Interactive results dashboard at `http://personal.muser.local/report` (bucket distribution, P/uncertainty histograms, signal-driver bars, clickable gpt-4o-mini benchmark confusion matrix). **Loaded 2026-06-11** via `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.muser-personal.serve.plist`. **Rewritten 2026-06-12:** the original plist had invalid XML (raw `&&` in a bash -c string), literal `$HOME` in log paths (launchd doesn't expand it), and a 5s `StartInterval`; replaced with direct `uv run muser personal serve` ProgramArguments + `EnvironmentVariables MUSER_HOME` + absolute log paths (`~/Library/Logs/muser-personal-serve.{log,err.log}`). **Both muser plists now set `SoftResourceLimits NumberOfFiles=8192`** — launchd's default 256-fd soft limit crashed the personal service with `Too many open files` (LanceDB holds each data fragment open ×3; the incrementally-ingested personal table has hundreds of fragments). Reversal of the limit: delete the SoftResourceLimits dict from both plists and `launchctl kickstart -k` them.
  - **Reversal:** `launchctl bootout gui/$(id -u)/com.muser-personal.serve` then `rm ~/Library/LaunchAgents/com.muser-personal.serve.plist` (and `rm -rf ~/.muser-personal` to drop the isolated index/data).
- **Menu-bar icon (xbar):** `brew install --cask xbar` (in `/Applications/xbar.app`, launches at login). Plugin `~/Library/Application Support/xbar/plugins/locallocal.5s.py` (git-tracked at `~/dev/local-local/deploy/xbar-locallocal.5s.py`) renders the `local.local` services in the menu bar — `◉ N/M` title, per-service status dot, click-to-open, and a `↻ restart` action per LaunchAgent. Reads the dashboard API (`127.0.0.1:7779/api/services`); refreshes every 5 s (the `.5s.` in the filename).
  - **Reversal:** `rm "~/Library/Application Support/xbar/plugins/locallocal.5s.py"`; quit xbar; `brew uninstall --cask xbar`.

## DaVinci Resolve MCP (2026-06-13)

`samuelgursky/davinci-resolve-mcp` (v2.51.0) cloned to `~/dev/davinci-resolve-mcp` —
MCP server that drives the DaVinci Resolve scripting API for AI-assisted editing
(installed primarily to verify `screen-studio-alternative`'s FCPXML pan-calibration via
a real Resolve round-trip).

- **Edition:** DaVinci Resolve **Studio 20.3.2** at `/Applications/DaVinci Resolve/` —
  Studio is **required**; the free edition blocks external scripting entirely. (The
  installer reads the real product string and confirmed "Studio 20.3.2".)
- **Install:** `python3 install.py --clients claude-code` created `~/dev/davinci-resolve-mcp/venv`
  (Python 3.14.5 — `fusionscript.so` imports fine under 3.14; downgrade to 3.10–3.12 only
  if `scriptapp("Resolve")` returns None) and wrote a project-scoped `.mcp.json` in that repo.
- **Registration (the one that matters):** user-scope in `~/.claude.json` via
  `claude mcp add davinci-resolve -s user` → command `~/dev/davinci-resolve-mcp/venv/bin/python
  ~/dev/davinci-resolve-mcp/src/server.py`, with env `RESOLVE_SCRIPT_API` =
  `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting`,
  `RESOLVE_SCRIPT_LIB` = `…/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so`,
  `PYTHONPATH` = `$RESOLVE_SCRIPT_API/Modules`. Compound mode (34 tools); `--full` = 341.
- **Required Resolve pref (manual, one-time):** Preferences → General → **External scripting
  using → Local**, with Resolve running, or no external process can attach. Not yet
  end-to-end verified (Resolve was not launched this session) — `claude mcp list` shows the
  server process connects, but the Resolve attach is unproven until Resolve is open + pref set.
- **Reversal:** `claude mcp remove davinci-resolve -s user`; `trash ~/dev/davinci-resolve-mcp`.

## Local hostnames → Caddy reverse proxy (services on :80)

`http://muser.localhost` (preferred) / `http://muser` / `http://muser.local` → the
[Muser](file:///Users/conner/dev/Muser/) web UI, via a **Caddy** reverse proxy on port
80 that routes by Host header. Replaced an earlier `pf rdr` hack (see below) that broke
the app.

- **Any of `muser` / `muser.local` / `muser.localhost` work, including the reverse-image
  buttons (Lens / TinEye).** Those copy the image to the clipboard; the browser's async
  Clipboard API needs a **secure context** (`127.0.0.1`, `*.localhost`, `https` — but NOT
  `.local`), so Muser's service exposes `POST /api/clipboard` that copies the image
  server-side via macOS `osascript` (`«class PNGf»`). The web UI tries that first, so
  copy works on every origin; it falls back to the browser Clipboard API on secure
  origins, then to "open engine + image to drag in" (non-macOS). `muser.localhost` is
  still the most correct (secure context end-to-end) but no longer required.
- `/etc/hosts` — `127.0.0.1 muser.localhost` + `::1 muser.localhost` (and the legacy
  `muser` / `muser.local` A+AAAA pairs). Chrome/Edge auto-resolve `*.localhost` to
  loopback without a hosts entry; Safari/curl/other tools need the line. Both A and AAAA
  per name: without the IPv6 line, macOS Happy Eyeballs waits 5 s on the unanswered AAAA
  mDNS query before falling back to IPv4 and every load feels broken.
- `/opt/homebrew/etc/Caddyfile` — site blocks (Caddyfile is owned by `conner`, so edits need NO sudo; only `/etc/hosts` does):
  - `http://muser.localhost, http://muser, http://muser.local { reverse_proxy 127.0.0.1:7777 }`
  - `http://feed-demon.localhost, http://feed-demon, http://feed-demon.local { reverse_proxy 127.0.0.1:7778 }` (feed-demon reader, 2026-06-11)
  - `http://local.localhost, http://local, http://local.local { reverse_proxy 127.0.0.1:7779 }` (services dashboard, 2026-06-11)
  - `http://personal.muser.local, http://personal-muser.localhost, http://personal-muser { reverse_proxy 127.0.0.1:7780 }` (HIDDEN Muser Google-Photos triage sub-tool, 2026-06-11)
  The `http://` prefix forces plain HTTP on :80 (no auto-TLS).
  **Add a service:** edit the Caddyfile (no sudo), add `/etc/hosts` lines (sudo) if you want the `.local` name, then `caddy reload --config /opt/homebrew/etc/Caddyfile`.
- `/etc/hosts` (added 2026-06-11) — `127.0.0.1 feed-demon.local` + `::1` + `feed-demon`; `127.0.0.1 local.local` + `::1` + `local`; `127.0.0.1 personal.muser.local` + `::1` + `personal-muser`. (`*.localhost` auto-resolves, so `feed-demon.localhost`/`local.localhost`/`personal-muser.localhost` work without the hosts line.)
- Caddy installed via `brew install caddy` (`/opt/homebrew/bin/caddy`, 2.11.x). **Boot persistence IS handled** — by a root LaunchDaemon `/Library/LaunchDaemons/com.local.caddy.plist` (see LaunchDaemons section below), NOT by `brew services` (so `brew services list` shows `caddy none` — that's expected, don't "fix" it). Do NOT `brew services start caddy`: it installs a *user* agent that can't bind :80 and just errors. The `.local`/`.localhost` proxies survive reboot as-is.

### Why not pf (history — do NOT reintroduce)

The original setup (2026-06-01) used `pf rdr pass on lo0 ... port 80 -> 127.0.0.1:7777`
plus a boot daemon to `pfctl -e`. **Enabling pf with that loopback rdr broke concurrent
TCP connection setup to 127.0.0.1:7777** — direct connects stalled in `SYN_RCVD` and
timed out. The Muser MCP gallery + web UI fetch ~24 thumbnails at once, so nearly all
came back "no preview". Proven by: an identical trivial uvicorn app failed 24/24 on
:7777 but passed 24/24 on every other port; disabling pf restored 24/24. Caddy (a normal
userspace proxy) handles the concurrency cleanly — 24/24 in ~0.18 s. pf is now disabled
and the muser pf artifacts removed.

## LaunchDaemons

- `/Library/LaunchDaemons/com.local.caddy.plist` — runs `/opt/homebrew/bin/caddy run
  --config /opt/homebrew/etc/Caddyfile --adapter caddyfile` at boot (`RunAtLoad` +
  `KeepAlive`), as root so it can bind :80. Logs `/var/log/caddy.local.{out,err}.log`.
  Owned `root:wheel`, mode `644`. Loaded via `sudo launchctl bootstrap system <plist>`.
  Reload after Caddyfile edits: `caddy reload --config /opt/homebrew/etc/Caddyfile`
  (or `sudo launchctl kickstart -k system/com.local.caddy`).
- ~~`/Library/LaunchDaemons/com.muser.pfctl.plist`~~ — removed 2026-06-02 (see pf history).

Note: `muser serve` (the :7777 backend) is not yet daemonized — start it manually
(`uv run muser serve` in [Muser](file:///Users/conner/dev/Muser/)). Caddy just proxies to it.

## Reversal — Caddy local proxy

```sh
sudo launchctl bootout system/com.local.caddy
sudo rm /Library/LaunchDaemons/com.local.caddy.plist /opt/homebrew/etc/Caddyfile
brew uninstall caddy            # optional
sudo sed -i '' '/[[:space:]]muser$/d;/[[:space:]]muser\.local$/d;/[[:space:]]muser\.localhost$/d' /etc/hosts
```

pf itself is already disabled and the `com.muser` anchor/daemon/`pf.conf` patch were
reverted (backup was `/etc/pf.conf.bak`); nothing further to undo there.

## Login Items / background apps

### noTunes — stop headphone play/pause button from launching Apple Music

Bluetooth headphone media buttons send a system play/pause key that macOS routes
to Apple Music, launching it. No built-in toggle exists (Apple removed the old
`defaults` workaround). [noTunes](https://github.com/tombonez/noTunes) registers
itself as the handler and silently swallows the launch.

- Installed: `brew install --cask notunes` → `/Applications/noTunes.app` (cask `notunes`, v3.5).
- Runs at login: added as a hidden Login Item (System Settings → General → Login Items, or
  `System Events` login items list). Must be running to intercept.

**Reversal:**

```sh
osascript -e 'tell application "System Events" to delete login item "noTunes"'
osascript -e 'tell application "noTunes" to quit'   # or: killall noTunes
brew uninstall --cask notunes
```

## App preferences — cmux

### Disable in-app file preview (clicks dispatch to system default app)

By default cmux intercepts clicks on `file://` markdown links and renders the file
in its own preview pane. To make clicks dispatch to the system default app
(Preview.app for PNG, etc.) instead:

```sh
defaults write com.cmuxterm.app openSupportedFilesInCmux -bool false
# restart cmux
```

The settings UI calls this **"Open Supported Files in cmux"** (Settings → App →
search "supported-file-previews"). Related siblings (both default `true`):

- `openMarkdownInCmuxViewer` — `.md/.mdx/.mkd/.mdx` in-app **markdown viewer**. This is
  SEPARATE from `openSupportedFilesInCmux` and **must also be set false** or `.md` clicks
  still open the cmux md viewer even with supported-file previews off. (This was the gap —
  2026-06-16: `openSupportedFilesInCmux` was already false but `.md` kept opening in cmux
  because this key was still true.)
- `preferredEditorCommand` / `preferredEditor` — string; editor command used when previews
  are off (e.g. `"code"`, `"cursor"`). Leave empty to fall through to the macOS default app.

**Authoritative config is `~/.config/cmux/cmux.json`, not the `defaults` domain.** Newer
cmux reads the schema'd JSON (`cmux.schema.json`); when a key is absent there it uses the
schema default (`true`), which *overrides* whatever is in `com.cmuxterm.app` defaults. So set
both in the JSON (and `~/.config/cmux/settings.json` for the legacy mirror):

```json
"app": { "openSupportedFilesInCmux": false, "openMarkdownInCmuxViewer": false }
```

Then **restart cmux** for it to reload. Result: `.md` file:// clicks dispatch to the macOS
default app → Google Chrome (see `.md` association below).

**Reversal:**

```sh
defaults write com.cmuxterm.app openSupportedFilesInCmux -bool true
# or to fully delete the key (revert to default true):
defaults delete com.cmuxterm.app openSupportedFilesInCmux
```

**Why this is documented here, not just "a UI toggle":** the agent's bash
sandbox on Tahoe 26.5 cannot launch GUI apps via `open` / `open -a`
(LaunchServices error -1712), and cmux's link-click intercept makes file:// links
preview internally instead of dispatching to the user's chosen viewer. Disabling
the intercept restores the expected click→system-default-app flow.

## Default file-type associations (LaunchServices)

- **.gif → Google Chrome** (2026-06-11): Preview can't animate GIFs (shows frames
  as a list). Set via `duti -s com.google.Chrome .gif all` (the UTI form
  `com.compuserve.gif` did not take on Tahoe; the extension form did).
  Verify: `duti -x gif` → Google Chrome. **Reverse:** `duti -s com.apple.Preview .gif all`.


### `.md` → Google Chrome (2026-06-16; was TextEdit, was Xcode)

`.md` is now set to open in **Google Chrome** so cmux's hand-off (above) renders markdown
in the browser instead of a terminal/editor pane. Verify: `duti -x md` → `Google Chrome.app`.
Set via `duti -s com.google.Chrome .md all`. **Reverse:** `duti -s com.apple.TextEdit .md all`
(or use the NSWorkspace snippet below with any bundle id). `.md` maps to the UTI
`net.daringfireball.markdown`.

History: `.md` originally fell back to **Xcode** (slow); was reassigned to **TextEdit**
(native, instant); now **Chrome** per the cmux markdown-in-browser preference.

Set via the modern `NSWorkspace.setDefaultApplication(at:toOpen:)` API — **not** the
deprecated `LSSetDefaultRoleHandlerForContentType`, which returns status `0` but is a
silent no-op on macOS 26:

```sh
swift - <<'EOF'
import AppKit; import UniformTypeIdentifiers
let app = NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.apple.TextEdit")!
try? NSWorkspace.shared.setDefaultApplication(at: app, toOpen: UTType("net.daringfireball.markdown")!)
EOF
```

The change is in the per-user LaunchServices DB (survives reboot, invisible from repos).
Verify: `swift` snippet resolving `NSWorkspace.shared.urlForApplication(toOpen: <url-to-a.md>)`
should return TextEdit.

**Reverse:** run the same snippet with `com.apple.dt.Xcode` (or any other bundle id) as
the app, or set it back via Finder → a `.md` file → Get Info → "Open with" → Change All.

## iOS dev / Simulator toolchain (Expo native builds + autonomous UI testing)

Set up 2026-06-07 for the `~/dev/superapp` Expo app (dev builds + agentic on-device testing).

- **iOS 26.5 Simulator runtime** — Xcode 26.5 shipped with only a stale iOS 18.6
  runtime, so `xcodebuild` reported *zero* simulator destinations ("iOS 26.5 is not
  installed") and `expo run:ios` failed at destination resolution. Fixed by
  downloading the matching runtime:
  `xcodebuild -downloadPlatform iOS` (~8.5 GB, installs the iOS 26.5 sim runtime;
  no sudo). After this, iOS 26.5 devices (iPhone 17 family) appear and builds work.
  - **Reverse:** `xcrun simctl runtime delete "iOS 26.5"` (or Xcode → Settings →
    Components → remove the runtime).
- **CocoaPods + watchman** — `brew install cocoapods watchman` (required by
  `expo prebuild` / `expo run:ios`). Reverse: `brew uninstall cocoapods watchman`.
- **idb (Facebook iOS Debug Bridge)** — already present: `idb` CLI at
  `~/.local/bin/idb` + `idb_companion` via brew. Used for **autonomous simulator UI
  automation** (tap by accessibility frame, type, screenshot) — the loop that lets an
  agent drive/verify the app on the sim without a device. Usage that works reliably:
  `idb describe --udid <udid>` (screen dims), `idb ui describe-all --udid <udid>`
  (a11y tree → element frames in **points**), `idb ui tap --udid <udid> <x> <y>`.
  Screenshots via `xcrun simctl io booted screenshot <path>` (simpler than idb).
  The `ios-simulator` MCP wraps idb but failed with "Could not determine valid screen
  dimensions" until a companion was connected — calling `idb` directly is the fallback.

**Why documented:** simulator runtimes, brew formulae, and the idb toolchain are
machine state invisible to any repo. Without the iOS 26.5 runtime, `expo run:ios`
silently fails destination resolution on this box.

## git-lfs (global filters)

Set up 2026-06-08 to work with the `~/dev/bas` repo, which stores media (`*.png *.jpg
*.mp4 *.mov *.stl` etc.) in **Git LFS**. git-lfs was not installed, so any
checkout/reset that needed to smudge LFS files failed with
`git-lfs filter-process: git-lfs: command not found` and left the clone half-broken
(empty index, untracked pointer files).

- **Installed:** `brew install git-lfs` (git-lfs 3.7.1).
- **Enabled globally:** `git lfs install` — writes `filter.lfs.{clean,smudge,process}`
  + `required=true` into `~/.gitconfig`, so **all** repos now route LFS files through
  git-lfs. This is the documentable part (affects every git repo for the user).
- To restructure a repo without downloading blobs: `GIT_LFS_SKIP_SMUDGE=1 git reset
  --hard HEAD` (writes pointer files; `git mv`/commit/push preserve pointers, no
  re-upload of unchanged objects).

**Reverse:** `git lfs uninstall` (removes the global filters from `~/.gitconfig`),
then `brew uninstall git-lfs` if you want the binary gone.

**Why documented:** the global LFS filter config in `~/.gitconfig` is invisible from
inside any repo but changes how every git checkout behaves.

## Claude Code `say` notification hook

Spoken notifications via macOS `say`. Set up 2026-06-10. **Central is the source of
truth**; only the one-line registration is machine-local.

- **Logic (canonical):** now lives in central at `skills/claude-code-agent-radio/` (published publicly as github.com/connerkward/claude-code-agent-radio); `scripts/agent-radio/` symlinks into it so the hook + LaunchAgent paths stay stable. Speaks a
  concise radio-chatter line + shows an RTS "incoming transmission" card.
- **Callsign (updated 2026-06-11):** agent override (`say-callsign.sh "X"`, keyed by
  `$CLAUDE_CODE_SESSION_ID`) > **Claude chat title** (`ai-title` in the transcript, the
  `/rename` name) > cmux surface title > project-dir basename. Two words, Title Case.
- **Focus-aware gating (2026-06-11):** uses `cmux tree` to (a) stay silent when you're
  looking at the firing window (`◀ here` == `◀ active`), (b) name the callsign from the
  window title. `SAY_LOG=1` logs decisions to `~/.claude/say-notify.log`.
- **Overlay = persistent daemon (2026-06-11):** `central/scripts/say-notify-overlayd.swift`
  (compiled to `say-notify-overlayd`, gitignored). ONE borderless click-through
  non-activating window, created once; each card is a faded-in subview. This is the fix
  for the focus theft — creating/ordering a NEW window per alert blurred the Ghostty
  terminal's input (even non-activating, even `.statusBar` level). The hook talks to it
  by dropping `<id>.card` / `<id>.dismiss` files in `$TMPDIR/say-notify-cards`. The old
  per-card binary `say-notify-overlay` is kept for demos/the lookdev devserver only.
- **LaunchAgent (machine-local):** `~/Library/LaunchAgents/com.conner.say-notify-overlayd.plist`
  runs the daemon at login with `KeepAlive` (so its one-time `orderFront` happens at login,
  never mid-typing). StdErr `/tmp/say-notify-overlayd.err`. The hook also lazy-launches it
  if not running. Single-instance lock: `$TMPDIR/say-notify-overlayd.lock/pid`.
- **Phrase bank:** `central/scripts/say-notify-phrases.md` (shelved movie/themed lines,
  inspiration only). `~/Desktop/say-notify-phrases.md` is a **symlink** to it.
- **Registration (machine-local, NOT git-tracked):** `~/.claude/settings.json` →
  `hooks.Notification[]` calls `say-notify.sh`. As of 2026-06-22 the **Stop hook is
  removed**: the script's needs-input gate only fires on `permission_prompt` /
  `elicitation_dialog` notifications and suppresses idle + Stop, so registering Stop
  was pure overhead. In bypass/auto-permission mode Claude suppresses `permission_prompt`
  itself, so what you hear is `elicitation_dialog` (an agent asking you to decide).
  `SAY_IDLE=1` opts back into idle callouts. Only the registration is outside central.
- **Runtime state:** `~/.claude/say-callsigns.tsv` — session→callsign overrides only now
  (agent-set via say-callsign.sh; no longer auto-appended).

- **Rate-limit fuel gauge (2026-06-11):** Claude Code's hook payload has NO
  rate-limit data, but the **statusLine** payload does (`rate_limits.{five_hour,
  seven_day}.{used_percentage,resets_at}`, `context_window.used_percentage`,
  `cost`). So the statusline (`central/scripts/statusline-devservers.sh`, symlinked
  to `~/.claude/statusline-devservers.sh`) both (a) renders the gauge — `⛽41%5h
  22%7d ◔50%`, green/yellow≥80/red≥95 — and (b) fires the say-notify "fuel" callout
  on a threshold crossing via a `RATELIMIT <window> <pct>` message (JOKER≥80 /
  BINGO≥95 / WINCHESTER≥100, each carrying "rate limit" + a gas metaphor). Fire-once
  per `(window,threshold,resets_at)` via atomic mkdir markers in `$TMPDIR` so only
  the first window that notices fires — account-wide, not per-tab. The statusLine
  command in settings.json points at the `~/.claude` symlink. (Claude Code itself
  only shows limits via `/usage`; a custom statusLine replaces the default's usage
  display — that's why it "disappeared".)

**Reverse:** remove the `Notification` + `Stop` blocks from `~/.claude/settings.json`;
`launchctl bootout gui/$(id -u)/com.conner.say-notify-overlayd` then
`rm ~/Library/LaunchAgents/com.conner.say-notify-overlayd.plist`; optionally
`rm ~/.claude/say-callsigns.tsv` and the Desktop symlink.

**Why documented:** the settings.json hook registration is machine-local and not in any
repo, so without this note the spoken-notification behavior has no discoverable origin.

## Playwright MCP — muted browser audio (2026-06-12)

Both Playwright MCP servers in `~/.claude.json` (`playwright`, `playwright-headed`)
pass `--config /Users/conner/.claude/playwright/mcp-config.json`, which sets
Chromium `launchOptions.args: ["--mute-audio"]`. Headless Chromium otherwise
plays page audio through the system speakers — a control-audit harness clicking
play on a WebAudio app made the laptop emit synth noise mid-session (skeuo-ui,
2026-06-12). Mute at launch is the root fix; per-page workaround when the MCP
server predates the config: block `AudioContext.prototype.resume` via evaluate
before clicking anything.

**Reverse:** remove the `--config …/mcp-config.json` pair from both servers'
args in `~/.claude.json`; `rm -r ~/.claude/playwright`.

## ComfyUI Desktop — segmentation custom nodes + models (2026-06-16)

Comfy Desktop runs the install at `~/ComfyUI-Installs/Local/ComfyUI` (server on
:8188; `~/Documents/ComfyUI` is a stale separate install — not what's running).
Models are shared via `~/ComfyUI-Shared/models` (set by `~/Library/Application
Support/Comfy Desktop/shared_model_paths.yaml`). For a skeuo-ui slot-detection
bake-off I installed into that running install:

- **Custom nodes** (`~/ComfyUI-Installs/Local/ComfyUI/custom_nodes/`):
  `ComfyUI-Florence2` (kijai), `ComfyUI_BiRefNet_ll` (lldacing),
  `comfyui_segment_anything` (storyicon, GroundingDINO+SAM).
- **venv pip adds** (`.venv`, py3.13): `tokenizers matplotlib pillow segment_anything
  timm addict yapf opencv-python`.
- **Models** (in `~/ComfyUI-Shared/models/`): `checkpoints/sam3.1_multiplex_fp16.safetensors`
  (SAM3.1, 1.6G), plus auto-downloaded Florence-2-base, BiRefNet General,
  GroundingDINO SwinT + SAM vit_b.
- **Vendored patch:** `comfyui_segment_anything/local_groundingdino/models/
  GroundingDINO/bertwarper.py` — shimmed `get_head_mask` for transformers≥5
  (still broken downstream on a `.to()` signature; GroundingDINO is effectively
  non-functional on this torch/transformers stack — left installed but unused).
- Reboot the server after node changes: `curl -XPOST :8188/v2/manager/reboot`.

**Reverse:** `rm -rf ~/ComfyUI-Installs/Local/ComfyUI/custom_nodes/{ComfyUI-Florence2,ComfyUI_BiRefNet_ll,comfyui_segment_anything}`
and the added model files under `~/ComfyUI-Shared/models/`; reboot.

**Workflows folder (for [[comfyui-workflow-export-rule]]):** save generated workflows into
the active install's `user/default/workflows/`. **Two candidates disagree on this box** —
resolve by checking the live server, don't assume:
- `~/Documents/ComfyUI/user/default/workflows/` — the path the user treats as active (holds
  the hand-saved `*.workflow.json`; has a `skeuo` symlink → `skeuo-ui/generation/comfyui`).
- `~/ComfyUI-Installs/Local/ComfyUI/user/default/workflows/` — where the **server actually
  running on :8188 reads from** (per the 2026-06-16 note above + a live `lsof`/`ps` check:
  PID serves `main.py` from `~/ComfyUI-Installs/Local/ComfyUI`).

These can be out of sync. Before claiming a workflow will load in the GUI, confirm the live
server's path (`lsof -nP -iTCP:8188 -sTCP:LISTEN` → `ps -p <pid> -o command=`) and write to
*that* folder, or to whichever GUI the user is actually refreshing — and say which one you used.

## Entire session-tracking — all ~/dev repos + auto-enable (2026-06-18)

Enabled [Entire](https://github.com/entireio/cli) AI-session tracking across all `~/dev`
repos with a **private-checkpoint-repo** privacy model so transcripts never land on a public
remote. Full rationale + commands in the **`entire`** skill; the machine-state pieces:

- **Private checkpoint repo:** `github.com/connerkward/entire-checkpoints` (PRIVATE). All
  repos I own push their `entire/checkpoints/v1` branch here instead of the code remote.
- **Per-repo config** (`.entire/settings.json`, untracked — added to each repo's
  `.git/info/exclude`): owned repos get `checkpoint_remote=connerkward/entire-checkpoints`;
  forks/no-origin (comfyui-mcp, davinci-resolve-mcp, notesutils, feed-demon, local-local) get
  `push_sessions:false` (local-only). Per-repo Claude hooks removed (user-level hooks suffice).
- **`~/.zshrc` `chpwd` hook** (machine-local; `.zshrc` is NOT symlinked to central): function
  `_entire_autoenable` auto-runs `central/scripts/entire-autoenable` on first `cd` into an
  un-enabled `~/dev` git repo. Telemetry disabled; not logged in (local checkpoints only).
- **Existing git hooks** in `bas` and `central` were backed up by Entire to
  `.git/hooks/{post-commit,pre-push}.pre-entire` (Entire chains them).

**Reverse** (all, or one repo): per repo `cd <repo> && entire disable && git branch -D entire/checkpoints/v1`;
remove the `_entire_autoenable`/`add-zsh-hook chpwd` block from `~/.zshrc`; restore any
`.git/hooks/*.pre-entire` backups; optionally `gh repo delete connerkward/entire-checkpoints`.
To opt a single repo out of auto-enable without disabling: `touch <repo>/.entire/.skip`.

## Claude Code PostToolUse hook — screenstudio-alt auto-republish trigger (2026-06-18)

Auto-triggers the publish-skill sanitize+publish pass whenever a central commit touches the
screenstudio-alt skill. **Central is the source of truth**; only the one-line registration is
machine-local (per central-authoring-rule).

- **Logic (canonical, central):** `skills/publish-skill/scripts/on-screenstudio-commit.sh`.
  Reads the PostToolUse Bash payload on stdin; pre-filters to git commit/merge/rebase commands;
  if `git -C ~/dev/central diff-tree --name-only -r HEAD` shows a `skills/screenstudio-alt/`
  path, emits `{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"…run
  the publish-skill sanitize+security pass and publish to connerkward/screenstudio-alternative-skill…"}}`
  so the directive reaches the model next turn. **Silent (exit 0, no output) on every other
  commit.** It does NOT auto-publish — the sanitize/security pass needs the agent's judgment and
  is human-gated; the hook only injects the directive.
- **Registration (machine-local, NOT git-tracked):** `~/.claude/settings.json` →
  `hooks.PostToolUse[]` entry `{matcher:"Bash", command:"~/dev/central/skills/publish-skill/scripts/on-screenstudio-commit.sh"}`.
  Coexists with the existing PostToolUse Task/TodoWrite hooks and the PreToolUse Bash
  devserver-track hook (independent event arrays). Backup made at
  `~/.claude/settings.json.bak-20260618-104314`.
- **Reverse:** remove that one PostToolUse Bash block from `~/.claude/settings.json` (or restore
  the `.bak-*`). The central script can stay; it's inert without the registration.

## rclone — Google Drive CLI (2026-06-24)

`brew install rclone` (v1.74.3 at `/opt/homebrew/bin/rclone`). Used for headless/scripted
Google Drive transfers — the `gdrive` central skill documents usage and the skin-backup
script. The interactive claude.ai Google Drive MCP connector is the in-chat alternative
(not scriptable).

- **Remote `gdrive`** (type `drive`, scope `drive`) scaffolded in
  `~/.config/rclone/rclone.conf` (outside any git repo — standard rclone location; holds
  the OAuth token once authorized, so never to be committed). **OAuth NOT yet completed** —
  the token is empty until the user runs the browser consent once:
  `rclone config reconnect gdrive:`. `rclone listremotes` already shows `gdrive:`;
  `rclone about gdrive:` errors `empty token` until authorized.
- **Service-account path ruled out:** consumer Gmail (`conner.k.ward@gmail.com`, GCP
  project `muser-2605300220` has no parent org) → no Shared Drive, and an SA writing to a
  shared My-Drive folder has 0 quota (`storageQuotaExceeded`). OAuth is the only viable
  path unless the account moves to Google Workspace.
- **Backup script:** `~/dev/central/skills/gdrive/scripts/backup-skeuo-skins.sh` syncs
  `~/dev/skeuo-ui/public/generated/` → `gdrive:skeuo-skins/`. Canonical archive remains
  Cloudflare R2; Drive is a secondary backup.
- **Reversal:** `rm ~/.config/rclone/rclone.conf` (drops the remote + any token);
  `brew uninstall rclone`.

## tailscale serve — skeuo alignment proof (2026-06-24)
- `tailscale serve --bg 65001` proxies `https://lappy-heavy.tilapia-micro.ts.net/` → `http://127.0.0.1:65001`
  (the skeuo-ui `.proof/` gallery, served by `python3 -m http.server 65001 --bind 127.0.0.1`).
- **tailnet-only** (Serve, not Funnel — not public). HTTPS via Tailscale's cert.
- Persists across reboot via tailscaled serve config.
- Reverse: `tailscale serve --https=443 off` (and kill the python http.server on :65001).
