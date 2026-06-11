import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import os from 'node:os'

// Bind ONLY to the home-Wi-Fi LAN interface (192.168.8.0/24), not 0.0.0.0.
// This machine is also on Tailscale, so 0.0.0.0 would expose the dev server to
// the tailnet too — we want home-Wi-Fi only. Falls back to localhost if the
// home subnet isn't found (e.g. off the home network).
function homeLanIp(): string {
  for (const addrs of Object.values(os.networkInterfaces())) {
    for (const a of addrs ?? []) {
      if (a.family === 'IPv4' && !a.internal && a.address.startsWith('192.168.8.')) {
        return a.address
      }
    }
  }
  return '127.0.0.1'
}
const HOST = homeLanIp()

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: HOST,          // home-Wi-Fi LAN IP only (not the tailnet / not all interfaces)
    port: 5173,
    strictPort: true,
    allowedHosts: ['.local'],   // accept the Bonjour name for iOS (lappy-heavy.local)
  },
  preview: {
    host: HOST,
    port: 4173,
    strictPort: true,
    allowedHosts: ['.local'],
  },
})
