# NYU Library Next — sponsor proposal

This is a **separate proposed site** alongside the original OpenSquare prototype at the repository root. It does not replace or modify NYU's production services.

Hosted private review copy: https://nyu-library-next-capstone.sound-park-7168.chatgpt.site

## Experience

- Broader discovery through the Google Books Volumes API, combined with the 329-book OpenSquare metadata snapshot.
- Advanced title, author, ISBN, subject, publication-year, language, access, and ranking controls.
- Exact title/ISBN priority; BM25 + corpus LSA; optional in-browser MiniLM neural reranking.
- Source labels, metadata descriptions, score explanations, original-record links, and separate NYU catalog checks.
- Browser-local bookshelf, basic citation copying, and CSV export.
- A source-grounded **routing chatbot**, with retrieved book suggestions and NYU service links. It is not an LLM and does not invent a conversational answer to unsupported questions.
- Policy-aware Bobst study planning, with a handoff to NYU LibCal for actual availability and NetID booking.
- Local relevance-assessment form with 0–3 judgments, anonymous reviewer codes, notes, time-to-find, expected titles, and JSON export. Unjudged results remain null rather than being treated as irrelevant.
- Sponsor brief explaining capabilities, remaining integrations, source limitations, and an evaluation plan.

## Run

Requires Node.js 22+.

```sh
cd proposal
npm ci
npm run serve  # API server on 127.0.0.1:3101
# In another terminal, in proposal/
npm run dev    # app on port 3001
```

Set `GOOGLE_BOOKS_API_KEY` in the server/hosting environment for a project-owned quota. It is optional in the implementation: without it the proxy attempts public requests, which can be refused or rate limited. Do not paste an API key into chat, use a `VITE_` key, commit `.env`, or expose it to browser code. `.env.example` only documents the server variable. The Node development server reads the process environment; it does not automatically load `.env`.

The hosted Sites build includes a same-origin `/api/books` proxy. GitHub Pages cannot run this server; the static app there detects the absent API route and attempts direct public Google Books calls without a key. Reliable quota and private API credentials require a server-backed host. A Google Books result is **not** proof of NYU ownership, borrowing eligibility, or full-text entitlement.

## Models and retrieval

`src/discovery.js` implements normalization, API queries, deduplication, and ranking. Candidate acquisition is separate from reranking: a reranker cannot recover a relevant book absent from its candidate set.

- Up to 40 Google Books candidates per call, 240 per session; up to 60 OpenSquare candidates.
- Title/author/ISBN query operators; language and full-view constraints sent to Google.
- Additional constraints applied to retrieved records. Counts are local matching-record counts, not exhaustive Google catalog counts.
- Edition deduplication by ISBN or matching title and author. Records without an ISBN can still represent different editions.
- Exact-title and ISBN matches receive priority independently of the blended score.
- Default hybrid = 0.60 semantic cosine + 0.30 normalized BM25 + 0.10 provider-rank signal.
- BM25 `k1=1.2`, `b=0.75`; normalization `1-exp(-BM25/6)`.
- Default semantics: the original 96-dimensional OpenSquare LSA projection. It is limited outside the original corpus vocabulary.
- Optional semantics: quantized `Xenova/all-MiniLM-L6-v2`, mean pooling and normalized embeddings in a Web Worker, reranking up to 60 candidates. Downloaded from Hugging Face via Transformers.js 3.7.3; the JavaScript module is delivered through jsDelivr. Browser network/storage/model support is required. It is English-oriented, not a validated multilingual model. Language filters do not imply equally good semantic quality in every language.

Google may rank broadly related results that are not appropriate for a user's intent. Known sponsor regression topics (AI risk, global warming, classical music, architecture) use conservative metadata evidence checks. These can reduce recall and are not a general-purpose semantic safety guarantee. Ambiguous `911` searches ask for clarification rather than silently assuming a topic. The UI never displays similarity as confidence percentages.

## Sponsor materials reviewed

Read-only review of the user-provided Drive folder included:

- `NYU LIBRARIES - Kickoff_updated.pptx`: semantic discovery, working MVP, sponsor integration, and a feedback-driven assessment loop.
- `Open Square Beta Testing_Refined.xlsx`: examples where unrelated results had nontrivial similarity scores, plus a stale-query input issue explicitly marked fixed in the sheet.
- `NYU_Library_Portal_Comparison_Final2 (1).pdf`.
- `NYU BobCat Exploratory Research Comparison and Peer Benchmarking.pdf`: distinguishes broad NYU catalog discovery from the smaller open-access portals and records uncertainties in the team's public-page research.

The live NYU NLP beta was inaccessible through the available tools. No claim is made that the new proposal outperforms the current beta. No private Drive documents, personal profiles, or account records are ingested into the public search corpus. Repository tests use a few topic queries as targeted regression examples rather than copying the source documents. Claims in sponsor documents are research context, not independently verified current institutional facts.

## Rooms and library services

Official sources are in `src/services.js`, checked November 14, 2026:

- https://nyu.libcal.com/reserve/bobst-group-study
- https://library.nyu.edu/spaces/bobst-group-study-rooms/
- https://library.nyu.edu/spaces/individual-study-rooms-bobst/
- https://library.nyu.edu/locations/elmer-holmes-bobst-library/
- https://library.nyu.edu/services/borrowing/nyu/

The planner validates a date within 14 days, group size of 2–6, half-hour increments, and a duration of 30–180 minutes in New York time. It cannot enforce one reservation per day because it cannot see accounts. The plan is not a reservation. It does not display synthetic availability, invent room identifiers, issue booking confirmations, or submit a booking. Actual inventory, capacities, eligibility, holidays, and authentication remain with NYU. Group sizes above six are directed to NYU for suitable space advice.

For integrated live availability, the sponsor must provide authorized LibCal access/API details. For holdings and entitlements, use approved Alma/Primo APIs. For authenticated renewals or bookings, use NYU-approved identity, authorization, and transactional APIs. This prototype does not ask for NetID passwords.

## Tests and evidence

```sh
npm test
npm run build
npm run build:worker
# With dev server running and Chromium installed:
npm run test:browser
```

Tests cover normalization, Google request construction, exact matches, deduplication, known bad-match regressions, filters, intent routing, room constraints, API key handling, quota/network failures, stale query responses, bookshelf persistence/export, assistant suggestions, mobile overflow, and official service handoffs.

Google API calls were blocked by the development environment's outbound policy. The adapter's success and failure paths were tested with isolated fixtures. Those fixtures are test-only and never shipped as Google results. The actual neural model download is subject to the same network limitation; the fallback is surfaced in the interface. Do not describe either as live-provider-validated unless a deployed request/model load is verified.

The original six-query evaluation in the root project applies only to that original prototype. It is not evidence for Google Books or neural retrieval quality. Before choosing a production model, freeze librarian relevance judgments across known-item, topical, paraphrase, negation, multilingual, and out-of-domain queries, and report Recall@10, nDCG@10, MRR, latency, coverage, and failure cases on a held-out test set.

## Hosting

`npm run build` produces a static Vite app. The root GitHub Pages workflow builds both prototypes and places this proposal under `/proposal/`.

`npm run build:worker`, after the frontend build, bundles the client assets and same-origin Google Books proxy into `dist/server/index.js` for Sites/Cloudflare Workers. `.openai/hosting.json` retains this proposal's Site identity. It is not shared with the original prototype. Configure server secrets in the host's environment settings. Never publish local `.env` files.

The original application code license in the repository root applies; publisher records, descriptions, cover artwork, trademarks, and third-party model/software licenses retain their own terms.

### Google Books connection setup

See [the Google Books setup guide](docs/GOOGLE_BOOKS_SETUP.md) for Google Cloud API enablement, a server-side secret, redeployment, and verification. The app now distinguishes missing/invalid keys, disabled APIs, key restrictions, quota errors, and network errors. Where no server key is configured, it may attempt the same public API directly from the visitor's browser; this is still subject to Google's access rules and quota. Google-only errors no longer claim that an empty result set contains OpenSquare records.
