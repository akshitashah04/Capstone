# Pilot human review

These 12 small CSV files contain the 233 books returned in the [first pilot run](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43693270526). Each file covers one question. The order is by book ID, without search ranks, so graders can judge the book rather than follow the engine's order. The [manifest](manifest.json) pins the source run and exact question–book pairs.

To grade in GitHub, open one CSV file, use **Edit**, and change only the final `relevance` cell of each row. The question text, title, short abstract, and book URL are included. Open the URL for more context when the preview is insufficient. Save your change to a purpose-named branch and merge it after the lightweight **Check human review progress** job passes.

| Grade | Meaning |
| --- | --- |
| `0` | The book does not answer the question |
| `1` | The book is related or partly useful |
| `2` | The book is clearly useful |
| blank | Not judged yet |

Do not change IDs, titles, URLs, previews, or other columns. A blank grade is not a zero. The progress job rejects missing, extra, changed, or invalid rows and shows how many grades remain. When all 233 are graded, manually start **Collect and score owned search evaluation** on `main`. It will recheck the candidate pool and calculate metrics. See the [runbook](../../../Documentation/Evaluation/runbook.md) for limits and interpretation.
