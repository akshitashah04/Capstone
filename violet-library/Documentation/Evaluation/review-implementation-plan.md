# Human review handoff implementation plan

**Goal:** Put the pilot's ungraded results in GitHub as compact per-question sheets, validate partial progress, and score only complete human judgments.

**Architecture:** `review.py` initializes a versioned sheet set from a verified cloud artifact, checks grades and the frozen question–book pool, and assembles a temporary full judgment CSV from a fresh cloud run. A lightweight workflow reports progress; the existing cloud workflow scores only when the review is complete.

**Tech stack:** Python standard library, existing evaluation package, pytest, Ruff, GitHub Actions.

## Global constraints

- Keep the full 91,667-book catalog, model weights, and index off team laptops.
- Use the pinned published index and project-owned retrieval/ranking code.
- Never create grades in code or claim that blank grades are irrelevant.
- Use a purpose-named branch; update the root README, evaluation docs, and handover.

## File map

| Path | Purpose |
| --- | --- |
| `src/libraries_evaluation/review.py` | Initialize split review sheets, validate progress, assemble complete judgments |
| `evaluation/review/pilot/` | Shared, ungraded per-question sheets and source manifest |
| `tests/test_review.py` | Synthetic progress, missing/extra row, invalid grade, and assembly tests |
| `.github/workflows/review-progress.yml` | Lightweight checks on grading edits |
| `.github/workflows/evaluate-search.yml` | Assemble and score only a complete pilot after collection |
| `Documentation/Evaluation/runbook.md` | Browser grading and cloud scoring steps |

## Task 1: Review contract and initialization

1. Write a failing test that builds a tiny synthetic `review.csv` and manifest, then expects one sheet per query with blank grades and a frozen pair digest.
2. Implement artifact checksum and query validation, deterministic per-query CSV output, and the manifest.
3. Run the focused test and lint; commit the review contract.

## Task 2: Progress and assembly

1. Write failing tests for partial counts, complete assembly, invalid grade, missing/extra/duplicate pair, and changed candidate pool.
2. Implement `review_progress(queries_path, review_dir)` and `assemble_judgments(queries_path, review_dir, run_dir, output_path)`.
3. Ensure assembly creates no output until every row is graded and the frozen pool matches the freshly collected run.
4. Run the focused and full tests and lint; commit the implementation.

## Task 3: Cloud and handover

1. Add a lightweight progress workflow and change the full evaluation workflow to use the split sheets without treating a partial review as failure.
2. Generate the 12 ungraded sheets from the verified 233-pair pilot artifact; check their digest and row counts.
3. Update README, runbook, evaluation record, and handover with exact review instructions and limits.
4. Verify locally, push the branch, confirm CI, merge to `main`, and inspect the lightweight and cloud jobs.
