import type { Book, ModelKey, SampleManifest } from './types';
import { cleanDescription } from './book-text';

export interface Catalog {
  books: Book[];
  manifest: SampleManifest;
  checksum: string;
}

const root = `${import.meta.env.BASE_URL}data/`;
let catalogPromise: Promise<Catalog> | null = null;
const vectorPromises = new Map<ModelKey, Promise<Float32Array>>();

async function fetchChecked(name: string, expected: { sha256: string; bytes: number }): Promise<ArrayBuffer> {
  const response = await fetch(`${root}${name}`);
  if (!response.ok) throw new Error(`Could not load ${name} (${response.status}).`);
  const bytes = await response.arrayBuffer();
  if (bytes.byteLength !== expected.bytes) throw new Error(`${name} has an unexpected size.`);
  const actual = await sha256(bytes);
  if (actual !== expected.sha256) throw new Error(`${name} did not pass its integrity check.`);
  return bytes;
}

async function sha256(bytes: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
}

export function loadCatalog(): Promise<Catalog> {
  if (catalogPromise) return catalogPromise;
  catalogPromise = (async () => {
    const response = await fetch(`${root}manifest.json`);
    if (!response.ok) throw new Error('The demonstration catalog is unavailable.');
    const manifest = await response.json() as SampleManifest;
    if (manifest.schema !== 1 || manifest.vector_encoding !== 'float16-le-row-major' ||
        !manifest.files['catalog.json'] || !Number.isInteger(manifest.books) || manifest.books < 1) {
      throw new Error('The demonstration catalog format is not supported.');
    }
    const baseFile = manifest.files['catalog.json'];
    const supplementFile = manifest.files['multilingual.json'];
    const [baseBytes, supplementBytes] = await Promise.all([
      fetchChecked('catalog.json', baseFile),
      supplementFile ? fetchChecked('multilingual.json', supplementFile) : null,
    ]);
    const decoder = new TextDecoder();
    const base = JSON.parse(decoder.decode(baseBytes)) as Book[];
    const supplement = supplementBytes ? JSON.parse(decoder.decode(supplementBytes)) as Book[] : [];
    const checksum = supplementFile
      ? await sha256(new TextEncoder().encode(baseFile.sha256 + supplementFile.sha256).buffer)
      : baseFile.sha256;
    if (!Array.isArray(base) || base.length !== manifest.books || !Array.isArray(supplement) ||
        supplement.length !== (manifest.supplemental_books ?? 0) ||
        checksum !== (manifest.catalog_sha256 ?? baseFile.sha256)) {
      throw new Error('The demonstration catalog is incomplete.');
    }
    const books = [...base, ...supplement];
    if (books.some(book => !book.id || !book.title || !book.url?.startsWith('https://')) ||
        new Set(books.map(book => book.id)).size !== books.length) {
      throw new Error('The demonstration catalog contains invalid book records.');
    }
    return { books: books.map(book => ({
      ...book, description: cleanDescription(book.description),
    })), manifest, checksum };
  })().catch(error => { catalogPromise = null; throw error; });
  return catalogPromise;
}

function halfToFloat(bits: number): number {
  const sign = (bits & 0x8000) ? -1 : 1;
  const exponent = (bits >> 10) & 0x1f;
  const fraction = bits & 0x3ff;
  if (exponent === 0) return sign * 2 ** -14 * (fraction / 1024);
  if (exponent === 31) return fraction ? Number.NaN : sign * Number.POSITIVE_INFINITY;
  return sign * 2 ** (exponent - 15) * (1 + fraction / 1024);
}

export function decodeHalfVectors(bytes: ArrayBuffer): Float32Array {
  if (bytes.byteLength % 2 !== 0) throw new Error('Vector bytes are incomplete.');
  const view = new DataView(bytes);
  const result = new Float32Array(bytes.byteLength / 2);
  for (let index = 0; index < result.length; index += 1) {
    result[index] = halfToFloat(view.getUint16(index * 2, true));
  }
  return result;
}

export function loadVectors(model: ModelKey, catalog: Catalog): Promise<Float32Array> {
  const prior = vectorPromises.get(model);
  if (prior) return prior;
  const promise = (async () => {
    const file = `${model}.f16`;
    const expected = catalog.manifest.files[file];
    const dimensions = catalog.manifest.models[model]?.dimensions;
    if (!expected || !Number.isInteger(dimensions) || dimensions < 1 ||
        expected.bytes !== catalog.manifest.books * dimensions * 2) {
      throw new Error(`The ${model} vector file is not aligned with the book sample.`);
    }
    const result = decodeHalfVectors(await fetchChecked(file, expected));
    if (result.some(value => !Number.isFinite(value))) {
      throw new Error(`The ${model} vectors contain invalid values.`);
    }
    return result;
  })().catch(error => { vectorPromises.delete(model); throw error; });
  vectorPromises.set(model, promise);
  return promise;
}
