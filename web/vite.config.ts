import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { buildProxy } from './proxy'

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: {
    proxy: buildProxy(loadEnv(mode, '.', '')),
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
}))
