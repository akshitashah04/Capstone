import type { Book, SearchHit, SearchMode } from './types';
import { cleanDescription } from './book-text';

const RRF_OFFSET = 60;
const CANDIDATES = 500;
const STOPWORDS = new Set([
  'a', 'about', 'an', 'and', 'are', 'as', 'at', 'be', 'book', 'books', 'but', 'can', 'do', 'for',
  'from', 'get', 'have', 'how', 'i', 'in', 'is', 'it', 'me', 'my', 'need', 'of', 'on',
  'or', 'read', 'that', 'the', 'this', 'to', 'want', 'what', 'with', 'without', 'would',
  'you', 'de', 'des', 'du', 'en', 'et', 'je', 'la', 'le', 'les', 'pour', 'sur', 'un', 'une',
  'con', 'del', 'el', 'en', 'la', 'las', 'los', 'para', 'por', 'que', 'quiero', 'una',
  'das', 'der', 'die', 'ein', 'eine', 'ich', 'mit', 'und', 'von', 'wie', 'zu',
]);

export function tokens(text: string): string[] {
  const normalized = text.normalize('NFKC').toLowerCase()
    .replace(/\p{Script=Latin}\p{M}*/gu, letter => letter.normalize('NFD').replace(/\p{M}/gu, ''));
  const words = normalized.match(/\p{Script=Han}+|(?:(?!\p{Script=Han})[\p{L}\p{M}\p{N}])+/gu) ?? [];
  return words.flatMap(word => {
    if (/^\p{Script=Han}{2,}$/u.test(word)) {
      const chars = Array.from(word);
      return chars.slice(1).map((char, index) => chars[index] + char);
    }
    return word.length > 1 && !STOPWORDS.has(word) ? [word] : [];
  });
}

interface IndexedBook {
  terms: Map<string, number>;
  length: number;
}

export interface SearchIndex {
  books: Book[];
  terms: IndexedBook[];
  frequency: Map<string, number>;
}

export function buildSearchIndex(books: Book[]): SearchIndex {
  const frequency = new Map<string, number>();
  const terms = books.map(book => {
    const termWeights = new Map<string, number>();
    for (const [text, weight] of [
      [book.title, 3], [(book.aliases ?? []).join(' '), 3],
      [book.subjects.join(' '), 2], [cleanDescription(book.description), 1],
    ] as const) {
      for (const term of tokens(text)) {
        termWeights.set(term, (termWeights.get(term) ?? 0) + weight);
      }
    }
    for (const term of termWeights.keys()) {
      frequency.set(term, (frequency.get(term) ?? 0) + 1);
    }
    return { terms: termWeights, length: Array.from(termWeights.values()).reduce((a, b) => a + b, 0) };
  });
  return { books, terms, frequency };
}

function keywordOrder(query: string, index: SearchIndex): number[] {
  const terms = [...new Set(tokens(query))];
  const n = index.books.length;
  return index.terms.map((book, position) => {
    let score = 0;
    for (const term of terms) {
      const tf = book.terms.get(term) ?? 0;
      if (tf) score += (Math.log((n + 1) / ((index.frequency.get(term) ?? 0) + 1)) + 1) *
        (tf / (tf + 1.2 + 0.004 * book.length));
    }
    return { position, score };
  }).filter(item => item.score > 0)
    .sort((a, b) => b.score - a.score || a.position - b.position)
    .slice(0, CANDIDATES).map(item => item.position);
}

function semanticOrder(queryVector: Float32Array, vectors: Float32Array, count: number): {
  order: number[]; similarities: Float32Array;
} {
  const dimensions = queryVector.length;
  if (dimensions < 1 || vectors.length !== count * dimensions) {
    throw new Error('The selected model and book vectors have different dimensions.');
  }
  const similarities = new Float32Array(count);
  for (let row = 0; row < count; row += 1) {
    let score = 0;
    const start = row * dimensions;
    for (let column = 0; column < dimensions; column += 1) {
      score += queryVector[column] * vectors[start + column];
    }
    similarities[row] = score;
  }
  const order = Array.from({ length: count }, (_, index) => index)
    .sort((a, b) => similarities[b] - similarities[a] || a - b)
    .slice(0, CANDIDATES);
  return { order, similarities };
}

export function rankBooks(
  query: string, queryVector: Float32Array, vectors: Float32Array,
  index: SearchIndex, mode: SearchMode, keywordWeight = 1,
): SearchHit[] {
  if (!query.trim()) throw new Error('Enter a question to search.');
  const { order: meaning, similarities } = semanticOrder(queryVector, vectors, index.books.length);
  const keywords = mode === 'hybrid' ? keywordOrder(query, index) : [];
  const scores = new Map<number, number>();
  for (const [order, weight] of [[meaning, 1], [keywords, keywordWeight]] as const) {
    order.forEach((position, indexInOrder) => {
      scores.set(position, (scores.get(position) ?? 0) + weight / (RRF_OFFSET + indexInOrder + 1));
    });
  }
  const ordered = [...scores.entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0]);
  const seenTitles = new Set<string>();
  const hits: SearchHit[] = [];
  for (const [position, relevance] of ordered) {
    const book = index.books[position];
    if (!cleanDescription(book.description)) continue;
    const titleKey = book.title.normalize('NFKD').toLowerCase().replace(/\s+/g, ' ').trim();
    if (seenTitles.has(titleKey)) continue;
    seenTitles.add(titleKey);
    hits.push({ book, rank: hits.length + 1, relevance, semanticSimilarity: similarities[position] });
    if (hits.length === 10) break;
  }
  return hits;
}

export function rankKeywordBooks(query: string, index: SearchIndex): SearchHit[] {
  if (!query.trim()) throw new Error('Enter a question to search.');
  const seenTitles = new Set<string>();
  const hits: SearchHit[] = [];
  for (const [rank, position] of keywordOrder(query, index).entries()) {
    const book = index.books[position];
    if (!cleanDescription(book.description)) continue;
    const titleKey = book.title.normalize('NFKD').toLowerCase().replace(/\s+/g, ' ').trim();
    if (seenTitles.has(titleKey)) continue;
    seenTitles.add(titleKey);
    hits.push({ book, rank: hits.length + 1, relevance: 1 / (RRF_OFFSET + rank + 1),
      semanticSimilarity: 0 });
    if (hits.length === 10) break;
  }
  return hits;
}
