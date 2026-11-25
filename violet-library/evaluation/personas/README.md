# Synthetic student search study

This folder contains 50 fictional student scenarios and their inspected search run. It contains no real student names, emails, profiles, or course registrations.

| File | Contents |
| --- | --- |
| `student-personas.jsonl` | The frozen 25 undergraduate and 25 graduate profiles, with majors, goals, reading needs, and query text |
| `search-run-99e564e.zip` | The small verified cloud artifact: all top-ten rankings, timings, metadata review pool, and manifest |
| `search-run-manifest.json` | Human-readable copy of the run's checksums and pinned index revision |
| `ai-labels.csv` | Assistant's topic, level, and overall grades for the 599 distinct top-five pairs |
| `persona-metrics.json` | Validated aggregate, grouped, and per-persona scores |
| `persona-findings.csv` | Fifty plain-language outcomes and the first returned title for each mode |

The [report](../../Documentation/Evaluation/persona-results.md) explains the rubric, scores, examples, and limits. The [runbook](../../Documentation/Evaluation/runbook.md) explains how to rerun the cloud search and rescore an extracted artifact. The archive is about 605 KB; it is an evaluation sample, not the full 91,667-book dataset or index. The query file for the collector lives at `evaluation/queries/student-personas.jsonl`.

The ZIP's SHA-256 is `a19183ba82ab5f28ff804bd042eb9aa902fc2b19f2474f6a8e06b81bb1e2bba0`. It came from [cloud run 43776657495](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43776657495), whose source commit is `99e564e93ed4aa0d9f86ce33e95c41ec949b3a34`.

The grades are independent assistant judgments from title, subjects, language, and at most 600 characters of abstract. They are not librarian or student judgments. Do not merge them into the human pilot sheets. A blank strong-match rank means no grade-2 book in the first five for that mode.
