import { pipeline } from '@huggingface/transformers';
import { MODELS } from './model-config';
import type { ModelKey } from './types';

export async function loadEncoder(model: ModelKey, progress?: () => void) {
  const config = MODELS[model];
  const extractor = await pipeline('feature-extraction', config.repo, {
    revision: config.revision,
    dtype: 'q8',
    progress_callback: event => {
      if (event.status === 'progress') progress?.();
    },
  });

  return {
    dispose: () => extractor.dispose(),
    async encode(texts: string[], kind: 'query' | 'passage'): Promise<Float32Array> {
      if (!texts.length) return new Float32Array();
      const prefix = kind === 'query' ? config.queryPrefix : model === 'gte-base' ? '' : 'passage: ';
      const output = await extractor(texts.map(text => prefix + text), {
        pooling: config.pooling, normalize: true,
      });
      const vector = new Float32Array(output.data as Float32Array);
      if (vector.length !== config.dimensions * texts.length ||
          vector.some(value => !Number.isFinite(value))) {
        throw new Error('The model returned invalid embeddings.');
      }
      return vector;
    },
  };
}
