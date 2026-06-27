# Home Router

- **Hostname:** root@192.168.8.1 (LAN gateway)
- **Role:** Home network gateway/router/AP. OpenWrt-based.
- **Hardware:** GL.iNet AX1800 (Flint), GL-AX1800
- **Firmware:** GL.iNet 4.6.8 / OpenWrt 21.02-SNAPSHOT (BusyBox v1.33.2)
- **Access:** SSH key-based auth as root. Dropbear SSH (LAN-only, port 22). Password auth enabled.
- **LAN:** Bridge `br-lan` spanning eth1-4 (wired) + wlan0/wlan1 (WiFi). Subnet 192.168.8.0/24.
- **WAN:** eth0, DHCP from ISP.
- **WiFi:** Dual-band. AP isolation off on main radios. Guest networks (guest2g, guest5g) have isolation on.

## Tailscale

- **Tailscale IP:** 100.66.148.53 (IPv6: fd7a:115c:a1e0::e538:9435)
- **DNS name:** gl-ax1800.tilapia-micro.ts.net
- **Version:** 1.66.4 (gl-sdk4-tailscale package, bundled with GL.iNet firmware)
- **Tags:** None (untagged, owned by autogroup:member)
- **Key expiry:** 2026-08-23
- **Config:** UCI `tailscale.settings` — enabled, port 41641, LAN/WAN access disabled (`lan_enabled=0`, `wan_enabled=0`)
- **Role:** Basic tailnet membership. Not an exit node, not a subnet router.
- **Note:** Tailscale version is old but tied to GL.iNet firmware; updating requires firmware update or manual binary replacement.

## Services

| Service       | Bind address        | Purpose                          |
|---------------|---------------------|----------------------------------|
| nginx         | 0.0.0.0:80,443      | GL.iNet admin UI (LuCI/GL)       |
| AdGuardHome   | :::3000, :::3053    | DNS filtering (UI + DNS-over-TLS)|
| dnsmasq       | LAN+lo+TS:53        | DHCP + DNS (forwards to AGH@3053)|
| dropbear      | 192.168.8.1:22      | SSH (LAN-only)                   |
| uhttpd        | 127.0.0.1:8080      | OpenWrt admin (localhost only)    |
| tailscaled    | 100.66.148.53:35713 | Tailscale PeerAPI                |

## Firewall

- **WAN input policy:** DROP (default deny)
- **Explicit WAN blocks:** SSH(22), DNS(53), HTTP(80), HTTPS(443), RPC(135), SMB(137-139,445), AdGuard(3000,3053), SQL(1433), RDP(3389), VNC(5900), X11(6000-6002,6008), Admin(8080), Plex(32400), misc(61205)
- **WAN ping:** Blocked (Block-WAN-Ping)
- **No port forwards** (removed all DNAT rules 2026-02-23)
- **LAN→WAN forwarding:** Allowed (masquerade/NAT)
- **Guest zone:** Isolated, only DHCP(67-68) and DNS(53) allowed

## DNS Chain

Clients → dnsmasq (:53) → AdGuardHome (127.0.0.1:3053) → upstream
