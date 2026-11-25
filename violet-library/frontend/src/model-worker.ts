/// <reference lib="webworker" />

import { env } from '@huggingface/transformers';
import { loadEncoder } from './embedding';
import { MODELS } from './model-config';
import type { ModelKey } from './types';

env.allowLocalModels = false;
env.useBrowserCache = true;
if (env.backends.onnx.wasm) env.backends.onnx.wasm.numThreads = 1;

let activeKey: ModelKey | null = null;
let activeEncoder: Awaited<ReturnType<typeof loadEncoder>> | null = null;
let activeSupplement: { catalog: string; vectors: Float32Array } | null = null;

interface EncodeRequest {
  id: number;
  model: ModelKey;
  text: string;
  catalog: string;
  passages: string[];
}

self.addEventListener('message', async (event: MessageEvent<EncodeRequest>) => {
  const { id, model, text, catalog, passages } = event.data;
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
      if (passages.length) {
        self.postMessage({ type: 'progress', id, message: 'Indexing supplemental titles…' });
      }
      activeSupplement = { catalog, vectors: await activeEncoder.encode(passages, 'passage') };
    }
    self.postMessage({ type: 'progress', id, message: 'Understanding your question…' });
    const vector = await activeEncoder.encode([text], 'query');
    const supplement = activeSupplement.vectors.slice();
    self.postMessage({ type: 'embedding', id, vector, supplement }, [vector.buffer, supplement.buffer]);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'The selected model could not be loaded.';
    self.postMessage({ type: 'error', id, message });
  }
});
