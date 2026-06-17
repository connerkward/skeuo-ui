import { defineConfig } from 'vite'
import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import { devApiPlugin } from './server/devApiPlugin'

// Bind all interfaces: reachable via mDNS on home wifi (http://lappy-heavy.local:5173)
// AND via the tailnet (http://lappy-heavy.tilapia-micro.ts.net:5173). No router port
// forwards exist, so 0.0.0.0 = home LAN + tailnet only. See central/rules/dev-server-network-rule.md.
const allowedHosts = ['.local', '.ts.net', 'lappy-heavy']

// https://vite.dev/config/
export default defineConfig({
  // devApiPlugin serves POST /api/generate locally (mirrors the CF Pages Function)
  plugins: [react(), devApiPlugin()],
  // Single-page app. (Template authoring is now the in-app Create wizard's
  // Layout step — the old standalone editor.html / WorkshopEditor was removed.)
  build: {
    rollupOptions: {
      input: { main: resolve(__dirname, 'index.html') },
    },
  },
  // Pre-bundle the Tauri packages so the widget's lazy import()s resolve in dev
  // (a cold, un-optimized dep makes the WKWebView throw "Importing a module
  // script failed" on first dynamic import). Harmless for the web build.
  optimizeDeps: {
    include: [
      '@tauri-apps/api/event',
      '@tauri-apps/api/window',
      '@tauri-apps/plugin-deep-link',
      '@tauri-apps/plugin-opener',
    ],
  },
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
