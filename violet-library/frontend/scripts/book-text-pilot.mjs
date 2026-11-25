import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { promisify } from 'node:util';
import { createServer } from 'vite';

const download = promisify(execFile);
const sources = {
  'gutenberg-23839': {
    url: 'https://raw.githubusercontent.com/chinese-poetry/chinese-poetry/b8594f81a89752241442f2ce267d6f66f96704ee/%E8%AE%BA%E8%AF%AD/lunyu.json',
    extract: raw => JSON.parse(raw).flatMap(chapter => chapter.paragraphs).join(''),
  },
  'gutenberg-7337': {
    url: 'https://raw.githubusercontent.com/ilaydabdogan/ancient-wisdom-atlas/07b52ea814bd96b0d6322ec684eeb555fe9dd10f/texts/public-domain/taoist/project-gutenberg/daodejing-chinese-laozi.md',
    extract: raw => raw.slice(raw.indexOf('第一章')).replace(/^第.+章$/gm, ''),
  },
};
const queries = [
  { query: '有朋自远方来', target: 'gutenberg-23839' },
  { query: '三人行必有我师', target: 'gutenberg-23839' },
  { query: '夫子如何看待学习和反思', target: 'gutenberg-23839' },
  { query: '道可道非常道', target: 'gutenberg-7337' },
  { query: '小國寡民', target: 'gutenberg-7337' },
  { query: '有什么书讲自然和无为', target: 'gutenberg-7337' },
];
const args = process.argv.slice(2);
if (args.length && (args.length !== 1 || args[0] !== '--e5')) {
  throw new Error('Usage: node book-text-pilot.mjs [--e5]');
}

function chunks(text) {
  const passages = [];
  for (let start = 0; start < text.length; start += 160) {
    passages.push(text.slice(start, start + 192));
  }
  return passages;
}

function sparseEncoder(documents, tokens) {
  const frequency = new Map();
  for (const text of documents) {
    for (const term of new Set(tokens(text))) {
      frequency.set(term, (frequency.get(term) ?? 0) + 1);
    }
  }
  function encode(text) {
    const vector = new Map();
    for (const term of tokens(text)) vector.set(term, (vector.get(term) ?? 0) + 1);
    let sumSquares = 0;
    for (const [term, count] of vector) {
      const weight = (1 + Math.log(count)) * (1 + Math.log(
        (documents.length + 1) / ((frequency.get(term) ?? 0) + 1),
      ));
      vector.set(term, weight);
      sumSquares += weight ** 2;
    }
    const norm = Math.sqrt(sumSquares);
    for (const [term, value] of vector) vector.set(term, value / norm);
    return vector;
  }
  return {
    encode: async texts => texts.map(encode),
    similarity: (query, document) => [...query].reduce(
      (sum, [term, value]) => sum + value * (document.get(term) ?? 0), 0,
    ),
  };
}

const vite = await createServer({
    configFile: false,
    root: new URL('..', import.meta.url).pathname,
    server: { middlewareMode: true, ws: false },
  });
try {
  const load = name => vite.ssrLoadModule(new URL(`../src/${name}.ts`, import.meta.url).pathname);
  const [{ tokens }, { passageText }] = await Promise.all([load('search'), load('passages')]);
  const catalog = JSON.parse(await readFile(
    new URL('../public/data/multilingual.json', import.meta.url), 'utf8',
  ));
  const texts = new Map(await Promise.all(Object.entries(sources).map(async ([id, source]) => {
    const { stdout } = await download('curl', ['-fsSL', '--max-time', '60', source.url]);
    const text = source.extract(stdout).replace(/\s/gu, '');
    if (text.length < 3000) throw new Error(`Incomplete source text for ${id}.`);
    return [id, text];
  })));
  const records = catalog.map(book => {
    const full = texts.get(book.id) ?? '';
    const excerpt = full.slice(0, Math.ceil(full.length / 10));
    return { id: book.id, metadata: passageText(book), excerpt: chunks(excerpt), full: chunks(full) };
  });
  const documents = records.flatMap(book => [book.metadata, ...book.full]);
  let encoder = sparseEncoder(documents, tokens);
  let model;
  if (args.includes('--e5')) {
    const { env } = await import('@huggingface/transformers');
    env.cacheDir = process.env.LIBRARIES_MODEL_CACHE ?? '/tmp/libraries-model-cache';
    model = await (await load('embedding')).loadEncoder('e5-small');
    encoder = {
      async encode(passages, kind) {
        const vectors = [];
        for (let start = 0; start < passages.length; start += 8) {
          const batch = passages.slice(start, start + 8);
          const data = await model.encode(batch, kind);
          const dimensions = data.length / batch.length;
          for (let i = 0; i < batch.length; i += 1) {
            vectors.push(data.subarray(i * dimensions, (i + 1) * dimensions));
          }
        }
        return vectors;
      },
      similarity: (a, b) => a.reduce((sum, value, i) => sum + value * b[i], 0),
    };
  }
  try {
    const queryVectors = await encoder.encode(queries.map(item => item.query), 'query');
    const allPassages = [...new Set(records.flatMap(book =>
      [book.metadata, ...book.excerpt, ...book.full]))];
    const vectors = new Map(allPassages.map((text, i) => [text, i]));
    const encoded = await encoder.encode(allPassages, 'passage');
    const arms = ['metadata', 'first10Percent', 'fullText'];
    const comparisons = queries.map(({ query, target }, i) => {
      const scores = new Map(allPassages.map(text => [
        text, encoder.similarity(queryVectors[i], encoded[vectors.get(text)]),
      ]));
      return { query, target, ...Object.fromEntries(arms.map(arm => {
        const ranked = records.map(book => {
          const extras = arm === 'first10Percent' ? book.excerpt : arm === 'fullText' ? book.full : [];
          return { id: book.id, score: Math.max(...[book.metadata, ...extras].map(text => scores.get(text))) };
        }).sort((a, b) => b.score - a.score || a.id.localeCompare(b.id, 'en'));
        const rank = ranked.findIndex(book => book.id === target) + 1;
        const similarity = ranked[rank - 1].score;
        return [arm, { rank: model || similarity > 0 ? rank : null, similarity: Number(similarity.toFixed(6)) }];
      })) };
    });
    console.log(JSON.stringify({
      model: model ? 'browser-e5-small-q8' : 'tf-idf',
      candidates: records.length,
      sources: Object.fromEntries([...texts].map(([id, text]) => [id, {
        url: sources[id].url,
        sha256: createHash('sha256').update(text).digest('hex'),
        fullCharacters: text.length,
        excerptCharacters: Math.ceil(text.length / 10),
      }])),
      comparisons,
    }, null, 2));
  } finally {
    await model?.dispose();
  }
} finally {
  await vite.close();
}
