import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  server: { host: '127.0.0.1', port: Number(process.env.WEB_PORT ?? 5173), proxy: { '/api': process.env.VITE_API_TARGET ?? 'http://127.0.0.1:8000' } },
})
