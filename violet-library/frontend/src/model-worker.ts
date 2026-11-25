/// <reference lib="webworker" />

import { env } from '@huggingface/transformers';
import wasmUrl from 'onnxruntime-web/ort-wasm-simd-threaded.wasm?url';
import { encodeCatalogPassages, loadEncoder } from './embedding';
import { MODELS } from './model-config';
import { encodeSemanticQuery } from './semantic-query';
import type { ModelKey } from './types';

env.allowLocalModels = false;
env.useBrowserCache = true;
if (env.backends.onnx.wasm) {
  env.backends.onnx.wasm.numThreads = 1;
  env.backends.onnx.wasm.wasmPaths = { wasm: new URL(wasmUrl, self.location.origin).href };
}

let encoderPromise: ReturnType<typeof loadEncoder> | null = null;
let activeSupplement: { catalog: string; vectors: Float32Array } | null = null;
let lastQuery: { text: string; vector: Float32Array } | null = null;

function encoderFor(model: ModelKey, onDownload?: () => void) {
  encoderPromise ??= loadEncoder(model, onDownload, 'wasm').catch(error => {
    encoderPromise = null;
    throw error;
  });
  return encoderPromise;
}

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
  prepared: boolean;
}

self.addEventListener('message', async (event: MessageEvent<EncodeRequest | { model: ModelKey; type: 'warm' }>) => {
  const request = event.data;
  if (!Object.hasOwn(MODELS, request.model)) return;
  if ('type' in request) {
    await encoderFor(request.model).catch(() => undefined);
    return;
  }
  const { id, model, text, catalog, prepared } = request;
  if (!text.trim()) {
    self.postMessage({ type: 'error', id, message: 'A search question is required.' });
    return;
  }
  const { label } = MODELS[model];
  try {
    self.postMessage({ type: 'progress', id, message: `Preparing ${label} search…` });
    const encoder = await encoderFor(model, () => {
      self.postMessage({ type: 'progress', id, message: `Downloading the ${label} model for first use…` });
    });
    if (!prepared && activeSupplement?.catalog !== catalog) {
      activeSupplement = { catalog, vectors: await loadSupplement(encoder, request) };
    }
    self.postMessage({ type: 'progress', id, message: 'Understanding your question…' });
    if (lastQuery?.text !== text) {
      lastQuery = { text, vector: await encodeSemanticQuery(encoder, text, model) };
    }
    const vector = lastQuery.vector.slice();
    const supplement = prepared ? new Float32Array() : activeSupplement!.vectors.slice();
    self.postMessage({ type: 'embedding', id, vector, supplement }, [vector.buffer, supplement.buffer]);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'The selected model could not be loaded.';
    self.postMessage({ type: 'error', id, message });
  }
});
