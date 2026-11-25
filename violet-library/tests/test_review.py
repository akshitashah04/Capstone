"""Small synthetic contracts for the shared human-review sheets."""

import csv
import hashlib
import json

import pytest

from libraries_evaluation.collect import REVIEW_FIELDS
from libraries_evaluation.review import assemble_judgments, initialize_review, review_progress


def _write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _rows(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _source(tmp_path):
    queries_path = tmp_path / "queries.jsonl"
    queries_path.write_text(
        '\n'.join(
            [
                json.dumps(
                    {
                        "query_id": query_id,
                        "text": text,
                        "language": "en",
                        "intent": "topic",
                        "split": "development",
                    }
                )
                for query_id, text in (("q1", "climate cities"), ("q2", "urban health"))
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    books = (("q1", "climate cities", "b2"), ("q1", "climate cities", "b1"),
             ("q2", "urban health", "b3"))
    rows = []
    for query_id, query_text, book_id in books:
        row = dict.fromkeys(REVIEW_FIELDS, "")
        row.update(
            query_id=query_id,
            query_text=query_text,
            query_language="en",
            query_intent="topic",
            query_split="development",
            book_id=book_id,
            title=f"Title {book_id}",
            book_url=f"https://example.org/{book_id}",
            abstract_excerpt=f"About {book_id}\nwith context",
        )
        rows.append(row)
    review_path = run_dir / "review.csv"
    _write_csv(review_path, REVIEW_FIELDS, rows)
    manifest = {
        "schema_version": 1,
        "query_count": 2,
        "candidate_count": 3,
        "queries_sha256": hashlib.sha256(queries_path.read_bytes()).hexdigest(),
        "review_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
        "index_revision": "fixed-index",
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return queries_path, run_dir


def _set_grade(path, book_id, grade):
    rows = _rows(path)
    for row in rows:
        if row["book_id"] == book_id:
            row["relevance"] = grade
    _write_csv(path, tuple(rows[0]), rows)


def test_initialize_review_creates_blinded_per_query_sheets(tmp_path):
    queries_path, run_dir = _source(tmp_path)
    review_dir = tmp_path / "sheets"
    manifest = initialize_review(queries_path, run_dir, review_dir)

    assert manifest["candidate_count"] == 3
    assert len(manifest["pair_sha256"]) == 64
    assert sorted(path.name for path in review_dir.glob("*.csv")) == ["q1.csv", "q2.csv"]
    q1 = _rows(review_dir / "q1.csv")
    assert [row["book_id"] for row in q1] == ["b1", "b2"]
    assert all(row["relevance"] == "" for row in q1)
    assert all("rank" not in row for row in q1)
    assert q1[0]["abstract_excerpt"] == "About b1 with context"
    assert review_progress(queries_path, review_dir)["remaining_count"] == 3


def test_partial_review_reports_progress_and_complete_review_assembles(tmp_path):
    queries_path, run_dir = _source(tmp_path)
    review_dir = tmp_path / "sheets"
    initialize_review(queries_path, run_dir, review_dir)
    _set_grade(review_dir / "q1.csv", "b1", "2")

    progress = review_progress(queries_path, review_dir)
    assert progress["graded_count"] == 1
    assert progress["remaining_count"] == 2
    assert progress["complete"] is False
    output_path = tmp_path / "judgments.csv"
    assert assemble_judgments(queries_path, review_dir, run_dir, output_path) is False
    assert not output_path.exists()

    _set_grade(review_dir / "q1.csv", "b2", "0")
    _set_grade(review_dir / "q2.csv", "b3", "1")
    assert assemble_judgments(queries_path, review_dir, run_dir, output_path) is True
    judgments = _rows(output_path)
    assert {row["book_id"]: row["relevance"] for row in judgments} == {
        "b1": "2", "b2": "0", "b3": "1"
    }
    assert tuple(judgments[0]) == REVIEW_FIELDS


@pytest.mark.parametrize("change", ["invalid_grade", "missing_pair", "extra_pair", "changed_title"])
def test_review_rejects_invalid_or_changed_sheets(tmp_path, change):
    queries_path, run_dir = _source(tmp_path)
    review_dir = tmp_path / "sheets"
    initialize_review(queries_path, run_dir, review_dir)
    path = review_dir / "q1.csv"
    rows = _rows(path)
    if change == "invalid_grade":
        rows[0]["relevance"] = "3"
    elif change == "missing_pair":
        rows.pop()
    elif change == "extra_pair":
        rows.append({**rows[0], "book_id": "not-in-pilot"})
    else:
        rows[0]["title"] = "Wrong book"
    _write_csv(path, tuple(rows[0]), rows)

    with pytest.raises(ValueError):
        review_progress(queries_path, review_dir)


def test_assembly_rejects_changed_cloud_candidate_pool(tmp_path):
    queries_path, run_dir = _source(tmp_path)
    review_dir = tmp_path / "sheets"
    initialize_review(queries_path, run_dir, review_dir)
    for book_id, grade in (("b1", "2"), ("b2", "0")):
        _set_grade(review_dir / "q1.csv", book_id, grade)
    _set_grade(review_dir / "q2.csv", "b3", "1")
    rows = _rows(run_dir / "review.csv")
    rows[0]["book_id"] = "new-book"
    _write_csv(run_dir / "review.csv", REVIEW_FIELDS, rows)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["review_sha256"] = hashlib.sha256((run_dir / "review.csv").read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="candidate pool"):
        assemble_judgments(queries_path, review_dir, run_dir, tmp_path / "judgments.csv")


def test_assembly_checks_cloud_pool_before_humans_finish_grading(tmp_path):
    queries_path, run_dir = _source(tmp_path)
    review_dir = tmp_path / "sheets"
    initialize_review(queries_path, run_dir, review_dir)
    rows = _rows(run_dir / "review.csv")
    rows[0]["book_id"] = "new-book"
    _write_csv(run_dir / "review.csv", REVIEW_FIELDS, rows)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["review_sha256"] = hashlib.sha256((run_dir / "review.csv").read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="candidate pool"):
        assemble_judgments(queries_path, review_dir, run_dir, tmp_path / "judgments.csv")
