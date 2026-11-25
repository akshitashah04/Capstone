import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { CATALOG_BOOK_IDS, CATALOG_SHA256, KNOWN_BOOK_IDS } from '../worker/known-books.js';

test('backend validates current and legacy catalogs against their exact book IDs', async () => {
  const root = new URL('../../frontend/public/data/', import.meta.url);
  const read = async name => JSON.parse(await readFile(new URL(name, root), 'utf8'));
  const [base, supplement, manifest] = await Promise.all([
    read('catalog.json'), read('multilingual.json'), read('manifest.json'),
  ]);
  assert.equal(CATALOG_SHA256, manifest.catalog_sha256);
  assert.deepEqual(KNOWN_BOOK_IDS, new Set([...base, ...supplement].map(book => book.id)));
  assert.deepEqual(CATALOG_BOOK_IDS.get(manifest.files['catalog.json'].sha256),
    new Set(base.map(book => book.id)));
  const previousSha = '675bf0e008198b79f1c4f60a9df4d33301e4a1b92751b42baf78c7af18cb587f';
  assert.deepEqual(CATALOG_BOOK_IDS.get(previousSha),
    new Set([...base, ...supplement.slice(0, 7)].map(book => book.id)));
  assert.equal(CATALOG_BOOK_IDS.get(previousSha).has('educationusa-undergraduate-study'), false);
  const visaCatalog = JSON.parse(await readFile(
    new URL('../scripts/catalog-compatibility.json', import.meta.url), 'utf8',
  ))[1].catalogSha256;
  assert.deepEqual(CATALOG_BOOK_IDS.get(visaCatalog),
    new Set([...base, ...supplement.slice(0, 13)].map(book => book.id)));
});
