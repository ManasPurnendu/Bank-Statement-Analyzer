import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  root: 'static',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'static/js/main.js')
      }
    }
  }
});
