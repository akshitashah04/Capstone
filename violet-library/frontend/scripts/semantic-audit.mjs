import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createServer } from 'vite';

const model = process.env.VIOLET_AUDIT_MODEL ?? 'gte-base';
const dir = new URL('../public/data/', import.meta.url);
const read = async name => JSON.parse(await readFile(new URL(name, dir)));
const [base, supplement, manifest] = await Promise.all([
  read('catalog.json'), read('multilingual.json'), read('manifest.json'),
]);
const queries = JSON.parse(await readFile(
  new URL('../../evaluation/queries/browser-semantic-audit.json', import.meta.url),
));
assert.equal(queries.length, 10);
const vite = await createServer({
  configFile: false, root: new URL('..', import.meta.url).pathname,
  server: { middlewareMode: true, ws: false },
});
let encoder;
try {
  const load = name => vite.ssrLoadModule(new URL(`../src/${name}.ts`, import.meta.url).pathname);
  const [catalog, embeddings, passage, search, intent, bookText] = await Promise.all(
    ['catalog', 'embedding', 'passages', 'search', 'query-intent', 'book-text'].map(load),
  );
  const books = [...base, ...supplement].map(book => ({
    ...book, description: bookText.cleanDescription(book.description),
  }));
  const ids = new Set(books.map(book => book.id));
  for (const { relevant, id } of queries) {
    assert.ok(relevant.every(bookId => ids.has(bookId)), `Unknown target in ${id}`);
  }
  const { env } = await import('@huggingface/transformers');
  env.cacheDir = '/tmp/violet-library-audit-models';
  console.log(`Loading ${model}`);
  encoder = await embeddings.loadEncoder(model);
  const baseVectors = new Uint8Array(await readFile(new URL(`${model}.f16`, dir))).buffer;
  const extra = await embeddings.encodeCatalogPassages(
    encoder, supplement.map(passage.passageText), manifest.models[model].dimensions,
  );
  const vectors = passage.appendVectors(catalog.decodeHalfVectors(baseVectors), extra);
  const index = search.buildSearchIndex(books);
  const output = [];
  for (const row of queries) {
    const vector = await encoder.encode([intent.interpretQuery(row.query).embeddingText], 'query');
    const hits = search.rankBooks(row.query, vector, vectors, index, 'semantic', 0, row.language);
    const top = hits.slice(0, 5).map(hit => ({
      id: hit.book.id, title: hit.book.title, score: Number(hit.relevance.toFixed(4)),
    }));
    const pass = row.relevant.length ? top.some(hit => row.relevant.includes(hit.id)) : !top.length;
    output.push({ id: row.id, split: row.split, pass, top });
  }
  console.log(JSON.stringify({ model, catalog: manifest.catalog_sha256, passed: output.filter(row => row.pass).length, output }));
} finally {
  await encoder?.dispose();
  await vite.close();
}
