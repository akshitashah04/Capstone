import './style.css';
import { loadCatalog, loadVectors } from './catalog';
import { DEFAULT_MODEL, MODELS } from './model-config';
import { buildSearchIndex, rankBooks, rankKeywordBooks } from './search';
import type { Catalog } from './catalog';
import type { ModelKey, SearchHit, SearchMode } from './types';
import { appendVectors, passageText } from './passages';
import { cleanDescription } from './book-text';
import { createFeedbackWidget } from './feedback/widget';
import type { FeedbackState } from './feedback/widget';
import type { FeedbackContext } from './feedback/client';

function byId<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) throw new Error(`Missing interface element: ${id}`);
  return element as T;
}

const form = byId<HTMLFormElement>('search-form');
const query = byId<HTMLTextAreaElement>('query');
const modelSelect = byId<HTMLSelectElement>('model');
const modeSelect = byId<HTMLSelectElement>('mode');
const submit = byId<HTMLButtonElement>('search-button');
const queryError = byId<HTMLParagraphElement>('query-error');
const count = byId<HTMLSpanElement>('query-count');
const badge = byId<HTMLSpanElement>('sample-badge');
const results = byId<HTMLElement>('results');
const status = byId<HTMLDivElement>('status');
const list = byId<HTMLDivElement>('results-list');
const subtitle = byId<HTMLParagraphElement>('results-subtitle');
const modelLabel = byId<HTMLDivElement>('results-model');
const more = byId<HTMLButtonElement>('more-button');
const listFeedback = byId<HTMLDivElement>('list-feedback');
const voice = byId<HTMLButtonElement>('voice-button');
const languageLabels = new Intl.DisplayNames(['en'], { type: 'language' });

let catalog: Catalog | null = null;
let searchIndex: ReturnType<typeof buildSearchIndex> | null = null;
let worker: Worker | null = null;
let nextId = 1;
let currentHits: SearchHit[] = [];
let visibleCount = 5;
let activeQuery = '';
let activeModel: ModelKey | 'keyword-only' = DEFAULT_MODEL;
let activeMode: SearchMode | 'keyword-only' = 'hybrid';
let feedbackStates = new Map<string, FeedbackState>();

function feedbackContext(): FeedbackContext {
  if (!catalog) throw new Error('The book catalog is unavailable.');
  return {
    query: activeQuery,
    model: activeModel,
    mode: activeMode,
    release: import.meta.env.VITE_RELEASE_ID ?? 'local',
    catalogSha256: catalog.checksum,
    shownBooks: currentHits.slice(0, visibleCount).map(hit => ({ bookId: hit.book.id, rank: hit.rank })),
  };
}

function feedbackState(key: string): FeedbackState {
  let state = feedbackStates.get(key);
  if (!state) {
    state = {};
    feedbackStates.set(key, state);
  }
  return state;
}

function setStatus(message: string, error = false): void {
  status.hidden = !message;
  status.textContent = message;
  status.classList.toggle('error', error);
}

function setBusy(busy: boolean): void {
  submit.disabled = busy;
  modelSelect.disabled = busy;
  modeSelect.disabled = busy;
  form.setAttribute('aria-busy', String(busy));
  submit.querySelector('span')!.textContent = busy ? 'Searching…' : 'Find books';
}

function selectedModel(): ModelKey {
  const value = modelSelect.value;
  return value === 'auto' ? DEFAULT_MODEL : value as ModelKey;
}

function embed(text: string, model: ModelKey, source: Catalog): Promise<{
  vector: Float32Array;
  supplement: Float32Array;
}> {
  worker ??= new Worker(new URL('./model-worker.ts', import.meta.url), { type: 'module' });
  const id = nextId++;
  return new Promise((resolve, reject) => {
    const onMessage = (event: MessageEvent) => {
      if (event.data?.id !== id) return;
      if (event.data.type === 'progress') setStatus(event.data.message);
      if (event.data.type === 'embedding' || event.data.type === 'error') {
        worker?.removeEventListener('message', onMessage);
        if (event.data.type === 'embedding') resolve({ vector: event.data.vector, supplement: event.data.supplement });
        else reject(new Error(event.data.message as string));
      }
    };
    worker!.addEventListener('message', onMessage);
    worker!.postMessage({
      id, text, model, catalog: source.checksum,
      passages: source.books.slice(source.manifest.books).map(passageText),
    });
  });
}

function displaySummary(description: string): string {
  const clean = cleanDescription(description);
  if (!clean) return 'The publisher has not supplied a description for this book.';
  if (clean.length <= 320) return clean;
  const excerpt = clean.slice(0, 320);
  const lastSpace = excerpt.lastIndexOf(' ');
  return `${excerpt.slice(0, lastSpace > 250 ? lastSpace : 320).trim()}…`;
}

function renderCard(hit: SearchHit): HTMLElement {
  const card = document.createElement('article');
  card.className = 'book-card';
  const number = document.createElement('div');
  number.className = 'book-number';
  number.textContent = String(hit.rank).padStart(2, '0');
  number.setAttribute('aria-hidden', 'true');

  const content = document.createElement('div');
  const title = document.createElement('h3');
  title.className = 'book-title';
  title.textContent = hit.book.title;
  const meta = document.createElement('p');
  meta.className = 'book-meta';
  meta.textContent = [hit.book.authors.slice(0, 2).join(', ') || 'Author not listed',
    hit.book.year, hit.book.languages.slice(0, 2).map(language => languageLabels.of(language) ?? language).join(', ')].filter(Boolean).join(' · ');
  const summary = document.createElement('p');
  summary.className = 'book-summary';
  summary.textContent = displaySummary(hit.book.description);
  const tags = document.createElement('div');
  tags.className = 'book-tags';
  for (const subject of hit.book.subjects.slice(0, 2)) {
    const tag = document.createElement('span');
    tag.className = 'book-tag';
    tag.textContent = subject.length > 45 ? `${subject.slice(0, 42)}…` : subject;
    tags.append(tag);
  }
  content.append(title, meta, summary, tags,
    createFeedbackWidget(hit.book.id, feedbackState(hit.book.id), feedbackContext));

  const side = document.createElement('div');
  side.className = 'book-side';
  const relevance = document.createElement('div');
  relevance.className = 'relevance';
  relevance.textContent = String(Math.round(100 * hit.relevance / currentHits[0].relevance));
  const scoreLabel = document.createElement('small');
  scoreLabel.textContent = 'RELATIVE SCORE';
  relevance.append(scoreLabel);
  const link = document.createElement('a');
  link.className = 'book-link';
  link.href = hit.book.url;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  link.textContent = 'View open-access book ↗';
  side.append(relevance, link);
  card.append(number, content, side);
  return card;
}

function renderHits(): void {
  list.replaceChildren(...currentHits.slice(0, visibleCount).map(renderCard));
  listFeedback.replaceChildren(...(currentHits.length
    ? [createFeedbackWidget(null, feedbackState('whole-list'), feedbackContext)] : []));
  more.hidden = currentHits.length <= visibleCount;
  subtitle.textContent = `Showing ${Math.min(visibleCount, currentHits.length)} of ${currentHits.length} results from ${catalog?.books.length.toLocaleString() ?? 'the'} demo books. Top relative score = 100; these are not confidence percentages.`;
  if (!currentHits.length) setStatus('No books in this sample matched. Try a broader request.', false);
}

async function search(): Promise<void> {
  const text = query.value.trim();
  queryError.hidden = true;
  if (text.length < 3 && !/\p{Script=Han}{2}/u.test(text)) {
    queryError.textContent = 'Write at least a few words about the book you need.';
    queryError.hidden = false;
    query.focus();
    return;
  }
  if (!navigator.onLine) {
    results.hidden = false;
    setStatus('You are offline. Connect to load the selected model and book sample.', true);
    return;
  }
  const model = selectedModel();
  const mode = modeSelect.value as SearchMode;
  activeQuery = text;
  activeModel = model;
  activeMode = mode;
  feedbackStates = new Map();
  results.hidden = false;
  currentHits = [];
  list.replaceChildren();
  listFeedback.replaceChildren();
  more.hidden = true;
  setBusy(true);
  setStatus(`Preparing ${MODELS[model].label}. First use may download about ${MODELS[model].downloadMb} MB.`);
  modelLabel.textContent = `${MODELS[model].label} · ${mode === 'hybrid' ? 'Meaning + keywords' : 'Meaning only'}`;
  results.scrollIntoView({ behavior: 'smooth', block: 'start' });
  try {
    catalog ??= await loadCatalog();
    badge.textContent = `${catalog.books.length.toLocaleString()} open-access demo books`;
    searchIndex ??= buildSearchIndex(catalog.books);
    const [{ vector, supplement }, bookVectors] = await Promise.all([
      embed(text, model, catalog), loadVectors(model, catalog),
    ]);
    currentHits = rankBooks(text, vector, appendVectors(bookVectors, supplement), searchIndex, mode);
    visibleCount = 5;
    setStatus('');
    renderHits();
    const url = new URL(window.location.href);
    url.searchParams.set('q', text);
    url.searchParams.set('model', modelSelect.value);
    url.searchParams.set('mode', mode);
    history.replaceState(null, '', url);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Search could not finish.';
    const downloadInterrupted = /network error|failed to fetch/i.test(message);
    const guidance = downloadInterrupted
      ? 'A download was interrupted. Check your connection, then try again.'
      : `Search could not finish: ${message} Try again or choose another model.`;
    setStatus(guidance, true);
    if (downloadInterrupted && searchIndex) {
      const preview = document.createElement('button');
      preview.type = 'button';
      preview.className = 'fallback-button';
      preview.textContent = 'Show keyword-only preview';
      preview.addEventListener('click', () => {
        currentHits = rankKeywordBooks(text, searchIndex!);
        visibleCount = 5;
        activeModel = 'keyword-only';
        activeMode = 'keyword-only';
        feedbackStates = new Map();
        modelLabel.textContent = 'Keyword-only preview · model unavailable';
        setStatus('');
        renderHits();
      });
      status.append(preview);
    }
  } finally {
    setBusy(false);
  }
}

form.addEventListener('submit', event => { event.preventDefault(); void search(); });
query.addEventListener('input', () => { count.textContent = `${query.value.length} / 500`; });
query.addEventListener('keydown', event => {
  if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
    event.preventDefault(); form.requestSubmit();
  }
});
more.addEventListener('click', () => {
  visibleCount = 10;
  renderHits();
  more.hidden = true;
});
document.querySelectorAll<HTMLButtonElement>('[data-query]').forEach(button => {
  button.addEventListener('click', () => {
    query.value = button.dataset.query ?? '';
    query.dispatchEvent(new Event('input'));
    form.requestSubmit();
  });
});

interface SpeechResultEvent { results: ArrayLike<ArrayLike<{ transcript: string }>>; }
interface SpeechRecognizer {
  lang: string;
  onresult: ((event: SpeechResultEvent) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start(): void;
}
type SpeechConstructor = new () => SpeechRecognizer;
const speech = (window as unknown as {
  SpeechRecognition?: SpeechConstructor;
  webkitSpeechRecognition?: SpeechConstructor;
}).SpeechRecognition ?? (window as unknown as { webkitSpeechRecognition?: SpeechConstructor }).webkitSpeechRecognition;
if (speech) {
  voice.hidden = false;
  voice.addEventListener('click', () => {
    const recognition = new speech();
    recognition.lang = navigator.language;
    voice.classList.add('listening');
    voice.setAttribute('aria-label', 'Listening for your question');
    recognition.onresult = event => {
      query.value = event.results[0][0].transcript;
      query.dispatchEvent(new Event('input'));
      query.focus();
    };
    recognition.onerror = () => { queryError.textContent = 'Voice input did not work. Please type your question.'; queryError.hidden = false; };
    recognition.onend = () => { voice.classList.remove('listening'); voice.setAttribute('aria-label', 'Use voice input'); };
    recognition.start();
  });
}

void loadCatalog().then(loaded => {
  catalog = loaded;
  badge.textContent = `${loaded.books.length.toLocaleString()} open-access demo books`;
}).catch(() => { badge.textContent = 'Book sample unavailable · Search to retry'; });

const params = new URLSearchParams(window.location.search);
const initialQuery = params.get('q');
if (initialQuery) {
  query.value = initialQuery.slice(0, 500);
  query.dispatchEvent(new Event('input'));
}
const initialModel = params.get('model');
if (initialModel && Array.from(modelSelect.options).some(option => option.value === initialModel)) modelSelect.value = initialModel;
const initialMode = params.get('mode');
if (initialMode === 'semantic' || initialMode === 'hybrid') modeSelect.value = initialMode;
