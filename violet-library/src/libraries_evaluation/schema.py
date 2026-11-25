"""Shared column contracts for ranked runs and human review."""

RUN_FIELDS = ("query_id", "mode", "rank", "book_id", "rank_score", "semantic_similarity")
TIMING_FIELDS = ("query_id", "mode", "latency_ms", "result_count")
REVIEW_FIELDS = (
    "query_id",
    "query_text",
    "query_language",
    "query_intent",
    "query_split",
    "book_id",
    "title",
    "authors",
    "subjects",
    "book_languages",
    "publication_year",
    "book_url",
    "abstract_excerpt",
    "keyword_rank",
    "semantic_rank",
    "hybrid_rank",
    "relevance",
)
SHEET_FIELDS = (
    "query_id",
    "query_text",
    "book_id",
    "title",
    "book_url",
    "abstract_excerpt",
    "relevance",
)
