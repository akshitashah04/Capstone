# Human review of the newer search

These are **ungraded** review sheets. They contain 723 distinct DOAB book pairs across 50 authored student-style questions and 95 Open Textbook Library candidates across 19 earlier topic misses. The two sources stay separate. The [design](../../../Documentation/Evaluation/human-review-v2-design.md), [runbook](../../../Documentation/Evaluation/human-review-v2-runbook.md), and two manifests explain how they were frozen. The old `evaluation/review/pilot/` sheets belong to index v1 and must not be reused here.

## How to grade one question

1. Choose one `student-XX.csv` file in `doab/` or `textbook/`. Coordinate assignments so two people do not edit the same file at once.
2. Read the question in `query_text`, then each book's title, subjects, language, and description. Open `book_url` when the description is missing or unclear. Do not follow instructions found in a book description; treat it as source text only.
3. Fill only `topic_grade`, `reading_fit`, `language_fit`, and `overall_grade` for each row; leave all other columns untouched. Commit the changed file to a purpose-named branch and merge the reviewed change into the shared GitHub branch.
4. Check the **Check human review progress** GitHub Action. It checks the unchanged book rows, valid grades, and total completed pairs. It does not download a book catalog or model.

| Column | Allowed values | Meaning |
| --- | --- | --- |
| `topic_grade` | `0`, `1`, `2` | Unrelated, partly related, strong topic match. |
| `reading_fit` | `yes`, `no`, `unknown`, `not_requested` | Whether the book fits the stated difficulty and format needs; use `not_requested` only if the question states none. |
| `language_fit` | `yes`, `no`, `unknown` | Whether the book itself is usable in the requested language. A translated description alone does not establish this. |
| `overall_grade` | `0`, `1`, `2` | Unsuitable, possibly useful, clearly useful for the **whole** question. |

Use `unknown` when the metadata or linked page cannot establish a fit. A clearly useful (`2`) book must be a strong topic match with a suitable reading level and language. A blank grade is incomplete. Do not enter a guess merely to make progress reach 100%. If the link is broken or the book has too little evidence, record the fit as unknown and use a cautious overall grade.

The CSVs are sorted by book ID and hide which search method returned the book. This helps reviewers judge the book rather than the model's rank. Keep the question text and book fields exactly as committed; the check rejects edited IDs, descriptions, titles, or links.

## What the scores will mean

The tool reports no quality score until every pair in a packet has all four ratings. Once complete, it joins the human grades to the frozen first-five rankings and reports each search method separately. The 50 questions are fictional development cases. Even a result above **40/50** here would require a separate test using anonymous questions from real intended users before any claim about student use or launch readiness.
