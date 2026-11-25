"""Synthetic catalog tests; no real DOAB data is downloaded on a laptop."""

import hashlib
import json
import sqlite3

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from libraries_data.schema import BOOK_SCHEMA
from libraries_search.assemble import assemble_index
from libraries_search.build import build_index, write_index_manifest
from libraries_search.publish import publish_index, validate_index_bundle
from libraries_search.search import SearchEngine
from libraries_search.shards import build_shard
from libraries_search.upgrade import upgrade_index


class FakeEncoder:
    def __init__(self, vectors: dict[str, list[float]]):
        self.vectors = vectors
        self.inputs: list[str] = []

    def encode(self, texts, **_kwargs):
        self.inputs.extend(texts)
        return np.asarray([self.vectors[text] for text in texts], dtype=np.float32)


class FakeReranker:
    def __init__(self):
        self.pairs = []

    def predict(self, pairs, **_kwargs):
        self.pairs.extend(pairs)
        return np.asarray([
            9.0 if "Marine resilience" in book_text else 1.0 for _, book_text in pairs
        ])


def _book(book_id: str, title: str, description: str) -> dict[str, object]:
    return {
        "book_id": book_id,
        "title": title,
        "alternate_titles": [],
        "authors": ["Example Author"],
        "subjects": ["Cities"],
        "classifications": [],
        "abstract": description,
        "other_language_abstract": "",
        "languages": ["eng"],
        "publication_year": 2024,
        "isbns": [],
        "doi": "",
        "publisher": "Example Press",
        "book_url": f"https://example.org/{book_id}",
        "download_url": "",
        "license_url": "",
        "semantic_text": f"Title: {title}\nSubject: Cities\nDescription: {description}",
    }


def _source(tmp_path, books):
    parquet_path = tmp_path / "books.parquet"
    pq.write_table(pa.Table.from_pylist(books, schema=BOOK_SCHEMA), parquet_path)
    checksum = hashlib.sha256(parquet_path.read_bytes()).hexdigest()
    return parquet_path, {
        "schema_version": 1,
        "books_written": len(books),
        "parquet_sha256": checksum,
    }


def _encoder(books):
    mapping = {
        f"passage: {books[0]['semantic_text']}": [1.0, 0.0],
        f"passage: {books[1]['semantic_text']}": [0.8, 0.6],
        f"passage: {books[2]['semantic_text']}": [0.0, 1.0],
        "query: coastal adaptation": [1.0, 0.0],
        "query: Marine resilience": [0.0, 1.0],
    }
    return FakeEncoder(mapping)


def test_build_index_keeps_book_order_and_checks_both_artifacts(tmp_path):
    books = [
        _book("a", "Coastal planning", "Sea level response"),
        _book("b", "Urban studies", "Flooding in cities"),
        _book("c", "Marine resilience", "Ocean conservation"),
    ]
    source, source_manifest = _source(tmp_path, books)
    encoder = _encoder(books)
    output = tmp_path / "index"

    manifest = build_index(
        source,
        source_manifest,
        output,
        encoder,
        source_revision="source-commit",
        model_repo="example/model",
        model_revision="model-commit",
        dimensions=2,
        batch_size=2,
    )

    assert manifest["books_indexed"] == 3
    assert manifest["source_revision"] == "source-commit"
    assert manifest["model_revision"] == "model-commit"
    assert encoder.inputs[:3] == [f"passage: {book['semantic_text']}" for book in books]
    np.testing.assert_allclose(np.load(output / "vectors.npy")[0], [1, 0])
    with sqlite3.connect(output / "books.sqlite") as connection:
        assert connection.execute("SELECT book_id FROM books ORDER BY ordinal").fetchall() == [
            ("a",),
            ("b",),
            ("c",),
        ]
    assert validate_index_bundle(output)["books_indexed"] == 3
    assert json.loads((output / "manifest.json").read_text()) == manifest


def test_build_index_rejects_changed_source_before_creating_output(tmp_path):
    books = [_book("a", "Coastal planning", "Sea level response")]
    source, source_manifest = _source(tmp_path, books)
    source_manifest["parquet_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="checksum"):
        build_index(
            source,
            source_manifest,
            tmp_path / "index",
            FakeEncoder({}),
            source_revision="source-commit",
            model_repo="example/model",
            model_revision="model-commit",
            dimensions=2,
        )
    assert not (tmp_path / "index").exists()


def test_search_uses_our_keyword_and_semantic_lists(tmp_path):
    books = [
        _book("a", "Coastal planning", "Sea level response"),
        _book("b", "Urban studies", "Flooding in cities"),
        _book("c", "Marine resilience", "Ocean conservation"),
    ]
    source, source_manifest = _source(tmp_path, books)
    encoder = _encoder(books)
    output = tmp_path / "index"
    build_index(
        source,
        source_manifest,
        output,
        encoder,
        source_revision="source-commit",
        model_repo="example/model",
        model_revision="model-commit",
        dimensions=2,
        batch_size=2,
    )

    with SearchEngine(output, encoder) as engine:
        semantic = engine.search("coastal adaptation", mode="semantic", limit=2)
        keyword = engine.search("Marine resilience", mode="keyword", limit=2)
        hybrid = engine.search("Marine resilience", mode="hybrid", limit=2)

    assert [item["book_id"] for item in semantic] == ["a", "b"]
    assert keyword[0]["book_id"] == "c"
    assert hybrid[0]["book_id"] == "c"
    assert hybrid[0]["keyword_rank"] == 1
    assert hybrid[0]["semantic_rank"] == 1
    assert hybrid[0]["score_kind"] == "relative_rank_fusion"
    assert "query: coastal adaptation" in encoder.inputs


def test_source_description_and_alternate_title_are_searchable_with_provenance(tmp_path):
    book = _book("a", "Primary title", "")
    book["alternate_titles"] = ["Hidden coastal guide"]
    book["other_language_abstract"] = "An original source description in another language."
    book["semantic_text"] = (
        "Title: Primary title\nAlternative title: Hidden coastal guide\n"
        "Subject: Cities\nOther-language description: "
        "An original source description in another language."
    )
    source, source_manifest = _source(tmp_path, [book])
    output = tmp_path / "index"
    build_index(
        source, source_manifest, output,
        FakeEncoder({f"passage: {book['semantic_text']}": [1.0, 0.0]}),
        source_revision="source-commit", model_repo="example/model",
        model_revision="model-commit", dimensions=2,
    )

    with sqlite3.connect(output / "books.sqlite") as database:
        row = database.execute(
            "SELECT abstract, description_source FROM books WHERE book_id = 'a'"
        ).fetchone()
        assert row == (book["other_language_abstract"], "other_language_abstract")
    with SearchEngine(output, FakeEncoder({})) as engine:
        result = engine.search("Hidden coastal guide", mode="keyword", limit=1)[0]
    assert result["book_id"] == "a"
    assert result["description_source"] == "other_language_abstract"
    assert result["description_excerpt"].startswith("An original source description")


def test_upgrade_keeps_existing_vectors_and_checks_source_order(tmp_path):
    books = [_book("a", "Coastal planning", "Sea level response"),
             _book("b", "Urban studies", "Flooding in cities")]
    source, source_manifest = _source(tmp_path, books)
    old_dir = tmp_path / "old"
    old_manifest = build_index(
        source, source_manifest, old_dir, FakeEncoder({
            f"passage: {books[0]['semantic_text']}": [1.0, 0.0],
            f"passage: {books[1]['semantic_text']}": [0.0, 1.0],
        }),
        source_revision="source-commit", model_repo="example/model",
        model_revision="model-commit", dimensions=2,
    )
    old_manifest["index_version"] = 1
    (old_dir / "manifest.json").write_text(json.dumps(old_manifest))
    new_dir = tmp_path / "new"
    manifest = upgrade_index(source, source_manifest, old_dir, new_dir)

    assert manifest["index_version"] == 2
    assert manifest["vectors_npy_sha256"] == old_manifest["vectors_npy_sha256"]
    assert validate_index_bundle(new_dir)["books_indexed"] == 2

    bad_books = list(reversed(books))
    (tmp_path / "different").mkdir()
    bad_source, bad_manifest = _source(tmp_path / "different", bad_books)
    old_manifest["source_parquet_sha256"] = bad_manifest["parquet_sha256"]
    (old_dir / "manifest.json").write_text(json.dumps(old_manifest))
    with pytest.raises(ValueError, match="order"):
        upgrade_index(bad_source, bad_manifest, old_dir, tmp_path / "bad-output")


def test_existing_v1_index_remains_searchable(tmp_path):
    index = tmp_path / "legacy"
    index.mkdir()
    np.save(index / "vectors.npy", np.array([[1.0, 0.0]], dtype=np.float32))
    with sqlite3.connect(index / "books.sqlite") as database:
        database.execute(
            "CREATE TABLE books (ordinal INTEGER PRIMARY KEY, book_id TEXT, title TEXT, "
            "authors TEXT, subjects TEXT, abstract TEXT, languages TEXT, "
            "publication_year INTEGER, book_url TEXT)"
        )
        database.execute(
            "CREATE VIRTUAL TABLE books_fts USING fts5(title, authors, subjects, abstract)"
        )
        database.execute(
            "INSERT INTO books VALUES (1, 'legacy', 'Coastal planning', '[]', '[]', "
            "'Sea level response', '[\"eng\"]', 2024, 'https://example.org/legacy')"
        )
        database.execute(
            "INSERT INTO books_fts(rowid, title, authors, subjects, abstract) "
            "VALUES (1, 'Coastal planning', '', '', 'Sea level response')"
        )
    manifest = write_index_manifest(
        index, {"parquet_sha256": "source-checksum"}, book_count=1,
        source_revision="source-commit", model_repo="example/model",
        model_revision="model-commit", dimensions=2,
    )
    manifest["index_version"] = 1
    (index / "manifest.json").write_text(json.dumps(manifest))
    with SearchEngine(index, FakeEncoder({})) as engine:
        result = engine.search("Coastal planning", mode="keyword", limit=1)[0]
    assert result["book_id"] == "legacy"
    assert result["description_source"] == "abstract"


def test_reranker_checks_full_query_against_grounded_candidates(tmp_path):
    books = [
        _book("a", "Coastal planning", "Sea level response"),
        _book("b", "Urban studies", "Flooding in cities"),
        _book("c", "Marine resilience", "Ocean conservation"),
    ]
    source, source_manifest = _source(tmp_path, books)
    encoder = _encoder(books)
    encoder.vectors["query: coastal adaptation with practical examples"] = [1.0, 0.0]
    output = tmp_path / "index"
    build_index(
        source, source_manifest, output, encoder,
        source_revision="source-commit", model_repo="example/model",
        model_revision="model-commit", dimensions=2,
    )
    reranker = FakeReranker()
    with SearchEngine(output, encoder, reranker=reranker) as engine:
        results = engine.search(
            "coastal adaptation with practical examples", mode="reranked", limit=3
        )
    assert results[0]["book_id"] == "c"
    assert results[0]["score_kind"] == "cross_encoder_relative"
    assert all("coastal adaptation" in query for query, _ in reranker.pairs)
    assert all("Title:" in book_text and "Description:" in book_text
               for _, book_text in reranker.pairs)


def test_reranked_mode_requires_explicit_model(tmp_path):
    books = [_book("a", "Coastal planning", "Sea level response")]
    source, source_manifest = _source(tmp_path, books)
    encoder = FakeEncoder({
        f"passage: {books[0]['semantic_text']}": [1.0, 0.0],
        "query: coastal adaptation": [1.0, 0.0],
    })
    output = tmp_path / "index"
    build_index(
        source, source_manifest, output, encoder,
        source_revision="source-commit", model_repo="example/model",
        model_revision="model-commit", dimensions=2,
    )
    with SearchEngine(output, encoder) as engine:
        with pytest.raises(ValueError, match="reranker"):
            engine.search("coastal adaptation", mode="reranked")


def test_reranked_page_cannot_exceed_candidate_pool(tmp_path):
    books = [_book("a", "Coastal planning", "Sea level response")]
    source, source_manifest = _source(tmp_path, books)
    encoder = FakeEncoder({f"passage: {books[0]['semantic_text']}": [1.0, 0.0]})
    output = tmp_path / "index"
    build_index(
        source, source_manifest, output, encoder,
        source_revision="source-commit", model_repo="example/model",
        model_revision="model-commit", dimensions=2,
    )
    with SearchEngine(output, encoder, reranker=FakeReranker()) as engine:
        with pytest.raises(ValueError, match="50-book candidate pool"):
            engine.search("coastal adaptation", mode="reranked", limit=10, offset=45)


def test_search_rejects_empty_query_and_invalid_page(tmp_path):
    books = [_book("a", "Coastal planning", "Sea level response")]
    source, source_manifest = _source(tmp_path, books)
    encoder = FakeEncoder({f"passage: {books[0]['semantic_text']}": [1.0, 0.0]})
    output = tmp_path / "index"
    build_index(
        source,
        source_manifest,
        output,
        encoder,
        source_revision="source-commit",
        model_repo="example/model",
        model_revision="model-commit",
        dimensions=2,
    )
    with SearchEngine(output, encoder) as engine:
        with pytest.raises(ValueError, match="empty"):
            engine.search("  ")
        with pytest.raises(ValueError, match="limit"):
            engine.search("cities", limit=0)
        with pytest.raises(ValueError, match="offset"):
            engine.search("cities", offset=-1)


def test_validate_index_bundle_rejects_corrupted_vector_file(tmp_path):
    books = [_book("a", "Coastal planning", "Sea level response")]
    source, source_manifest = _source(tmp_path, books)
    encoder = FakeEncoder({f"passage: {books[0]['semantic_text']}": [1.0, 0.0]})
    output = tmp_path / "index"
    build_index(
        source,
        source_manifest,
        output,
        encoder,
        source_revision="source-commit",
        model_repo="example/model",
        model_revision="model-commit",
        dimensions=2,
    )
    with (output / "vectors.npy").open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        validate_index_bundle(output)


def test_build_index_rejects_duplicate_book_ids(tmp_path):
    books = [
        _book("same", "Coastal planning", "Sea level response"),
        _book("same", "Marine resilience", "Ocean conservation"),
    ]
    source, source_manifest = _source(tmp_path, books)
    encoder = FakeEncoder(
        {
            f"passage: {books[0]['semantic_text']}": [1.0, 0.0],
            f"passage: {books[1]['semantic_text']}": [0.0, 1.0],
        }
    )
    with pytest.raises(ValueError, match="duplicate book IDs"):
        build_index(
            source,
            source_manifest,
            tmp_path / "index",
            encoder,
            source_revision="source-commit",
            model_repo="example/model",
            model_revision="model-commit",
            dimensions=2,
        )


def test_parallel_shards_assemble_in_exact_source_order(tmp_path):
    books = [_book(str(number), f"Book {number}", f"Description {number}") for number in range(5)]
    source, source_manifest = _source(tmp_path, books)
    mapping = {
        f"passage: {book['semantic_text']}": [1.0, 0.0] if number < 3 else [0.0, 1.0]
        for number, book in enumerate(books)
    }
    mapping["query: Book 4"] = [0.0, 1.0]
    encoder = FakeEncoder(mapping)
    shards_dir = tmp_path / "shards"
    shards_dir.mkdir()
    manifests = [
        build_shard(
            source,
            source_manifest,
            shards_dir / f"shard-{number}",
            encoder,
            shard_index=number,
            shard_count=3,
            source_revision="source-commit",
            model_repo="example/model",
            model_revision="model-commit",
            dimensions=2,
            batch_size=2,
        )
        for number in range(3)
    ]
    assert [(item["start_row"], item["end_row_exclusive"]) for item in manifests] == [
        (0, 1),
        (1, 3),
        (3, 5),
    ]
    assert encoder.inputs == [f"passage: {book['semantic_text']}" for book in books]

    output = tmp_path / "assembled"
    manifest = assemble_index(
        source,
        source_manifest,
        shards_dir,
        output,
        shard_count=3,
        source_revision="source-commit",
        model_repo="example/model",
        model_revision="model-commit",
        dimensions=2,
        batch_size=2,
    )
    assert manifest["books_indexed"] == 5
    assert validate_index_bundle(output)["books_indexed"] == 5
    with sqlite3.connect(output / "books.sqlite") as connection:
        assert connection.execute("SELECT book_id FROM books ORDER BY ordinal").fetchall() == [
            (str(number),) for number in range(5)
        ]
    with SearchEngine(output, encoder) as engine:
        assert engine.search("Book 4", mode="semantic", limit=2)[0]["book_id"] == "3"


def test_parallel_assembly_rejects_missing_and_changed_shards(tmp_path):
    books = [_book(str(number), f"Book {number}", "Cities") for number in range(2)]
    source, source_manifest = _source(tmp_path, books)
    encoder = FakeEncoder({f"passage: {book['semantic_text']}": [1.0, 0.0] for book in books})
    shards_dir = tmp_path / "shards"
    shards_dir.mkdir()
    for number in range(2):
        build_shard(
            source,
            source_manifest,
            shards_dir / f"shard-{number}",
            encoder,
            shard_index=number,
            shard_count=2,
            source_revision="source-commit",
            model_repo="example/model",
            model_revision="model-commit",
            dimensions=2,
        )
    vectors_path = shards_dir / "shard-1" / "vectors.npy"
    with vectors_path.open("r+b") as stream:
        stream.seek(-1, 2)
        stream.write(b"X")
    with pytest.raises(ValueError, match="checksum"):
        assemble_index(
            source,
            source_manifest,
            shards_dir,
            tmp_path / "assembled",
            shard_count=2,
            source_revision="source-commit",
            model_repo="example/model",
            model_revision="model-commit",
            dimensions=2,
        )
    assert not (tmp_path / "assembled").exists()
    vectors_path.unlink()
    with pytest.raises(ValueError, match="Missing shard"):
        assemble_index(
            source,
            source_manifest,
            shards_dir,
            tmp_path / "assembled",
            shard_count=2,
            source_revision="source-commit",
            model_repo="example/model",
            model_revision="model-commit",
            dimensions=2,
        )


def test_publisher_uploads_only_the_versioned_search_files(tmp_path, monkeypatch):
    books = [_book("a", "Coastal planning", "Sea level response")]
    source, source_manifest = _source(tmp_path, books)
    encoder = FakeEncoder({f"passage: {books[0]['semantic_text']}": [1.0, 0.0]})
    output = tmp_path / "index"
    build_index(
        source,
        source_manifest,
        output,
        encoder,
        source_revision="source-commit",
        model_repo="example/model",
        model_revision="model-commit",
        dimensions=2,
    )
    calls = []

    class FakeApi:
        def __init__(self, token):
            assert token == "test-token"

        def create_commit(self, **kwargs):
            calls.append(kwargs)
            return type("Commit", (), {"commit_url": "https://example.org/commit"})()

    monkeypatch.setattr("libraries_search.publish.HfApi", FakeApi)
    assert publish_index(output, "test-token") == "https://example.org/commit"
    assert len(calls) == 1
    assert calls[0]["repo_type"] == "dataset"
    assert {item.path_in_repo for item in calls[0]["operations"]} == {
        "search/v2/manifest.json",
        "search/v2/books.sqlite",
        "search/v2/vectors.npy",
    }
