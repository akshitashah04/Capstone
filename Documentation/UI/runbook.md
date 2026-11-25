# Browser demo runbook

## Browser search

The public GitHub Pages site serves a static interface, metadata for 1,884 open-access DOAB books plus seven supplemental titles, and three compact vector files for the DOAB rows. The visitor's browser downloads one selected multilingual model and encodes the query and the supplemental records. Supplemental embeddings are reused while that model is loaded. Project-owned JavaScript ranks every book in the demo sample. No outside provider chooses candidates for a visitor's query. The full 91,667-book research index is **not** queried by the public demo.

The 1,884 records are the union of saved top-ten result pools from the prior 50-question E5 small, E5 base, and GTE comparisons. The source order is preserved and every file is checked against a SHA-256 manifest. Because this sample was selected from evaluated results, it is not representative of the full collection and cannot be used to verify the earlier 17/50, 18/50, or 19/50 quality figures. The index uses book metadata. The four Chinese records come from Project Gutenberg and the three Hindi records from Hindi Wikisource, with original titles, English aliases, and source-linked summaries.

The sample has thin coverage for topics outside those earlier questions. For example, a live Chrome search for `chinese culture` completed but returned broad China-related books because no sampled title directly addresses Chinese culture. Do not demonstrate arbitrary topics as though this sample covers the full catalog. Source placeholder summaries such as `undefined` are treated as missing and books without a usable description are omitted from recommendations.

## File map

| File or folder | Purpose |
| --- | --- |
| `frontend/index.html` | Search page structure and accessible labels |
| `frontend/src/style.css` | NYU-inspired colors, layout, mobile rules, and focus styles |
| `frontend/src/main.ts` | Form, model controls, loading states, result cards, and voice entry |
| `frontend/src/book-text.ts` | Cleans missing-description placeholders before display and ranking |
| `frontend/src/model-config.ts` | Pinned browser model revisions and query settings |
| `frontend/src/model-worker.ts` | Loads a selected model and encodes the visitor's question |
| `frontend/src/catalog.ts` | Fetches and verifies sample data; decodes compact vectors |
| `frontend/src/search.ts` | Own keyword, semantic, and hybrid ranking rules |
| `frontend/src/types.ts` | Shared book, model, and result shapes |
| `frontend/src/*.test.ts` | Synthetic ranking and vector-format checks |
| `frontend/public/data/` | Small shared book catalog, model vectors, and checksum manifest |
| `frontend/package.json`, `package-lock.json`, `tsconfig.json`, `vite.config.ts` | Pinned dependencies, TypeScript, and site build settings |
| `src/libraries_evaluation/browser_demo_sample.py` | Cloud-only extraction from verified full indexes |
| `tests/test_browser_demo_sample.py` | Synthetic sample-selection and provenance tests |
| `.github/workflows/build-browser-demo-sample.yml` | Creates the compact sample on temporary GitHub storage |
| `.github/workflows/publish-browser-demo-sample.yml` | Verifies and commits the compact sample |
| `.github/workflows/deploy-demo-pages.yml` | Tests, builds, and publishes the site |

## Run it locally

1. Clone the `build-nyu-search-demo` branch of `VeedantBrahmbhatt/Libraries`.
2. Install Node 22 or later and run `npm ci --prefix frontend` from the repository root.
3. Run `npm test --prefix frontend` and `npm run build --prefix frontend`.
4. Run `npm run dev --prefix frontend` and open the localhost URL that Vite prints.
5. Write a full-sentence request, choose a book language if needed, and select **Find books**. GTE Base and semantic search are selected by default.
6. The first query downloads the GTE model; later queries reuse its browser cache. Switch to E5 small or E5 base to compare them.
7. Read five results; select **Show more books** for up to ten. Open a source link to inspect a book record.

The approximate first-use model downloads are E5 small 118 MB, E5 base 278 MB, and GTE base 340 MB. Browser cache behavior varies. Wait for the loading message before assuming the search has failed. A stable internet connection is required for the initial model download. Voice entry appears only where the browser supports its speech API.

If a model download is interrupted, the page offers an explicit **keyword-only preview** from the same book sample. This is a fallback for walking through the interface; it does not demonstrate semantic matching and must be described that way. Retry the chosen model when the connection is stable.

The fallback was checked on the deployed page with `chinese culture`: five linked cards appeared, **Show more books** expanded to ten, and no card showed a placeholder summary. Its topic fit was weak, so it should not stand in for a successful semantic-search demonstration.

## Meeting demo

Open `https://veedantbrahmbhatt.github.io/Libraries/` on a laptop with a current Chrome or Edge browser and stable internet. **Before the meeting, complete one actual model query in that same browser** so the default model is cached; a loaded page or the keyword-only preview does not prove semantic inference is ready. Explain that the first five results and their summaries come from metadata and the 1,891-book catalog is a limited prototype. Enter a new natural-language question live; the examples are optional. Compare models only if the meeting connection can handle their separate first-use downloads. The UI has no real student login, profile storage, or NYU catalog access.

## Publish and maintain

The `deploy-demo-pages.yml` workflow builds and tests `frontend/` from the purpose branch, then publishes `frontend/dist` to GitHub Pages. The branch's `frontend/public/data/` contains only the small, checked sample. `build-browser-demo-sample.yml` regenerates the sample on a temporary GitHub runner from pinned source/index revisions and saved result pools. `publish-browser-demo-sample.yml` verified and committed the sample once; its source artifact expires, so future regeneration should use a fresh build run and update its artifact run ID. Do not commit the 91,667-book Parquet source, full search index, model weights, `HF_TOKEN`, or local caches.

Update this runbook and the root README when the sample, models, ranking, hosting, or user flow changes. Check [the evaluation reports](../Evaluation/embedding-model-comparison-results.md) before making claims about search quality. The 40/50 target remains unmet and human review is pending.

## Verification on 2026-11-17

The [latest Pages deployment](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/44174658531) passed frontend tests and the production build; the [dependency-update deployment](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/44074832303) reported zero known npm vulnerabilities. The public page and its 1,884-book catalog load, and the hosted catalog hash matches the committed manifest. A real E5 small hybrid query completed in Chrome for `chinese culture`, showing ten ranked cards; their topic fit was weak. The Codex in-app browser separately interrupted a large Hugging Face model download, so pre-cache and check the desired model in the exact meeting browser before presenting. This verifies one functional query path, not the relevance of arbitrary results or all three models.


## Update the multilingual supplement

Edit `frontend/public/data/multilingual.json` with source links and original-language metadata, then run `node feedback-api/scripts/sync-catalog.mjs --refresh-manifest`. This updates the checksum and backend allowlist. Deploy the feedback service before publishing Pages. The base catalog publish workflow refreshes both files if the compact DOAB artifact changes.
