import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import worker from '../worker/index.js';
import { CATALOG_BOOK_IDS, CATALOG_SHA256, KNOWN_BOOK_IDS } from '../worker/known-books.js';

const origin = 'https://akshitashah04.github.io';
const bookId = KNOWN_BOOK_IDS.values().next().value;

function database() {
  const db = new DatabaseSync(':memory:');
  db.exec(`
    CREATE TABLE feedback (id TEXT PRIMARY KEY, payload_digest TEXT NOT NULL,
      query_text TEXT NOT NULL, results_json TEXT NOT NULL, target_book_id TEXT,
      rating TEXT NOT NULL, reason TEXT, model_key TEXT NOT NULL, search_mode TEXT NOT NULL,
      release_id TEXT NOT NULL, catalog_sha TEXT NOT NULL, ip_hash TEXT NOT NULL,
      created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL, book_language TEXT);
    CREATE TABLE feedback_events (id INTEGER PRIMARY KEY AUTOINCREMENT,
      feedback_id TEXT NOT NULL, action TEXT NOT NULL, rating TEXT, reason TEXT,
      created_at INTEGER NOT NULL);
    CREATE TABLE rate_counters (key TEXT PRIMARY KEY, count INTEGER NOT NULL,
      updated_at INTEGER NOT NULL);
  `);
  const bound = (sql, args) => ({
    sql, args,
    run: async () => ({ meta: db.prepare(sql).run(...args) }),
    first: async () => db.prepare(sql).get(...args) ?? null,
  });
  return {
    raw: db,
    prepare: sql => ({ bind: (...args) => bound(sql, args) }),
    batch: async statements => {
      db.exec('BEGIN');
      try {
        const results = [];
        for (const statement of statements) results.push(await statement.run());
        db.exec('COMMIT');
        return results;
      } catch (error) { db.exec('ROLLBACK'); throw error; }
    },
  };
}

function payload(id = '33333333-3333-4333-8333-333333333333') {
  return {
    submissionId: id,
    query: 'I need a beginner book about social research',
    results: [{ bookId, rank: 1 }], targetBookId: bookId,
    rating: 'useful', reason: null, model: 'e5-small', mode: 'hybrid',
    release: 'a8fe74b', catalogSha256: CATALOG_SHA256,
  };
}

function request(method, path, body, headers = {}) {
  return new Request(`https://feedback.example${path}`, {
    method,
    headers: { Origin: origin, 'CF-Connecting-IP': '203.0.113.10',
      'Content-Type': 'application/json', ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

function environment(limit = 20) {
  const DB = database();
  return { DB, RATE_PEPPER: 'unit-test-secret', DAILY_LIMIT: String(limit) };
}

test('creates, deduplicates, corrects, and deletes one private rating', async () => {
  const env = environment();
  const first = await worker.fetch(request('POST', '/v1/feedback', payload()), env);
  assert.equal(first.status, 201);
  const saved = await first.json();
  assert.equal(saved.id, payload().submissionId);
  assert.ok(saved.receipt.length > 20);
  assert.equal(env.DB.raw.prepare('SELECT COUNT(*) AS n FROM feedback').get().n, 1);
  const retry = await worker.fetch(request('POST', '/v1/feedback', payload()), env);
  assert.equal(retry.status, 200);
  assert.deepEqual(await retry.json(), saved);
  const changed = await worker.fetch(request('PUT', `/v1/feedback/${saved.id}`,
    { rating: 'not_useful', reason: 'wrong_topic' },
    { 'X-Feedback-Receipt': saved.receipt }), env);
  assert.equal(changed.status, 200);
  assert.equal(env.DB.raw.prepare('SELECT rating FROM feedback').get().rating, 'not_useful');
  assert.equal(env.DB.raw.prepare('SELECT COUNT(*) AS n FROM feedback_events').get().n, 2);
  const removed = await worker.fetch(request('DELETE', `/v1/feedback/${saved.id}`, undefined,
    { 'X-Feedback-Receipt': saved.receipt }), env);
  assert.equal(removed.status, 204);
  assert.equal(env.DB.raw.prepare('SELECT COUNT(*) AS n FROM feedback').get().n, 0);
  assert.equal(env.DB.raw.prepare('SELECT COUNT(*) AS n FROM feedback_events').get().n, 0);
});

test('accepts short Chinese queries and keeps legacy submissions tied to legacy IDs', async () => {
  const env = environment();
  const legacySha = [...CATALOG_BOOK_IDS.keys()].find(sha => sha !== CATALOG_SHA256);
  const newBook = 'gutenberg-23839';
  const chinese = {
    ...payload(), query: '论语', language: 'zh', results: [{ bookId: newBook, rank: 1 }], targetBookId: newBook,
  };
  const mismatched = await worker.fetch(request('POST', '/v1/feedback',
    { ...chinese, catalogSha256: legacySha }), env);
  assert.equal(mismatched.status, 400);
  const combined = await worker.fetch(request('POST', '/v1/feedback', chinese), env);
  assert.equal(combined.status, 201);
  assert.equal(env.DB.raw.prepare('SELECT book_language FROM feedback').get().book_language, 'zh');
  const legacy = await worker.fetch(request('POST', '/v1/feedback', {
    ...payload('44444444-4444-4444-8444-444444444444'), catalogSha256: legacySha,
  }), env);
  assert.equal(legacy.status, 201);
});

test('rejects other origins, malformed ratings, and unauthorized edits', async () => {
  const env = environment();
  const wrongOrigin = await worker.fetch(request('POST', '/v1/feedback', payload(),
    { Origin: 'https://attacker.example' }), env);
  assert.equal(wrongOrigin.status, 403);
  const bad = await worker.fetch(request('POST', '/v1/feedback',
    { ...payload(), rating: 'invalid' }), env);
  assert.equal(bad.status, 400);
  const saved = await (await worker.fetch(request('POST', '/v1/feedback', payload()), env)).json();
  const edit = await worker.fetch(request('PUT', `/v1/feedback/${saved.id}`,
    { rating: 'not_useful' }, { 'X-Feedback-Receipt': 'wrong' }), env);
  assert.equal(edit.status, 403);
});

test('limits new submissions without stopping health or search', async () => {
  const env = environment(1);
  const first = await worker.fetch(request('POST', '/v1/feedback', payload()), env);
  assert.equal(first.status, 201);
  const second = await worker.fetch(request('POST', '/v1/feedback',
    payload('44444444-4444-4444-8444-444444444444')), env);
  assert.equal(second.status, 429);
  const health = await worker.fetch(new Request('https://feedback.example/health'), env);
  assert.equal(health.status, 200);
});
