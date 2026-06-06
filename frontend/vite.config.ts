import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Keep the React runtime in a stable, separately-cacheable chunk. The
        // crypto (@scure/@noble/ethers) and charts (lightweight-charts) bundles are left
        // to Rollup's natural code-splitting so they stay in the async chunks
        // behind their dynamic-import boundaries (login modal, signing,
        // PriceChart) rather than being promoted into the initial preload.
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
        },
      },
    },
  },
})
