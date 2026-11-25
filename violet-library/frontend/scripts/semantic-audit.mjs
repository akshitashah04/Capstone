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
  const [catalog, embeddings, passage, search, intent, bookText, queryTools] = await Promise.all(
    ['catalog', 'embedding', 'passages', 'search', 'query-intent', 'book-text', 'semantic-query'].map(load),
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
  const variants = [0, 0.25, 0.5, 0.75, 1];
  const predicted = [];
  for (const row of queries) {
    const original = intent.interpretQuery(row.query).embeddingText;
    const focus = queryTools.focusedQuery(original);
    const originalVector = await encoder.encode([original], 'query');
    const focusedVector = focus === original ? originalVector : await encoder.encode([focus], 'query');
    const rankings = variants.map(weight => {
      const vector = queryTools.blendQueryVectors(originalVector, focusedVector, weight);
      const hits = search.keepSemanticMatches(
        search.rankBooks(row.query, vector, vectors, index, 'semantic', 0, row.language),
        row.query, model,
      );
      const position = row.relevant.length ? hits.findIndex(hit => row.relevant.includes(hit.book.id)) : -1;
      const reciprocalRank = row.relevant.length ? (position < 0 ? 0 : 1 / (position + 1)) : Number(!hits.length);
      return {
        weight, reciprocalRank, pass: row.relevant.length ? position >= 0 && position < 5 : !hits.length,
        top: hits.slice(0, 5).map(hit => ({
          title: hit.book.title, score: Number(hit.relevance.toFixed(4)),
        })),
        resultCount: hits.length,
      };
    });
    predicted.push({ id: row.id, split: row.split, rankings });
  }
  const scores = variants.map((weight, i) => ({
    weight,
    score: predicted.filter(row => row.split === 'development')
      .reduce((sum, row) => sum + row.rankings[i].reciprocalRank, 0),
  }));
  scores.sort((a, b) => b.score - a.score || a.weight - b.weight);
  const selected = scores[0].weight;
  const output = predicted.map(({ id, split, rankings }) => ({
    id, split, ...rankings[variants.indexOf(selected)],
  }));
  console.log(JSON.stringify({ model, selected, scores, passed: output.filter(row => row.pass).length, output }));

} finally {
  await encoder?.dispose();
  await vite.close();
}
