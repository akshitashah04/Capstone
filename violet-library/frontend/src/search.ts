import type { Book, ModelKey, SearchHit, SearchMode } from './types';
import { bookAccess } from './book-access';
import { cleanDescription } from './book-text';
import { bookLanguages } from './languages';
import { interpretQuery, supportsQueryIntent } from './query-intent';

const MAX_KEYWORD_BONUS = 0.025;
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
  languages: string[];
  hasDescription: boolean;
  fullText: boolean;
  metadata: string;
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
    return {
      terms: termWeights,
      length: Array.from(termWeights.values()).reduce((a, b) => a + b, 0),
      languages: bookLanguages(book),
      hasDescription: Boolean(cleanDescription(book.description)),
      fullText: bookAccess(book).type !== 'record',
      metadata: [book.title, ...(book.aliases ?? []), ...book.subjects, cleanDescription(book.description)].join('; '),
    };
  });
  return { books, terms, frequency };
}

function eligiblePositions(query: string, index: SearchIndex, language?: string, fullTextOnly = false): number[] {
  const intent = interpretQuery(query);
  return index.terms.flatMap((book, position) =>
    book.hasDescription && (!fullTextOnly || book.fullText) &&
    (!language || book.languages.includes(language)) &&
    supportsQueryIntent(book.metadata, intent) ? [position] : []);
}

export function hasEligibleBooks(query: string, index: SearchIndex, language?: string, fullTextOnly = false): boolean {
  return eligiblePositions(query, index, language, fullTextOnly).length > 0;
}

function keywordScores(query: string, index: SearchIndex, positions: number[]): Map<number, number> {
  const terms = [...new Set(tokens(query))];
  const n = index.books.length;
  const scores = new Map<number, number>();
  for (const position of positions) {
    const book = index.terms[position];
    let score = 0;
    for (const term of terms) {
      const tf = book.terms.get(term) ?? 0;
      if (tf) score += (Math.log((n + 1) / ((index.frequency.get(term) ?? 0) + 1)) + 1) *
        (tf / (tf + 1.2 + 0.004 * book.length));
    }
    if (score > 0) scores.set(position, score);
  }
  return scores;
}

function searchHits(
  ranked: Array<{ position: number; relevance: number; semanticSimilarity: number }>,
  index: SearchIndex,
): SearchHit[] {
  ranked.sort((a, b) => b.relevance - a.relevance ||
    b.semanticSimilarity - a.semanticSimilarity || a.position - b.position);
  const seen = new Set<string>();
  const hits: SearchHit[] = [];
  for (const { position, relevance, semanticSimilarity } of ranked) {
    const book = index.books[position];
    const key = [book.title, book.authors[0] ?? ''].map(value =>
      value.normalize('NFKC').toLowerCase().replace(/\s+/g, ' ').trim()).join('\u0000');
    if (seen.has(key)) continue;
    seen.add(key);
    hits.push({ book, rank: hits.length + 1, relevance, semanticSimilarity });
    if (hits.length === 10) break;
  }
  return hits;
}

export function rankBooks(
  query: string, queryVector: Float32Array, vectors: Float32Array,
  index: SearchIndex, mode: SearchMode, keywordWeight = 1, language?: string, fullTextOnly = false,
): SearchHit[] {
  if (!query.trim()) throw new Error('Enter a question to search.');
  const dimensions = queryVector.length;
  if (dimensions < 1 || vectors.length !== index.books.length * dimensions) {
    throw new Error('The selected model and book vectors have different dimensions.');
  }

  const queryNorm = Math.sqrt(queryVector.reduce((sum, value) => sum + value ** 2, 0));
  const positions = eligiblePositions(query, index, language, fullTextOnly);
  const keywords = mode === 'hybrid' ? keywordScores(interpretQuery(query).embeddingText, index, positions) : new Map<number, number>();
  const strongestKeyword = Math.max(0, ...keywords.values());
  const bonusLimit = MAX_KEYWORD_BONUS * Math.min(2, Math.max(0, keywordWeight));
  return searchHits(positions.map(position => {
    let dotProduct = 0;
    let bookSquaredNorm = 0;
    const start = position * dimensions;
    for (let column = 0; column < dimensions; column += 1) {
      const value = vectors[start + column];
      dotProduct += queryVector[column] * value;
      bookSquaredNorm += value ** 2;
    }
    const denominator = queryNorm * Math.sqrt(bookSquaredNorm);
    const similarity = denominator ? Math.max(-1, Math.min(1, dotProduct / denominator)) : 0;
    const bonus = strongestKeyword ? bonusLimit * (keywords.get(position) ?? 0) / strongestKeyword : 0;
    return { position, relevance: similarity + bonus, semanticSimilarity: similarity };
  }), index);
}

export function rankKeywordBooks(query: string, index: SearchIndex, language?: string): SearchHit[] {
  if (!query.trim()) throw new Error('Enter a question to search.');
  const scores = keywordScores(interpretQuery(query).embeddingText, index, eligiblePositions(query, index, language));
  return searchHits([...scores].map(([position, relevance]) => ({
    position, relevance, semanticSimilarity: 0,
  })), index);
}

/** Keep display rounding separate from ranking. Keyword scores have no fixed scale. */
export function displayRelevance(score: number, keywordTopScore?: number): string {
  const scaled = keywordTopScore === undefined ? score : keywordTopScore > 0 ? score / keywordTopScore : 0;
  return (100 * Math.max(0, Math.min(1, scaled))).toFixed(1);
}

export function keepSemanticMatches(hits: SearchHit[], query: string, model: ModelKey): SearchHit[] {
  const intent = interpretQuery(query);
  if (model !== 'gte-base' || intent.exactPhrases.length || intent.visaClasses.length ||
      intent.usStudentVisa || intent.requestedModel) return hits;

  // Drop the weaker cluster only when the model shows a clear break after a result.
  const breakAt = hits.findIndex((hit, i) =>
    i > 0 && hits[i - 1].semanticSimilarity - hit.semanticSimilarity >= 0.08);
  return breakAt > 0 ? hits.slice(0, breakAt) : hits;
}
