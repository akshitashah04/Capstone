# Answer-derived search diagnostic results

## What was tested

This session used two separate checks against the pinned 91,667-book index. First, the assistant judged all 233 distinct question–book pairs from the existing 12-question pilot, using title, subjects, language, and at most 600 characters of abstract. Grades were `0` (unsupported), `1` (partial or related), and `2` (clearly useful). There were 77, 97, and 59 pairs in those categories, respectively. The [compact grades](../../evaluation/ai-review/pilot-grades.csv) and [exact scored JSON](../../evaluation/ai-review/pilot-metrics.json) are in Git; the 233 human-review cells remain blank. The source was the [verified pilot run](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43694776677), whose review SHA-256 is `fdc28a1343ba587da2f215d5249b1790a18d2ffe7e659de5e220da577ec10912`.

Second, 24 questions were written backward from 24 different books in that pilot's returned pool, two per original question. Each question paraphrases its source book's description without using the title. All questions and target IDs were frozen in Git before the new cloud search. This measures whether the engine recovers a known source book from its own corpus. It does not measure the relevance of every returned book.

## AI-judged pilot: 12 authored questions

| Measure | Keyword | Semantic | Hybrid | Provisional hybrid target |
| --- | ---: | ---: | ---: | ---: |
| Clearly useful book in top 5 | 7/12 (58.3%) | 11/12 (91.7%) | 10/12 (83.3%) | At least 80% |
| Pooled nDCG at 10 | 0.4418 | 0.8221 | 0.6759 | At least 10% over keyword |
| Known title at rank 1 | 1/1 | 1/1 | 1/1 | At least 95% |
| Warm-search p95 on GitHub runner | 96 ms | 50 ms | 119 ms | Under 2 seconds |

The hybrid nDCG is **53.0% above keyword**, meeting that provisional bar numerically. Semantic search is **21.6% above hybrid** on these judgments and finds one more clearly useful book in the top five. This is the clearest ranking issue in the pilot: the current fusion weakens strong semantic matches on some non-English questions. For the Spanish coastal adaptation and French energy/justice questions, semantic found a grade-2 book in the top five while hybrid did not. Spanish and French each have only two pilot questions, so their percentages are especially unstable.

The one known-title result is correct, but one case cannot validate a 95% rate. The latency is warm search inside a temporary cloud runner. It excludes first-time model/index loading, network access, and a future interface. The pooled nDCG ideal is limited to books found by at least one of the three modes; it cannot see relevant books that all modes missed.

## Book-recovery diagnostic: 24 answer-derived questions

The [cloud run](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43775201104) passed on 2026-11-15, using the same pinned index. Its [artifact](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43775201104/artifacts/14186206397) holds the ranked results, timings, review pool, manifest, and exact metrics through 2026-12-15. The compact [metrics JSON](../../evaluation/diagnostics/answer-derived-metrics.json) and [manifest](../../evaluation/diagnostics/answer-derived-manifest.json) are retained in Git. We checked the question-file SHA-256 against the manifest and independently recomputed the exact same metrics from the cloud files.

| Source-book recovery | Keyword | Semantic | Hybrid |
| --- | ---: | ---: | ---: |
| At rank 1 | 16/24 (66.7%) | 19/24 (79.2%) | 17/24 (70.8%) |
| Within top 5 | 17/24 (70.8%) | 23/24 (95.8%) | 20/24 (83.3%) |
| Within top 10 | 17/24 (70.8%) | 23/24 (95.8%) | 21/24 (87.5%) |
| Reciprocal rank, top 10 | 0.6875 | 0.8681 | 0.7525 |
| Warm-search p95 on GitHub runner | 167 ms | 45 ms | 191 ms |

The strongest signal is that semantic search alone finds the source book more often and higher in the list. Hybrid loses the source book entirely from its top ten for three questions where semantic placed it at rank 2 or 3: [housing tensions tied to migration](../../evaluation/queries/answer-derived.jsonl), Spanish public-policy methods, and German digital university exams. In each case, keyword search also missed the target. With the current reciprocal-rank fusion, books supported by both ranking lists can crowd out a strong semantic-only book. On a Spanish coastal-adaptation question, semantic ranked the source book first while hybrid put it ninth. These are ranking examples, not proof that the other returned books are irrelevant.

The 24 questions cover 12 English, 4 Spanish, 4 French, and 4 German cases. Semantic recovered the target within five for 11/12 English and all 12 non-English cases. Hybrid did so for 11/12 English, 2/4 Spanish, 4/4 French, and 3/4 German. Each language slice is too small to establish stable language performance. Every question was written from a book already found in the original pilot, and all are marked `development`; this deliberately easy, answer-derived set is not an unbiased student test.

## Decision and limits

The current search is a working multilingual baseline. At this point, semantic search was the leading candidate for the prototype's default because it beat hybrid in both checks above. A [later 50-persona study](persona-results.md) gave hybrid a narrow top-five lead on more varied authored requests, so the default choice remains open. The numerical KPI comparisons above are **diagnostics, not an official KPI pass**. The required release assessment remains 100–150 natural, anonymous student-style questions, complete human judgments, and a held-out result. AI labels based on short previews can be wrong; 37 of the 233 pilot pairs have no abstract preview. The assistant also knew these books came from search results, so its grading was not fully blind. The book-recovery score checks one known source book per query, although other books may also be useful. No score here is a calibrated confidence probability.
