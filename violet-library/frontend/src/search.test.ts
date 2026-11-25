import { describe, expect, it } from 'vitest';
import { buildSearchIndex, displayRelevance, hasEligibleBooks, keepSemanticMatches, rankBooks, rankKeywordBooks, tokens } from './search';
import type { Book } from './types';
import { cleanDescription } from './book-text';
import base from '../public/data/catalog.json';
import supplementalRecords from '../public/data/multilingual.json';
import { appendVectors } from './passages';
import { interpretQuery } from './query-intent';
import { availableLanguages } from './languages';

const supplement = supplementalRecords as Book[];

function book(id: string, title: string, description: string): Book {
  return { id, title, description, authors: [], subjects: [], languages: ['en'], year: 2024,
    url: `https://example.org/${id}` };
}

describe('browser ranking', () => {
  it('keeps useful words from natural-language queries', () => {
    expect(tokens('I want a beginner book about AI for business')).toEqual(['beginner', 'ai', 'business']);
  });

  it('finds supplemental titles with Han bigrams and intact Devanagari words', () => {
    const index = buildSearchIndex([...base, ...supplement]);
    expect(tokens('निर्मला दहेज')).toEqual(['निर्मला', 'दहेज']);
    for (const [query, id] of [
      ['论语', 'gutenberg-23839'], ['道德經', 'gutenberg-7337'],
      ['ग्रामीण जीवन के उपन्यास', 'wikisource-hi-godan'], ['निर्मला दहेज', 'wikisource-hi-nirmala'],
    ]) {
      expect(rankKeywordBooks(query, index)[0]?.book.id).toBe(id);
    }
  });

  it('retrieves the additional titles across subjects and book languages', () => {
    const index = buildSearchIndex([...base, ...supplement]);
    for (const [query, language, id] of [
      ['introduction to python programming', 'en', 'openstax-introduction-python-programming'],
      ['principles of finance', 'en', 'openstax-principles-finance'],
      ['introduction to philosophy', 'en', 'openstax-introduction-philosophy'],
      ['introducción a la estadística', 'es', 'openstax-intro-estadistica-es'],
      ['天工开物', 'zh', 'gutenberg-25273'],
      ['प्रेमाश्रम', 'hi', 'wikisource-hi-premashram'],
    ]) {
      expect(rankKeywordBooks(query, index, language).slice(0, 5).map(hit => hit.book.id)).toContain(id);
    }
  });

  it('ranks appended vectors against the matching supplemental book rows', () => {
    const index = buildSearchIndex([book('base', 'Ocean', 'Marine life'), supplement[4]]);
    const vectors = appendVectors(new Float32Array([1, 0]), new Float32Array([0, 1]));
    expect(rankBooks('गोदान', new Float32Array([0, 1]), vectors, index, 'semantic')[0].book.id)
      .toBe('wikisource-hi-godan');
  });

  it('ranks by meaning even when a weaker book contains the exact query terms', () => {
    const books = [book('a', 'Entry-level machine learning', 'Case studies for company leaders'),
      book('b', 'Business AI engineering', 'Technical algorithms and programming')];
    const index = buildSearchIndex(books);
    const vectors = new Float32Array([1, 0, 0.8, 0.6]);
    const query = new Float32Array([1, 0]);
    const meaning = rankBooks('Business AI', query, vectors, index, 'semantic');
    const hybrid = rankBooks('Business AI', query, vectors, index, 'hybrid', 2);
    expect(meaning[0].book.id).toBe('a');
    expect(hybrid[0].book.id).toBe('a');
    expect(hybrid[1].relevance).toBeCloseTo(0.85);
    expect(rankKeywordBooks('Business AI', index)[0].book.id).toBe('b');
  });

  it('computes cosine similarity regardless of vector norm and formats relevance by mode', () => {
    const index = buildSearchIndex([book('a', 'Aligned', 'Description'), book('b', 'Partial', 'Description')]);
    const hits = rankBooks('question', new Float32Array([2, 0]),
      new Float32Array([0.5, 0, 3, 4]), index, 'semantic');
    expect(hits.map(hit => displayRelevance(hit.relevance))).toEqual(['100.0', '60.0']);
    expect(displayRelevance(-0.1)).toBe('0.0');
    expect(displayRelevance(1.025)).toBe('100.0');
    expect(displayRelevance(4, 5)).toBe('80.0');
  });

  it('requires evidence for a specific visa even when broad migration has higher cosine similarity', () => {
    const index = buildSearchIndex([
      book('migration', 'Innovative Concepts for Alternative Migration Policies', 'Immigration research and policy'),
      book('tourist', 'Visitor visa handbook', 'B-2 visa rules'),
      book('race', 'F1 racing', 'Racing strategies and the status of the championship'),
      book('student', 'International academic study', 'A guide to U.S. student visas for academic study'),
    ]);
    const query = 'looking for F‑1 visa related books';
    expect(interpretQuery(query).embeddingText).toContain('U.S. student visa for academic study');
    const queryVector = new Float32Array([1, 0]);
    const vectors = new Float32Array([1, 0, 1, 0, 1, 0, 0.6, 0.8]);
    for (const mode of ['semantic', 'hybrid'] as const) {
      expect(rankBooks(query, queryVector, vectors, index, mode).map(hit => hit.book.id)).toEqual(['student']);
    }
    expect(rankKeywordBooks(query, index).map(hit => hit.book.id)).toEqual(['student']);
    expect(hasEligibleBooks('books about "housing policy"', index)).toBe(false);
    expect(rankBooks('books about "migration policies"', queryVector, vectors, index, 'semantic')
      .map(hit => hit.book.id)).toEqual(['migration']);
    expect(rankBooks('F1 racing status', queryVector, vectors, index, 'semantic').length).toBe(4);
    expect(hasEligibleBooks('Can you find books on F-2 visas?', index)).toBe(false);
    expect(interpretQuery('美国F-1签证相关书籍').visaClasses).toEqual(['f1']);
  });

  it('finds the curated full-text entries for the original F-1 visa query', () => {
    const books = [...base, ...supplement];
    const index = buildSearchIndex(books);
    const query = 'looking for f-1 visa related books';
    expect(hasEligibleBooks(query, buildSearchIndex(base), 'en')).toBe(false);
    const vectors = new Float32Array(books.length * 2);
    books.forEach((_, i) => {
      // Give the broad catalog higher scores to catch a regression in the intent check.
      vectors[i * 2] = i < base.length ? 1 : 0.6;
      vectors[i * 2 + 1] = i < base.length ? 0 : 0.8;
    });
    const expected = [
      'educationusa-undergraduate-study', 'kit-johnson-open-immigration-casebook-4',
      'unlv-international-student-handbook', 'uc-merced-new-international-student-handbook',
      'newman-f1-international-student-handbook', 'cgc-f1-student-handbook',
    ];
    for (const text of [query, 'a book about the U.S. student visa']) {
      const hits = rankBooks(text, new Float32Array([1, 0]), vectors, index, 'semantic', 1, 'en');
      expect(hits.map(hit => hit.book.id)).toEqual(expected);
    }
    expect(hasEligibleBooks(query, index, 'hi')).toBe(false);
  });

  it('withholds generic books when the requested product manual is missing', () => {
    const index = buildSearchIndex([
      book('water', 'Water Treatment Engineering', 'A reference on pumps and water supplies'),
      book('toyota', 'Toyota Corolla Workshop Manual', 'Toyota Corolla repair and parts'),
    ]);
    const query = 'I need a repair manual for the 2017 Toyota Corolla water pump.';
    expect(rankBooks(query, new Float32Array([1, 0]), new Float32Array([1, 0, 0.6, 0.8]),
      index, 'semantic').map(hit => hit.book.id)).toEqual(['toyota']);
    expect(hasEligibleBooks(query, buildSearchIndex([index.books[0]]))).toBe(false);
  });

  it('drops the weaker GTE cluster while keeping direct matches on constrained queries', () => {
    const index = buildSearchIndex([
      book('a', 'First', 'A description'), book('b', 'Second', 'A different description'),
      book('c', 'Third', 'Another description'),
    ]);
    const hits = rankBooks('cars', new Float32Array([1, 0]),
      new Float32Array([1, 0, 0.98, 0.2, 0.6, 0.8]), index, 'semantic');
    expect(keepSemanticMatches(hits, 'cars', 'gte-base').map(hit => hit.book.id)).toEqual(['a', 'b']);
    expect(keepSemanticMatches(hits, 'cars', 'e5-small')).toEqual(hits);
    expect(keepSemanticMatches(hits, 'F-1 visa', 'gte-base')).toEqual(hits);
  });

  it('uses key terms to resolve a close semantic match', () => {
    const index = buildSearchIndex([book('a', 'Classical ethics', 'Teachings and sayings'),
      book('b', 'The Analects', 'Early Chinese philosophy')]);
    const vectors = new Float32Array([1, 0, 0.99, 0.14]);
    const query = new Float32Array([1, 0]);
    expect(rankBooks('The Analects', query, vectors, index, 'semantic')[0].book.id).toBe('a');
    expect(rankBooks('The Analects', query, vectors, index, 'hybrid')[0].book.id).toBe('b');
  });

  it('filters the full catalog before ranking, including multilingual and lower-scoring books', () => {
    const books = Array.from({ length: 501 }, (_, i) => book(String(i), 'Rural fiction', 'Farming'));
    books.push({ ...book('hi', 'गोदान', 'Struggles of farmers'), languages: ['hin', 'eng'] });
    const index = buildSearchIndex(books);
    const vectors = new Float32Array([...Array(501).fill(1), 0.5]);
    expect(rankBooks('Farming', new Float32Array([1]), vectors, index, 'semantic', 1, 'hi')
      .map(hit => hit.book.id)).toEqual(['hi']);
    expect(rankKeywordBooks('Farming farmers', index, 'hi').map(hit => hit.book.id)).toEqual(['hi']);
    expect(rankKeywordBooks('Farming', index, 'zh')).toEqual([]);
    expect(availableLanguages([...base, ...supplement])).toEqual(expect.arrayContaining(['en', 'zh', 'hi']));
  });

  it('shows only one copy of a repeated title and rejects mismatched vectors', () => {
    const books = [book('a', 'Repeated title', 'A useful first edition.'),
      book('b', 'Repeated title', 'A useful second edition.'),
      book('c', 'Different title', 'Another useful text.')];
    const index = buildSearchIndex(books);
    const hits = rankBooks('repeated title', new Float32Array([1, 0]),
      new Float32Array([1, 0, 0.9, 0.1, 0, 1]), index, 'semantic');
    expect(hits.map(hit => hit.book.id)).toEqual(['a', 'c']);
    expect(() => rankBooks('query', new Float32Array([1]), new Float32Array(2), index,
      'semantic')).toThrow('different dimensions');
  });

  it('offers a clearly separate keyword preview when a model cannot load', () => {
    const index = buildSearchIndex([book('a', 'Ocean science', 'marine biology'),
      book('b', 'AI for business', 'A guide for managers')]);
    expect(rankKeywordBooks('I study business and need AI without coding', index)
      .map(hit => hit.book.id)).toEqual(['b']);
  });

  it('removes source placeholder descriptions from displayed recommendations', () => {
    expect(cleanDescription('  undefined  ')).toBe('');
    expect(cleanDescription('A real summary')).toBe('A real summary');
    const books = [book('a', 'Chinese Romanization Self-Study Guide', 'undefined'),
      book('b', 'Chinese history', 'A book about the history of China.')];
    const index = buildSearchIndex(books);
    const semantic = rankBooks('chinese culture', new Float32Array([1, 0]),
      new Float32Array([1, 0, 0.9, 0.1]), index, 'semantic');
    expect(semantic.map(hit => hit.book.id)).toEqual(['b']);
    expect(rankKeywordBooks('chinese culture', index).map(hit => hit.book.id)).toEqual(['b']);
  });
});
