# Answer-derived diagnostic implementation plan

**Goal:** Assess the existing search with separately marked AI relevance judgments and frozen book-derived retrieval questions.

**Architecture:** A compact AI grade file overlays the verified pilot review pool for the existing scorer. A target-recovery scorer compares ranked results with one known source-book ID per new question. GitHub Actions runs the new questions against the pinned index on temporary storage.

**Tech stack:** Python 3.11, existing search/evaluation packages, CSV/JSON, pytest, Ruff, GitHub Actions.

## Global constraints

- No full catalog or index on a laptop; the only local input is the small published review artifact.
- Keep AI judgments separate from human grades, and do not represent answer-derived questions as natural student queries.
- Freeze query/target files before the new cloud run and report all three modes on the same questions.
- Use a purpose-named branch and update README, evaluation docs, and handover.

## Tasks

1. Record the deterministic target selection and hand-write 24 paraphrased multilingual questions from the selected descriptions. Validate IDs, languages, and target coverage.
2. Write failing synthetic tests for complete AI grade overlay, missing/duplicate grades, and target recovery metrics; implement the smallest standard-library scoring helpers.
3. Grade all 233 pilot pairs from the saved metadata, document the rubric, preserve exact book IDs, and score the existing run without changing human sheets.
4. Add a cloud workflow for the frozen 24 questions, run it, verify artifact provenance, and score target recovery for keyword, semantic, and hybrid.
5. Compare both diagnostic reports with the provisional KPI bars, record failures and sample-size limits, update the handover and README, run all checks, and publish the branch to `main` after CI passes.
