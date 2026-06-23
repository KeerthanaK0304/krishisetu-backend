import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/bridge/loginForDevice': {
        target: 'https://ca.cosmitude.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/bridge/, ''),
      },
      '/bridge': {
        target: 'https://fs.cosmitude.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/bridge/, ''),
      }
    }
  }
})