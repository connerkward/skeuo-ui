# Desky

_Last verified: 2026-06-09_

- **Hostname:** conner@desky (tailscale), conner@desky.local (home-lan)
- **SSH:** Key-based only (`~/.ssh/id_ed25519`). Tailscale SSH not supported on Windows. Use `ssh desky` (configured in `~/.ssh/config`).
- **Role:** Personal always-on hub. Tailscale peer.
- **Hardware:** Windows 10, i7-2600K, 32GB, GTX 960. No MDM.
- **Availability:** Always on
- **Storage:** Syncthing (ideas-syncthing): creative projects, archives; no ComfyUI output here. GDrive/Comfy if used: Windows path per project. Emby media: `E:\Media\{Movies,TV,Music,Other,Downloads}` **and** `C:\Media\{Movies,...}` (secondary library root; both mapped in Emby).
- **⚠ E: drive (RAID) write issues:** E: is experiencing RAID write failures. Prefer reads; avoid new writes to E:\ until resolved. Route new downloads / Media additions to another drive (C: or D:) and reconcile later. Revisit before assuming E: is healthy.
- **Emby credentials:** User `conner`. Password in macOS keychain on lappy/lappyheavy: `security find-generic-password -s emby-desky -w`.
- **Python:** 3.11.9 (`C:\Users\conner\AppData\Local\Programs\Python\Python311\python.exe`), also system default
- **Tools:** yt-dlp, ffmpeg (`C:\tools` on PATH), piactl (`C:\Program Files\Private Internet Access\` on PATH)
- **Services:**
  - Emby Server: `http://desky:8096` (local/tailnet), `https://desky.tilapia-micro.ts.net` (Tailscale Funnel for external smart TVs). v4.9.3.0, auto-update enabled.
  - Deluge WebUI: `http://desky:8112`. Download dir: `E:\Media\Downloads`.
  - PIA VPN: client **v3.7.2-08420** (upgraded 2026-06-02 from ancient v3.3.1/2022 — see PIA upgrade note below). Headless config: `connectOnLaunch=true`, `persistDaemon=true`, background mode enabled → daemon auto-connects on boot without an interactive login/GUI. Default region `ca-vancouver`. Killswitch `off`. Login token at `C:\Program Files\Private Internet Access\data\account.json`. Control via `piactl get connectionstate` / `piactl connect`.
  - Landing Page: `http://desky.local/` or `http://192.168.8.244/` (port 80, local/tailnet only; also via Tailscale Serve `/`). Single-page dashboard (`server.py` + `index.html`): live PIA state/region/IP, `C:`/`E:` disk usage, and Deluge VPN-binding health via the `/api/status` JSON endpoint, plus `/torrent`→Deluge redirect and Emby/Deluge links. `server.py` binds 8080; port-80 service must run `server.py` (NOT plain `http.server`, or `/api/status` breaks — `setup-port80.ps1` is stale on this point). NSSM service `desky-landingpage`. Location: `C:\Users\conner\dev\desky-landingpage` (repo: `https://github.com/connerkward/desky-landingpage`, **private**; see repo `README.md`).
- **Scheduled Tasks:**
  - `EmbyMonitor` (15 min): failed auth alerts, version stale, process down, disk space, PIA+Deluge safety. Telegram via `@conward_desky_monitor_bot`.
  - `MediaSorter` (10 min): auto-classifies and moves completed downloads from `E:\Media\Downloads` to correct Emby library folder.
  - `CentralSync` (1 min): `git pull --ff-only` on central.
- **Startup:**
  - `pia_watchdog.bat` — real-time PIA monitor (NSSM service): kills Deluge instantly if VPN disconnects, re-syncs forwarded port + tunnel IP on reconnect, 5-min health check on listen-port binding, and a 30s torrent-monitor thread that Telegrams on download completion (name/size/`E:` usage).
- **Monitor scripts:** `C:\Users\conner\dev\emby-monitor\` (repo: `https://github.com/connerkward/emby-monitor`, **private**) — `emby_monitor.py`, `media_sorter.py`, `pia_watchdog.py`. See repo `README.md` for per-script detail. ⚠ Telegram bot token + chat id are hardcoded in source (not in `.env`) — private repo, but a secrets-hygiene exception to revisit.
- **Tailscale Funnel:** `https://desky.tilapia-micro.ts.net` → Emby (port 8096). External smart TV Emby apps point here.
- **Projects:** `C:\Users\conner\exp-notes-indexing\` — Apple Notes → Graphiti/Kuzu knowledge graph. Kuzu DB at `graphiti_notes.kuzu/`. Has checkpoint resume.
- **Tools → MCP:**

## Maintenance log

### 2026-06-02 — PIA client upgrade 3.3.1 → 3.7.2 (fixed VPN auto-connect + Deluge)
- **Symptom:** PIA showed `Disconnected` after a reboot; Deluge not running. Root cause: PIA client was **v3.3.1 (April 2022)**, far too old — its local IPC desynced against PIA's current backend data (`piactl` logged a flood of *"Invalid message: missing or incorrect magic tag"* and timed out). `piactl get connectionstate` misreported `Disconnected` even while the WireGuard tunnel was up and tunneling. Because `pia_watchdog.py` drives entirely off `piactl ... connectionstate`, it concluded the VPN was down and **killed Deluge**, despite a working tunnel.
- **Also contributing:** desky had **no interactive login session** (sat at the Windows login screen post-reboot, no `explorer.exe`). PIA's GUI `connectOnLaunch` only fires on interactive login, so headless it never connected via the GUI path.
- **Fix:** `choco install pia -y --force` (Chocolatey 2.6.0 already present; pulled `pia-windows-x64-3.7.2-08420.exe`). Installed in place to `C:\Program Files\Private Internet Access`, **preserved login + region**. After upgrade: `piactl connect` → `Connected` in 5s, **port-forward now active (e.g. 24010)**, `piactl` reports state accurately. Restarted `pia-watchdog` service → it synced Deluge config (PF port + `wgpia0` tunnel IP `10.x`) and started `deluge-daemon`/`deluge-web`.
- **Headless auto-connect:** enabled `piactl background enable` (+ existing `connectOnLaunch`/`persistDaemon`) so the daemon auto-connects on boot without needing the GUI/interactive login.
- **Also reset** PIA's region cache once during diagnosis: backed up `C:\Program Files\Private Internet Access\data\data.json` → `data.json.bak-pre-reset` (the upgrade supersedes this; the `.bak` can be deleted).
- **Note:** SSH-as-`conner` over Tailscale runs **elevated (admin)**, so installers/`choco` run without an interactive UAC prompt. PIA reinstall did **not** disturb Tailscale/OpenSSH (independent services).
- **Reversal:** `choco uninstall pia -y` then reinstall the desired version; PIA keeps an auto-uninstaller. To disable headless auto-connect: `piactl background disable`.
