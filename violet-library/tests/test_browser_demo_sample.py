"""Small synthetic checks for sample provenance and vector alignment."""

import csv
import hashlib
import io
import json
import zipfile

import numpy as np
import pytest

from libraries_evaluation import browser_demo_sample as sample
from libraries_evaluation.embedding_model_trial import BASELINE_INDEX_REVISION


def _result_bytes() -> bytes:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("query_id", "book_id", "rank"))
    writer.writeheader()
    for index in range(1, 51):
        writer.writerow({
            "query_id": f"student-{index:02d}", "book_id": f"book-{index % 3}",
            "rank": 1,
        })
    return stream.getvalue().encode()


def test_select_ids_checks_three_frozen_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(sample, "EXPECTED_BOOKS", 3)
    data = _result_bytes()
    digest = hashlib.sha256(data).hexdigest()
    archive_path = tmp_path / "v2.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("runs.csv", data)
        archive.writestr("manifest.json", json.dumps({
            "runs_sha256": digest, "index_revision": BASELINE_INDEX_REVISION,
            "queries_sha256": "same-queries",
        }))
    for key in ("e5-base", "gte-base"):
        folder = tmp_path / key
        folder.mkdir()
        (folder / "runs.csv").write_bytes(data)
        (folder / "manifest.json").write_text(json.dumps({
            "model_key": key, "runs_sha256": digest,
            "baseline_index_revision": BASELINE_INDEX_REVISION,
            "queries_sha256": "same-queries",
        }))
    assert sample.select_ids(archive_path, tmp_path / "e5-base", tmp_path / "gte-base") == {
        "book-0", "book-1", "book-2",
    }
    (tmp_path / "gte-base" / "runs.csv").write_bytes(data + b"changed")
    with pytest.raises(ValueError, match="gte-base result provenance"):
        sample.select_ids(archive_path, tmp_path / "e5-base", tmp_path / "gte-base")


def test_write_half_vectors_keeps_selected_order_and_rejects_bad_input(tmp_path):
    vectors = np.array([[1, 0], [0, 1], [-1, 0]], dtype=np.float32)
    target = tmp_path / "vectors.f16"
    sample.write_half_vectors(vectors, [2, 0], target)
    assert np.fromfile(target, dtype="<f2").reshape(2, 2).tolist() == [
        [-1, 0], [1, 0],
    ]
    with pytest.raises(ValueError, match="not normalized"):
        sample.write_half_vectors(np.array([[3, 4]], dtype=np.float32), [0], target)


def test_clean_description_rejects_export_placeholders():
    assert sample.clean_description("  undefined  ") == ""
    assert sample.clean_description("NaN") == ""
    assert sample.clean_description(None) == ""
    assert sample.clean_description("A real\n summary") == "A real summary"
