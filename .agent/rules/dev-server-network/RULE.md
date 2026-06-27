---
name: "dev-server-network-rule"
id: "dev-net-01"
description: "Bind dev servers the user wants to reach from another device to 0.0.0.0 so they're reachable via home-wifi mDNS (.local) and tailnet (MagicDNS); never bind a single LAN IP or port-forward to the public internet."
globs: ["**/*"]
applyTo: ["**/*"]
alwaysApply: true
priority: "high"
human-reviewed-at: 2026-06-16
human-reviewed-by: connerward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

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
