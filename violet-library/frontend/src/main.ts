import './style.css';
import { loadCatalog, loadVectors } from './catalog';
import { DEFAULT_MODEL, MODELS } from './model-config';
import { buildSearchIndex, displayRelevance, hasEligibleBooks, rankBooks, rankKeywordBooks } from './search';
import type { Catalog } from './catalog';
import type { ModelKey, SearchHit, SearchMode } from './types';
import { appendVectors, passageText } from './passages';
import { cleanDescription } from './book-text';
import { interpretQuery } from './query-intent';
import { availableLanguages, bookLanguages, languageName } from './languages';
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
const languageSelect = byId<HTMLSelectElement>('language');
const modeSelect = byId<HTMLSelectElement>('mode');
const submit = byId<HTMLButtonElement>('search-button');
const queryError = byId<HTMLParagraphElement>('query-error');
const count = byId<HTMLSpanElement>('query-count');
const badge = byId<HTMLSpanElement>('sample-badge');
const results = byId<HTMLElement>('results');
const status = byId<HTMLDivElement>('status');
const list = byId<HTMLDivElement>('results-list');
const subtitle = byId<HTMLParagraphElement>('results-subtitle');
const scoreHelp = byId<HTMLDetailsElement>('score-help');
const scoreMethod = byId<HTMLParagraphElement>('score-method');
const modelLabel = byId<HTMLDivElement>('results-model');
const more = byId<HTMLButtonElement>('more-button');
const listFeedback = byId<HTMLDivElement>('list-feedback');
const voice = byId<HTMLButtonElement>('voice-button');
const params = new URLSearchParams(window.location.search);

let catalog: Catalog | null = null;
let searchIndex: ReturnType<typeof buildSearchIndex> | null = null;
let worker: Worker | null = null;
let nextId = 1;
let currentHits: SearchHit[] = [];
let visibleCount = 5;
let activeQuery = '';
let activeModel: ModelKey | 'keyword-only' = DEFAULT_MODEL;
let activeMode: SearchMode | 'keyword-only' = 'semantic';
let activeLanguage = '';
let feedbackStates = new Map<string, FeedbackState>();

function feedbackContext(): FeedbackContext {
  if (!catalog) throw new Error('The book catalog is unavailable.');
  return {
    query: activeQuery,
    model: activeModel,
    mode: activeMode,
    language: activeLanguage || undefined,
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
  languageSelect.disabled = busy;
  form.setAttribute('aria-busy', String(busy));
  submit.querySelector('span')!.textContent = busy ? 'Searching…' : 'Find books';
}

function setCatalog(loaded: Catalog): Catalog {
  catalog = loaded;
  badge.textContent = `${loaded.books.length.toLocaleString()} open-access books`;
  if (languageSelect.options.length === 1) {
    for (const code of availableLanguages(loaded.books)) {
      languageSelect.add(new Option(languageName(code), code));
    }
    const initialLanguage = params.get('lang');
    if (initialLanguage && Array.from(languageSelect.options).some(option => option.value === initialLanguage)) {
      languageSelect.value = initialLanguage;
    }
  }
  return loaded;
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

  const content = document.createElement('div');
  const title = document.createElement('h3');
  title.className = 'book-title';
  title.textContent = hit.book.title;
  const meta = document.createElement('p');
  meta.className = 'book-meta';
  const languages = bookLanguages(hit.book);
  if (hit.book.aliases && languages.length === 1) title.lang = languages[0];
  meta.textContent = [hit.book.authors.slice(0, 2).join(', ') || hit.book.publisher || 'Author not listed',
    hit.book.year, hit.book.format, languages.map(languageName).join(', ')].filter(Boolean).join(' · ');
  const summary = document.createElement('p');
  summary.className = 'book-summary';
  if (title.lang) summary.lang = title.lang;
  summary.textContent = displaySummary(hit.book.description);
  const tags = document.createElement('div');
  tags.className = 'book-tags';
  for (const subject of hit.book.subjects.slice(0, 2)) {
    const tag = document.createElement('span');
    tag.className = 'book-tag';
    tag.textContent = subject.length > 45 ? `${subject.slice(0, 42)}…` : subject;
    tags.append(tag);
  }
  content.append(title, meta, summary, tags);

  const side = document.createElement('div');
  side.className = 'book-side';
  const link = document.createElement('a');
  link.className = 'book-link';
  link.href = hit.book.url;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  const itemType = hit.book.format?.toLowerCase() ?? 'book';
  link.textContent = `Read ${itemType}`;
  link.setAttribute('aria-label', `Read ${itemType}: ${hit.book.title} (opens in a new tab)`);
  const keywordMode = activeMode === 'keyword-only';
  const score = document.createElement('div');
  score.className = 'book-score';
  const scoreLabel = document.createElement('span');
  scoreLabel.textContent = keywordMode ? 'Keyword relevance' : 'Relevance';
  const scoreValue = document.createElement('strong');
  const topKeywordScore = keywordMode ? currentHits[0].relevance : undefined;
  scoreValue.textContent = `${displayRelevance(hit.relevance, topKeywordScore)} / 100`;
  score.append(scoreLabel, scoreValue);
  side.append(score, link);
  card.append(content, side, createFeedbackWidget(hit.book.id, feedbackState(hit.book.id), feedbackContext));
  return card;
}

function renderHits(): void {
  list.replaceChildren(...currentHits.slice(0, visibleCount).map(renderCard));
  listFeedback.replaceChildren(...(currentHits.length
    ? [createFeedbackWidget(null, feedbackState('whole-list'), feedbackContext)] : []));
  more.hidden = currentHits.length <= visibleCount;
  const language = activeLanguage ? ` · ${languageName(activeLanguage)}` : '';
  subtitle.textContent = currentHits.length
    ? `Showing ${Math.min(visibleCount, currentHits.length)} recommendations${language}`
    : '';
  scoreHelp.hidden = !currentHits.length;
  if (activeMode === 'keyword-only') {
    scoreMethod.textContent = 'This preview weights matched words by how rare they are and where they appear. The strongest keyword match in these results scores 100. Compare these scores within this search.';
  } else {
    const bonus = activeMode === 'hybrid' ? ' Key terms can add up to 2.5 points.' : '';
    scoreMethod.textContent = `The model compares your question with each book’s metadata using cosine similarity. We scale the score from 0 to 100.${bonus} Use it to compare results within this search. It does not predict whether a book will meet your needs.`;
  }
  if (!currentHits.length) {
    const intent = interpretQuery(activeQuery);
    const languageNameSuffix = activeLanguage ? ` in ${languageName(activeLanguage)}` : '';
    const message = intent.usStudentVisa
      ? `No books in this catalog${languageNameSuffix} directly cover the requested U.S. student visa topic.`
      : `No matching books in this catalog${languageNameSuffix}. Try a different search or book language.`;
    setStatus(message);

  }
}

async function search(): Promise<void> {
  if (submit.disabled) return;
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
  const model = modelSelect.value as ModelKey;
  const mode = modeSelect.value as SearchMode;
  activeQuery = text;
  activeModel = model;
  activeMode = mode;
  subtitle.textContent = '';
  scoreHelp.hidden = true;
  scoreHelp.open = false;
  feedbackStates = new Map();
  results.hidden = false;
  currentHits = [];
  list.replaceChildren();
  listFeedback.replaceChildren();
  more.hidden = true;
  setBusy(true);
  setStatus(`Preparing ${MODELS[model].label}. First use may download about ${MODELS[model].downloadMb} MB.`);
  modelLabel.textContent = `${MODELS[model].label} · ${mode === 'hybrid' ? 'Semantic + key terms' : 'Semantic search'}`;
  results.scrollIntoView({ behavior: 'smooth', block: 'start' });
  try {
    catalog ??= setCatalog(await loadCatalog());
    activeLanguage = languageSelect.value;
    searchIndex ??= buildSearchIndex(catalog.books);
    const url = new URL(window.location.href);
    url.searchParams.set('q', text);
    url.searchParams.set('model', modelSelect.value);
    url.searchParams.set('mode', mode);
    if (activeLanguage) url.searchParams.set('lang', activeLanguage);
    else url.searchParams.delete('lang');
    history.replaceState(null, '', url);
    if (!hasEligibleBooks(text, searchIndex, activeLanguage)) {
      modelLabel.textContent = 'Catalog coverage';
      renderHits();
      return;
    }
    const [{ vector, supplement }, bookVectors] = await Promise.all([
      embed(interpretQuery(text).embeddingText, model, catalog), loadVectors(model, catalog),
    ]);
    currentHits = rankBooks(text, vector, appendVectors(bookVectors, supplement), searchIndex, mode, 1, activeLanguage);
    visibleCount = 5;
    setStatus('');
    renderHits();
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
        currentHits = rankKeywordBooks(text, searchIndex!, activeLanguage);
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
    if (button.dataset.language && Array.from(languageSelect.options).some(option => option.value === button.dataset.language)) {
      languageSelect.value = button.dataset.language;
    }
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

void loadCatalog().then(setCatalog).catch(() => {
  badge.textContent = 'Collection unavailable. Search to retry.';
});

const initialQuery = params.get('q');
if (initialQuery) {
  query.value = initialQuery.slice(0, 500);
  query.dispatchEvent(new Event('input'));
}
const initialModel = params.get('model');
if (initialModel && Array.from(modelSelect.options).some(option => option.value === initialModel)) modelSelect.value = initialModel;
const initialMode = params.get('mode');
if (initialMode === 'semantic' || initialMode === 'hybrid') modeSelect.value = initialMode;
