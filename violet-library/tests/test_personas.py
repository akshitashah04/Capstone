"""Frozen synthetic personas export to the existing search-evaluation contract."""

import json
from pathlib import Path

import pytest

from libraries_evaluation.personas import export_persona_queries, load_personas
from libraries_evaluation.queries import load_queries


def test_frozen_personas_export_exact_queries(tmp_path):
    source = Path("evaluation/personas/student-personas.jsonl")
    personas = load_personas(source)
    assert len(personas) == 50
    assert sum(persona["level"] == "undergraduate" for persona in personas) == 25
    assert sum(persona["level"] == "graduate" for persona in personas) == 25
    assert len({persona["major"] for persona in personas}) == 50
    output = tmp_path / "queries.jsonl"
    export_persona_queries(source, output)
    queries = load_queries(output)
    assert [query.text for query in queries] == [persona["query"] for persona in personas]
    assert all(query.intent == "topic" and query.split == "development" for query in queries)


def test_persona_loader_rejects_duplicate_ids(tmp_path):
    source = tmp_path / "personas.jsonl"
    persona = {
        "persona_id": "student-01", "level": "undergraduate", "major": "Business",
        "language": "en", "learning_goal": "Understand AI", "reading_need": "Introductory",
        "query": "I need a beginner AI book.",
    }
    source.write_text("\n".join(json.dumps(persona) for _ in range(2)) + "\n")
    with pytest.raises(ValueError, match="Duplicate persona"):
        load_personas(source)
