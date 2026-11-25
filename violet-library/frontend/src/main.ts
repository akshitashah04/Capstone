import './style.css';
import { loadCatalog, loadPreparedSupplement, loadVectors } from './catalog';
import { COMPACT_MODEL, DEFAULT_MODEL, MODELS, needsCompactModel, selectSearchModel } from './model-config';
import { buildSearchIndex, displayRelevance, hasEligibleBooks, keepSemanticMatches, rankBooks } from './search';
import type { Catalog } from './catalog';
import type { Book, ModelKey, SearchHit } from './types';
import { appendVectors, passageText } from './passages';
import { cleanDescription } from './book-text';
import { citationText, loadReadingList, readingListRis, storeReadingList } from './reading-list';
import { bookAccess } from './book-access';
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
const fullTextOnly = byId<HTMLInputElement>('full-text');
const publishedSince = byId<HTMLSelectElement>('published-since');
const savedCount = byId<HTMLSpanElement>('saved-count');
const readingItems = byId<HTMLUListElement>('reading-list-items');
const readingEmpty = byId<HTMLParagraphElement>('reading-list-empty');
const readingStatus = byId<HTMLParagraphElement>('reading-list-status');
const exportList = byId<HTMLButtonElement>('export-reading-list');
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
const compactSearch = needsCompactModel(navigator);
const modelInactivityMs = 60_000;

let catalog: Catalog | null = null;
let searchIndex: ReturnType<typeof buildSearchIndex> | null = null;
let worker: Worker | null = null;
let workerModel: ModelKey | null = null;
let warmTimer: number | undefined;
let nextId = 1;
let currentHits: SearchHit[] = [];
let visibleCount = 5;
let activeQuery = '';
let activeModel: ModelKey = DEFAULT_MODEL;
let activeLanguage = '';
let activeFullText = false;
let activeYear = 0;
const savedIds = loadReadingList();
let feedbackStates = new Map<string, FeedbackState>();

function feedbackContext(): FeedbackContext {
  if (!catalog) throw new Error('The book catalog is unavailable.');
  return {
    query: activeQuery,
    model: activeModel,
    mode: 'semantic',
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
  if (status.textContent !== message) status.textContent = message;
  status.classList.toggle('error', error);
}

function setBusy(busy: boolean): void {
  submit.disabled = busy;
  modelSelect.disabled = busy;
  languageSelect.disabled = busy;
  fullTextOnly.disabled = busy;
  publishedSince.disabled = busy;
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
  renderReadingList();
  return loaded;
}

function workerFor(model: ModelKey): Worker {
  if (worker && model === workerModel) return worker;
  worker?.terminate();
  workerModel = model;
  const selected = new Worker(new URL('./model-worker.ts', import.meta.url), { type: 'module' });
  selected.addEventListener('error', () => {
    if (worker === selected) worker = null;
    selected.terminate();
  }, { once: true });
  worker = selected;
  return selected;
}

function embed(text: string, model: ModelKey, source: Catalog, prepared: boolean): Promise<{
  vector: Float32Array;
  supplement: Float32Array;
}> {
  const selected = workerFor(model);
  const id = nextId++;
  return new Promise((resolve, reject) => {
    let timer: number;
    const clean = () => {
      window.clearTimeout(timer);
      selected.removeEventListener('message', onMessage);
      selected.removeEventListener('error', onWorkerError);
      selected.removeEventListener('messageerror', onWorkerError);
    };
    const fail = (message: string) => {
      clean();
      if (worker === selected) worker = null;
      selected.terminate();
      reject(new Error(message));
    };
    const onWorkerError = () => fail('The semantic model stopped unexpectedly.');
    const waitForProgress = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => fail('The semantic model stopped responding.'), modelInactivityMs);
    };
    const onMessage = (event: MessageEvent) => {
      if (event.data?.id !== id) return;
      if (event.data.type === 'progress') {
        waitForProgress();
        setStatus(event.data.message);
      }
      if (event.data.type === 'embedding' || event.data.type === 'error') {
        clean();
        if (event.data.type === 'embedding') resolve({ vector: event.data.vector, supplement: event.data.supplement });
        else reject(new Error(event.data.message as string));
      }
    };
    selected.addEventListener('message', onMessage);
    selected.addEventListener('error', onWorkerError);
    selected.addEventListener('messageerror', onWorkerError);
    waitForProgress();
    selected.postMessage({
      id, text, model, prepared, catalog: source.checksum,
      passages: prepared ? [] : source.books.slice(source.manifest.books).map(passageText),
    });
  });
}

function warmSearch(): void {
  window.clearTimeout(warmTimer);
  if (compactSearch) return;
  const connection = (navigator as Navigator & {
    connection?: { saveData?: boolean; effectiveType?: string };
  }).connection;
  if (connection?.saveData || (connection?.effectiveType && connection.effectiveType !== '4g') ||
      !navigator.onLine || submit.disabled || query.value.trim().length < 3) return;
  warmTimer = window.setTimeout(() => {
    const model = selectSearchModel(modelSelect.value, compactSearch);
    workerFor(model).postMessage({ type: 'warm', model });
  }, 350);
}

function displaySummary(description: string): string {
  const clean = cleanDescription(description);
  if (!clean) return 'The publisher has not supplied a description for this book.';
  if (clean.length <= 320) return clean;
  const excerpt = clean.slice(0, 320);
  const lastSpace = excerpt.lastIndexOf(' ');
  return `${excerpt.slice(0, lastSpace > 250 ? lastSpace : 320).trim()}…`;
}

function savedBooks(): Book[] {
  return (catalog?.books ?? []).filter(book => savedIds.has(book.id));
}

function citationControl(book: Book): HTMLElement {
  const group = document.createElement('div');
  group.className = 'citation-control';
  const copy = document.createElement('button');
  copy.type = 'button';
  copy.className = 'secondary-button';
  copy.textContent = 'Copy citation';
  copy.setAttribute('aria-label', `Copy citation for ${book.title}`);
  const feedback = document.createElement('span');
  feedback.className = 'citation-feedback';
  feedback.setAttribute('role', 'status');
  copy.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(citationText(book));
      feedback.textContent = 'Citation copied';
    } catch {
      const previous = group.querySelector('textarea');
      if (previous) {
        previous.focus();
        previous.select();
        return;
      }
      const field = document.createElement('textarea');
      field.readOnly = true;
      field.rows = 2;
      field.value = citationText(book);
      field.setAttribute('aria-label', `Citation for ${book.title}`);
      group.append(field);
      field.focus();
      field.select();
      feedback.textContent = 'Citation selected for copying';
    }
  });
  group.append(copy, feedback);
  return group;
}

function toggleSaved(book: Book): void {
  const removed = savedIds.delete(book.id);
  if (!removed) savedIds.add(book.id);
  const persisted = storeReadingList(savedIds);
  renderReadingList();
  for (const button of Array.from(list.querySelectorAll<HTMLButtonElement>('[data-save-book]'))) {
    if (button.dataset.saveBook !== book.id) continue;
    button.textContent = removed ? 'Save to reading list' : 'Saved';
    button.setAttribute('aria-pressed', String(!removed));
  }
  readingStatus.textContent = persisted
    ? `${removed ? 'Removed' : 'Saved'} ${book.title}`
    : 'This browser cannot keep the reading list after you leave.';
}

function renderReadingList(): void {
  const books = savedBooks();
  savedCount.textContent = String(books.length);
  readingEmpty.hidden = books.length > 0;
  exportList.disabled = books.length === 0;
  readingItems.replaceChildren(...books.map(book => {
    const item = document.createElement('li');
    const title = document.createElement('a');
    title.href = bookAccess(book).url;
    title.referrerPolicy = 'no-referrer';
    title.textContent = book.title;
    const remove = document.createElement('button');
    remove.className = 'secondary-button';
    remove.type = 'button';
    remove.textContent = 'Remove';
    remove.setAttribute('aria-label', `Remove ${book.title} from reading list`);
    remove.addEventListener('click', () => {
      toggleSaved(book);
      readingItems.querySelector<HTMLButtonElement>('button')?.focus();
      if (!readingItems.hasChildNodes()) byId<HTMLElement>('reading-list-title').focus();
    });
    const buttons = document.createElement('div');
    buttons.className = 'reading-actions';
    buttons.append(citationControl(book), remove);
    item.append(title, buttons);
    return item;
  }));
}

exportList.addEventListener('click', () => {
  const books = savedBooks();
  if (!books.length) return;
  const url = URL.createObjectURL(new Blob([readingListRis(books)], { type: 'application/x-research-info-systems' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'violet-library-reading-list.ris';
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 30000);
});

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

  const access = bookAccess(hit.book);
  const link = document.createElement('a');
  link.className = 'book-link';
  link.href = access.url;
  link.referrerPolicy = 'no-referrer';
  const label = access.type === 'pdf' ? 'Read PDF' : access.type === 'web' ? 'Read online' : 'View catalog record';
  link.textContent = label;
  link.setAttribute('aria-label', `${label}: ${hit.book.title}`);
  const actions = document.createElement('div');
  actions.className = 'book-actions';
  actions.append(link);
  const score = document.createElement('div');
  score.className = 'book-score';
  const scoreLabel = document.createElement('span');
  scoreLabel.textContent = 'Relevance';
  const scoreValue = document.createElement('strong');
  scoreValue.textContent = `${displayRelevance(hit.relevance)} / 100`;
  score.append(scoreLabel, scoreValue);
  const save = document.createElement('button');
  save.className = 'secondary-button';
  save.type = 'button';
  save.dataset.saveBook = hit.book.id;
  save.textContent = savedIds.has(hit.book.id) ? 'Saved' : 'Save to reading list';
  save.setAttribute('aria-pressed', String(savedIds.has(hit.book.id)));
  save.addEventListener('click', () => toggleSaved(hit.book));
  actions.append(save, citationControl(hit.book));
  if (access.sourceUrl) {
    const source = document.createElement('a');
    source.className = 'book-source';
    source.href = access.sourceUrl;
    source.referrerPolicy = 'no-referrer';
    source.textContent = 'Source page';
    source.setAttribute('aria-label', `Source page: ${hit.book.title}`);
    actions.append(source);
  }
  card.append(content, score, actions, createFeedbackWidget(hit.book.id, feedbackState(hit.book.id), feedbackContext));
  return card;
}

function renderHits(): void {
  list.replaceChildren(...currentHits.slice(0, visibleCount).map(renderCard));
  listFeedback.replaceChildren(...(currentHits.length
    ? [createFeedbackWidget(null, feedbackState('whole-list'), feedbackContext)] : []));
  more.hidden = currentHits.length <= visibleCount;
  const refinements = [activeLanguage ? languageName(activeLanguage) : '', activeYear ? `Since ${activeYear}` : '',
    activeFullText ? 'Direct full text' : ''].filter(Boolean).map(label => ` · ${label}`).join('');
  subtitle.textContent = currentHits.length
    ? `Showing ${Math.min(visibleCount, currentHits.length)} recommendations${refinements}`
    : '';
  scoreHelp.hidden = !currentHits.length;
  scoreMethod.textContent = 'The model compares the meaning of your question and each book’s metadata using cosine similarity. Use the displayed score to compare results within the same search.';
  if (!currentHits.length) {
    const intent = interpretQuery(activeQuery);
    const languageNameSuffix = activeLanguage ? ` in ${languageName(activeLanguage)}` : '';
    const message = intent.usStudentVisa
      ? `No books in this catalog${languageNameSuffix} directly cover the requested U.S. student visa topic.`
      : `No matching books in this catalog${languageNameSuffix}. Try a different search or book language.`;
    setStatus(activeFullText && !intent.usStudentVisa
      ? `No direct full-text matches in this catalog${languageNameSuffix}. Clear the full-text filter to include catalog records.`
      : message);
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
  window.clearTimeout(warmTimer);
  const model = selectSearchModel(modelSelect.value, compactSearch);
  activeQuery = text;
  activeModel = model;
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
  modelLabel.textContent = `${MODELS[model].label} · Semantic search`;
  results.scrollIntoView({ behavior: 'smooth', block: 'start' });
  try {
    catalog ??= setCatalog(await loadCatalog());
    activeLanguage = languageSelect.value;
    activeFullText = fullTextOnly.checked;
    activeYear = Number(publishedSince.value);
    searchIndex ??= buildSearchIndex(catalog.books, false);
    const url = new URL(window.location.href);
    url.searchParams.set('q', text);
    url.searchParams.set('model', model);
    url.searchParams.set('mode', 'semantic');
    if (activeLanguage) url.searchParams.set('lang', activeLanguage);
    else url.searchParams.delete('lang');
    if (activeFullText) url.searchParams.set('access', 'full');
    else url.searchParams.delete('access');
    if (activeYear) url.searchParams.set('year', String(activeYear));
    else url.searchParams.delete('year');
    history.replaceState(null, '', url);
    if (!hasEligibleBooks(text, searchIndex, activeLanguage, activeFullText, activeYear)) {
      modelLabel.textContent = 'Catalog coverage';
      renderHits();
      return;
    }
    const source = catalog;
    const bookVectors = loadVectors(model, source);
    // Desktop can overlap model warmup with the catalog. Compact search starts one load with progress reporting.
    if (!compactSearch) workerFor(model).postMessage({ type: 'warm', model });
    const prepared = loadPreparedSupplement(model, source);
    const [baseVectors, precomputed, { vector, supplement }] = await Promise.all([
      bookVectors, prepared,
      prepared.then(vectors => embed(interpretQuery(text).embeddingText, model, source, vectors !== null)),
    ]);
    const hits = rankBooks(text, vector, appendVectors(baseVectors, precomputed ?? supplement),
      searchIndex, 'semantic', 0, activeLanguage, activeFullText, activeYear);
    currentHits = keepSemanticMatches(hits, text, model);
    visibleCount = 5;
    setStatus('');
    renderHits();
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Search could not finish.';
    const downloadInterrupted = /network error|failed to fetch/i.test(message);
    const retry = compactSearch ? 'Tap Find books to retry.' : 'Try again or choose another model.';
    const guidance = downloadInterrupted
      ? `A download was interrupted. Check your connection. ${retry}`
      : `Search could not finish. ${message} ${retry}`;
    setStatus(guidance, true);

  } finally {
    setBusy(false);
  }
}

form.addEventListener('submit', event => { event.preventDefault(); void search(); });
query.addEventListener('input', () => {
  count.textContent = `${query.value.length} / 500`;
  warmSearch();
});
modelSelect.addEventListener('change', warmSearch);
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

fullTextOnly.checked = params.get('access') === 'full';
const initialYear = params.get('year');
if (initialYear && Array.from(publishedSince.options).some(option => option.value === initialYear)) {
  publishedSince.value = initialYear;
}
modelSelect.value = selectSearchModel(params.get('model'), compactSearch);
if (compactSearch) {
  for (const option of Array.from(modelSelect.options)) {
    if (option.value === COMPACT_MODEL) option.textContent = 'E5 Small (mobile semantic search)';
    else option.disabled = true;
  }
}
const initialQuery = params.get('q');
if (initialQuery) {
  query.value = initialQuery.slice(0, 500);
  query.dispatchEvent(new Event('input'));
}
