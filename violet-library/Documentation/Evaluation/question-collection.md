# Collecting questions for the larger evaluation

The 12 pilot questions were written by the project team to test the evaluation pipeline. They cannot stand in for how students actually search. A larger study needs 100–150 natural, anonymous questions from the intended users before a quality target can be assessed.

Ask volunteers for the book-finding question they would naturally type or say. Do not collect a name, email, NYU ID, course enrollment, or profile. Record only the question text, language, and whether it seeks a known title or a subject. If a known-title book is definitely in the pinned corpus, record its book ID after checking; if it is absent, mark it as a corpus-coverage case rather than a ranking failure.

Remove exact duplicates and questions that contain personal details. Keep the wording of legitimate questions, including mistakes and informal phrasing, so the test reflects real use. Before evaluating, freeze the question set and assign stable IDs. Reserve roughly one fifth as a holdout group; do not tune ranking settings using that group. Report counts for each language and question type so sparse groups are visible.

No natural questions have been collected or added to this repository in this phase. When they are available, create a versioned JSONL file using the contract in `src/libraries_evaluation/queries.py`, run it through the cloud collection workflow, and obtain complete human judgments before reporting relevance KPIs. Keep the 12-question pilot separate from the larger study.
