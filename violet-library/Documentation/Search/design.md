# Search index design — 2026-11-14

## Goal and boundary

Build a reproducible search baseline for the published DOAB metadata. Our code selects candidates and ranks them from the start. Hugging Face stores the input and output files; it does not run a search. GitHub Actions does the full index build on a temporary runner. No real book dataset or index is placed on a team member's laptop. The UI, voice input, student accounts, personalization, and graph model are outside this phase.

## Fixed inputs

- Dataset: `Tox1/LibrariesBookData`, revision `daba70f6e6de9f7a5c9a1f830fd255415c6d6bb7`, with 91,667 books and schema version 1.
- Model: `intfloat/multilingual-e5-small`, revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`, MIT license, 384 output dimensions.
- The source manifest's Parquet checksum is checked before indexing. Changes to the source or model revision require an explicit code and documentation update.

## Data flow

1. Download the pinned Parquet and manifest into GitHub's temporary runner storage.
2. Build a local SQLite full-text index over title, authors, subjects, and abstract. SQLite's BM25 score provides our keyword candidate order.
3. Encode each book's existing `semantic_text` using E5 with the required `passage: ` prefix. Keep one normalized 384-dimensional vector per book, in the same order as SQLite's numbered rows. The model truncates long text at 512 tokens; the preparation step puts title and subjects before the abstract.
4. Validate book count, unique IDs, vector shape and values, row alignment, and file checksums. Write a manifest containing source and model revisions, sizes, and checksums.
5. Upload only `search/v1/` files to the same Hugging Face dataset in one commit. Metadata files remain separate.
6. At query time, the search service loads these artifacts in a remote demo environment. E5 encodes the query with `query: `; our code compares it with every book vector. SQLite independently finds keyword matches. Our code combines the two ranks with reciprocal rank fusion (RRF), with deterministic ties.

## Failure behavior

The job stops before upload if the source checksum changes, the schema or row count differs, a vector is invalid, SQLite and vectors disagree, or the bundle checksum fails. Missing `HF_TOKEN` stops publishing without exposing a secret. The runner deletes temporary files after every run. A failed build leaves the previously published search snapshot in place.

## Outputs and interpretation

The output is a SQLite keyword index, a NumPy vector file, and a manifest under `search/v1/` in `Tox1/LibrariesBookData`. Query results include the book's display metadata, keyword and semantic ranks, and an RRF ranking score. These scores are relative ordering signals, not probabilities or calibrated confidence. No claim of improved relevance is made until people judge representative student queries.

## Alternatives considered

- A provider search API would choose the first candidates, which conflicts with the project's control requirement.
- Training a new model now would require query-to-book labels that the metadata does not contain.
- A graph autoencoder was discussed and rejected for this phase. It may be a later experiment against the same judged queries.
