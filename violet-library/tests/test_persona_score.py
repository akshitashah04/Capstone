"""Persona scoring uses a checked search run and complete top-five judgments."""

import csv
import hashlib
import json

import pytest

from libraries_evaluation.persona_score import LABEL_FIELDS, score_persona_results
from libraries_evaluation.schema import REVIEW_FIELDS, RUN_FIELDS, TIMING_FIELDS


def _csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path):
    persona = {
        "persona_id": "student-01", "level": "undergraduate", "major": "Business",
        "language": "en", "learning_goal": "Understand AI in business",
        "reading_need": "Beginner without coding", "query": "AI for business without coding",
    }
    personas = tmp_path / "personas.jsonl"
    personas.write_text(json.dumps(persona) + "\n", encoding="utf-8")
    queries = tmp_path / "queries.jsonl"
    queries.write_text(json.dumps({
        "query_id": "student-01", "text": persona["query"], "language": "en",
        "intent": "topic", "split": "development",
    }) + "\n", encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    orders = {
        "keyword": ["b2", "b3", "b5", "b6", "b1"],
        "semantic": ["b1", "b4", "b2", "b3", "b5"],
        "hybrid": ["b2", "b1", "b4", "b3", "b6"],
    }
    _csv(run_dir / "runs.csv", RUN_FIELDS, [
        {"query_id": "student-01", "mode": mode, "rank": rank, "book_id": book,
         "rank_score": "0.1", "semantic_similarity": "0.2"}
        for mode, books in orders.items() for rank, book in enumerate(books, 1)
    ])
    _csv(run_dir / "timings.csv", TIMING_FIELDS, [
        {"query_id": "student-01", "mode": mode, "latency_ms": 25,
         "result_count": 5} for mode in orders
    ])
    review = []
    for book in ("b1", "b2", "b3", "b4", "b5", "b6"):
        row = dict.fromkeys(REVIEW_FIELDS, "")
        row.update(query_id="student-01", query_text=persona["query"],
                   book_id=book, title=f"Title {book}")
        review.append(row)
    _csv(run_dir / "review.csv", REVIEW_FIELDS, review)
    manifest = {
        "schema_version": 1, "modes": ["keyword", "semantic", "hybrid"],
        "query_count": 1, "candidate_count": 6, "top_k": 10,
        "index_revision": "synthetic-index", "queries_sha256": _sha(queries),
        "runs_sha256": _sha(run_dir / "runs.csv"),
        "timings_sha256": _sha(run_dir / "timings.csv"),
        "review_sha256": _sha(run_dir / "review.csv"),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    labels = tmp_path / "labels.csv"
    grades = {"b1": (2, "yes", 2), "b2": (2, "unclear", 1),
              "b3": (0, "unclear", 0), "b4": (2, "yes", 2),
              "b5": (1, "unclear", 1), "b6": (0, "no", 0)}
    _csv(labels, LABEL_FIELDS, [
        {"query_id": "student-01", "book_id": book, "topic_grade": topic,
         "level_fit": level, "overall_grade": overall}
        for book, (topic, level, overall) in grades.items()
    ])
    return personas, queries, run_dir, labels


def test_persona_score_rewards_topic_and_reading_level(tmp_path):
    personas, queries, run_dir, labels = _fixture(tmp_path)
    report = score_persona_results(personas, queries, run_dir, labels)
    overall = report["metrics"]["overall"]
    assert overall["semantic"]["top_one_strong_rate"] == 1.0
    assert overall["keyword"]["top_one_strong_rate"] == 0.0
    assert overall["semantic"]["pooled_ndcg_at_5"] > overall["keyword"]["pooled_ndcg_at_5"]
    assert report["level_fit_counts"]["unclear"] == 3
    assert report["per_persona"][0]["top_book_by_mode"]["semantic"]["book_id"] == "b1"


def test_persona_score_rejects_missing_top_five_label(tmp_path):
    personas, queries, run_dir, labels = _fixture(tmp_path)
    rows = list(csv.DictReader(labels.open(encoding="utf-8")))[:-1]
    _csv(labels, LABEL_FIELDS, rows)
    with pytest.raises(ValueError, match="missing"):
        score_persona_results(personas, queries, run_dir, labels)
