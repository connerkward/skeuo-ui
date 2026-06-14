import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { isWidget } from './platform'

// The same bundle is the website AND the Tauri desktop widget. In widget mode we
// mount a single transparent skin (WidgetApp); otherwise the full site (App).
// Lazy-import so neither path pulls in the other's components needlessly.
async function boot() {
  const root = createRoot(document.getElementById('root')!)
  if (isWidget()) {
    document.documentElement.classList.add('widget') // transparent-bg hook (widget.css)
    const { default: WidgetApp } = await import('./widget/WidgetApp')
    root.render(<StrictMode><WidgetApp /></StrictMode>)
  } else {
    const { default: App } = await import('./App.tsx')
    root.render(<StrictMode><App /></StrictMode>)
  }
}

void boot()
