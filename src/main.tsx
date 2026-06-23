import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { isWidget } from './platform'

// The same bundle is the website AND the Tauri desktop widget. In widget mode we
// mount a single transparent skin (WidgetApp); otherwise the full site (App).
// Lazy-import so neither path pulls in the other's components needlessly.
async function boot() {
  const root = createRoot(document.getElementById('root')!)
  // DEV-ONLY harnesses: ?cutcheck (real cutSprite on saved paints), ?cutcompare (VLM vs SAM masking).
  if (import.meta.env.DEV && new URLSearchParams(location.search).has('cutcheck')) {
    const { default: CutCheck } = await import('./debug/CutCheck')
    root.render(<StrictMode><CutCheck /></StrictMode>)
    return
  }
  if (import.meta.env.DEV && (new URLSearchParams(location.search).has('cutcompare') || new URLSearchParams(location.search).has('pipeline'))) {
    const { default: Pipeline } = await import('./debug/Pipeline')
    root.render(<StrictMode><Pipeline /></StrictMode>)
    return
  }
  if (import.meta.env.DEV && new URLSearchParams(location.search).has('recut')) {
    const { default: Recut } = await import('./debug/Recut')
    root.render(<StrictMode><Recut /></StrictMode>)
    return
  }
  if (import.meta.env.DEV && new URLSearchParams(location.search).has('segcheck')) {
    const { default: SegCheck } = await import('./debug/SegCheck')
    root.render(<StrictMode><SegCheck /></StrictMode>)
    return
  }
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
