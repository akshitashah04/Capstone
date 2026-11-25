# Assistant review of the v2 search results

## Decision

The current search does **not** meet the requested bar of more than 40 of 50 searches with a clearly suitable book in the first five. Hybrid is the strongest of the four DOAB modes on that measure, at **17/50**. The experimental second pass raises the number of suitable first results by one, but finds suitable books for fewer questions overall and is too slow for the provisional two-second target. Keep hybrid as the prototype baseline while improving coverage and book descriptions. Do not present any of these numbers as human acceptance results or confidence probabilities.

## What was judged

The frozen [DOAB packet](../../evaluation/review/query-fit-v2/doab/manifest.json) contains 723 distinct question–book pairs pooled from the first five results of keyword, semantic, hybrid, and reranked search for 50 fictional student questions. The [textbook packet](../../evaluation/review/query-fit-v2/textbook/manifest.json) contains 95 different pairs for 19 earlier misses. The assistant assigned a binary `clear_fit` judgment to all **818** pairs: `1` only when the available source description or checked source page supports the whole request, including subject, practical need, reading level, and usable language. `0` also covers partial or uncertain matches; it does not prove a book is useless.

Of the DOAB judgments, **539** carry the earlier assistant's grade for the same question and book. Those pairs were not independently rejudged. The assistant inspected **182** newly returned pairs from the compact packet; two more new pairs were checked on their source pages. Nineteen carried pairs that gained a description in v2 were rechecked and did not gain a clear fit. All **95** textbook pairs were inspected; two clear matches were checked on their source pages. The records are [DOAB labels](../../evaluation/ai-review/v2-doab-labels.csv), [textbook labels](../../evaluation/ai-review/v2-textbook-labels.csv), and checksum-validated [DOAB](../../evaluation/ai-review/v2-doab-metrics.json) and [textbook](../../evaluation/ai-review/v2-textbook-metrics.json) score reports. All human-review cells remain blank.

## KPIs on the same 50 DOAB questions

| Search | Searches with a clear fit in first five | Clear fit at rank one | Clearly fitting books among 250 shown | Mean reciprocal rank at five | Warm search p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Keyword | 10/50 (20%) | 3/50 | 6.8% | 0.107 | 101 ms |
| Semantic | 14/50 (28%) | 8/50 | 8.8% | 0.217 | 27 ms |
| Hybrid | **17/50 (34%)** | 8/50 | **10.0%** | 0.220 | 152 ms |
| Second pass | 15/50 (30%) | **9/50** | 9.6% | **0.226** | **7,507 ms** |

The first column is the main requested KPI. Hybrid misses the **>40/50** goal by at least **24 searches** (the goal requires at least 41). Its 17/50 is also below the earlier provisional 80% acceptance bar of 40/50. Warm p95 for the second pass exceeds the provisional 2,000 ms limit. Reciprocal rank rewards placing the first suitable book nearer the top; the second pass's small lead there does not offset its lower coverage and long wait. These are measured runner times for the saved runs, not hosted-site response times.

All four modes found **zero** clear fits for the four French and four Spanish questions. The English group contained most successes; the German group has only two questions, so its one success is not a stable language estimate. The complete first-clear-rank and source link for each question and mode are in `query_findings` in the [DOAB score report](../../evaluation/ai-review/v2-doab-metrics.json). This packet judges only five results per mode, so it cannot support nDCG@10 or a known-title accuracy claim.

## Separate textbook coverage check

The first five textbook results contain a clear match for **2/19** selected DOAB misses (10.5%): [Web Literacy for Student Fact-Checkers](https://open.umn.edu/opentextbooks/textbooks/web-literacy-for-student-fact-checkers) for student 17 and [Leveraging Data Visualization to Communicate Effectively](https://open.umn.edu/opentextbooks/textbooks/leveraging-data-visualization-to-communicate-effectively) for student 23. Both appeared at rank two. The other 17 searches had no established clear fit in their first five textbook results. If these two results were simply available alongside the current hybrid successes, the **hypothetical count is 19/50**; no combined index or merged ranking has been built or measured, so 19/50 is not an achieved search KPI.

Two newly returned DOAB books were supported by their source pages: [Contemporary Issues in Industry 5.0](https://link.springer.com/book/10.1007/978-3-031-74779-3) for the beginner business AI question and [The Global Film Market Transformation in the Post-Pandemic Era](https://directory.doabooks.org/handle/20.500.12854/99523) for the streaming and film question. Several plausible looking books were left at `0` because the available material did not establish a requested feature, such as measured learning effects, tested vaccine outreach, or community ecological practice.

## Interpretation and next work

The main failure is **finding a book that covers the full need**, especially practical examples, the student's background, and multilingual requests. A relevant subject tag often points to a book that misses one of those conditions. A different ranking formula cannot recover books absent from the candidate pool or the catalog. Prioritize a targeted coverage audit of the 31 hybrid misses, better source descriptions where books do exist, and improved multilingual metadata. Then rerun this frozen diagnostic and collect real anonymous student questions for a separate holdout review.

These 50 questions were written by the project team, and many of the judgments reuse an earlier assistant pass. No one read every full book. A source description may omit useful chapters, and the binary rule can miss them. The reported figures are a **development diagnostic**, not an independent estimate of student satisfaction. The [human sheets](../../evaluation/review/query-fit-v2/README.md) remain ungraded and must be completed before an acceptance claim.

## Reproduce

From the repository root, with the project environment installed:

```bash
python -m libraries_evaluation.assistant_v2_score \
  --queries evaluation/queries/student-personas.jsonl \
  --packet-dir evaluation/review/query-fit-v2/doab \
  --archive evaluation/query-fit/reranked-run.zip \
  --labels evaluation/ai-review/v2-doab-labels.csv \
  --output evaluation/ai-review/v2-doab-metrics.json

python -m libraries_evaluation.assistant_v2_score \
  --queries evaluation/queries/student-personas.jsonl \
  --packet-dir evaluation/review/query-fit-v2/textbook \
  --archive evaluation/query-fit/otl-coverage-run.zip \
  --miss-report evaluation/personas/miss-audit.json \
  --labels evaluation/ai-review/v2-textbook-labels.csv \
  --output evaluation/ai-review/v2-textbook-metrics.json
```

The scorer validates every pair, source checksum, label, and frozen question before writing a report. It uses only compact results saved in Git; it does not download the full book catalog or index.
