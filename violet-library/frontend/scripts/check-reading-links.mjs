import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createServer } from 'vite';

const root = new URL('../public/data/', import.meta.url);
const read = async name => JSON.parse(await readFile(new URL(name, root)));
const books = [...await read('catalog.json'), ...await read('multilingual.json')];
const ids = ['3907773b-6336-4d2c-9a7b-3b4a377f22a9', 'openstax-us-history',
  'gutenberg-13842', 'gutenberg-64572', 'nyupress-9781479800575', 'nyupress-9781479891672',
  'gutenberg-14594', 'gutenberg-69812'];
const vite = await createServer({
  configFile: false, root: new URL('..', import.meta.url).pathname,
  server: { middlewareMode: true, ws: false },
});
try {
  const { bookAccess } = await vite.ssrLoadModule(new URL('../src/book-access.ts', import.meta.url).pathname);
  const checks = await Promise.allSettled(ids.map(async id => {
    const book = books.find(item => item.id === id);
    const entry = bookAccess(book);
    if (book.readingPath) {
      const html = await readFile(new URL(book.readingPath, new URL('../public/', import.meta.url)), 'utf8');
      assert.match(html, /Project Gutenberg/i, `${book.title} lacks the edition notice`);
      assert.ok(html.length > 10000, `${book.title} reader appears to be incomplete`);
      return `${book.title}: bundled full-text HTML`;
    }
    const response = await fetch(entry.url, {
      headers: entry.type === 'pdf' ? { Range: 'bytes=0-1023' } : {},
      signal: AbortSignal.timeout(25000),
    });
    if (!response.ok) {
      await response.body?.cancel();
      throw new Error(`${book.title} returned HTTP ${response.status} at ${response.url}`);
    }
    if (!response.body) throw new Error(`${book.title} returned an empty response`);
    if (entry.type === 'pdf') {
      const reader = response.body.getReader();
      try {
        const chunk = await reader.read();
        assert.match(new TextDecoder().decode(chunk.value), /^%PDF-/u, `${book.title} did not return a PDF`);
      } finally {
        await reader.cancel();
      }
    } else {
      const text = await response.text();
      assert.match(text, id === 'openstax-us-history' ? /Chapter Outline/i : /PROJECT GUTENBERG EBOOK/i,
        `${book.title} did not return its reading page`);
    }
    return `${book.title}: HTTP ${response.status} (${entry.type})`;
  }));
  checks.forEach(result => {
    if (result.status === 'fulfilled') console.log(result.value);
    else console.error(result.reason.message);
  });
  if (checks.some(result => result.status === 'rejected')) process.exitCode = 1;
} finally {
  await vite.close();
}
