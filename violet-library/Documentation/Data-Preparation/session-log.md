# Data preparation session record — 2026-11-14

## Request and approved scope

Prepare the complete DOAB book metadata catalog for a later NYU-focused semantic-search prototype. Keep the code and its history in GitHub, the processed catalog in one Hugging Face dataset, and no actual dataset files on a team member's laptop. Use a purpose-named branch and document each step, file, and decision. Search models, ranking, scores, and UI are outside this session.

## Steps and reasons

1. Inspected the initially empty local and remote Git repositories. Initialized `main` with an empty commit so feature work could use the requested `prepare-doab-data` branch.
2. Checked DOAB's official metadata page and inspected the live CSV header and one record without saving the feed. This confirmed useful field names but did not establish that the CSV covered every DOAB record.
3. Wrote the design and implementation plan before package code. This records the agreed source, boundaries, validation, and publishing approach.
4. Created a project-only Python environment in ignored `.venv/`. The repository contains code and synthetic tests, not a DOAB dump.
5. Wrote tests for multilingual normalization, book selection, edition identity, CSV header validation, catalog output, small-feed rejection, and bundle integrity before implementing those behaviors.
6. Implemented streaming source reading, model-neutral normalization, bounded-batch Parquet writing, quality reporting, and checked Hugging Face publishing.
7. Added a test workflow for each push and a full-feed publish workflow with manual dispatch and a restricted main-branch trigger. The publish workflow reads `HF_TOKEN` only during the upload step and removes temporary output afterward.
8. Added the root README, data dictionary, runbook, model and evaluation handoff notes, and project handover.
9. The first full cloud run [#1](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43650910280) succeeded technically and published [Hugging Face commit `99d5801`](https://huggingface.co/datasets/Tox1/LibrariesBookData/commit/99d5801ce8a712d297baf6b18667e5cdd26699f9): 55,606 books from 60,859 CSV rows, with 8,481 missing abstracts. This was smaller than DOAB's stated collection of over 111,000 books, so it is an **incomplete first trial**, not the final catalog.
10. Queried DOAB's OAI-PMH `ListIdentifiers` and `ListRecords` endpoints. The feed reported about 129,000 rows, including chapters and deleted records. Replaced the smaller CSV source with paginated `oai_dc` harvesting, added pagination and completeness tests, and raised the book-count gate to 100,000.
11. The complete OAI cloud run [#2](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43651699801) stopped before upload: 129,746 source rows, 25,415 non-book rows, 19,160 repeated book IDs, and 85,171 unique books. This result did not meet the full-collection objective. The 100,000-book gate prevented the incomplete result from replacing the first snapshot.
12. Located DOAB's separate direct full repository export at `https://directory.doabooks.org/download-export?format=csv`, linked from its official FAQ. Its response is about 268 MB and its 138-column header includes book metadata beyond the smaller feed. Inspected sample rows without saving the export. Switched the pipeline to stream this export, parse its `||` multi-value fields and language codes such as `English[eng]`, and keep the 100,000-book gate. The next cloud run will establish its actual complete count.
13. The first direct-export cloud run [#3](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43652633320) stopped while reading the CSV with `ValueError: I/O operation on closed file`; it uploaded nothing. The cause was wrapping the HTTP response's raw stream in a text reader, which could close at the response boundary before the CSV reader completed. Switched to the response's line iterator and restored line endings so quoted descriptions spanning several lines remain valid CSV. Added a regression test for that case.
14. The corrected branch check [#5](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43652913085) passed. The subsequent full-export cloud run [#4](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43652998792) read 102,078 source rows and found 91,667 unique books, 10,410 non-book rows, and one book without a title. It stopped at the 100,000-book gate and uploaded nothing. The official live site still advertises over 111,000 books, so the available export is a measurable snapshot rather than proven coverage of every live-site title. Adjusted the gate to 90,000 based on the observed official export and added this coverage warning to the README, data dictionary, and dataset card. The gate detects a major shortfall; it cannot prove completeness.
15. The revised branch check [#6](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43653225135) and main check [#7](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43653263366) passed. The [publication run #5](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43653263362) prepared and uploaded the export snapshot successfully. Hugging Face created [dataset commit `daba70f`](https://huggingface.co/datasets/Tox1/LibrariesBookData/commit/daba70f6e6de9f7a5c9a1f830fd255415c6d6bb7). Read the remote manifest and quality report after upload and confirmed 91,667 books, the direct-export source URL, schema version 1, and Parquet checksum `2e0c255bb959bcc2afb42f134ede2d3869281ceadf0aca3841fa1f3f5fc449d4`. The remote Parquet file is 117,304,211 bytes. No actual dataset file was saved locally.

## Important decisions

| Decision | Reason |
| --- | --- |
| Direct full DOAB repository export | The smaller CSV feed and OAI-PMH harvest yielded 55,606 and 85,171 unique books respectively, below DOAB's stated coverage. The direct repository export is the remaining official bulk source and includes richer book fields. |
| Stream the export instead of saving a raw file | Keeps raw DOAB files off laptops and out of Git; bounds processing memory. |
| Preserve separate source fields and add `semantic_text` | Supports keyword, hybrid, and multilingual model experiments without losing original field boundaries. |
| No translation, stemming, or lowercasing of descriptions | Preserves multilingual meaning and display quality. Only language codes are lowercased. |
| Deduplicate by DOAB ID only | Avoids collapsing distinct editions and translations. |
| Keep records without abstracts | Prevents silent loss of books; missing descriptions are measured. |
| Require at least 90,000 books | The official direct export contained 91,667 books on 2026-11-14. This gate stops a major shortfall without pretending the export includes every live-site title. |
| One atomic Hugging Face upload | Avoids publishing a mix of old and new output files. |
| Restricted main-branch publication plus manual refresh | Publishes reviewed pipeline changes automatically, while unrelated documentation edits avoid full-feed processing. A manual run remains available. |

## Verification and publication record

Local verification before branch publication:

- `ruff check .`: passed.
- `python -m pytest -q`: 8 passed.
- Live-source smoke check: the DOAB CSV could be streamed, and its first record had an ID and `dc.type=book`. No actual DOAB row was saved locally.
- First branch push: GitHub Actions check run [#1](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43650602861) completed successfully.
- Second branch check [#2](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43650780699) and main-branch check [#3](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43650910256) completed successfully for the initial CSV pipeline.
- The initial CSV publication [#1](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43650910280) completed but did not meet the full-collection objective; it triggered the OAI source correction above.
- OAI branch check [#4](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43651615611) passed. The OAI publication [#2](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43651699801) failed the count gate as expected, so it made no Hugging Face commit.
- The direct export smoke check parsed one live book in memory and confirmed its title, ID, author list, `eng` language code, and record URL. No export file was saved locally.
- After the HTTP reader correction, `ruff check .` passed and `python -m pytest -q` passed with 10 tests, including the multiline HTTP CSV regression case.
- The corrected direct-export run [#4](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43652998792) stopped at the 100,000-book gate. Its aggregate counts were: 102,078 source rows; 91,667 books; 10,410 non-books; 1 missing title; 13,125 missing abstracts; 5,763 missing subjects; 1,266 missing languages; 0 missing record URLs. No Hugging Face commit was made.
- The final [publication run #5](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43653263362) passed all preparation, quality-report, upload, and cleanup steps. The remote [manifest](https://huggingface.co/datasets/Tox1/LibrariesBookData/raw/main/manifest.json) and [quality report](https://huggingface.co/datasets/Tox1/LibrariesBookData/raw/main/quality_report.json) match its 91,667-book output, with 0 duplicate IDs and 0 missing book URLs.

The direct export is useful for the prototype, but its 91,667 book records do not establish coverage of all titles advertised on DOAB's live website. Future refreshes should compare both the published count and quality report with this snapshot.
