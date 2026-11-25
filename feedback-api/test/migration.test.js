import { readFile } from 'node:fs/promises';
import { DatabaseSync } from 'node:sqlite';
import { test } from 'node:test';
import assert from 'node:assert/strict';

test('published migration creates every table and index the API needs', async () => {
  const sql = await readFile(new URL('../drizzle/0000_feedback.sql', import.meta.url), 'utf8');
  const db = new DatabaseSync(':memory:');
  for (const statement of sql.split('--> statement-breakpoint').map(value => value.trim()).filter(Boolean)) {
    db.exec(statement);
  }
  const languageMigration = await readFile(new URL('../drizzle/0001_book_language.sql', import.meta.url), 'utf8');
  db.exec(languageMigration);
  assert.ok(db.prepare('PRAGMA table_info(feedback)').all().some(row => row.name === 'book_language'));
  const names = db.prepare("SELECT name FROM sqlite_master WHERE type IN ('table', 'index')")
    .all().map(row => row.name);
  for (const expected of ['feedback', 'feedback_events', 'rate_counters',
    'feedback_created_at_idx', 'feedback_events_feedback_id_idx']) {
    assert.ok(names.includes(expected), `Missing ${expected}`);
  }
  db.close();
});
