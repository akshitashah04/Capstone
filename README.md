# Libraries

Libraries is an independent, NYU-inspired prototype for discovering open-access books. The repository contains **data preparation**, project-owned **keyword and multilingual semantic search**, **search-quality evaluations**, and a **browser search demo**. It is not an official NYU Libraries service.

## Current phase

The current phase adds a free public browser demo. It can search **1,891 open-access books** with natural-language questions, three multilingual models, and a book-language filter. The browser defaults to GTE Base semantic search. Historical model comparisons used the **full 91,667-book index** and different ranking rules. Human-reviewed browser relevance is still pending. The 1,884-book DOAB sample was drawn from prior top-ten result pools, so it is **not a representative subset** and must not be used to claim the earlier KPI or a new quality score. The [UI runbook](Documentation/UI/runbook.md) gives demo and development steps. Seven additional Chinese and Hindi titles come from Project Gutenberg and Hindi Wikisource. The original catalog comes from DOAB's [repository metadata export](https://www.doabooks.org/en/researchers/full-faq) and is shared through [Tox1/LibrariesBookData](https://huggingface.co/datasets/Tox1/LibrariesBookData). DOAB metadata is CC0; individual books have their own licenses. No full DOAB dataset is committed here.

A live E5 small query has shown that the site can return ranked cards, but its small sample can miss a requested topic. In particular, `chinese culture` produced broad China-related results with weak fit. The browser demo now removes source placeholders such as `undefined` from summaries and omits books without a usable description. Treat the page as a working interface prototype, not a proven recommendation-quality demo.

The [live browser demo](https://veedantbrahmbhatt.github.io/Libraries/) now includes a [public visitor feedback loop](Documentation/Feedback/design.md): per-book ratings, optional fixed reasons, and a whole-list none-fit signal. A separate [feedback service](feedback-api/README.md) saves submissions privately; the [runbook](Documentation/Feedback/runbook.md) covers release and human review. A [private evaluation workflow](Documentation/Feedback/runbook.md#test-ranking-changes-with-reviewed-feedback) uses reviewed reports to test hybrid ranking weights on an independent holdout. Because there is no login, submissions are visitor reports rather than verified NYU student judgments.

See the [search pipeline diagram](Documentation/Search/pipeline.md) and the [book-text indexing pilot](Documentation/Evaluation/book-text-pilot.md) for the metadata workflow and the comparison with excerpt and full-text indexing.

## Repository guide

| Path | Purpose |
| --- | --- |
| `src/libraries_data/` | Data preparation and publishing commands |
| `src/libraries_search/` | Keyword and meaning-based index building, publishing, and query ranking |
| `src/libraries_evaluation/` | Comparable search runs, human-review pool, and judged scoring |
| `frontend/` | Public browser demo, compact sample, model loader, owned ranking, and frontend tests |
| `feedback-api/` | Separate public submission API, private database migration, strict validation, and service tests |
| `evaluation/queries/` | Authored pilot and book-derived questions; no student details |
| `evaluation/review/pilot/` | Twelve small, shared CSV sheets for human grading of the pilot candidates |
| `evaluation/review/query-fit-v2/` | Fifty DOAB and nineteen textbook review sheets, with pinned manifests and blank human grades |
| `evaluation/ai-review/` | Separate assistant grades, v2 per-question findings, and diagnostic metrics; no human grades |
| `evaluation/diagnostics/` | Saved book-recovery metrics from the cloud run |
| `evaluation/personas/` | Fifty fictional student scenarios, their small search artifact, assistant grades, and findings |
| `evaluation/metadata/` | Small source-field coverage report; no book dataset |
| `evaluation/query-fit/` | Compact cloud ranking and supplemental-coverage artifacts |
| `evaluation/model-comparison/` | Compact E5 base and GTE rankings, assistant labels, and reproducible scores |
| `tests/` | Synthetic-record tests; no DOAB dump |
| `.github/workflows/` | GitHub Actions validation and manual publication |
| `Documentation/Data-Preparation/` | Design, steps, field definitions, operations, and session record |
| `Documentation/Search/` | Search design, plan, cloud runbook, and session record |
| `Documentation/Model/` | Model choice, pinned version, encoding method, and limits |
| `Documentation/Evaluation/` | Evaluation design, cloud runbook, session record, and provisional targets |
| `Documentation/UI/` | Interface design, implementation plan, demo runbook, and phase record |
| `Documentation/Feedback/` | Feedback design, build sequence, release/review runbook, and decision record |
| `Documentation/HANDOVER.md` | How to continue the project |

## Run and update

### Browser demo

The [UI runbook](Documentation/UI/runbook.md) covers the public link, model selection, first-use download sizes, local preview, and deployment. In the repository, run `npm ci --prefix frontend`, `npm test --prefix frontend`, then `npm run dev --prefix frontend`. The public site runs the query model and ranking in the visitor's browser; GitHub Pages hosts only static files. Results show five books first and up to ten with “Show more books.” If a model download fails, an explicitly labeled keyword-only preview is available. The demo has no student login or stored profile.

On the feedback release, visitors can rate individual results or say none fit. A submitted rating sends the question and displayed book IDs to a separate API; browsing and searching alone do not submit feedback. The [feedback runbook](Documentation/Feedback/runbook.md) explains storage, privacy limits, deployment order, retention, and the manual evaluation loop. Anonymous feedback is a diagnostic signal and has not improved or retrained a model yet.

See [the data preparation runbook](Documentation/Data-Preparation/runbook.md) for exact setup, commands, publishing steps, and troubleshooting. The GitHub Actions workflow is the intended way to publish: it uses the `HF_TOKEN` repository secret and temporary runner storage. It runs after data-preparation changes reach `main`, and can also be started manually.

See [the search runbook](Documentation/Search/runbook.md) for the four-part cloud index build, own-code ranking modes, output files, and failure handling. The full build is restricted to GitHub Actions so a teammate cannot accidentally download the dataset onto a laptop.

See [the evaluation runbook](Documentation/Evaluation/runbook.md) to run the pilot in GitHub Actions, inspect the review pool, grade books, and read a scored report. The real-index evaluation command also runs only in GitHub Actions. It does not use Google's or Hugging Face's search ranking.

See [the query-fit runbook](Documentation/Evaluation/query-fit-runbook.md) for the new metadata, second-ranking, and supplemental-catalog cloud jobs. The exact outcomes and limits are in the [query-fit report](Documentation/Evaluation/query-fit-results.md). The full source and search indexes remain off team laptops.

See [the model comparison runbook](Documentation/Evaluation/embedding-model-comparison-runbook.md) to reproduce the saved E5 base and GTE scores from compact ranked results and assistant labels. Its original cloud workflow used short-lived shards and needs a fresh E5 build before a future rerun.

See [the v2 human-review runbook](Documentation/Evaluation/human-review-v2-runbook.md) to assign question files, enter ratings, check GitHub progress, and score a completed packet. The [review tool](src/libraries_evaluation/review_packet.py) validates both saved compact artifacts without loading a model or index. It reports development and holdout groups separately when a later natural-question packet includes both.

The [pilot review sheets](evaluation/review/pilot/README.md) let teammates grade one question at a time in GitHub. A lightweight workflow checks partial progress without downloading the index. Once all 233 pairs have human grades, a manual cloud evaluation run validates the frozen candidate pool and calculates metrics. [Question collection guidance](Documentation/Evaluation/question-collection.md) explains the later 100–150-question study.

The [verified review handoff run](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43694776677) passed on 2026-11-15. It confirmed that a fresh search still returns the same 233 pairs as the shared sheets, and reported **0 human grades / 233 remaining**. A separate [AI-judged diagnostic](Documentation/Evaluation/answer-derived-results.md) now compares the three modes on that saved run and on 24 questions written from known books. The human review sheets remain untouched.

## Project status

The first preparation phase is complete. [The published snapshot](https://huggingface.co/datasets/Tox1/LibrariesBookData/commit/daba70f6e6de9f7a5c9a1f830fd255415c6d6bb7) contains **91,667 books** from 102,078 rows in DOAB's direct export, prepared on 2026-11-14. The compressed Parquet file is about 117 MB in the shared Hugging Face repository. [The manifest](https://huggingface.co/datasets/Tox1/LibrariesBookData/raw/main/manifest.json) gives the exact count, source, date, and checksum; [the quality report](https://huggingface.co/datasets/Tox1/LibrariesBookData/raw/main/quality_report.json) lists missing fields and exclusions. The [publication run](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43653263362) passed. No actual dataset file was saved on a team member's laptop.

The search index is published. The [four-part cloud run](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43682889772) passed on 2026-11-15: it encoded **all 91,667 books**, assembled the keyword and semantic indexes, returned results for a real smoke query, and [published the verified files](https://huggingface.co/datasets/Tox1/LibrariesBookData/commit/f54ded49b97a92ca8e5dce0463500043ea2a19a4). The [index manifest](https://huggingface.co/datasets/Tox1/LibrariesBookData/raw/f54ded49b97a92ca8e5dce0463500043ea2a19a4/search/v1/manifest.json) records the exact source and model revisions, checksums, and file sizes: about 367 MB for `books.sqlite` and 141 MB for `vectors.npy`. This workflow kept the real catalog and index on cloud runners and Hugging Face, without downloading either to the laptop. The [parallel build record](Documentation/Search/parallel-build-plan.md) explains why the first single-runner attempt was replaced.

Search selection and ranking run in this project's code. Results include a relative rank score and semantic similarity; neither is a calibrated confidence percentage. The smoke query proves the system runs. The [evaluation pilot](Documentation/Evaluation/README.md) compares keyword, semantic, and hybrid results for 12 authored questions in four languages. Human relevance labels are still required before ranking quality can be claimed.

The [first evaluation cloud run](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43693270526) passed on 2026-11-15. It produced **233 distinct question–book review pairs** from the 12 questions, with all human grades blank. Its [small review artifact](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43693270526/artifacts/14153335931) holds the ranked runs, timings, review sheet, manifest, and browser summary through 2026-12-15. The same push also reran [catalog publication](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43693270595) because `pyproject.toml` changed; it again wrote 91,667 books. The search evaluation remains pinned to its previously verified index revision.

The earlier [answer-derived report](Documentation/Evaluation/answer-derived-results.md) checked 12 AI-judged pilot questions and 24 questions written from known books. Clearly useful top-five results appeared for 7 keyword, 11 semantic, and 10 hybrid pilot searches; the source book appeared in the top five for 17 keyword, 23 semantic, and 20 hybrid answer-derived searches. The [cloud run](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43775201104) and [saved metrics](evaluation/diagnostics/answer-derived-metrics.json) are traceable. Semantic was stronger on those tests. Their small authored question sets and assistant judgments did not establish a pass for student use.

The [50-persona follow-up](Documentation/Evaluation/persona-results.md) tests fictional undergraduate and graduate requests that include study level and reading needs. The [cloud run](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43776657495) passed. From 599 assistant-judged top-five question–book pairs, a clearly suitable book appeared for **11/50 keyword**, **14/50 semantic**, and **15/50 hybrid** searches. Hybrid narrowly leads on top-five fit, while semantic has more suitable first results and lower warm latency. No mode meets the provisional 80% top-five bar in this diagnostic. The [50 individual findings](evaluation/personas/persona-findings.csv), [scores](evaluation/personas/persona-metrics.json), and compact [source artifact](evaluation/personas/search-run-99e564e.zip) are in Git. These synthetic questions and assistant judgments are not real student validation.

The [query-fit phase](Documentation/Evaluation/query-fit-results.md) audited all 50 misses, added source-provided descriptions and alternate titles to a [versioned v2 index](https://huggingface.co/datasets/Tox1/LibrariesBookData/tree/b745902168aca10589fd0b376b58eb8019291b37/search/v2), parsed explicitly stated reading needs, and tested a multilingual second ranking pass. The new pass is **experimental**: its runner p95 was about **7.5 seconds**, and the [assistant review](Documentation/Evaluation/assistant-v2-results.md) found a clear first-five fit for only **15/50** questions, so it is not the UI default. A separate cloud test indexed **1,915** Open Textbook Library records from its complete CSV snapshot to inspect coverage gaps; it did not merge those books into DOAB. The target of more than 40 suitable top-five searches out of 50 was **not met in this assistant diagnostic**. The [small artifacts](evaluation/query-fit/) and cloud links are saved in the report.

A [controlled E5 base and GTE comparison](Documentation/Evaluation/embedding-model-comparison-results.md) completed on purpose branch `test-multilingual-embedding-models`. On the same 91,667 books and 50 authored questions, first-five hybrid clear fits were **17/50** for current E5 small, **18/50** for E5 base, and **19/50** for GTE. The [cloud recovery run](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43896334769) finished all model shards and searches. Full model files and vectors stayed on temporary runners; compact results, assistant labels, and reproducible scores are in [Git](evaluation/model-comparison/README.md). The two larger models do not meet the requested at-least-40/50 bar, so the published E5 small index remains the baseline. These are assistant judgments of authored questions, not human acceptance results.

DOAB's website advertises over 111,000 books, more than this official export yielded. Treat this as an export snapshot for the prototype, not proven coverage of every live-site title. The current [review packets](evaluation/review/query-fit-v2/README.md) contain **723 DOAB pairs** and **95 separate textbook pairs**, all ungraded. Human ratings of these authored questions can guide development; an independent holdout of anonymous questions from intended users is still needed for acceptance. The browser demo is a shareable interface over 1,891 selected books; it does not solve full-catalog hosting or the unmet 40/50 quality goal. Update this README and the relevant `Documentation/` folder after each phase.
