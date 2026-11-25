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
