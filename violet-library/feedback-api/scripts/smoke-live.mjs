import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { CATALOG_SHA256 } from '../worker/known-books.js';

const endpoint = new URL('/v1/feedback', process.env.FEEDBACK_API_URL);
const origin = 'https://akshitashah04.github.io';
const bookId = 'gutenberg-13842';
const submissionId = randomUUID();

const preflight = await fetch(endpoint, {
  method: 'OPTIONS',
  headers: {
    Origin: origin,
    'Access-Control-Request-Method': 'POST',
    'Access-Control-Request-Headers': 'content-type',
  },
});
assert.equal(preflight.status, 204, 'The feedback preflight failed');
assert.equal(preflight.headers.get('Access-Control-Allow-Origin'), origin);

const saved = await fetch(endpoint, {
  method: 'POST',
  headers: { Origin: origin, 'Content-Type': 'application/json' },
  body: JSON.stringify({
    submissionId, query: 'Synthetic deployment check for a New York City history book',
    results: [{ bookId, rank: 1 }], targetBookId: bookId,
    rating: 'useful', model: 'gte-base', mode: 'semantic', language: 'en',
    release: 'deployment-smoke-test', catalogSha256: CATALOG_SHA256,
  }),
});
assert.equal(saved.status, 201, 'The synthetic feedback submission failed');
const { id, receipt } = await saved.json();
assert.equal(id, submissionId);
assert.ok(receipt, 'The feedback service did not return a deletion receipt');
const removed = await fetch(new URL(`/v1/feedback/${id}`, endpoint), {
  method: 'DELETE',
  headers: { Origin: origin, 'X-Feedback-Receipt': receipt },
});
assert.equal(removed.status, 204, 'The synthetic rating could not be deleted');
console.log('CORS, rating creation, and receipt-based deletion passed.');
