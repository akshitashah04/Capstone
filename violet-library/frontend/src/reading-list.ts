import { bookAccess } from './book-access';
import type { Book } from './types';

const shelfKey = 'violet-library-reading-list-v1';

export function loadReadingList(): Set<string> {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(shelfKey) ?? '[]');
    return new Set(Array.isArray(value) ? value.filter(item => typeof item === 'string') : []);
  } catch {
    return new Set();
  }
}

export function storeReadingList(ids: Set<string>): boolean {
  try {
    localStorage.setItem(shelfKey, JSON.stringify([...ids]));
    return true;
  } catch {
    return false;
  }
}

function citationUrl(book: Book): string {
  return book.sourceUrl ?? bookAccess(book).sourceUrl ?? book.url;
}

export function citationText(book: Book): string {
  return [
    book.authors.join('; '), book.title, book.publisher, book.year, citationUrl(book),
  ].filter(Boolean).map(value => String(value).replace(/[.\s]+$/, '')).join('. ') + '.';
}

export function readingListRis(books: Book[]): string {
  const field = (key: string, value: string | number) =>
    `${key}  - ${String(value).replace(/\s+/g, ' ').trim()}`;
  return books.map(book => [
    'TY  - BOOK',
    field('TI', book.title),
    ...book.authors.map(author => field('AU', author)),
    ...(book.year ? [field('PY', book.year)] : []),
    ...(book.publisher ? [field('PB', book.publisher)] : []),
    field('UR', citationUrl(book)),
    'ER  - ',
  ].join('\r\n')).join('\r\n\r\n') + '\r\n';
}
