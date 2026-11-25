# Assistant review of the v2 search

## Goal

Give the user a reproducible, explicitly assistant-judged KPI comparison for the frozen 50 authored queries, four DOAB search modes, and separate 19-query textbook coverage experiment. This is development evidence, not human validation.

## Method

Use the committed rank-blind v2 packet and saved cloud-result ZIPs; never download the full catalog or model. Carry forward an earlier assistant grade only when the same question–book pair appears in the v2 first-five pool. Inspect every new pair against its question and source metadata. Recheck earlier pairs that newly gained a source description. Open publisher or catalog pages for borderline positive claims and record the evidence link. Keep the human-review sheets entirely blank.

Record one binary decision per pair: `1` only when a book clearly fits the whole subject, reading need, and usable language; `0` means the available evidence does not establish that full fit. `0` is not proof the book is useless. A title alone, a translated description, or a broad topic match is insufficient for `1`. Keep a basis field to distinguish carried prior judgments, newly inspected metadata, source-page checks, and corrections.

Validate label coverage, uniqueness, source hashes, and allowed decision values before computing Success@5, strong Precision@5, top-one success, reciprocal rank, and warm p95 latency. Score the textbook set separately. Show whether any judged textbook results would add to the DOAB hybrid first-five successes, without implying that the two indexes are already merged. Do not report nDCG@10 or known-title accuracy: this packet covers only the first five and has no known-title query.

## Implementation steps

1. Write synthetic tests for complete label coverage, score calculation, and rejection of changed labels.
2. Add a small read-only assistant scorer that consumes the existing verified packet and archived rankings.
3. Save separate assistant labels for all 723 DOAB and 95 textbook pairs, with provenance and source links for externally checked positives.
4. Compute and document every KPI, language slices, representative wins/failures, and uncertainty. Update README, evaluation index, session record, and handover.
5. Verify tests, lint, packet integrity, and remote checks before publishing the purpose-named branch.
