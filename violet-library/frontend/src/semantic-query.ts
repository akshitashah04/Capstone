import type { loadEncoder } from './embedding';
import type { ModelKey } from './types';

export const GTE_FOCUS_WEIGHT = 0.25;

export function focusedQuery(text: string): string {
  const focus = text
    .replace(/(^|[.!?]\s+)where can i learn to\s+/giu, '$1Learn to ')
    .replace(/^(?:i (?:need|want|would like)\s+)(?:an?\s+)?(?:(?:college|open-access)\s+)?(?:books?|textbooks?|guides?)\s+(?:that\s+explains?\s+|(?:on|about)\s+)/iu, '')
    .replace(/[.!?]\s+(?:please\s+)?find (?:me )?(?:one|a book) written in [\p{L}\p{M} -]+[.!?]?$/iu, '')
    .trim();
  return focus || text;
}

export function blendQueryVectors(
  original: Float32Array,
  focused: Float32Array,
  weight: number,
): Float32Array {
  if (original.length !== focused.length) throw new Error('Query embeddings are misaligned.');
  return original.map((value, i) => (1 - weight) * value + weight * focused[i]);
}

export async function encodeSemanticQuery(
  encoder: Awaited<ReturnType<typeof loadEncoder>>,
  original: string,
  model: ModelKey,
): Promise<Float32Array> {
  const focus = focusedQuery(original);
  const originalVector = await encoder.encode([original], 'query');
  if (model !== 'gte-base' || focus === original) return originalVector;
  const focusedVector = await encoder.encode([focus], 'query');
  return blendQueryVectors(originalVector, focusedVector, GTE_FOCUS_WEIGHT);
}
