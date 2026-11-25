# E5 base and GTE comparison results

## Decision

Neither larger model meets the requested search-quality bar. On the same 50 authored student questions and 91,667 DOAB books, the current E5 small hybrid search found a clearly suitable book in the first five for **17/50** questions, E5 base hybrid for **18/50**, and GTE hybrid for **19/50**. GTE's two-question improvement over the current model is too small to justify replacing the published index. Keep E5 small as the existing baseline while improving source coverage and book descriptions, then retest with human judgments and natural student questions. GTE meaning-only search is worth retaining as a development candidate, because its first-result performance is better than GTE hybrid's, but this trial does not establish a production winner.

The target of at least **40/50** is **21 questions away** from the best observed result; a target strictly above 40/50 is 22 questions away. These are assistant-reviewed development numbers, not a measure of real student satisfaction or a calibrated confidence score.

## Controlled comparison

Both candidate models used the same pinned v2 DOAB keyword database, 50 queries, 512-token limit, full 91,667-book catalog, and project-owned search/ranking code. The encoder and its required text-prefix convention differed between models. The existing E5 small figures come from the [earlier v2 assistant review](assistant-v2-results.md), which used the same questions and catalog, though it was a separate run. Full model weights and vectors stayed on temporary GitHub runners; this repository retains only the first ten results per question/mode, model/source checksums, labels, and scores.

| Model and search mode | Questions with a clear fit in first five | Clear fit first | Clearly fitting book slots in first five | Warm p95 on runner |
| --- | ---: | ---: | ---: | ---: |
| Current E5 small, meaning only | 14/50 | 8/50 | 8.8% | 27 ms |
| Current E5 small, meaning + keyword | 17/50 | 8/50 | 10.0% | 152 ms |
| E5 base, meaning only | 18/50 | 8/50 | 10.8% | 125 ms |
| E5 base, meaning + keyword | 18/50 | 12/50 | 11.2% | 199 ms |
| GTE base, meaning only | **19/50** | **12/50** | **12.0%** | 156 ms |
| GTE base, meaning + keyword | **19/50** | 11/50 | 11.6% | 200 ms |

These times exclude model startup, downloads, network, and a future UI. They are not a deployed response-time guarantee. A `rank_score` in the saved CSV orders books within that run; it is not a probability that the book is useful.

## What changed in the results

GTE hybrid succeeds for two questions where E5 base hybrid fails: ocean plastic pollution and a Spanish request for research-based reading interventions. E5 base hybrid succeeds where GTE hybrid fails on one Caribbean colonial-archives question. They share the other 17 successful hybrid questions. GTE meaning-only succeeds on ocean plastics, local outbreak communication, an accessible quantum-computing introduction, and corporate sustainability decisions where E5 base meaning-only fails. E5 base meaning-only succeeds where GTE fails on streaming and film production, vaccine-trust communication, and assistive-robot evaluation.

GTE meaning-only found [*Learning from Experience*](https://www.rand.org/content/dam/rand/pubs/technical_reports/2005/RAND_TR285.pdf) for the local public-health question and [*A Guide to Sustainable Corporate Responsibility*](https://directory.doabooks.org/handle/20.500.12854/77331) for the MBA sustainability question, but GTE hybrid omitted both from its first five. E5 base has a similar fusion loss for Spanish reading interventions and vaccine-trust communication. These examples support testing the ranking logic separately, but the hindsight union of GTE's two modes covers only **21/50** questions. That union is a diagnostic ceiling on the reviewed result lists, not an implemented algorithm; search cannot know the answer labels in advance.

GTE hybrid successes by query language were 17/40 English, 1/2 German, 1/4 Spanish, and 0/4 French. E5 base hybrid had 17/40, 1/2, 0/4, and 0/4 respectively. The non-English groups are too small for a reliable language ranking. The French misses remain a clear problem to investigate.

## Review and traceability

The [recovery cloud run](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43896334769) completed all eight GTE vector shards and both full-catalog evaluations. The E5 trial used the four completed E5 shards from [run 43848201040](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43848201040). Its compact result is [artifact 14239726079](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43896334769/artifacts/14239726079); GTE's is [artifact 14258321947](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43896334769/artifacts/14258321947). The committed manifests and CSV checksums reproduce both reports without downloading the full catalog.

For E5 base, 222 of 413 distinct first-five question–book pairs kept an earlier identical-pair assistant judgment and 191 were inspected anew. For GTE, 189 of 415 pairs kept the earlier v2 judgment, 35 kept the E5 base judgment for the identical question and book, and 191 were newly inspected. GTE's three newly supported full fits were [*Marine Plastics Abatement*](https://iwaponline.com/ebooks/book/868/Marine-Plastics-AbatementChallenges-Implications) for readable ocean-plastics sources and solutions, [*Learning from Experience*](https://www.rand.org/content/dam/rand/pubs/technical_reports/2005/RAND_TR285.pdf) for local outbreak-response cases, and [*Neuropsicología Educativa, Narrativa y Proceso Lector*](https://libros.usc.edu.co/index.php/usc/es/catalog/book/575) for a Spanish research-based reading intervention with case evidence. The last is small case-study evidence, not proof that the intervention works broadly.

The [E5 manifest and rankings](../../evaluation/model-comparison/e5-base/), [GTE manifest and rankings](../../evaluation/model-comparison/gte-base/), [assistant labels and computed scores](../../evaluation/model-comparison/README.md), and [scoring runbook](embedding-model-comparison-runbook.md) preserve the details. A `0` label means that the available title, metadata preview, and any checked source page did not establish the *whole* reading need; it is not a claim that the book has no value. No human reviewer has graded these model outputs. All 50 questions were authored for fictional personas and are development cases; there is no natural-question holdout. Neither model was trained on these questions.

## Next quality work

1. Audit missed questions against the full catalog to distinguish missing books, thin descriptions, language mismatches, and ranking failures.
2. Improve or add permitted book metadata and a vetted beginner-textbook source, then build a new versioned index in the cloud.
3. Test a ranking change that protects useful meaning-only books from being buried by keyword fusion; score it on a frozen, human-graded candidate pool.
4. Collect anonymous natural student questions in the intended languages, set aside a holdout, and require human Success@5 of at least 40/50 before claiming the prototype meets the bar.

Do not display the current rank numbers as confidence percentages, or present this model comparison as a passing acceptance test.
