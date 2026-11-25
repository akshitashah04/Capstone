import test from 'node:test';
import assert from 'node:assert/strict';
import { validateSubmission } from '../worker/validation.js';

const bookA = '11111111-1111-4111-8111-111111111111';
const bookB = '22222222-2222-4222-8222-222222222222';
const catalogSha256 = 'a'.repeat(64);
const context = { catalogSha256, knownBookIds: new Set([bookA, bookB]) };

function submission(overrides = {}) {
  return {
    submissionId: '33333333-3333-4333-8333-333333333333',
    query: 'I want an introduction to Chinese culture',
    results: [{ bookId: bookA, rank: 1 }, { bookId: bookB, rank: 2 }],
    targetBookId: bookA,
    rating: 'useful',
    reason: null,
    model: 'e5-small',
    mode: 'hybrid',
    release: 'a8fe74b',
    catalogSha256,
    ...overrides,
  };
}

test('accepts a contextual per-book rating and trims the question', () => {
  const result = validateSubmission(submission({ query: '  Chinese culture for beginners  ' }), context);
  assert.equal(result.query, 'Chinese culture for beginners');
  assert.equal(result.results.length, 2);
  assert.equal(result.targetBookId, bookA);
});

test('accepts a whole-list none-fit rating without inventing a book target', () => {
  const result = validateSubmission(submission({ targetBookId: null, rating: 'none_fit' }), context);
  assert.equal(result.targetBookId, null);
});

test('rejects unknown books, duplicates, gaps, and mismatched targets', () => {
  assert.throws(() => validateSubmission(submission({ targetBookId: 'unknown' }), context));
  assert.throws(() => validateSubmission(submission({ results: [{ bookId: bookA, rank: 2 }] }), context));
  assert.throws(() => validateSubmission(submission({ results: [
    { bookId: bookA, rank: 1 }, { bookId: bookA, rank: 2 },
  ] }), context));
});

test('rejects stale catalogs, invalid reasons, and embedded email addresses', () => {
  assert.throws(() => validateSubmission(submission({ catalogSha256: 'b'.repeat(64) }), context));
  assert.throws(() => validateSubmission(submission({ reason: 'excellent' }), context));
  assert.throws(() => validateSubmission(submission({ query: 'Email me at student@nyu.edu' }), context));
});

test('rejects unsupported modes and oversized or malformed questions', () => {
  assert.throws(() => validateSubmission(submission({ mode: 'google' }), context));
  assert.throws(() => validateSubmission(submission({ query: 'x'.repeat(501) }), context));
  assert.throws(() => validateSubmission(submission({ submissionId: 'not-a-uuid' }), context));
});
