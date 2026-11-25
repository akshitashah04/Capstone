import type { Book } from './types';

type BookAccess = { url: string; type: 'pdf' | 'web' | 'record'; sourceUrl?: string };

const verifiedEditions: Readonly<Record<string, BookAccess>> = {
  '3907773b-6336-4d2c-9a7b-3b4a377f22a9': {
    url: 'https://www.cambridge.org/core/services/aop-cambridge-core/content/view/DB655ABF01065CD15F581F41EF4ED894/9781108494069AR.pdf/The_Making_of_an_Imperial_Polity.pdf%3Fevent-type%3DFTLA',
    type: 'pdf',
    sourceUrl: 'https://doi.org/10.1017/9781108625227',
  },
  'gutenberg-14594': {
    url: `${import.meta.env.BASE_URL}reading/cassells-vegetarian-cookery/14594-h.htm`,
    type: 'web',
    sourceUrl: 'https://www.gutenberg.org/ebooks/14594',
  },
  'gutenberg-69812': {
    url: `${import.meta.env.BASE_URL}reading/practical-vegetarian-cookery/69812-h.htm`,
    type: 'web',
    sourceUrl: 'https://www.gutenberg.org/ebooks/69812',
  },
};

export function bookAccess(book: Book): BookAccess {
  const verified = verifiedEditions[book.id];
  if (verified) return verified;
  if (book.readingPath?.startsWith('reading/')) {
    return { url: `${import.meta.env.BASE_URL}${book.readingPath}`, type: 'web', sourceUrl: book.sourceUrl };
  }
  if (book.access) return { url: book.url, type: book.access, sourceUrl: book.sourceUrl };
  const url = new URL(book.url);
  if (url.hostname === 'admin.directory.doabooks.org') url.hostname = 'directory.doabooks.org';
  return { url: url.href, type: 'record' };
}
