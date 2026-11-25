export type ModelKey = 'e5-small' | 'e5-base' | 'gte-base';
export type SearchMode = 'hybrid' | 'semantic';

export interface Book {
  id: string;
  title: string;
  aliases?: string[];
  authors: string[];
  subjects: string[];
  languages: string[];
  year: number | null;
  url: string;
  description: string;
}

export interface SampleManifest {
  schema: number;
  books: number;
  supplemental_books?: number;
  catalog_sha256?: string;
  vector_encoding: string;
  files: Record<string, { sha256: string; bytes: number }>;
  models: Record<ModelKey, { dimensions: number; repo: string; revision: string }>;
}

export interface SearchHit {
  book: Book;
  rank: number;
  relevance: number;
  semanticSimilarity: number;
}
