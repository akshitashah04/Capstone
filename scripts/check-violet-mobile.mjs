import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import { devices, expect, webkit } from '@playwright/test';

const frontend = fileURLToPath(new URL('../violet-library/frontend/', import.meta.url));
const site = 'http://127.0.0.1:4175/Capstone/libraries/';
const preview = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', '4175', '--strictPort'], {
  cwd: frontend, stdio: ['ignore', 'ignore', 'inherit'],
});
let browser;
try {
  let previewReady = false;
  for (let attempt = 0; attempt < 25 && preview.exitCode === null; attempt += 1) {
    const response = await fetch(site).catch(() => null);
    if (response?.ok) {
      await response.body?.cancel();
      previewReady = true;
      break;
    }
    await delay(200);
  }
  assert.ok(previewReady, 'Violet Library preview did not start.');
  browser = await webkit.launch();
  const mobile = await browser.newPage(devices['iPhone 13']);
  const modelRequests = [];
  mobile.on('request', request => {
    if (request.url().includes('/resolve/') && /e5-small|e5-base|gte-multilingual-base/.test(request.url())) {
      modelRequests.push(request.url());
    }
  });
  await mobile.goto(`${site}?q=Veg+food&model=gte-base&mode=semantic`);
  await expect(mobile.locator('#query')).toHaveValue('Veg food');
  await expect(mobile.locator('#model')).toHaveValue('e5-small');
  await expect(mobile.locator('#model option[value="gte-base"]')).toBeDisabled();
  const filters = mobile.getByRole('group', { name: 'Filter books' });
  await expect(filters.getByLabel('Published since')).toBeVisible();
  await expect(filters.getByLabel('Book language')).toBeVisible();
  await filters.getByLabel('Direct full text only').check();
  await mobile.getByRole('button', { name: 'Find books' }).click();
  const first = mobile.locator('#results-list .book-card').first();
  try {
    await expect(first.getByRole('heading')).toContainText(/Vegetarian Cookery/i, { timeout: 150_000 });
  } catch (error) {
    const status = await mobile.locator('#status').textContent().catch(() => 'Browser closed');
    throw new Error(`Mobile semantic search status: ${status}`, { cause: error });
  }
  const reader = first.getByRole('link', { name: /read online/i });
  await expect(reader).toHaveAttribute('href', /\/reading\/(cassells|practical)-vegetarian-cookery\//);
  await expect(mobile.locator('#results-model')).toHaveText(/E5 small · Semantic search/);
  await expect(mobile.locator('#results-subtitle')).toContainText('Direct full text');
  assert.ok(modelRequests.every(url => url.includes('multilingual-e5-small')), 'A larger model loaded on mobile.');
  const title = await first.getByRole('heading').textContent();
  await first.getByRole('button', { name: 'Save to reading list' }).click();
  await expect(first.getByRole('button', { name: 'Saved' })).toHaveAttribute('aria-pressed', 'true');
  await first.getByRole('button', { name: /copy citation/i }).click();
  await expect(first.locator('.citation-feedback')).toHaveText(/Citation copied|Citation selected for copying/);
  const shelf = mobile.getByRole('region', { name: 'Reading list' });
  await expect(shelf.getByRole('link', { name: title })).toBeVisible();
  const [ris] = await Promise.all([
    mobile.waitForEvent('download'),
    shelf.getByRole('button', { name: 'Export citations (RIS)' }).click(),
  ]);
  assert.match(await readFile(await ris.path(), 'utf8'), /TI  - .*Vegetarian Cookery/i);
  console.log('Mobile WebKit filtered results, saved a book, copied its citation, and exported a RIS file.');
  await reader.click();
  await expect(mobile).toHaveURL(/\/reading\/(cassells|practical)-vegetarian-cookery\//);
  await expect(mobile.locator('body')).toContainText(/END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK/i);
  console.log(`Mobile WebKit returned and opened ${title} for “Veg food”.`);
} finally {
  try {
    await browser?.close();
  } finally {
    preview.kill();
  }
}
