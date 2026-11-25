# Human review handoff design

## Decision

The first cloud pilot produced 233 ungraded question–book pairs. The next step is to make those pairs reviewable from the shared GitHub repository and to track genuine human grading without rerunning the large search index after every edit. No relevance grade will be filled by code or inferred from the model.

Three approaches were considered: one large CSV, one file per question, and a custom web reviewer. One large CSV is awkward in GitHub's browser editor. A web reviewer would need storage and access controls the prototype does not have. One small CSV per question is the recommended first version: teammates can open the book link, edit a grade in GitHub, and commit their work to one shared source.

## Data contract

`evaluation/review/pilot/` contains a provenance manifest and 12 CSV files, one per pilot question. Each file contains the question, book ID, title, source link, a short abstract preview, and a blank `relevance` column. The rows are sorted by book ID and contain no search-mode ranks, so reviewers are not led by the system's order. These files contain only the 233 selected metadata records; they are not the full corpus or index.

The manifest pins the original pilot run and query checksum, expected pair count, and a digest of all question–book IDs. A small review command checks duplicate, missing, extra, or invalid rows and reports how many 0/1/2 grades are complete. Partial grading remains a valid work-in-progress state, never a measured search score.

Every full cloud run compares its freshly collected `review.csv` with the frozen review pool, even while grading is incomplete. When all grades are complete, the same command overlays them and writes a temporary full judgment file. The existing scorer checks every row and computes metrics. The temporary file is discarded with the runner. If the new candidate pool differs from the pinned pilot, the job stops and the team must start a new review version.

## Cloud behavior and limits

A lightweight GitHub Actions job checks review progress on every grade-file change. The large evaluation job runs for code/question changes or on manual request, so each partial grade commit does not download the index. On a manual run after grading is complete, the evaluation job recollects the pinned candidate pool, assembles judgments, and scores them. It publishes the progress report and small outputs as an artifact.

Human reviewers decide the grades. The 12 authored questions are only a pilot; even a fully graded pilot is too small to validate the provisional 100–150-question quality targets. A larger anonymous question set and a held-out judgment pass remain later work.
