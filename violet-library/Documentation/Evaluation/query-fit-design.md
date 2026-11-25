# Query fit and catalog coverage design

## Goal and boundary

Improve the chance that the first five books satisfy the student's subject and stated reading need. Work through the first five agreed steps: audit misses, improve available metadata, interpret query needs, recheck candidate books, and decide whether the collection needs expansion. Stop before human ratings and the final acceptance retest. The 40/50 target remains a goal, not a result to assume.

The source is the pinned 91,667-book DOAB catalog. Keep complete source and index files on temporary GitHub runners and Hugging Face, not a team laptop. Preserve the existing index and evaluation so comparisons remain reproducible. No real student profile, paid service, external provider search ranking, or full-book text is required.

## Approaches considered

1. **Tune fusion weights alone.** Cheap, but it cannot find a missing book or tell whether a book fits a beginner.
2. **Add a second, multilingual query–book check.** Recommended: use the existing project-owned candidate search, then score a bounded set of book descriptions against the whole query. Keep a no-model baseline and compare on frozen questions.
3. **Train a custom model immediately.** Postpone until people grade real questions and books; the current assistant labels are too small and uncertain for a trustworthy training target.

## Data flow

1. A repeatable audit reads the saved 50-query artifact and its separate assistant labels. It reports which failures are known ranking losses, which lack reading-level evidence, and which have no clearly suitable book in the judged pool. It must distinguish unjudged books from proven catalog gaps.
2. A cloud-only metadata audit compares the pinned source fields with the index's fields. An available alternate-language abstract may supply a description when the primary abstract is empty; an alternate title may help exact matching. Source values and provenance must not be invented.
3. A query parser identifies explicit needs such as introductory level, practical examples, methods, and language. It preserves the original full query for multilingual meaning matching and returns an explicit structure for later ranking and explanation. Unknown needs stay unknown.
4. Keyword and semantic retrieval each contribute candidates. A pinned multilingual second-stage model compares the full query with a bounded, source-grounded book text. Its score orders the candidate pool, with original rank used only to break ties. The scoring method is recorded; the score is not a confidence percentage. Missing descriptions remain visible as an evidence limitation.
5. A coverage review decides, question by question, whether the existing collection may contain a suitable title and whether a new source is justified. Adding a source requires a separate provenance, rights, deduplication, and build plan; no title is silently mixed into the pinned DOAB snapshot.

## Failure handling and evaluation

The search keeps keyword, semantic, and hybrid baselines. The second-stage mode fails clearly if its model or source data is unavailable; it does not quietly substitute another ranking method. The audit validates saved query and result checksums, rejects duplicate or unknown labels, and records unknowns honestly. Unit tests use synthetic books. Any cloud check uses a temporary runner and publishes only compact diagnostic output. Assistant-graded results are development evidence only; the later human-rating and held-out acceptance steps remain separate.
