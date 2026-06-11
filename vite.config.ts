import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Bind all interfaces: reachable via mDNS on home wifi (http://lappy-heavy.local:5173)
// AND via the tailnet (http://lappy-heavy.tilapia-micro.ts.net:5173). No router port
// forwards exist, so 0.0.0.0 = home LAN + tailnet only. See central/rules/dev-server-network-rule.md.
const allowedHosts = ['.local', '.ts.net', 'lappy-heavy']

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // 0.0.0.0
    port: 5173,
    strictPort: true,
    allowedHosts,
  },
  preview: {
    host: true,
    port: 4173,
    strictPort: true,
    allowedHosts,
  },
})
