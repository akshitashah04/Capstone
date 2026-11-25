# Search-quality evaluation design

## Scope and decision

The user approved evaluation as the phase after publishing the search index. This phase measures our existing keyword, semantic, and hybrid ranking on the same questions. It does not change the model, build a student portal, or use real student profiles. The first cloud run is a **pilot** that prepares results for human review; it cannot establish relevance quality without judgments.

The recommended approach is a reproducible GitHub Actions job. It downloads the exact published `search/v1` index on a temporary runner, runs this project's `SearchEngine`, and uploads a small candidate-review sheet. A separate scoring command reads completed human judgments and rejects incomplete ones. This keeps the full catalog and index off laptops, gives teammates one GitHub source for code and records, and prevents missing labels from becoming false negative examples.

## Inputs and outputs

| Item | Contract |
| --- | --- |
| Published index | Hugging Face dataset commit `f54ded49b97a92ca8e5dce0463500043ea2a19a4`, path `search/v1/` |
| Questions | UTF-8 JSONL; stable `query_id`, `text`, `language`, `intent`, and `split`; `expected_book_id` only for known-title questions |
| Pilot questions | A small, openly marked draft set covering several subjects and languages; it is not a representative student sample |
| Candidate run | CSV of top 10 results per question for keyword, semantic, and hybrid, with ranks and warm query times |
| Review sheet | One CSV row per distinct question–book pair across the three modes, with metadata, a short abstract excerpt, source link, and an empty `relevance` cell |
| Human judgments | The same review rows with `relevance` filled as 0 (not useful), 1 (partly useful), or 2 (clearly useful) |
| Scored report | JSON with sample counts, Success@5, pooled nDCG@10, known-title top-one rate, p95 warm time, language and split breakdowns, abstract-availability counts, and hybrid versus keyword difference |

The cloud run records the index manifest checksum and question-file checksum. Candidate files are GitHub Actions artifacts with limited retention; the source questions, later completed judgments, code, and documentation belong in Git. The job summary shows top-result examples and the full review pool in the browser.

## Measurement rules

- Collect all three search modes with the same top-10 cutoff and the same query text.
- Warm each mode once before timing; report each measured search time and its nearest-rank p95.
- Pool the union of the top-10 books from all modes for each question. Every pooled pair must have a human label before a scored report is accepted.
- Success@5 requires a clearly useful book (`relevance=2`) in the first five.
- Pooled nDCG@10 uses graded gains `2^relevance - 1` and the judged pool as the ideal list; it does not measure books outside the pool.
- Known-title top-one compares the first book ID with the explicitly supplied expected ID.
- Report development and holdout questions separately; do not tune settings against the holdout results.
- Preserve language and question type so sparse or weak groups are visible rather than hidden inside one average.
- Never call RRF scores or cosine similarity confidence probabilities.

## Gates and limits

The pilot can verify the evaluation machinery and expose examples for review. The provisional project targets are at least 80% Success@5, at least 10% higher hybrid nDCG@10 than keyword-only, 95% known-title top-one, and 95% of warm searches within two seconds. Do not claim those targets are met until the team has 100–150 natural student-style questions across intended languages, complete human judgments, and a held-out assessment. Questions must contain no names, email addresses, or student profile details.

The source covers 91,667 exported DOAB books, not proven coverage of every live DOAB title. Record a genuinely absent book separately from an irrelevant returned book. A result with no abstract may be harder to judge from the review sheet; its DOAB link remains available.

## Failures

Reject duplicate question IDs, blank questions, unsupported modes, missing or changed index files, duplicate result IDs within one query/mode, invalid grades, missing pooled judgments, and mismatched run/question files. Fail the score command rather than silently treating an unjudged book as irrelevant. Temporary cloud files are removed after each run.
