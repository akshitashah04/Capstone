import type { Book } from './types';

const names = new Intl.DisplayNames(['en'], { type: 'language', fallback: 'none' });
const aliases: Record<string, string> = { chi: 'zh', ger: 'de', fre: 'fr', cze: 'cs' };
const unspecified = new Set(['mis', 'mul', 'und', 'zxx']);

export function languageCode(raw: string): string | null {
  const code = raw.trim().toLowerCase();
  if (!/^[a-z]{2,3}$/.test(code) || unspecified.has(code)) return null;
  return aliases[code] ?? new Intl.Locale(code).language;
}

export function languageName(code: string): string {
  const language = languageCode(code);
  return language ? names.of(language) ?? code : code;
}

export function bookLanguages(book: Book): string[] {
  return [...new Set(book.languages.map(languageCode).filter(code => code !== null))];
}

export function availableLanguages(books: Book[]): string[] {
  return [...new Set(books.flatMap(bookLanguages))]
    .sort((a, b) => languageName(a).localeCompare(languageName(b), 'en'));
}
