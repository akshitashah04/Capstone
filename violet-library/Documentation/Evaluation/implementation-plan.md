# Search-quality evaluation implementation plan

**Goal:** Collect comparable search results for a multilingual pilot in the cloud and score them only after complete human judgments exist.

**Architecture:** A query loader validates JSONL; a collector uses one `SearchEngine` instance for all three modes and writes a ranked run plus a deduplicated review sheet. A separate scorer validates the judged pool and computes quality and speed metrics. GitHub Actions downloads the pinned published index into temporary runner storage and exposes the small review files as an artifact.

**Tech stack:** Python 3.11, the existing `libraries_search` package, CSV/JSON from the standard library, pytest, Ruff, GitHub Actions, and the already published Hugging Face dataset.

## Global constraints

- Keep the source catalog, model weights, and full index off the laptop.
- Use the exact published index revision and this project's retrieval and ranking code.
- Do not create or infer real student profiles; do not use personal queries in the pilot.
- Do not report search-quality targets as achieved from unlabeled pilot results.
- Work on `evaluate-search-quality`, then update `README.md`, `Documentation/Evaluation/`, and `Documentation/HANDOVER.md` before merging to `main`.

## File map

| Path | Responsibility |
| --- | --- |
| `src/libraries_evaluation/queries.py` | Validate and load the question contract |
| `src/libraries_evaluation/collect.py` | Run the three search modes and write reproducible review files |
| `src/libraries_evaluation/score.py` | Validate human labels and compute metrics |
| `evaluation/queries/pilot.jsonl` | Clearly marked draft questions for a cloud pilot |
| `tests/test_evaluation.py` | Synthetic loader, collector, and scorer behavior |
| `.github/workflows/evaluate-search.yml` | Remote-only index download, pilot collection, artifact, and summary |
| `Documentation/Evaluation/runbook.md` | How to inspect, label, rerun, and interpret results |
| `Documentation/Evaluation/session-log.md` | Decisions, verification, cloud run, and limitations |

## Task 1: Query contract

1. Write failing tests for duplicate IDs, blank text, unsupported intent/split, and a valid multilingual JSONL file.
2. Implement `load_queries(path: Path) -> list[EvaluationQuery]` with explicit errors and stable order.
3. Add a small pilot question file, marked as authored prompts rather than student evidence.
4. Run focused tests, then commit the query contract and examples.

## Task 2: Candidate collection

1. Write a failing synthetic test using the existing fake book encoder and index builder; assert that one query produces three top-10 lists and one row per distinct candidate in the review sheet.
2. Implement `collect_results(engine: SearchEngine, queries_path: Path, output_dir: Path, *, index_revision: str, top_k: int = 10) -> dict` with warm timing, deterministic CSV order, and index/question provenance.
3. Add cloud-only CLI guards and a pinned `snapshot_download` call that fetches `search/v1/*` into runner temporary storage.
4. Run focused tests and lint, then commit the collector.

## Task 3: Judged scoring

1. Write failing tests for complete 0/1/2 labels, a missing pooled label, invalid grade, and a known-title mismatch.
2. Implement `score_results(queries_path: Path, run_dir: Path, judgments_path: Path) -> dict` with Success@5, pooled nDCG@10, known-title top-one, p95 warm time, split/language sample counts, and hybrid improvement.
3. Require every pooled query–book pair to be judged and reject duplicate or changed run rows.
4. Run focused tests and lint, then commit the scorer.

## Task 4: Cloud operation and handover

1. Add `libraries-collect-evaluation` and `libraries-score-evaluation` console entries and a GitHub Actions workflow that uses only temporary runner storage for the index/model.
2. Upload `runs.csv`, `review.csv`, and the provenance manifest as a short-lived artifact; render a compact job summary in GitHub.
3. Run all synthetic tests, lint, CLI guards, and workflow syntax checks; push the purpose-named branch and confirm CI.
4. Merge to `main`, inspect the pilot cloud run and artifact metadata, then record exact results and any failures in the README, evaluation runbook/session log, and handover.

No final relevance target is claimed in this phase until people supply and review real judgments.
