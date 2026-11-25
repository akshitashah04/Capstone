import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
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
  assert.ok(modelRequests.every(url => url.includes('multilingual-e5-small')), 'A larger model loaded on mobile.');
  const title = await first.getByRole('heading').textContent();
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
