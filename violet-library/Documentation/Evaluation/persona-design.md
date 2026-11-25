# Fifty synthetic student search evaluation

## Question

Can the current keyword, semantic, or hybrid search return books that fit a student's subject **and** their stated reading level or purpose?

## Design

Create 50 fictional, anonymous student profiles before viewing any search results: 25 undergraduates and 25 graduate students across different majors. Each profile stores its major, level, learning goal, reading need, language, and one query in a plausible student voice. Some queries are short; others explain a constraint such as no coding, introductory reading, case studies, or research methods. Include English, Spanish, French, and German. These are authored scenarios, not real student queries or profiles.

Export the 50 query texts to the existing evaluation JSONL format. Run the project's three search modes against the same pinned DOAB index on a temporary GitHub runner. Keep the top 10 and metadata for inspection, but judge the union of each mode's **top five** per persona. The assistant assigns `0` (wrong topic or unusable), `1` (related or reading level unclear), or `2` (clearly fits the goal and level) from title, subjects, and a short abstract preview. Record a short finding for every persona, including why its best books fit or miss the request. Do not infer a book's readability from its title alone; mark it uncertain if metadata does not support a level judgment.

Compare modes with Success@5 (at least one grade-2 book), top-one grade, and pooled nDCG@5. Report per-persona results, representative book titles, undergraduate and graduate breakdowns, language breakdowns, and warm search timing. These metrics are diagnostic because the questions and judgments are synthetic and assistant-created. The existing 80% Success@5 and +10% hybrid nDCG@10 bars remain provisional; nDCG@5 here is a different measure and must not be presented as that KPI. No real student details or full index are stored locally.

## Decisions

The same 50 questions and review rubric apply to all three modes. A topic-only match is insufficient when the student explicitly needs a beginner, business-facing, practical, or advanced research book. A book can be useful without being the exact course text. When the abstract is missing or unclear, record uncertainty rather than inventing contents. The study identifies which current mode is best on these scenarios and where it fails; it does not train or tune the model.
