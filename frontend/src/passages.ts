import type { Book } from './types';

export function passageText(book: Book): string {
  return [
    book.title, ...book.authors, ...(book.aliases ?? []),
    ...book.subjects, book.description,
  ].join('\n');
}

export function appendVectors(base: Float32Array, supplement: Float32Array): Float32Array {
  if (!supplement.length) return base;
  const vectors = new Float32Array(base.length + supplement.length);
  vectors.set(base);
  vectors.set(supplement, base.length);
  return vectors;
}
