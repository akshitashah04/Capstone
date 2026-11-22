# November 17 sponsor follow-up

Implemented in the existing proposal; the original OpenSquare prototype and its 329-book collection remain separate.

## Sponsor requests and delivered behavior

| Request | Implementation | Boundary |
| --- | --- | --- |
| Add non-English books, especially Chinese and Hindi | A separate four-record research pilot includes 論語 (Chinese, Confucius) and निर्मला (Hindi, Premchand), with original source links, native-script metadata and curated aliases. Hindi language filter; Unicode-safe matching and deduplication. | Two native-language records are a starting pilot, not broad multilingual coverage. Annotations are capstone-authored, not publisher abstracts. No unrestricted translation claim. |
| Compare metadata with actual book content | A research lab compares the same 333-book collection across metadata only, metadata plus opening 10%, and metadata plus full selected digital edition. Two English books have real, chunked content. Actual word coverage, chunk counts and source passages are visible. | Only two texts have body content. Hindi and Chinese records remain metadata-only. Opening 10% is not a representative sample; full text creates more opportunities to match. |
| Use feedback to improve ranking | Rating 0–3 changes order for the same normalized query using bounded local relevance feedback. Toggle original order, compare ranks, undo last round, reset query, persist locally, export. Exact-title/ISBN priority remains protected. | This is browser-local reranking, not embedding fine-tuning, collaborative learning or a validated accuracy gain. |
| Explain tokenization, embeddings and workflow | Search pipeline tab and standalone SVG show sources, actual text coverage, tokenization, small LSA model, retrieval, feedback and evaluation. | Model and dataset limitations are explicit. |
| Explore a specialized model rather than prioritize a large commercial LLM | Research corpus TF-IDF/SVD LSA with 64 dimensions; built locally with no paid model, API or GPU. | Statistical corpus semantics, not a small generative language model. Existing optional chatbot Gemini integration remains inactive. |

## Sources and rights

- Chinese metadata: https://www.gutenberg.org/ebooks/23839 (論語, Confucius, Chinese); source checked November 22, 2026.
- Hindi metadata: https://hi.wikisource.org/wiki/निर्मला (Hindi novel, Premchand); source checked November 22, 2026. Native work title/author and a short original catalog annotation are indexed; Wikisource body text is not redistributed.
- English content: The Art of War, Lionel Giles translation, Gutenberg #17405, https://www.gutenberg.org/ebooks/17405. This is the edition without Giles's commentary, rather than Gutenberg #132.
- English content: The Principles of Scientific Management, Frederick Winslow Taylor, Gutenberg #6435, https://www.gutenberg.org/ebooks/6435.
- Source files fetched from GITenberg mirrors; exact mirror URLs and SHA-256 hashes are recorded in `public/research/catalog.json`. Complete license material remains in the raw text files. Boundary material is excluded from retrieval. These editions are public domain in the USA; source license terms are retained.

## Reproduce the experiment

From `proposal`, run `npm ci`, then `npm run research:build`. Generated research catalog, index, coverage/chunks, evaluation JSON and diagram are tracked in `public/research/` so production requires no training or GPU.

1. Keep the original 329 OpenSquare records, add four pilot records.
2. Verify raw source hashes and strip Gutenberg start/end boundaries.
3. Count whitespace-delimited body words; select first `ceil(N × 0.1)` for partial coverage.
4. Form chunks of 180 words, overlap 30 words. Coverage counts unique words, not repeated overlap. Full coverage means the complete included digital edition, including any edition front matter within its body boundaries.
5. Unicode NFKD normalization and lowercasing; English stop words/stems, Hindi words with combining marks preserved, Chinese character unigrams and bigrams. This is basic segmentation, not a linguistically complete tokenizer.
6. Fit TF-IDF/SVD once on all pilot metadata and full-text chunks. Limit vocabulary to 1,600 terms, reserve the native-script pilot terms before filling by document frequency, and retain 64 dimensions. Freeze this same model across all comparison conditions. This is a transductive development experiment; full text participates in fitting even in metadata retrieval condition.
7. Score cosine (60%) plus normalized BM25 (40%), aggregate highest supported chunk/metadata score per book. BM25 document statistics vary by condition; more chunks and different lexical statistics are confounds. Do not interpret differences as an isolated causal model improvement.
8. Save the top results and Precision@5, Recall@5, nDCG@5, MRR for seven fixed development queries. See `public/research/evaluation.json`.

The seven provisional query judgments are authored development checks with one target per query, not independent librarian labels or a held-out test. Unlisted books are provisionally nonrelevant. They demonstrate reproducibility and differences on these cases, not superiority over NYU's system. Obtain broader relevance labels, include negative controls and paraphrases, freeze a held-out set, and compare models before making research claims. A focused AI/business collection remains a useful next sponsor validation scope.

## Feedback details

For a judged book, reranking adjustment is `(grade − 1.5) × 0.12`, between −0.18 and +0.18. Add it to the underlying retrieval score for ordering only; the displayed match score is unchanged. Latest explicit judgment wins for that book and normalized query. Exact ISBN/title priorities remain above thematic matches. Other queries are unaffected. Other sorts retain their order. Local feedback is not used in the controlled content comparison.

Assessments and feedback are kept in local browser storage; they are not sent to NYU or combined across users. Exported results include base rank, judgment, adjustment and ordering signal. Toggle, undo and reset support inspection. This is an interpretable baseline; the adjustment constant is not empirically optimized.

## Remaining external dependencies

No request was sent to Chris or the sponsor. If a larger content experiment requires GPU resources, the team still needs to ask Chris Policastro, as requested in the meeting. Live room availability still requires authorized NYU LibCal credentials; NYU holdings still require the institutional integration. These unrelated pending integrations are unchanged.
