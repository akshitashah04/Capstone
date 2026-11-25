const RATINGS = new Set(['useful', 'partial', 'not_useful', 'none_fit']);
const REASONS = new Set([
  'wrong_topic', 'too_advanced', 'too_basic', 'wrong_language',
  'inaccessible_link', 'poor_description', 'other',
]);
const MODELS = new Set(['e5-small', 'e5-base', 'gte-base', 'keyword-only']);
const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const EMAIL = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i;
const FIELDS = new Set([
  'submissionId', 'query', 'results', 'targetBookId', 'rating', 'reason',
  'model', 'mode', 'release', 'catalogSha256',
]);

export class ValidationError extends Error {
  constructor(message) {
    super(message);
    this.name = 'ValidationError';
  }
}

function requireCondition(condition, message) {
  if (!condition) throw new ValidationError(message);
}

export function validateSubmission(raw, { catalogSha256, knownBookIds }) {
  requireCondition(raw && typeof raw === 'object' && !Array.isArray(raw), 'Expected an object.');
  requireCondition(Object.keys(raw).every(key => FIELDS.has(key)), 'Unexpected field.');
  requireCondition(UUID_V4.test(raw.submissionId ?? ''), 'Invalid submission ID.');
  requireCondition(typeof raw.query === 'string', 'Question is required.');
  const query = raw.query.replace(/\s+/g, ' ').trim();
  requireCondition((query.length >= 3 || /\p{Script=Han}{2}/u.test(query)) && query.length <= 500 && !EMAIL.test(query),
    'Question is too short, too long, or contains an email address.');
  requireCondition(Array.isArray(raw.results) && raw.results.length >= 1 &&
    raw.results.length <= 10, 'Expected one to ten displayed books.');
  const seen = new Set();
  const results = raw.results.map((result, index) => {
    requireCondition(result && typeof result === 'object' && !Array.isArray(result) &&
      Object.keys(result).length === 2 && Object.hasOwn(result, 'bookId') &&
      Object.hasOwn(result, 'rank'), 'Invalid displayed book.');
    requireCondition(typeof result.bookId === 'string' && knownBookIds.has(result.bookId) &&
      !seen.has(result.bookId) && result.rank === index + 1, 'Invalid displayed book or position.');
    seen.add(result.bookId);
    return { bookId: result.bookId, rank: result.rank };
  });
  requireCondition(RATINGS.has(raw.rating), 'Invalid rating.');
  const targetBookId = raw.targetBookId ?? null;
  requireCondition(raw.rating === 'none_fit' ? targetBookId === null : seen.has(targetBookId),
    'Rating does not match a displayed book.');
  const reason = raw.reason ?? null;
  requireCondition(reason === null || REASONS.has(reason), 'Invalid reason.');
  requireCondition(MODELS.has(raw.model), 'Invalid model.');
  requireCondition(raw.model === 'keyword-only'
    ? raw.mode === 'keyword-only'
    : raw.mode === 'hybrid' || raw.mode === 'semantic', 'Invalid search mode.');
  requireCondition(typeof raw.release === 'string' &&
    /^[a-zA-Z0-9._-]{1,64}$/.test(raw.release), 'Invalid release.');
  requireCondition(raw.catalogSha256 === catalogSha256, 'Catalog version has changed.');
  return {
    submissionId: raw.submissionId.toLowerCase(), query, results, targetBookId,
    rating: raw.rating, reason, model: raw.model, mode: raw.mode,
    release: raw.release, catalogSha256,
  };
}

export function validateCorrection(raw) {
  requireCondition(raw && typeof raw === 'object' && !Array.isArray(raw), 'Expected an object.');
  requireCondition(Object.keys(raw).every(key => key === 'rating' || key === 'reason'),
    'Unexpected field.');
  requireCondition(RATINGS.has(raw.rating) && raw.rating !== 'none_fit', 'Invalid corrected rating.');
  const reason = raw.reason ?? null;
  requireCondition(reason === null || REASONS.has(reason), 'Invalid reason.');
  return { rating: raw.rating, reason };
}
