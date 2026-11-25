import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { CATALOG_BOOK_IDS, CATALOG_SHA256, KNOWN_BOOK_IDS } from '../worker/known-books.js';

test('backend validates both catalog versions against their exact book IDs', async () => {
  const root = new URL('../../frontend/public/data/', import.meta.url);
  const read = async name => JSON.parse(await readFile(new URL(name, root), 'utf8'));
  const [base, supplement, manifest] = await Promise.all([
    read('catalog.json'), read('multilingual.json'), read('manifest.json'),
  ]);
  assert.equal(CATALOG_SHA256, manifest.catalog_sha256);
  assert.deepEqual(KNOWN_BOOK_IDS, new Set([...base, ...supplement].map(book => book.id)));
  assert.deepEqual(CATALOG_BOOK_IDS.get(manifest.files['catalog.json'].sha256),
    new Set(base.map(book => book.id)));
});
