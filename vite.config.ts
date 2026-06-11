import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Bind to the LAN so devices on the home Wi-Fi (Second Bedroom 5g / 2G, same
  // 192.168.8.0/24 subnet) can reach it. This is home-network-only — the router
  // does not forward it to the public internet.
  server: {
    host: true,          // listen on 0.0.0.0 (all LAN interfaces)
    port: 5173,
    strictPort: true,
    // accept the Mac's Bonjour/mDNS name so iOS can use http://lappy-heavy.local:5173
    allowedHosts: [".local"],
  },
  preview: {
    host: true,
    port: 4173,
    strictPort: true,
    allowedHosts: [".local"],
  },
})
