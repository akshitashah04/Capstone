import { readFile, writeFile } from 'node:fs/promises';
import { CATALOG_BOOK_IDS } from '../worker/known-books.js';

const [source, destination] = process.argv.slice(2);
if (!source || !destination) {
  throw new Error('Usage: node prepare-ranking-review.mjs PRIVATE_EXPORT.json PRIVATE_REVIEW.json');
}

const exported = JSON.parse(await readFile(source, 'utf8'));
const rows = Array.isArray(exported) && exported.length === 1 && Array.isArray(exported[0].results)
  ? exported[0].results : exported;
if (!Array.isArray(rows)) throw new Error('Expected one query result or an array of feedback rows.');

const groups = new Map();
for (const row of rows) {
  const bookIds = CATALOG_BOOK_IDS.get(row.catalog_sha);
  if (!bookIds || !['hybrid', 'semantic', 'keyword-only'].includes(row.search_mode)) continue;
  const query = row.query_text.normalize('NFKC').replace(/\s+/g, ' ').trim();
  const language = row.book_language ?? null;
  const key = JSON.stringify([query.toLowerCase(), language]);
  const displayed = JSON.parse(row.results_json);
  if (!key || !Array.isArray(displayed) || displayed.length < 1 || displayed.length > 10 ||
      displayed.some((item, index) => !bookIds.has(item.bookId) || item.rank !== index + 1)) {
    throw new Error('Invalid feedback result list in export.');
  }

  if (!groups.has(key)) {
    groups.set(key, { query, language, shown: new Set(), signals: new Map(), listsWithoutFit: 0 });
  }
  const group = groups.get(key);
  for (const { bookId } of displayed) group.shown.add(bookId);
  if (row.rating === 'none_fit') {
    group.listsWithoutFit += 1;
    continue;
  }
  if (!['useful', 'partial', 'not_useful'].includes(row.rating) ||
      !displayed.some(item => item.bookId === row.target_book_id)) {
    throw new Error('Invalid per-book rating in export.');
  }
  const bookId = row.target_book_id;
  if (!group.signals.has(bookId)) group.signals.set(bookId, []);
  group.signals.get(bookId).push({
    rating: row.rating, reason: row.reason, rank: displayed.find(item => item.bookId === bookId).rank,
    model: row.model_key, mode: row.search_mode, release: row.release_id, catalog: row.catalog_sha,
  });
}

const review = [...groups.values()].map(({ query, language, shown, signals, listsWithoutFit }) => ({
  query, language,
  listsWithoutFit,
  books: [...shown].map(bookId => ({ bookId, visitorSignals: signals.get(bookId) ?? [] })),
}));
await writeFile(destination, JSON.stringify(review, null, 2) + '\n', { mode: 0o600, flag: 'wx' });
console.log(`Prepared ${review.length} distinct queries for private review.`);
