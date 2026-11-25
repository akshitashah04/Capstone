/// <reference lib="webworker" />

import { env } from '@huggingface/transformers';
import { encodeCatalogPassages, loadEncoder } from './embedding';
import { MODELS } from './model-config';
import { encodeSemanticQuery } from './semantic-query';
import type { ModelKey } from './types';

env.allowLocalModels = false;
env.useBrowserCache = true;
if (env.backends.onnx.wasm) env.backends.onnx.wasm.numThreads = 1;

let activeKey: ModelKey | null = null;
let activeEncoder: Awaited<ReturnType<typeof loadEncoder>> | null = null;
let activeSupplement: { catalog: string; vectors: Float32Array } | null = null;

async function loadSupplement(
  encoder: Awaited<ReturnType<typeof loadEncoder>>,
  { id, model, catalog, passages }: EncodeRequest,
): Promise<Float32Array> {
  const { revision, dimensions } = MODELS[model];
  const cache = await self.caches?.open('violet-library-supplement-v1').catch(() => undefined);
  const cacheUrl = new URL(`./supplement-${model}`, self.location.href);
  const version = `${catalog}:${revision}`;
  const cached = await cache?.match(cacheUrl).catch(() => undefined);
  if (cached?.headers.get('X-Embedding-Version') === version) {
    const payload = await cached.arrayBuffer().catch(() => undefined);
    if (payload?.byteLength === passages.length * dimensions * Float32Array.BYTES_PER_ELEMENT) {
      const vectors = new Float32Array(payload);
      if (vectors.every(Number.isFinite)) return vectors;
    }
  }
  const vectors = await encodeCatalogPassages(encoder, passages, dimensions, completed => {
    self.postMessage({
      type: 'progress', id, message: `Indexing additional books (${completed}/${passages.length})…`,
    });
  });
  await cache?.put(cacheUrl, new Response(vectors.buffer, {
    headers: { 'X-Embedding-Version': version },
  })).catch(() => undefined);
  return vectors;
}

interface EncodeRequest {
  id: number;
  model: ModelKey;
  text: string;
  catalog: string;
  passages: string[];
}

self.addEventListener('message', async (event: MessageEvent<EncodeRequest>) => {
  const { id, model, text, catalog } = event.data;
  if (!Object.hasOwn(MODELS, model) || !text?.trim()) {
    self.postMessage({ type: 'error', id, message: 'A model and question are required.' });
    return;
  }
  const { label } = MODELS[model];
  try {
    if (activeKey !== model || !activeEncoder) {
      const priorEncoder = activeEncoder;
      activeEncoder = null;
      activeKey = null;
      activeSupplement = null;
      await priorEncoder?.dispose();
      self.postMessage({ type: 'progress', id, message: `Loading ${label}…` });
      let downloadNoticeSent = false;
      activeEncoder = await loadEncoder(model, () => {
        if (downloadNoticeSent) return;
        downloadNoticeSent = true;
        self.postMessage({
          type: 'progress', id,
          message: `Downloading ${label} model files. This may take several minutes on first use.`,
        });
      });
      activeKey = model;
    }
    if (activeSupplement?.catalog !== catalog) {
      activeSupplement = { catalog, vectors: await loadSupplement(activeEncoder, event.data) };
    }
    self.postMessage({ type: 'progress', id, message: 'Understanding your question…' });
    const vector = await encodeSemanticQuery(activeEncoder, text, model);
    const supplement = activeSupplement.vectors.slice();
    self.postMessage({ type: 'embedding', id, vector, supplement }, [vector.buffer, supplement.buffer]);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'The selected model could not be loaded.';
    self.postMessage({ type: 'error', id, message });
  }
});
