import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { ToastProvider } from './context/ToastContext'

// Registered here rather than in an inline <script> in index.html: the CSP is
// script-src 'self', which blocks inline scripts, so an inline registration
// silently never runs.
// updateViaCache 'none': always revalidate the worker script itself. The
// default lets the HTTP cache delay an update, and a delayed service-worker
// update is how a stale page survives a deploy.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' })
  })
}

const rootEl = document.getElementById('root')
if (!rootEl) throw new Error('Root element not found')
createRoot(rootEl).render(
  <StrictMode>
    <ToastProvider>
      <App />
    </ToastProvider>
  </StrictMode>,
)
