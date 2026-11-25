import { defineConfig } from 'vite';

export default defineConfig({
  base: '/Capstone/libraries/',
  resolve: {
    // Search models only use CPU inference. Keep WebGPU and its asyncify runtime out of the worker.
    alias: [{ find: /^onnxruntime-web\/webgpu$/, replacement: 'onnxruntime-web/wasm' }],
  },
  build: {
    outDir: 'dist',
    target: 'es2022',
  },
});
