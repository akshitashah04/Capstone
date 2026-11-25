import { describe, expect, it } from 'vitest';
import { buildSubmission } from './client';

describe('feedback submission', () => {
  const context = {
    query: 'I need an approachable introduction to AI for business',
    model: 'gte-base' as const,
    mode: 'hybrid' as const,
    release: 'test-release',
    catalogSha256: 'abc123',
    shownBooks: [
      { bookId: 'first', rank: 1 },
      { bookId: 'second', rank: 2 },
    ],
  };

  it('records the exact displayed order and chosen book', () => {
    const item = buildSubmission(context, 'second', 'partial', 'too_advanced');
    expect(item).toMatchObject({
      query: context.query,
      model: 'gte-base', mode: 'hybrid',
      results: context.shownBooks,
      targetBookId: 'second', rating: 'partial', reason: 'too_advanced',
    });
    expect(item).not.toHaveProperty('language');
    expect(item.submissionId).toMatch(/^[0-9a-f-]{36}$/);
  });

  it('records a whole-list rejection without a book target', () => {
    expect(buildSubmission({ ...context, language: 'hi' }, null, 'none_fit', null)).toMatchObject({
      targetBookId: null, rating: 'none_fit', language: 'hi', results: context.shownBooks,
    });
  });

  it('rejects a book that was not displayed', () => {
    expect(() => buildSubmission(context, 'hidden', 'useful', null)).toThrow('displayed');
  });
});
