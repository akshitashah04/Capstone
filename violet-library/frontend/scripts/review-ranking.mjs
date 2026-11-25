import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { createServer } from 'vite';

const WEIGHTS = [0, 0.5, 1, 1.5, 2];
const BASELINE = 0;
const RANKER = 'semantic-cosine-v1';
const MODEL = 'gte-base';
const root = new URL('../public/data/', import.meta.url);
const digest = data => createHash('sha256').update(data).digest('hex');

const [command, source, destination] = process.argv.slice(2);
if (!['pool', 'score'].includes(command) || !source || !destination) {
  throw new Error('Usage: node review-ranking.mjs <pool|score> PRIVATE_INPUT.json PRIVATE_OUTPUT.json');
}

const input = JSON.parse(await readFile(source, 'utf8'));
const manifest = JSON.parse(await readFile(new URL('manifest.json', root), 'utf8'));
const catalog = manifest.catalog_sha256 ?? manifest.files['catalog.json'].sha256;

function validateQueries(queries) {
  const seen = new Set();
  if (!Array.isArray(queries)) throw new Error('Expected an array of queries.');
  for (const { id, query, split, language } of queries) {
    if (typeof id !== 'string' || !id.trim() || typeof query !== 'string' || !query.trim() ||
        !['development', 'holdout'].includes(split) ||
        (language != null && (typeof language !== 'string' || !/^[a-z]{2,3}$/.test(language)))) {
      throw new Error('Each query needs an ID, text, and development or holdout split.');
    }
    const key = query.normalize('NFKC').trim().replace(/\s+/g, ' ').toLowerCase();
    if (seen.has('text:' + key) || seen.has('id:' + id)) {
      throw new Error('Query IDs and normalized texts must be unique across splits.');
    }
    seen.add('text:' + key);
    seen.add('id:' + id);
  }
  if (!queries.some(row => row.split === 'development') ||
      !queries.some(row => row.split === 'holdout')) {
    throw new Error('Both development and holdout queries are required.');
  }
}

async function checkedFile(name) {
  const bytes = await readFile(new URL(name, root));
  const expected = manifest.files[name];
  if (bytes.length !== expected.bytes || digest(bytes) !== expected.sha256) {
    throw new Error(`${name} failed integrity checks.`);
  }
  return bytes;
}

async function generatePool(queries) {
  validateQueries(queries);
  const vite = await createServer({
    configFile: false,
    root: new URL('..', import.meta.url).pathname,
    server: { middlewareMode: true, ws: false },
  });
  try {
    // Vite loads the same TypeScript functions and ranker used by the browser.
    const files = ['catalog', 'embedding', 'passages', 'search', 'book-text', 'languages'];
    const [codec, embedding, passages, search, bookText, languages] = await Promise.all(
      files.map(name => vite.ssrLoadModule(new URL(`../src/${name}.ts`, import.meta.url).pathname)),
    );
    const [rawBase, rawSupplement, rawVectors] = await Promise.all([
      checkedFile('catalog.json'),
      manifest.files['multilingual.json'] ? checkedFile('multilingual.json') : Buffer.from('[]'),
      checkedFile(`${MODEL}.f16`),
    ]);
    const base = JSON.parse(rawBase);
    const supplement = JSON.parse(rawSupplement);
    const books = [...base, ...supplement].map(book => ({
      ...book, description: bookText.cleanDescription(book.description),
    }));
    const index = search.buildSearchIndex(books);
    const supportedLanguages = new Set(languages.availableLanguages(books));
    const { env } = await import('@huggingface/transformers');
    env.cacheDir = process.env.LIBRARIES_MODEL_CACHE ?? '/tmp/libraries-model-cache';
    const encoder = await embedding.loadEncoder(MODEL);
    try {
      const baseVectors = codec.decodeHalfVectors(
        rawVectors.buffer.slice(rawVectors.byteOffset, rawVectors.byteOffset + rawVectors.byteLength),
      );
      const supplementalVectors = await encoder.encode(
        books.slice(base.length).map(passages.passageText), 'passage',
      );
      const vectors = passages.appendVectors(baseVectors, supplementalVectors);
      const rows = [];
      for (const { id, query, split, language } of queries) {
        if (language && !supportedLanguages.has(language)) {
          throw new Error(`Unsupported book language for ${id}.`);
        }
        const vector = await encoder.encode([query], 'query');
        const ranks = Object.fromEntries(WEIGHTS.map(weight => [
          weight, search.rankBooks(query, vector, vectors, index, weight === BASELINE ? 'semantic' : 'hybrid', weight, language)
            .slice(0, 5).map(hit => hit.book.id),
        ]));
        // A blinded review copy can use this sorted union without the ranks.
        const bookIds = [...new Set(Object.values(ranks).flat())].sort();
        rows.push({
          id, query, split, language: language ?? null, ranks,
          grades: Object.fromEntries(bookIds.map(bookId => [bookId, null])),
        });
      }
      return { catalog, model: MODEL, ranker: RANKER, weights: WEIGHTS, queries: rows };
    } finally {
      await encoder.dispose();
    }
  } finally {
    await vite.close();
  }
}

function metrics(rows, weight) {
  const dcg = grades => grades.reduce(
    (sum, grade, i) => sum + (2 ** grade - 1) / Math.log2(i + 2), 0,
  );
  let clearFits = 0;
  let normalizedGain = 0;
  for (const { grades, ranks } of rows) {
    const ordered = ranks[weight].map(bookId => grades[bookId]);
    if (ordered.includes(2)) clearFits += 1;
    const ideal = dcg(Object.values(grades).sort((a, b) => b - a).slice(0, 5));
    if (ideal) normalizedGain += dcg(ordered) / ideal;
  }
  return { queries: rows.length, clearFits, ndcgAt5: normalizedGain / rows.length };
}

function scorePool(pool) {
  if (pool.catalog !== catalog || pool.model !== MODEL || pool.ranker !== RANKER ||
      JSON.stringify(pool.weights) !== JSON.stringify(WEIGHTS)) {
    throw new Error('Pool does not match this catalog, model, and ranking grid.');
  }
  validateQueries(pool.queries);
  for (const { id, grades, ranks } of pool.queries) {
    const lists = WEIGHTS.map(weight => ranks[weight]);
    if (lists.some(list => !Array.isArray(list) || list.length < 1 || list.length > 5 ||
        new Set(list).size !== list.length)) {
      throw new Error(`Invalid ranking for ${id}.`);
    }
    const ids = new Set(lists.flat());
    if (ids.size !== Object.keys(grades).length ||
        [...ids].some(bookId => !Object.hasOwn(grades, bookId) || ![0, 1, 2].includes(grades[bookId]))) {
      throw new Error(`Every pooled book needs a 0, 1, or 2 human grade for ${id}.`);
    }
  }
  const dev = pool.queries.filter(row => row.split === 'development');
  const holdout = pool.queries.filter(row => row.split === 'holdout');
  const development = WEIGHTS.map(weight => ({ weight, ...metrics(dev, weight) }));
  const candidate = [...development].sort((a, b) => b.clearFits - a.clearFits ||
    b.ndcgAt5 - a.ndcgAt5 || a.weight - b.weight)[0].weight;
  const baseline = metrics(holdout, BASELINE);
  const proposed = metrics(holdout, candidate);
  const passesHoldout = candidate !== BASELINE && holdout.length >= 50 &&
    proposed.clearFits / holdout.length >= 0.82 &&
    proposed.clearFits > baseline.clearFits && proposed.ndcgAt5 >= baseline.ndcgAt5;
  return { catalog, model: MODEL, candidate, development, holdout: { baseline, proposed }, passesHoldout };
}

const output = command === 'pool' ? await generatePool(input) : scorePool(input);
await writeFile(destination, JSON.stringify(output, null, 2) + '\n', { mode: 0o600, flag: 'wx' });
