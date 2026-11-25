"""The new diagnostic remains separate from the frozen human-review labels."""

import csv
import json

from libraries_evaluation.rerank_diagnostic import collect_rerank_diagnostic


class FakeEngine:
    manifest = {"index_version": 2, "books_indexed": 1, "vectors_npy_sha256": "vectors"}

    def search(self, query, *, mode, limit):
        assert "beginner" in query
        assert limit == 10
        return [{
            "book_id": "b1", "title": "Book one", "authors": ["Author"],
            "subjects": ["AI"], "languages": ["eng"], "publication_year": 2025,
            "book_url": "https://example.org/b1", "description_excerpt": "A source description.",
            "description_source": "other_language_abstract", "rank_score": 0.25,
            "score_kind": (
                "cross_encoder_relative" if mode == "reranked" else "relative_rank_fusion"
            ),
        }]


def test_collect_rerank_diagnostic_saves_query_needs_and_source_fields(tmp_path):
    queries = tmp_path / "queries.jsonl"
    queries.write_text(json.dumps({
        "query_id": "q1", "text": "AI beginner book with examples", "language": "en",
        "intent": "topic", "split": "development",
    }) + "\n")
    output = tmp_path / "output"
    report = collect_rerank_diagnostic(FakeEngine(), queries, output,
                                       index_revision="index-commit")

    assert report["query_count"] == 1
    assert report["modes"] == ["keyword", "semantic", "hybrid", "reranked"]
    with (output / "runs.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 4
    assert rows[-1]["description_source"] == "other_language_abstract"
    assert rows[-1]["book_url"] == "https://example.org/b1"
    assert json.loads((output / "query-needs.json").read_text())[0]["needs"]["level"] == (
        "introductory"
    )
