import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'node:fs';
import path from 'node:path';

function localUserGuideDownloads() {
  const userGuideRoot = path.resolve(__dirname, '../UserGuide');
  const contentTypes = {
    '.pdf': 'application/pdf',
    '.zip': 'application/zip',
    '.md': 'text/markdown; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
  };

  return {
    name: 'local-user-guide-downloads',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const requestPath = decodeURIComponent((req.url || '').split('?')[0]);
        if (!requestPath.startsWith('/download/user-guides/')) {
          next();
          return;
        }

        const relativePath = requestPath.replace('/download/user-guides/', '');
        const filePath = path.resolve(userGuideRoot, relativePath);
        if (!filePath.startsWith(userGuideRoot + path.sep)) {
          res.statusCode = 403;
          res.end('Access denied');
          return;
        }
        if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
          res.statusCode = 404;
          res.end('File not found');
          return;
        }

        const ext = path.extname(filePath).toLowerCase();
        res.setHeader('Content-Type', contentTypes[ext] || 'application/octet-stream');
        res.setHeader('Content-Length', fs.statSync(filePath).size);
        fs.createReadStream(filePath).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), localUserGuideDownloads()],
  server: {
    port: 5173,
    proxy: {
      // Proxy all /api/* requests to the backend during local dev
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      // Proxy /download/* for file download during local dev
      '/download': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      // Proxy /health
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
