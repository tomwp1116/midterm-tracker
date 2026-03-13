import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/midterm-tracker/',
  plugins: [react()],
  build: {
    outDir: 'docs',
  },
})