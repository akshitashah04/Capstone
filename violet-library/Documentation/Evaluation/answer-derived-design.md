# Answer-derived search diagnostic

## Purpose

The user asked for queries written backward from returned books and an independent judgment of the search responses. This is a diagnostic alongside the existing 12-question pilot. It is not a substitute for 100–150 natural student questions and human relevance judgments.

## Two measurements

1. **Pilot relevance:** Independently grade all 233 distinct question–book pairs in the saved pilot artifact as 0 (not useful), 1 (partly useful), or 2 (clearly useful), using the book metadata and abstract preview. Keep these AI judgments in `evaluation/ai-review/`, separate from the empty human review sheets. Run the existing validated scorer on the exact saved run and report keyword, semantic, and hybrid Success@5, pooled nDCG@10, known-title top-one, and warm p95 latency.
2. **Answer-derived recovery:** Select two distinct books per original pilot question from its returned pool by a fixed SHA-256 sort after requiring a usable abstract. Write a short, natural paraphrase of each selected book's description without copying its title. Freeze 24 questions and their target book IDs before running search. Run all three ranking modes against the same pinned index and report target hit@1, hit@5, hit@10, and MRR@10. This measures recovery of known source books, not general relevance.

## Fairness and evidence

The AI grader uses only title, subjects, languages, source link, and up to 600 characters of abstract from the published pilot artifact. A grade of 2 requires a clear answer to the stated question, 1 covers a useful part or adjacent topic, and 0 is off-topic or unsupported. Ambiguous cases may be checked on the source page; the report must count judgments based on limited metadata. The AI grades are reproducible and inspectable, but they are not human labels.

Answer-derived questions are intentionally biased toward books already in the corpus and response pool. They can reveal retrieval weaknesses, especially across languages, but high scores would be expected and cannot certify the provisional 80% Success@5, +10% hybrid nDCG, 95% known-title top-one, or two-second warm-latency targets. Compare measured numbers with those bars as **diagnostic only**. The original pilot has only one known-title question and is too small for a reliable 95% target.

## Outputs

- Frozen question and target files under `evaluation/queries/`.
- Compact AI grade file under `evaluation/ai-review/`, leaving human sheets untouched.
- Small scored JSON reports, exact run links, and failure examples in `Documentation/Evaluation/answer-derived-results.md`.
- Cloud-run artifacts with ranking and timing files; the full index remains on temporary GitHub runners.

The report must state sample sizes, grade source, corpus and language limits, and whether each provisional bar is met numerically. It must never call a ranking score a confidence probability.
