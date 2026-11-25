"""Synthetic tests for cloud-only embedding model comparisons."""

import csv
import hashlib
import json

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from libraries_data.schema import BOOK_SCHEMA
from libraries_evaluation.embedding_model_trial import (
    TRIAL_MODELS,
    TrialEncoder,
    assemble_trial,
    check_transformers_compatibility,
    collect_trial,
)
from libraries_search.build import build_index
from libraries_search.shards import build_shard


class FakeEncoder:
    def __init__(self, dimensions=2):
        self.inputs = []
        self.dimensions = dimensions

    def encode(self, texts, **_kwargs):
        self.inputs.extend(texts)
        return np.asarray([
            [1.0] + [0.0] * (self.dimensions - 1)
            if "First" in text else [0.0, 1.0] + [0.0] * (self.dimensions - 2)
            for text in texts
        ], dtype=np.float32)


def _book(book_id, title):
    return {
        "book_id": book_id, "title": title, "alternate_titles": [],
        "authors": [], "subjects": ["Education"], "classifications": [],
        "abstract": "A useful introduction", "other_language_abstract": "",
        "languages": ["eng"], "publication_year": 2024, "isbns": [],
        "doi": "", "publisher": "Example Press", "book_url": f"https://example.org/{book_id}",
        "download_url": "", "license_url": "",
        "semantic_text": f"Title: {title}\nDescription: A useful introduction",
    }


def test_trial_encoders_use_model_specific_input_conventions():
    e5_model = FakeEncoder()
    gte_model = FakeEncoder()
    TrialEncoder(e5_model, TRIAL_MODELS["e5-base"]).encode(
        ["query: First subject", "passage: Second book"]
    )
    TrialEncoder(gte_model, TRIAL_MODELS["gte-base"]).encode(
        ["query: First subject", "passage: Second book"]
    )
    assert e5_model.inputs == ["query: First subject", "passage: Second book"]
    assert gte_model.inputs == ["First subject", "Second book"]


def test_gte_rejects_transformers_five_to_avoid_corrupt_position_ids():
    check_transformers_compatibility(TRIAL_MODELS["e5-base"], "5.23.0")
    check_transformers_compatibility(TRIAL_MODELS["gte-base"], "4.57.6")
    with pytest.raises(RuntimeError, match="transformers<5"):
        check_transformers_compatibility(TRIAL_MODELS["gte-base"], "5.23.0")


def test_assemble_trial_reuses_verified_book_database_and_rejects_bad_shard(tmp_path):
    books = [_book("a", "First book"), _book("b", "Second book")]
    source = tmp_path / "books.parquet"
    pq.write_table(pa.Table.from_pylist(books, schema=BOOK_SCHEMA), source)
    source_manifest = {
        "schema_version": 1, "books_written": 2,
        "parquet_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    baseline = tmp_path / "baseline"
    build_index(
        source, source_manifest, baseline, FakeEncoder(),
        source_revision="source-commit", model_repo="small", model_revision="small-sha",
        dimensions=2, batch_size=1,
    )
    baseline_manifest = json.loads((baseline / "manifest.json").read_text())
    spec = TRIAL_MODELS["e5-base"]
    shards = tmp_path / "shards"
    shards.mkdir()
    for index in range(2):
        build_shard(
            source, source_manifest, shards / f"shard-{index}",
            FakeEncoder(dimensions=spec.dimensions), shard_index=index, shard_count=2,
            source_revision="source-commit", model_repo=spec.repo,
            model_revision=spec.revision, dimensions=spec.dimensions, batch_size=1,
        )
    result = assemble_trial(
        shards, tmp_path / "trial", source_manifest, baseline_manifest,
        baseline / "books.sqlite", spec, shard_count=2, source_revision="source-commit",
    )
    assert result["books_indexed"] == 2
    assert result["model_repo"] == spec.repo
    assert result["books_sqlite_sha256"] == baseline_manifest["books_sqlite_sha256"]
    assert np.load(tmp_path / "trial" / "vectors.npy").shape == (2, spec.dimensions)

    (shards / "shard-1" / "manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="Shard 1"):
        assemble_trial(
            shards, tmp_path / "bad", source_manifest, baseline_manifest,
            baseline / "books.sqlite", spec, shard_count=2, source_revision="source-commit",
        )
    assert not (tmp_path / "bad").exists()


def test_collect_trial_saves_unjudged_comparable_results(tmp_path):
    queries = tmp_path / "queries.jsonl"
    queries.write_text(json.dumps({
        "query_id": "q1", "text": "A beginner book", "language": "en",
        "intent": "topic", "split": "development",
    }) + "\n")

    class FakeSearcher:
        manifest = {"index_version": 2, "vectors_npy_sha256": "vector-sha"}

        def search(self, query, *, mode, limit):
            assert query == "A beginner book" and mode in {"semantic", "hybrid"}
            return [{
                "book_id": str(index), "title": f"Book {index}", "authors": [],
                "subjects": [], "languages": ["eng"], "publication_year": 2024,
                "book_url": f"https://example.org/{index}",
                "description_excerpt": "A source description",
                "description_source": "abstract", "rank_score": 0.2,
                "score_kind": "relative", "keyword_rank": None,
                "semantic_rank": index,
            } for index in range(limit)]

    output = tmp_path / "results"
    report = collect_trial(FakeSearcher(), queries, output, TRIAL_MODELS["e5-base"])
    assert report["query_count"] == 1
    assert report["judgment_status"] == "unjudged"
    with (output / "runs.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 20
    assert [row["mode"] for row in rows[::10]] == ["semantic", "hybrid"]
    assert report["runs_sha256"] == hashlib.sha256((output / "runs.csv").read_bytes()).hexdigest()
