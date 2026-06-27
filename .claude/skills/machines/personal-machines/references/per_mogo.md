# XGIMI MoGo 2 Pro (War Room projector)

- **Role:** Portable Android TV projector. Primary display for the **War Room**
  dashboard (`~/dev/war-room`, https://github.com/connerkward/war-room) — runs a
  TV browser pointed at the War Room SPA.
- **Hardware:** XGIMI MoGo 2 Pro (1080p DLP, ~400 ISO lumens, portable).
- **OS:** Android TV / Google TV. Cast build `3.72.446070` (cast revision
  3.72.446070, `build_version` 446070). Ships on Android TV 11. No ADB enabled
  yet, so exact Android build unconfirmed beyond the Cast fingerprint above.
- **Cast name:** `XGIMI MoGo 2 Pro` (`ssdp_udn f978fa72-ab55-a1e6-69d6-f8d29eb8f5ef`).
- **Always on?** No — portable projector, only networked while powered on. mDNS
  Cast/remote services disappear when it's off.

## Network

- **LAN IP:** `192.168.8.204` (DHCP, **not reserved** — may change on lease
  renewal; see "TODO" to pin it).
- **Connectivity:** WiFi only (`ethernet_connected: false`). On the home
  192.168.8.0/24 LAN behind the GL.iNet AX1800 ([[per_router]]).
- **MAC OUI:** `4c:24:ce` (Sichuan AI-Link Technology — common Android-TV
  board ODM). Full MAC not recorded (Cast endpoint reports `00:00:00:00:00:00`).
- **Tailscale:** Not installed / not on the tailnet. (Tailscale's Android app
  *can* run on Android TV if remote-on-the-go access is ever wanted.)
- **No stable hostname** — reached by IP, or by Cast name on the LAN. No `.local`
  reverse record.

## Open ports (live probe, projector on)

| Port | Service                         |
|------|---------------------------------|
| 8008 | Google Cast (HTTP, `eureka_info`) |
| 8009 | Google Cast (TLS)               |
| 6466 | Android TV Remote v2 (pairing)  |
| 5555 | ADB over network (enabled — see below) |

Query device state any time it's on:
`curl -s http://192.168.8.204:8008/setup/eureka_info?options=detail | python3 -m json.tool`

## ADB (enabled 2026-06-12)

- **Developer options + USB/network debugging are ON.** ADB listens on `192.168.8.204:5555`.
- **lappy-heavy's adb key is authorized** (accepted "Always allow" on-screen once). Reconnect:
  `adb connect 192.168.8.204:5555` then `adb -s 192.168.8.204:5555 ...`. adb installed via `brew install android-platform-tools`.
- Connection drops when the projector sleeps; just `adb connect` again when it's awake.
- **CPU ABI: `armeabi-v7a` (32-bit ARM only)** — arm64 APKs fail with `INSTALL_FAILED_NO_MATCHING_ABIS`. Use armeabi-v7a or ABI-agnostic builds.
- **System WebView: Chromium 148** (modern — renders React/Vite fine).
- To reverse: Settings → System → Developer options → turn off USB debugging (and revoke ADB authorizations).

## TV Bro (browser, installed 2026-06-12)

- Package `com.phlox.tvwebbrowser` (TV Bro 2.1.6, generic/geckoExcluded build — uses system WebView, ABI-agnostic; the arm64/armeabi gecko builds were avoided for RAM + ABI).
- Loads **https://war-room.ward.run**. Restores last page on relaunch.
- Launch to the dashboard via ADB:
  `adb -s 192.168.8.204:5555 shell am start -a android.intent.action.VIEW -d "https://war-room.ward.run" com.phlox.tvwebbrowser`
- To pin as start page: TV Bro → Settings → Home page → `war-room.ward.run` (remote, one-time). No native boot-autostart on Google TV without a helper app.

## War Room display

- **Audio split:** projector drives **video only**; audio lives on a separate
  Apple TV → AV/speakers chain. War Room emits no audio by design, so the two are
  independent (Apple TV has no web browser — tvOS ships none — so it can't host
  War Room; the Android TV here is the only browser-capable display in the path).
- **Browser:** install a D-pad-friendly TV browser — **TV Bro** (open-source,
  supports fullscreen + open-URL-on-boot) is the pick; Puffin is cloud-rendered
  and can't reach LAN/localhost, so it won't work for War Room.
- **URL:** **https://war-room.ward.run** — always-on (Cloudflare Pages, project
  `war-room`). Point TV Bro here and set it as the on-boot URL. (Local dev still
  runs at `http://lappy-heavy.local:5173` when iterating; deploy with
  `~/dev/war-room/deploy.sh`.)

## TODO / not yet done

- **Pin the IP:** add a DHCP reservation for `192.168.8.204` on the router so the
  whitelist stays stable (router change → document under [[per_router]] when
  done). Lower priority now that War Room is at a stable public URL rather than a
  LAN-IP dev server.
- **Optional ADB:** enable Developer Options → USB/Network debugging if remote
  install/control of TV Bro + kiosk launch is wanted (`adb connect 192.168.8.204:5555`).
- **Optional tailnet:** install the Tailscale Android app for off-LAN access.

## Reversal

Nothing persistent was changed on this device or the network to create this
entry — it was identified passively (ARP + mDNS/Cast probe). No reversal needed.
