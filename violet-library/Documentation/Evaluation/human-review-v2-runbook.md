# V2 human-review runbook

## Inputs and provenance

`evaluation/query-fit/reranked-run.zip` contains the pinned DOAB v2 results for 50 authored development questions. `evaluation/query-fit/otl-coverage-run.zip` contains the separate textbook results for 19 earlier misses. Their original ZIP checksums, embedded result checksums, question checksum, and source revisions are recorded in `evaluation/review/query-fit-v2/doab/manifest.json` and `.../textbook/manifest.json`. Do not replace either ZIP or regenerate sheets against a new search run under these folder names.

The book corpus, vector index, and model are **not** needed for this phase. The two saved ZIPs are small. The full source stayed on temporary cloud runners during the earlier search jobs; no provider selected candidates.

## Review on GitHub

Open [the packet guide](../../evaluation/review/query-fit-v2/README.md), assign whole question files among reviewers, and edit only the four grade columns. Each question file is a separate Git file, reducing merge conflicts. Use a purpose-named branch and a pull request for changes. The existing `review-progress.yml` Action runs after changes and reports counts for the old v1 pilot, the v2 DOAB packet, and the separate textbook packet. It will not call a model or download the index.

To check locally using only the committed small files:

```bash
PYTHONPATH=src python -m libraries_evaluation.review_packet progress \
  --queries evaluation/queries/student-personas.jsonl \
  --archive evaluation/query-fit/reranked-run.zip \
  --packet-dir evaluation/review/query-fit-v2/doab

PYTHONPATH=src python -m libraries_evaluation.review_packet progress \
  --queries evaluation/queries/student-personas.jsonl \
  --archive evaluation/query-fit/otl-coverage-run.zip \
  --miss-report evaluation/personas/miss-audit.json \
  --packet-dir evaluation/review/query-fit-v2/textbook
```

Once a packet is fully graded, GitHub Actions uploads its small score JSON. The same report can be reproduced locally by replacing `progress` with `score` and adding `--output /tmp/doab-human-scores.json` or `--output /tmp/textbook-human-scores.json`. `score` fails while any pair is ungraded. It never substitutes assistant ratings for people.

## Later acceptance test

Ask intended users to contribute book-finding questions without names, email addresses, student IDs, profiles, or course records. Follow [question collection](question-collection.md). Freeze a new JSONL question file and hold out roughly one fifth before changing the ranking. Run `libraries_evaluation.rerank_diagnostic` only on a temporary GitHub runner, save the compact result ZIP, and initialize **new** review packets in a new versioned folder. Do not repoint the current 50-question sheets. The generic packet tool will report development and holdout scores separately, but an actual student holdout does not exist yet.

Before a public demo, also confirm the chosen search mode's response time on its target free host. The experimental second ranker took about 7.5 seconds at the 95th percentile on a temporary runner, exceeding the provisional two-second bar. GitHub Pages can serve a static page but cannot run the Python search process on its own.
