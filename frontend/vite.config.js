import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/admin': { target: 'http://localhost:8000', ws: true },
      '/send-sms': 'http://localhost:8000',
    },
  },
})
