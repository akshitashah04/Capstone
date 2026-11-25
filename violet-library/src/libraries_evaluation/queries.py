"""Validate stable, privacy-safe search questions from JSONL."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

QUERY_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
LANGUAGE = re.compile(r"[a-z]{2,3}(?:-[a-z0-9]+)*\Z")
INTENTS = {"topic", "known_title"}
SPLITS = {"development", "holdout"}


@dataclass(frozen=True)
class EvaluationQuery:
    """One query and the metadata required for grouped evaluation."""

    query_id: str
    text: str
    language: str
    intent: str
    split: str
    expected_book_id: str | None = None


def load_queries(path: Path) -> list[EvaluationQuery]:
    """Load ordered JSONL queries, rejecting ambiguous or duplicate records."""
    queries: list[EvaluationQuery] = []
    seen: set[str] = set()
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON on query line {line_number}") from error
        if not isinstance(row, dict):
            raise ValueError(f"Query line {line_number} must be an object")
        allowed = {"query_id", "text", "language", "intent", "split", "expected_book_id"}
        if set(row) - allowed:
            raise ValueError(f"Query line {line_number} has unknown fields")
        query_id = row.get("query_id")
        if not isinstance(query_id, str) or not QUERY_ID.fullmatch(query_id):
            raise ValueError(f"Query line {line_number} has invalid query_id")
        if query_id in seen:
            raise ValueError(f"Duplicate query_id: {query_id}")
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Query {query_id} has empty text")
        language = row.get("language")
        if not isinstance(language, str) or not LANGUAGE.fullmatch(language):
            raise ValueError(f"Query {query_id} has invalid language")
        intent = row.get("intent")
        if intent not in INTENTS:
            raise ValueError(f"Query {query_id} has invalid intent")
        split = row.get("split")
        if split not in SPLITS:
            raise ValueError(f"Query {query_id} has invalid split")
        expected_book_id = row.get("expected_book_id")
        if intent == "known_title":
            if not isinstance(expected_book_id, str) or not expected_book_id.strip():
                raise ValueError(f"Query {query_id} requires expected_book_id")
        elif expected_book_id is not None:
            raise ValueError(f"Topic query {query_id} cannot have expected_book_id")
        queries.append(
            EvaluationQuery(
                query_id=query_id,
                text=text.strip(),
                language=language,
                intent=intent,
                split=split,
                expected_book_id=expected_book_id,
            )
        )
        seen.add(query_id)
    if not queries:
        raise ValueError("Query file is empty")
    return queries
