import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/health': 'http://localhost:8001',
      '/instruments': 'http://localhost:8001',
      '/research': 'http://localhost:8001',
      '/backtest': 'http://localhost:8001',
      '/execution': 'http://localhost:8001',
      '/dq': 'http://localhost:8001',
    },
  },
  build: {
    outDir: '../frontend/dist',
    emptyOutDir: true,
  },
})
