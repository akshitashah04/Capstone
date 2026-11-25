# Search Baseline Implementation Plan

**Goal:** Build and publish versioned keyword and multilingual semantic indexes for the pinned DOAB snapshot, plus an independently testable search command.

**Architecture:** Keep source download, lexical indexing, vector encoding, bundle validation, publishing, and query ranking in separate modules under `src/libraries_search/`. GitHub Actions owns full-data processing. Unit tests use small synthetic catalogs and a fake encoder, never real DOAB files.

**Tech stack:** Python 3.11, PyArrow, SQLite FTS5, NumPy, Sentence Transformers with pinned E5 weights, Hugging Face Hub, GitHub Actions.

## Tasks

1. Define versioned source/model configuration and a verified input download. Test revision and checksum rejection with synthetic files.
2. Build a SQLite book table and FTS5 index from Parquet batches. Test row order, ID uniqueness, and keyword ranking.
3. Add batched E5 encoding through a narrow encoder interface. Test vector count, dimension, finite values, and alignment with fake encoders.
4. Add a manifest, bundle validation, and atomic publishing of only `search/v1/` artifacts. Test corruption detection and upload arguments.
5. Implement a query engine with independently selected keyword and semantic candidates, RRF, pagination, and deterministic ties. Test exact-title, semantic, hybrid, and malformed-query cases.
6. Add a manually dispatched GitHub Actions build/publish workflow, using temporary runner storage and `HF_TOKEN` only for upload. Run the full job and verify the remote manifest and files.
7. Update README, Model, Evaluation, Search runbook, session record, and handover. Record results and limitations, including uncalibrated scores and the DOAB coverage gap.

## Verification gates

- `ruff check .` and `python -m pytest -q` pass locally and in GitHub Actions.
- The full build reads the pinned 91,667-book snapshot; all vectors are 384-dimensional and aligned with unique book IDs.
- The published manifest names both source and model revisions and matches remote file checksums.
- The query smoke test runs on the GitHub runner. This is a functionality check, not a relevance-quality claim.
