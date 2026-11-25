# Data preparation design

## Objective

Build a repeatable, free process that streams DOAB's direct full repository CSV export, keeps book records, and publishes a compact, model-neutral catalog to `Tox1/LibrariesBookData`. DOAB selects no search candidates for the eventual application. The workflow runs on a temporary GitHub Actions runner; actual DOAB records are not stored in this Git repository or on a team member's laptop.

The 2026-11-14 export contained 91,667 book records, while DOAB's live site advertised over 111,000. This pipeline covers the available export snapshot and does not assert that every live-site title is present.

## Data flow

1. Stream the official DOAB full repository export over HTTPS. Validate essential column names before processing records.
2. Select `dc.type=book`. Normalize useful fields without translating text or removing accents. Keep original multilingual text.
3. Drop records without a stable DOAB ID or title. Deduplicate by DOAB ID only, so distinct editions and translations remain distinct.
4. Write compressed Parquet in bounded batches. Keep original search fields alongside a derived `semantic_text` field.
5. Write a machine-readable manifest and quality report. Reject suspiciously small complete runs.
6. Upload the dataset artifacts together in one Hugging Face commit, using a repository-scoped token from the GitHub Actions secret `HF_TOKEN`.

The workflow runs when pipeline code, dependencies, or its own definition changes on `main`, and it can also be started manually. Documentation-only changes do not download the full feed.

## Boundaries

- This phase prepares metadata, not book full text, embeddings, a retrieval index, relevance labels, confidence scores, a login system, or a UI.
- Book licenses vary. The DOAB metadata feed is CC0; the catalog retains each book's license and link.
- A missing abstract does not exclude a book. Later evaluation must measure the effect on semantic search.
- `semantic_text` is an input candidate for future models, not a score. Future models may use the separate title, subject, and abstract fields instead.

## Failure behavior

- Network errors, changed column names, invalid output, or too few books stop the publish step.
- The report counts skipped records and missing fields without printing individual book descriptions into CI logs.
- GitHub Actions uses an ephemeral working directory and does not upload raw CSV as an artifact.

## Source

DOAB's metadata feed and CC0 terms: https://doabooks.org/en/librarians/doab-metadata
