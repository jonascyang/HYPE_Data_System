import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const apiTarget = process.env.DASHBOARD_DEV_API_TARGET ?? '<dashboard-url>';
const wsTarget = process.env.DASHBOARD_DEV_WS_TARGET ?? apiTarget.replace(/^http/, 'ws');

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/ws': {
        target: wsTarget,
        ws: true,
        changeOrigin: true,
      },
    },
  },
});
