# OpenSquare Discover

A working NYU Libraries capstone prototype for discovering **329 real NYU Press OpenSquare books** through semantic, keyword, and hybrid search. Independent student research prototype; not an official NYU service.

## Separate sponsor proposal

[NYU Library Next](proposal/README.md) is a separate proposed library experience with Google Books discovery, advanced filters, optional neural reranking, a source-grounded services assistant, and an honest Bobst reservation handoff. The original OpenSquare prototype below remains preserved. The Pages workflow builds both apps, with the proposal at `/proposal/`.

## What works

- Natural-language thematic search using **latent semantic analysis (LSA)**, a real corpus-trained NLP model with 96-dimensional embeddings.
- Keyword retrieval with BM25 and a hybrid score combining both methods.
- Side-by-side comparison of the top five results from each method.
- Subject, publication-year, and author filters; relevance, year, and title sorting.
- Per-result score explanations, related books, full publisher descriptions, and links to original OpenSquare pages.
- Reading list saved in the current browser, CSV export with ranking scores, accessible dialogs, responsive layouts, and empty/error states.
- Reproducible collection/index scripts, search tests, browser checks, an editable relevance set, and evaluation reports.

## Run locally

Requires Node.js 22 or newer and npm.

```sh
npm ci
npm run dev
```

Open http://localhost:3000. The checked-in catalog and model are ready to use. No API key, Python server, vector database, or external AI inference is required. Do not open index.html directly with file://; serve it through Vite or a static HTTP server.

```sh
npm test
npm run evaluate
npm run build
npm run preview
```

`dist/` is the deployable static website. Relative asset paths support GitHub project Pages at `/Capstone/` as well as other static hosts.

## Publish through GitHub Pages

The `.github/workflows/pages.yml` workflow tests, evaluates, builds, and deploys pushes to `main`.

1. If your GitHub plan does not support Pages for private repositories, make this repository public at **Settings → General → Danger Zone → Change repository visibility**. Review the repository contents first.
2. Open **Settings → Pages → Build and deployment → Source** and choose **GitHub Actions**.
3. Open **Actions → Test and deploy OpenSquare Discover → Run workflow** if the initial push ran before Pages was enabled.
4. Wait for both `build` and `deploy` jobs to finish. Use the deployment URL returned by the workflow.

Expected project URL after successful deployment: `https://akshitashah04.github.io/Capstone/`. This is an expected address, not a claim that deployment has completed. A private source repository does not necessarily make its Pages website private.

## Retrieval architecture

```text
Published OpenSquare catalog + publisher descriptions
  → normalize records
  → accent normalization, stop-word removal, Porter stemming
  → TF–IDF document-term matrix
  → truncated SVD / LSA (96 dimensions)
  → normalized book embeddings + term projection
  → query projection in the browser
  → cosine similarity + BM25
  → filtered, ranked books + explanation
```

The matrix is factorized through an eigendecomposition of its document Gram matrix. Title and subtitle terms are repeated twice and subjects twice to give them extra weight. Vocabulary terms must occur in at least two records. Each TF–IDF document is L2 normalized before training. Queries use the same tokenizer, IDF weights, and projection.

| Mode | Score |
| --- | --- |
| Semantic | Nonnegative cosine similarity between LSA embeddings |
| Keyword | `1 - exp(-BM25 / 8)` with `k1 = 1.2`, `b = 0.75` |
| Hybrid | `0.65 * semantic + 0.35 * keyword` |

Semantic results require cosine ≥ 0.12. Hybrid also includes any book with a positive BM25 match. Empty queries browse the catalog. A wholly unknown query returns no matches. Multiple selected subjects use OR; year and author filters combine with AND.

**Scores are retrieval signals, not confidence percentages, probabilities, or judgments of book quality.** The UI displays decimals to avoid implying calibrated confidence. Weights and thresholds are prototype defaults and have not been optimized on librarian judgments.

## Data provenance

All records and all 329 descriptions come from the published HTML in [NYULibraries/dlts-open-square](https://github.com/NYULibraries/dlts-open-square), under `docs/books/`. Source URLs, collection timestamp, and source ref are retained in `public/data/books.json`. The initial catalog is a November 14, 2026 snapshot. The source repository is the published-site export and may differ from the live production catalog.

Included fields: identifier/ISBN, title, subtitle, author/editor display string, subjects, publication year, description, source URL, metadata URL, access status, and cover URL. English is a prototype metadata assumption, not a verified language field for every book. Access status reflects catalog membership at collection time. No full book text, OCR, chapters, or downloadable PDFs have been ingested. Google Books enrichment is not implemented and no Google Books data is claimed.

Cover images load from the publisher’s image service. If they are unavailable, the interface renders a typographic placeholder, not a counterfeit publisher cover. The app itself sends no search queries to an AI API. The image host may receive ordinary image requests.

To refresh from the public source (curl and internet access required):

```sh
# For a pinned, reproducible snapshot, supply a Git commit SHA as SOURCE_REF.
SOURCE_REF=main npm run collect
npm run index
npm run evaluate
npm test
npm run build
```

Raw HTML is cached in ignored `.cache/books/`. Remove that cache before refreshing existing records. Commit updated `books.json` and `index.json` together; the app checks that book IDs align.

## Evaluate honestly

`scripts/judgments.json` contains six starter queries with author-created graded topic judgments. `npm run evaluate` writes per-query and mean **Precision@5, Recall@5, MRR@5, and nDCG@5** to `public/data/evaluation.json` for all three methods. Unjudged records are treated as nonrelevant; judgments are incomplete. These results are a reproducible demonstration, not a validated benchmark or proof of improvement over production OpenSquare.

For the capstone study: ask librarians to judge a broader set of query–book pairs, include known-item, paraphrase, negation, out-of-domain, and cross-disciplinary queries, separate tuning and held-out test sets, then compare BM25, LSA, hybrid, and a transformer model on the held-out set. Report latency and qualitative failure cases as well as retrieval metrics.

## Browser checks

The browser test covers search, comparison, filtering, persistence, details, source links, CSV downloads, out-of-vocabulary queries, and mobile overflow. Locally the configuration uses system Chromium at `/usr/bin/chromium`:

```sh
npm run dev
# in another terminal
npm run test:browser
```

For another OS, change `launchOptions.executablePath` in `playwright.config.js` to your installed Chromium or remove it and install Playwright's browser. The deployment workflow runs the nine search/data tests and production build; browser tests were also run locally.

## Limits and next steps

LSA learns catalog word co-occurrence; it is not a pretrained transformer, an LLM, or a question-answering service. It can miss nuanced intent and unfamiliar synonyms and may retrieve broadly related but unhelpful books. It does not reliably understand negation. The corpus is small, English metadata focused, and snapshot based.

A suitable next experiment is a MiniLM or E5 embedding model, evaluated against this baseline. For chapter-level retrieval, first obtain permission/appropriate licenses, ingest permitted full text, chunk it, preserve page-level provenance, and evaluate passage citations. Only integrate with NYU's production API or brand as an official service with project-owner approval.

Publisher metadata, descriptions, trademarks, and cover artwork remain with their respective rights holders. Their inclusion in this research prototype does not grant redistribution rights for full books or covers. Original application code is provided under the MIT License; that license excludes third-party content in `public/data/` and remote images.
