import assert from 'node:assert/strict';
import { once } from 'node:events';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { devices, expect, webkit } from '@playwright/test';

const frontend = fileURLToPath(new URL('../violet-library/frontend/', import.meta.url));
const site = 'http://127.0.0.1:4175/Capstone/libraries/';
const preview = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--port', '4175', '--strictPort'], {
  cwd: frontend, stdio: ['ignore', 'pipe', 'inherit'],
});
let browser;
try {
  const [output] = await Promise.race([
    once(preview.stdout, 'data'),
    once(preview, 'exit').then(([code]) => { throw new Error(`Preview exited with code ${code}.`); }),
  ]);
  assert.match(output.toString(), /127\.0\.0\.1:4175|localhost:4175/);
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
  await expect(first.getByRole('link', { name: /read online/i })).toHaveAttribute('href', /gutenberg\.org\/cache\/epub\/(14594|69812)\//);
  await expect(mobile.locator('#results-model')).toHaveText(/E5 small · Semantic search/);
  assert.ok(modelRequests.some(url => url.includes('multilingual-e5-small')), 'The mobile model was not requested.');
  assert.ok(modelRequests.every(url => url.includes('multilingual-e5-small')), 'A larger model loaded on mobile.');
  console.log(`Mobile WebKit returned ${await first.getByRole('heading').textContent()} for “Veg food”.`);
} finally {
  try {
    await browser?.close();
  } finally {
    preview.kill();
  }
}
