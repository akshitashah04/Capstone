import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
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
assert.ok(queries.length > 0, 'At least one semantic query is required.');
const vite = await createServer({
  configFile: false, root: new URL('..', import.meta.url).pathname,
  server: { middlewareMode: true, ws: false },
});
let encoder;
try {
  const load = name => vite.ssrLoadModule(new URL(`../src/${name}.ts`, import.meta.url).pathname);
  const [catalog, embeddings, passage, search, intent, bookText, queryTools, config] = await Promise.all(
    ['catalog', 'embedding', 'passages', 'search', 'query-intent', 'book-text', 'semantic-query', 'model-config'].map(load),
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
  const loadStart = performance.now();
  encoder = await embeddings.loadEncoder(model);
  const modelLoadMs = Math.round(performance.now() - loadStart);
  const rawVectors = await readFile(new URL(`${model}.f16`, dir));
  const baseVectors = rawVectors.buffer.slice(rawVectors.byteOffset, rawVectors.byteOffset + rawVectors.byteLength);
  const indexStart = performance.now();
  const exporting = process.env.VIOLET_SAVE_SUPPLEMENT === '1';
  const dimensions = manifest.models[model].dimensions;
  let extra;
  let precomputed = false;
  if (!exporting) {
    const descriptor = await read(`prepared/${model}.json`).catch(() => null);
    if (descriptor) {
      const bytes = await readFile(new URL(`prepared/${model}.f32`, dir));
      assert.equal(descriptor.catalog, manifest.catalog_sha256);
      assert.equal(descriptor.revision, config.MODELS[model].revision);
      assert.equal(bytes.length, supplement.length * dimensions * 4);
      assert.equal(descriptor.sha256, createHash('sha256').update(bytes).digest('hex'));
      extra = Float32Array.from({ length: bytes.length / 4 }, (_, i) => bytes.readFloatLE(i * 4));
      assert.ok(extra.every(Number.isFinite));
      precomputed = true;
    }
  }
  extra ??= await embeddings.encodeCatalogPassages(encoder, supplement.map(passage.passageText), dimensions);
  const supplementalEncodingMs = Math.round(performance.now() - indexStart);
  if (exporting) {
    const output = new URL('prepared/', dir);
    await mkdir(output, { recursive: true });
    const bytes = Buffer.allocUnsafe(extra.length * 4);
    extra.forEach((value, i) => bytes.writeFloatLE(value, i * 4));
    await writeFile(new URL(`${model}.f32`, output), bytes);
    await writeFile(new URL(`${model}.json`, output), JSON.stringify({
      model, catalog: manifest.catalog_sha256, revision: config.MODELS[model].revision,
      encoding: 'float32-le-row-major', bytes: bytes.length,
      sha256: createHash('sha256').update(bytes).digest('hex'),
    }, null, 2) + '\n');
  }
  const vectors = passage.appendVectors(catalog.decodeHalfVectors(baseVectors), extra);
  const index = search.buildSearchIndex(books);
  const variants = model === 'gte-base' ? [0, 0.25, 0.5, 0.75, 1] : [0];
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
  const selected = model === 'gte-base' ? queryTools.GTE_FOCUS_WEIGHT : 0;
  const output = predicted.map(({ id, split, rankings }) => ({
    id, split, ...rankings[variants.indexOf(selected)],
  }));
  console.log(JSON.stringify({ model, modelLoadMs, supplementalEncodingMs, precomputed, deployedWeight: selected, bestDevelopmentWeight: scores[0].weight, scores, passed: output.filter(row => row.pass).length, output }));
  if (!process.env.VIOLET_REPORT_ONLY) {
    assert.ok(output.every(row => row.pass), 'At least one semantic regression case failed.');
  }

} finally {
  await encoder?.dispose();
  await vite.close();
}
