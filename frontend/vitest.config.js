/* eslint-env node */
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  poolOptions: {
    threads: {
      isolate: false,
      singleThread: false,
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/setupTests.js'],
    css: false,
    pool: 'threads',
    exclude: ['**/tests/**', '**/node_modules/**'],
  },
})
