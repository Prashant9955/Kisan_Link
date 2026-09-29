import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: 'localhost',
    port: 5173,
    strictPort: true,
    // Disable Vite HMR in this project. This removes the broken
    // ws://localhost:undefined fallback seen in some local setups.
    // The page must be refreshed manually after source changes.
    hmr: false,
  },
})
