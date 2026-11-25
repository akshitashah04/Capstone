"""The v2 review packet must preserve provenance and genuine human grades."""

import csv
import hashlib
import io
import json
from zipfile import ZipFile

import pytest

from libraries_evaluation.assistant_v2_score import LABEL_FIELDS, score_assistant_packet
from libraries_evaluation.review_packet import (
    initialize_packet,
    main,
    packet_progress,
    score_packet,
)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _csv_bytes(fields, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write_archive(path, members):
    with ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)


def _doab_fixture(tmp_path, *, split="development"):
    queries = tmp_path / "queries.jsonl"
    queries.write_text(json.dumps({
        "query_id": "q1", "text": "Easy book about AI", "language": "en",
        "intent": "topic", "split": split,
    }) + "\n", encoding="utf-8")
    orders = {
        "keyword": ["b1", "b2", "b3", "b4", "b5"],
        "semantic": ["b2", "b3", "b4", "b5", "b6"],
        "hybrid": ["b2", "b1", "b3", "b4", "b5"],
        "reranked": ["b6", "b7", "b8", "b1", "b3"],
    }
    fields = (
        "query_id", "mode", "rank", "book_id", "title", "authors", "subjects",
        "book_languages", "publication_year", "book_url", "description_excerpt",
        "description_source", "rank_score", "score_kind", "latency_ms",
    )
    rows = [
        {
            "query_id": "q1", "mode": mode, "rank": rank, "book_id": book,
            "title": f"Title {book}", "authors": "A Writer", "subjects": "AI",
            "book_languages": "eng", "publication_year": "2024",
            "book_url": f"https://example.org/{book}",
            "description_excerpt": f"Description {book}", "description_source": "abstract",
            "rank_score": "0.2", "score_kind": "relative", "latency_ms": "10",
        }
        for mode, books in orders.items() for rank, book in enumerate(books, 1)
    ]
    runs = _csv_bytes(fields, rows)
    needs = b"[]\n"
    manifest = {
        "index_revision": "v2-pinned", "index_path": "search/v2",
        "query_count": 1, "queries_sha256": _sha(queries.read_bytes()),
        "modes": list(orders), "judgment_status": "unjudged",
        "runs_sha256": _sha(runs), "query_needs_sha256": _sha(needs),
    }
    archive = tmp_path / "doab.zip"
    _write_archive(archive, {
        "runs.csv": runs, "query-needs.json": needs,
        "manifest.json": json.dumps(manifest).encode(),
    })
    return queries, archive


def _fill_sheet(path):
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
        fields = list(rows[0])
    for row in rows:
        row.update(
            topic_grade="2" if row["book_id"] == "b2" else "0",
            reading_fit="yes", language_fit="yes",
            overall_grade="2" if row["book_id"] == "b2" else "0",
        )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_doab_packet_is_blind_and_scores_only_after_review(tmp_path):
    queries, archive = _doab_fixture(tmp_path)
    packet = tmp_path / "packet"
    manifest = initialize_packet("doab", archive, queries, packet)
    assert manifest["candidate_count"] == 8
    assert manifest["index_revision"] == "v2-pinned"
    with (packet / "q1.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert [row["book_id"] for row in rows] == [f"b{i}" for i in range(1, 9)]
    assert "rank" not in rows[0] and "mode" not in rows[0]
    assert all(row["overall_grade"] == "" for row in rows)
    assert packet_progress(queries, packet, archive)["remaining_count"] == 8
    with pytest.raises(ValueError, match="incomplete"):
        score_packet(queries, packet, archive)

    _fill_sheet(packet / "q1.csv")
    assert packet_progress(queries, packet, archive)["complete"] is True
    report = score_packet(queries, packet, archive)
    assert report["modes"]["keyword"]["top_five_success_count"] == 1
    assert report["modes"]["semantic"]["top_one_success_count"] == 1
    assert report["modes"]["reranked"]["top_five_success_count"] == 0
    assert report["by_split"]["development"]["query_count"] == 1
    assert report["grade_counts"]["overall_grade"] == {"0": 7, "2": 1}


def test_holdout_report_does_not_claim_holdout_was_unevaluated(tmp_path):
    queries, archive = _doab_fixture(tmp_path, split="holdout")
    packet = tmp_path / "packet"
    initialize_packet("doab", archive, queries, packet)
    _fill_sheet(packet / "q1.csv")
    report = score_packet(queries, packet, archive)
    assert report["by_split"]["holdout"]["query_count"] == 1
    assert "holdout not evaluated" not in report["limits"].lower()


def test_packet_rejects_modified_source_and_review_metadata(tmp_path):
    queries, archive = _doab_fixture(tmp_path)
    packet = tmp_path / "packet"
    initialize_packet("doab", archive, queries, packet)
    with ZipFile(archive, "a") as source:
        source.writestr("extra.txt", "changed")
    with pytest.raises(ValueError, match="archive"):
        packet_progress(queries, packet, archive)

    queries, archive = _doab_fixture(tmp_path)
    with (packet / "q1.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
        fields = list(rows[0])
    rows[0]["title"] = "A different book"
    with (packet / "q1.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="metadata"):
        packet_progress(queries, packet, archive)


def test_invalid_or_inconsistent_human_grade_is_rejected(tmp_path):
    queries, archive = _doab_fixture(tmp_path)
    packet = tmp_path / "packet"
    initialize_packet("doab", archive, queries, packet)
    _fill_sheet(packet / "q1.csv")
    with (packet / "q1.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
        fields = list(rows[0])
    rows[0]["reading_fit"] = "maybe"
    with (packet / "q1.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="grade"):
        packet_progress(queries, packet, archive)


def test_progress_removes_stale_score_when_review_is_incomplete(tmp_path, monkeypatch):
    queries, archive = _doab_fixture(tmp_path)
    packet = tmp_path / "packet"
    initialize_packet("doab", archive, queries, packet)
    old_score = tmp_path / "old-score.json"
    old_score.write_text('{"false_claim": true}', encoding="utf-8")
    monkeypatch.setattr("sys.argv", [
        "review-packet", "progress", "--queries", str(queries),
        "--archive", str(archive), "--packet-dir", str(packet),
        "--score-output", str(old_score),
    ])
    main()
    assert not old_score.exists()


def test_score_command_removes_old_report_before_refusing_incomplete_review(tmp_path, monkeypatch):
    queries, archive = _doab_fixture(tmp_path)
    packet = tmp_path / "packet"
    initialize_packet("doab", archive, queries, packet)
    old_score = tmp_path / "old-score.json"
    old_score.write_text('{"false_claim": true}', encoding="utf-8")
    monkeypatch.setattr("sys.argv", [
        "review-packet", "score", "--queries", str(queries),
        "--archive", str(archive), "--packet-dir", str(packet),
        "--output", str(old_score),
    ])
    with pytest.raises(ValueError, match="incomplete"):
        main()
    assert not old_score.exists()


def test_progress_removes_old_report_even_when_packet_validation_fails(tmp_path, monkeypatch):
    queries, archive = _doab_fixture(tmp_path)
    packet = tmp_path / "packet"
    initialize_packet("doab", archive, queries, packet)
    old_score = tmp_path / "old-score.json"
    old_score.write_text('{"false_claim": true}', encoding="utf-8")
    (packet / "q1.csv").unlink()
    monkeypatch.setattr("sys.argv", [
        "review-packet", "progress", "--queries", str(queries),
        "--archive", str(archive), "--packet-dir", str(packet),
        "--score-output", str(old_score),
    ])
    with pytest.raises(ValueError, match="missing or extra"):
        main()
    assert not old_score.exists()


def test_textbook_packet_matches_frozen_miss_list(tmp_path):
    queries, _ = _doab_fixture(tmp_path)
    misses = tmp_path / "misses.json"
    misses.write_text(json.dumps({"per_query": [
        {"query_id": "q1", "category": "no_topic_fit_in_judged_pool"}
    ]}), encoding="utf-8")
    fields = (
        "query_id", "query_text", "rank", "book_id", "title", "subjects",
        "book_url", "description_excerpt", "rank_score", "score_kind",
    )
    rows = [{
        "query_id": "q1", "query_text": "Easy book about AI", "rank": rank,
        "book_id": f"otl:{rank}", "title": f"Textbook {rank}", "subjects": "AI",
        "book_url": f"https://example.org/{rank}", "description_excerpt": "A summary",
        "rank_score": "1", "score_kind": "relative",
    } for rank in range(1, 6)]
    results = _csv_bytes(fields, rows)
    archive = tmp_path / "otl.zip"
    _write_archive(archive, {
        "coverage-results.csv": results,
        "coverage-manifest.json": json.dumps({
            "queries_examined": 1,
            "queries_sha256": _sha(queries.read_bytes()),
            "miss_report_sha256": _sha(misses.read_bytes()),
            "results_sha256": _sha(results),
            "source_csv_sha256": "source", "judgment_status": "unjudged",
        }).encode(),
        "source-quality.json": b"{}",
    })
    packet = tmp_path / "packet"
    manifest = initialize_packet("textbook", archive, queries, packet, miss_report=misses)
    assert manifest["candidate_count"] == 5
    assert packet_progress(queries, packet, archive, miss_report=misses)["complete"] is False
    assert (packet / "q1.csv").exists()


def test_assistant_score_uses_separate_complete_labels_without_editing_human_sheets(tmp_path):
    queries, archive = _doab_fixture(tmp_path)
    packet = tmp_path / "packet"
    initialize_packet("doab", archive, queries, packet)
    with (packet / "q1.csv").open(newline="", encoding="utf-8") as stream:
        candidates = list(csv.DictReader(stream))
    labels = tmp_path / "assistant-labels.csv"
    with labels.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=LABEL_FIELDS)
        writer.writeheader()
        writer.writerows({
            "query_id": row["query_id"], "book_id": row["book_id"],
            "clear_fit": "1" if row["book_id"] == "b2" else "0",
            "basis": "new_preview", "evidence_url": "",
        } for row in candidates)
    report = score_assistant_packet(queries, packet, archive, labels)
    assert report["assessment"] == "assistant_not_human"
    assert report["modes"]["keyword"]["success_at_5"] == 1.0
    assert report["modes"]["semantic"]["top_one_success_count"] == 1
    assert report["modes"]["reranked"]["success_at_5"] == 0.0
    assert report["modes"]["keyword"]["strong_precision_at_5"] == 0.2
    assert report["modes"]["keyword"]["warm_p95_ms"] == 10.0
    assert report["query_findings"]["q1"]["semantic"]["first_clear_rank"] == 1
    assert report["query_findings"]["q1"]["reranked"]["first_clear_rank"] is None
    assert packet_progress(queries, packet, archive)["graded_count"] == 0

    with labels.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=LABEL_FIELDS)
        writer.writeheader()
        writer.writerows({
            "query_id": row["query_id"], "book_id": row["book_id"],
            "clear_fit": "0", "basis": "new_preview", "evidence_url": "",
        } for row in candidates[:-1])
    with pytest.raises(ValueError, match="missing"):
        score_assistant_packet(queries, packet, archive, labels)


def test_assistant_score_describes_holdout_accurately(tmp_path):
    queries, archive = _doab_fixture(tmp_path, split="holdout")
    packet = tmp_path / "packet"
    initialize_packet("doab", archive, queries, packet)
    with (packet / "q1.csv").open(newline="", encoding="utf-8") as stream:
        candidates = list(csv.DictReader(stream))
    labels = tmp_path / "assistant-labels.csv"
    with labels.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=LABEL_FIELDS)
        writer.writeheader()
        writer.writerows({
            "query_id": row["query_id"], "book_id": row["book_id"],
            "clear_fit": "0", "basis": "new_preview", "evidence_url": "",
        } for row in candidates)
    report = score_assistant_packet(queries, packet, archive, labels)
    assert "authored development" not in report["limits"]
    assert report["by_split"]["holdout"]["query_count"] == 1
