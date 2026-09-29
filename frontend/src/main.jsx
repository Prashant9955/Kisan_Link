import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import { AuthProvider } from './context/AuthContext.jsx'
import { RealtimeProvider } from './context/RealtimeContext.jsx'
import { LanguageProvider } from './context/LanguageContext.jsx'
import 'leaflet/dist/leaflet.css'
import './index.css'

// Service workers are useful for the installed/PWA build, but they must not
// intercept Vite development traffic. The old worker was caching POST
// requests and also caching the Vite client, which caused stale HMR code.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    if (import.meta.env.PROD) {
      try {
        await navigator.serviceWorker.register('/sw.js')
      } catch (error) {
        console.warn('Service worker registration failed:', error)
      }
    } else {
      const registrations = await navigator.serviceWorker.getRegistrations()
      await Promise.all(registrations.map((registration) => registration.unregister()))
      const cacheNames = await caches.keys()
      await Promise.all(cacheNames.map((name) => caches.delete(name)))
    }
  })
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <LanguageProvider>
        <AuthProvider>
          <RealtimeProvider>
            <App />
          </RealtimeProvider>
        </AuthProvider>
      </LanguageProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
