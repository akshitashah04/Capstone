# V2 human review and acceptance gate

## Purpose

Judge whether the newer search returns books that actually answer a student's full request. The 50 authored persona questions are development material, not independent student evidence. Human ratings will decide whether to keep hybrid search, test the slower second ranker further, or improve the catalog. They cannot by themselves establish the final student-use KPI.

## Frozen inputs

The committed `reranked-run.zip` contains the same 50 questions searched through keyword, semantic, hybrid, and reranked modes against the pinned DOAB v2 index. The committed `otl-coverage-run.zip` contains five textbook candidates for each of the 19 earlier topic misses. The review tool checks the ZIP entry checksums, question checksum, modes, ranks, duplicate IDs, and source revisions before creating sheets. No full catalog or model is needed on a team laptop.

## Review packets

Create one small CSV per question in separate DOAB and textbook folders. Include the question, book ID, title, subjects, language if known, a source description excerpt, and the book link. Sort by book ID and hide search mode and rank so reviewers are not swayed by the model's order. The DOAB packet contains every distinct book in the first five of the four modes; the textbook packet contains all 95 candidates. A manifest pins the source ZIP, original results, metadata, question file, and candidate pairs. The old v1 review sheets remain untouched.

Reviewers fill four columns: `topic_grade` (0 unrelated, 1 partly related, 2 strong match), `reading_fit` (yes, no, unknown, or not_requested), `language_fit` (yes, no, or unknown), and `overall_grade` (0 unsuitable, 1 possibly useful, 2 clearly useful for the whole request). A blank is ungraded. A reviewer follows the source link when metadata is thin and marks unknown rather than inventing a fit. A clearly useful grade requires a strong topic match and no known reading or language mismatch. The tool checks grades and immutable book fields; it never fills grades itself.

## Decision gate

Progress is reportable while grading is incomplete. Search metrics are withheld until every pair in that packet is graded. The scorer uses only the frozen ranking and complete human grades to count questions with a clearly useful top-five book, top-one fit, and first-useful rank for each mode. The textbook packet is reported separately; it is not merged into DOAB. The acceptance target for the 50 authored development questions is more than 40 successful top-five searches, but passing that target still does not prove fit for real students.

For acceptance, obtain a separate set of anonymous questions written by actual intended users, freeze them before tuning, reserve a holdout group, collect and rate every top-five candidate, and run the same scoring gate once on the holdout. No names, email addresses, course records, or profiles belong in these files. The UI and deployment decision follows a human-grounded ranking choice and a verified free runtime.
