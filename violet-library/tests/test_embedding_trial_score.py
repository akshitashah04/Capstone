"""Trial scoring rejects incomplete or changed evidence before KPI claims."""

import csv
import hashlib
import json

import pytest

from libraries_evaluation.assistant_v2_score import LABEL_FIELDS
from libraries_evaluation.embedding_model_trial import RUN_FIELDS, TRIAL_MODELS
from libraries_evaluation.embedding_trial_score import score_trial


def _write_trial(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    queries = tmp_path / "queries.jsonl"
    queries.write_text(json.dumps({
        "query_id": "q1", "text": "Practical climate book", "language": "en",
        "intent": "topic", "split": "development",
    }) + "\n")
    directory = tmp_path / "trial"
    directory.mkdir()
    orders = {
        "semantic": ["b1", "b2", "b3", "b4", "b5", "b6", "b7", "b8", "b9", "b10"],
        "hybrid": ["b2", "b3", "b4", "b5", "b1", "b6", "b7", "b8", "b9", "b10"],
    }
    with (directory / "runs.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=RUN_FIELDS)
        writer.writeheader()
        for mode, books in orders.items():
            for rank, bid in enumerate(books, 1):
                writer.writerow({
                    "query_id": "q1", "mode": mode, "rank": rank,
                    "book_id": bid, "title": f"Book {bid}", "authors": "A Writer",
                    "subjects": "Climate", "book_languages": "eng",
                    "publication_year": 2024, "book_url": f"https://example.org/{bid}",
                    "description_excerpt": "A source description",
                    "description_source": "abstract", "rank_score": 0.2,
                    "score_kind": "relative", "latency_ms": 15,
                })
    spec = TRIAL_MODELS["e5-base"]
    manifest = {
        "model_key": spec.key, "model_repo": spec.repo,
        "model_revision": spec.revision,
        "query_count": 1, "queries_sha256": hashlib.sha256(queries.read_bytes()).hexdigest(),
        "modes": ["semantic", "hybrid"], "top_k": 10,
        "judgment_status": "unjudged", "index_vectors_sha256": "vector-sha",
        "runs_sha256": hashlib.sha256((directory / "runs.csv").read_bytes()).hexdigest(),
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))
    labels = tmp_path / "labels.csv"
    with labels.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=LABEL_FIELDS)
        writer.writeheader()
        for index in range(1, 6):
            writer.writerow({
                "query_id": "q1", "book_id": f"b{index}",
                "clear_fit": "1" if index == 1 else "0",
                "basis": "new_preview", "evidence_url": "",
            })
    return queries, directory, labels, spec


def test_trial_score_uses_complete_assistant_labels_and_reports_first_clear_rank(tmp_path):
    queries, directory, labels, spec = _write_trial(tmp_path)
    report = score_trial(queries, directory, labels, spec)
    assert report["assessment"] == "assistant_not_human"
    assert report["judged_pairs"] == 5
    assert report["modes"]["semantic"]["top_five_success_count"] == 1
    assert report["modes"]["hybrid"]["top_one_success_count"] == 0
    assert report["query_findings"]["q1"]["hybrid"]["first_clear_rank"] == 5
    assert report["modes"]["semantic"]["strong_precision_at_5"] == 0.2


def test_trial_score_rejects_changed_results_and_missing_labels(tmp_path):
    queries, directory, labels, spec = _write_trial(tmp_path)
    with labels.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=LABEL_FIELDS)
        writer.writeheader()
    with pytest.raises(ValueError, match="missing"):
        score_trial(queries, directory, labels, spec)
    _queries, directory, labels, spec = _write_trial(tmp_path / "fresh")
    runs = directory / "runs.csv"
    runs.write_text(runs.read_text().replace("Book b1", "Changed title"))
    with pytest.raises(ValueError, match="checksum"):
        score_trial(_queries, directory, labels, spec)
