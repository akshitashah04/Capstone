import { defineConfig } from 'vite';

export default defineConfig({
  base: '/Capstone/libraries/',
  build: {
    outDir: 'dist',
    target: 'es2022',
  },
});
