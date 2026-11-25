import { CATALOG_BOOK_IDS } from './known-books.js';
import { validateSubmission, validateCorrection, ValidationError } from './validation.js';

const ORIGIN = 'https://akshitashah04.github.io';
const encoder = new TextEncoder();

function reply(body, status, origin = null) {
  const headers = new Headers({ 'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Vary': 'Origin' });
  if (origin === ORIGIN) headers.set('Access-Control-Allow-Origin', ORIGIN);
  return new Response(body === null ? null : JSON.stringify(body), { status, headers });
}

const fail = (status, code, origin = null) => reply({ error: code }, status, origin);

async function readJson(request) {
  if (!request.headers.get('Content-Type')?.toLowerCase().startsWith('application/json')) {
    throw new ValidationError('JSON content type required.');
  }
  if (Number(request.headers.get('Content-Length') ?? 0) > 4096) {
    throw new ValidationError('Request is too large.');
  }
  const reader = request.body?.getReader();
  if (!reader) throw new ValidationError('Request body is required.');
  const chunks = []; let size = 0;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > 4096) { await reader.cancel(); throw new ValidationError('Request is too large.'); }
    chunks.push(value);
  }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  try { return JSON.parse(new TextDecoder().decode(bytes)); }
  catch { throw new ValidationError('Invalid JSON.'); }
}

async function hash(value, secret = null) {
  const data = encoder.encode(value);
  const digest = secret === null
    ? await crypto.subtle.digest('SHA-256', data)
    : await crypto.subtle.sign('HMAC', await crypto.subtle.importKey('raw',
      encoder.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']), data);
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
}

function sameSecret(expected, actual) {
  if (typeof actual !== 'string' || actual.length !== expected.length) return false;
  let difference = 0;
  for (let i = 0; i < expected.length; i += 1) difference |= expected.charCodeAt(i) ^ actual.charCodeAt(i);
  return difference === 0;
}

async function submit(request, env, origin) {
  const ip = request.headers.get('CF-Connecting-IP');
  if (!ip) return fail(503, 'visitor_context_unavailable', origin);
  const raw = await readJson(request);
  const catalogSha256 = raw?.catalogSha256;
  const knownBookIds = CATALOG_BOOK_IDS.get(catalogSha256);
  if (!knownBookIds) throw new ValidationError('Catalog version has changed.');
  const item = validateSubmission(raw, { catalogSha256, knownBookIds });
  const payloadDigest = await hash(JSON.stringify(item));
  const receipt = await hash(`receipt:${item.submissionId}`, env.RATE_PEPPER);
  const existing = await env.DB.prepare('SELECT payload_digest FROM feedback WHERE id = ?')
    .bind(item.submissionId).first();
  if (existing) return existing.payload_digest === payloadDigest
    ? reply({ id: item.submissionId, receipt }, 200, origin)
    : fail(409, 'submission_id_conflict', origin);

  const now = Date.now();
  const day = new Date(now).toISOString().slice(0, 10);
  const rateKey = await hash(`rate:${day}:${ip}`, env.RATE_PEPPER);
  const configuredLimit = Number(env.DAILY_LIMIT);
  const limit = Number.isInteger(configuredLimit) && configuredLimit > 0
    ? Math.min(configuredLimit, 100) : 20;
  const rate = await env.DB.prepare('INSERT INTO rate_counters (key, count, updated_at) VALUES (?, 1, ?) '
    + 'ON CONFLICT(key) DO UPDATE SET count = count + 1, updated_at = excluded.updated_at '
    + 'WHERE count < ?').bind(rateKey, now, limit).run();
  if (rate.meta?.changes !== 1) return fail(429, 'daily_feedback_limit', origin);
  await env.DB.batch([
    env.DB.prepare('INSERT INTO feedback (id, payload_digest, query_text, results_json, '
      + 'target_book_id, rating, reason, model_key, search_mode, release_id, catalog_sha, '
      + 'ip_hash, created_at, updated_at, book_language) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)')
      .bind(item.submissionId, payloadDigest, item.query, JSON.stringify(item.results),
        item.targetBookId, item.rating, item.reason, item.model, item.mode,
        item.release, item.catalogSha256, rateKey, now, now, item.language ?? null),
    env.DB.prepare('INSERT INTO feedback_events (feedback_id, action, rating, reason, created_at) '
      + 'VALUES (?, ?, ?, ?, ?)').bind(item.submissionId, 'created', item.rating, item.reason, now),
  ]);
  return reply({ id: item.submissionId, receipt }, 201, origin);
}

async function change(request, env, origin, id) {
  const receipt = await hash(`receipt:${id}`, env.RATE_PEPPER);
  if (!sameSecret(receipt, request.headers.get('X-Feedback-Receipt'))) {
    return fail(403, 'invalid_receipt', origin);
  }
  const previous = await env.DB.prepare('SELECT id, target_book_id FROM feedback WHERE id = ?').bind(id).first();
  if (!previous) return fail(404, 'not_found', origin);
  if (request.method === 'DELETE') {
    await env.DB.batch([
      env.DB.prepare('DELETE FROM feedback_events WHERE feedback_id = ?').bind(id),
      env.DB.prepare('DELETE FROM feedback WHERE id = ?').bind(id),
    ]);
    return reply(null, 204, origin);
  }
  if (previous.target_book_id === null) return fail(400, 'whole_list_rating_can_only_be_deleted', origin);
  const corrected = validateCorrection(await readJson(request));
  const now = Date.now();
  await env.DB.batch([
    env.DB.prepare('UPDATE feedback SET rating = ?, reason = ?, updated_at = ? WHERE id = ?')
      .bind(corrected.rating, corrected.reason, now, id),
    env.DB.prepare('INSERT INTO feedback_events (feedback_id, action, rating, reason, created_at) '
      + 'VALUES (?, ?, ?, ?, ?)').bind(id, 'corrected', corrected.rating, corrected.reason, now),
  ]);
  return reply({ id, rating: corrected.rating, reason: corrected.reason }, 200, origin);
}

async function cleanExpired(env) {
  const cutoff = Date.now() - 90 * 86400000;
  await env.DB.batch([
    env.DB.prepare('DELETE FROM feedback_events WHERE feedback_id IN '
      + '(SELECT id FROM feedback WHERE created_at < ?)').bind(cutoff),
    env.DB.prepare('DELETE FROM feedback WHERE created_at < ?').bind(cutoff),
    env.DB.prepare('DELETE FROM rate_counters WHERE updated_at < ?').bind(Date.now() - 2 * 86400000),
  ]);
}

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    const origin = request.headers.get('Origin');
    if (path === '/health' && request.method === 'GET') {
      if (!env.DB) return fail(503, 'storage_unavailable');
      try { await cleanExpired(env); return reply({ status: 'ok' }, 200); }
      catch { return fail(503, 'storage_unavailable'); }
    }
    if (path !== '/v1/feedback' && !/^\/v1\/feedback\/[0-9a-f-]{36}$/i.test(path)) {
      return fail(404, 'not_found');
    }
    if (origin !== ORIGIN) return fail(403, 'origin_not_allowed');
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: {
      'Access-Control-Allow-Origin': ORIGIN,
      'Access-Control-Allow-Methods': 'POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, X-Feedback-Receipt',
      'Access-Control-Max-Age': '600', 'Vary': 'Origin',
    } });
    if (!env.DB || !env.RATE_PEPPER) return fail(503, 'feedback_unavailable', origin);
    try {
      if (path === '/v1/feedback' && request.method === 'POST') return await submit(request, env, origin);
      const id = path.slice('/v1/feedback/'.length);
      if (id && (request.method === 'PUT' || request.method === 'DELETE')) {
        return await change(request, env, origin, id);
      }
      return fail(405, 'method_not_allowed', origin);
    } catch (caught) {
      if (caught instanceof ValidationError) return fail(400, caught.message, origin);
      return fail(503, 'feedback_unavailable', origin);
    }
  },
};
