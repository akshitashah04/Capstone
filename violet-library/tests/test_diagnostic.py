"""Diagnostic scoring uses synthetic runs and never downloads an index."""

import csv
import hashlib
import json

import pytest

from libraries_evaluation.diagnostic import score_target_recovery, write_ai_judgments
from libraries_evaluation.schema import REVIEW_FIELDS, RUN_FIELDS, TIMING_FIELDS
from libraries_evaluation.score import score_results


def _write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(tmp_path):
    queries = tmp_path / "queries.jsonl"
    queries.write_text(
        "\n".join(
            json.dumps(
                {
                    "query_id": query_id,
                    "text": text,
                    "language": language,
                    "intent": "topic",
                    "split": "development",
                }
            )
            for query_id, text, language in (("q1", "floods", "en"), ("q2", "villes", "fr"))
        )
        + "\n",
        encoding="utf-8",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    rankings = {
        ("q1", "keyword"): ["b2", "b1"],
        ("q1", "semantic"): ["b1", "b2"],
        ("q1", "hybrid"): ["b1", "b2"],
        ("q2", "keyword"): ["b1", "b2"],
        ("q2", "semantic"): ["b2", "b1"],
        ("q2", "hybrid"): ["b1", "b2"],
    }
    runs = [
        {"query_id": q, "mode": mode, "rank": rank, "book_id": book,
         "rank_score": "0.1", "semantic_similarity": "0.2"}
        for (q, mode), books in rankings.items()
        for rank, book in enumerate(books, 1)
    ]
    timings = [
        {"query_id": q, "mode": mode, "latency_ms": 100 if q == "q1" else 200,
         "result_count": 2}
        for q, mode in rankings
    ]
    review = []
    for q, text in (("q1", "floods"), ("q2", "villes")):
        for book in ("b1", "b2"):
            row = dict.fromkeys(REVIEW_FIELDS, "")
            row.update(query_id=q, query_text=text, book_id=book,
                       title=f"Title {book}", book_url=f"https://example.org/{book}")
            review.append(row)
    _write_csv(run_dir / "runs.csv", RUN_FIELDS, runs)
    _write_csv(run_dir / "timings.csv", TIMING_FIELDS, timings)
    _write_csv(run_dir / "review.csv", REVIEW_FIELDS, review)
    manifest = {
        "schema_version": 1,
        "modes": ["keyword", "semantic", "hybrid"],
        "query_count": 2,
        "candidate_count": 4,
        "top_k": 10,
        "index_revision": "synthetic-index",
        "queries_sha256": _sha(queries),
        "runs_sha256": _sha(run_dir / "runs.csv"),
        "timings_sha256": _sha(run_dir / "timings.csv"),
        "review_sha256": _sha(run_dir / "review.csv"),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    targets = tmp_path / "targets.json"
    targets.write_text(
        json.dumps(
            {"schema_version": 1, "targets": [
                {"query_id": "q1", "target_book_id": "b1"},
                {"query_id": "q2", "target_book_id": "b2"},
            ]}
        ),
        encoding="utf-8",
    )
    return queries, run_dir, targets


def test_target_recovery_compares_modes_and_languages(tmp_path):
    queries, run_dir, targets = _run(tmp_path)
    report = score_target_recovery(queries, run_dir, targets)
    assert report["query_count"] == 2
    assert report["overall"]["keyword"]["hit_at_1"] == 0.0
    assert report["overall"]["semantic"]["hit_at_1"] == 1.0
    assert report["overall"]["hybrid"]["hit_at_1"] == 0.5
    assert report["overall"]["hybrid"]["hit_at_5"] == 1.0
    assert report["overall"]["hybrid"]["mrr_at_10"] == 0.75
    assert report["overall"]["hybrid"]["latency_p95_ms"] == 200
    assert report["by_language"]["fr"]["hybrid"]["hit_at_1"] == 0.0


def test_ai_labels_overlay_exact_pool_for_existing_scorer(tmp_path):
    queries, run_dir, _targets = _run(tmp_path)
    labels = tmp_path / "ai-labels.csv"
    _write_csv(labels, ("query_id", "book_id", "grade"), [
        {"query_id": q, "book_id": book, "grade": grade}
        for q, book, grade in (("q1", "b1", 2), ("q1", "b2", 0),
                               ("q2", "b1", 1), ("q2", "b2", 2))
    ])
    output = tmp_path / "judgments.csv"
    write_ai_judgments(queries, run_dir, labels, output)
    report = score_results(queries, run_dir, output)
    assert report["judged_pairs"] == 4
    assert report["metrics"]["overall"]["semantic"]["success_at_5"] == 1.0


@pytest.mark.parametrize("error", ["missing", "duplicate", "invalid"])
def test_ai_labels_reject_incomplete_or_invalid_pool(tmp_path, error):
    queries, run_dir, _targets = _run(tmp_path)
    labels = tmp_path / "ai-labels.csv"
    rows = [
        {"query_id": q, "book_id": book, "grade": "2"}
        for q in ("q1", "q2") for book in ("b1", "b2")
    ]
    if error == "missing":
        rows.pop()
    elif error == "duplicate":
        rows.append(rows[0])
    else:
        rows[0]["grade"] = "3"
    _write_csv(labels, ("query_id", "book_id", "grade"), rows)
    with pytest.raises(ValueError):
        write_ai_judgments(queries, run_dir, labels, tmp_path / "judgments.csv")
    assert not (tmp_path / "judgments.csv").exists()
