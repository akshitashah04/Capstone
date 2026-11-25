import json

import pyarrow.parquet as pq
import pytest

from libraries_data.prepare import prepare_catalog


def _row(book_id: str, title: str, record_type: str = "book") -> dict[str, str]:
    return {
        "id": book_id,
        "dc.type": record_type,
        "dc.title": title,
        "dc.language": "eng",
        "dc.description.abstract": "An example description.",
        "dc.identifier.uri": f"https://example.org/{book_id}",
    }


def test_prepare_catalog_writes_only_unique_books_and_quality_report(tmp_path):
    rows = [
        _row("a", "First"),
        _row("a", "First"),
        _row("chapter", "Section", "book chapter"),
        _row("b", "Second") | {"dc.description.abstract": ""},
        _row("", "No ID"),
    ]

    summary = prepare_catalog(
        rows, tmp_path, source_url="https://example.org/doab.csv", min_books=2
    )

    table = pq.read_table(tmp_path / "data" / "books.parquet")
    assert table.num_rows == 2
    assert table.column("book_id").to_pylist() == ["a", "b"]
    assert table.column("semantic_text").to_pylist()[1] == "Title: Second"
    assert summary["books_written"] == 2

    report = json.loads((tmp_path / "quality_report.json").read_text())
    assert report["source_rows"] == 5
    assert report["non_book_rows"] == 1
    assert report["duplicate_ids"] == 1
    assert report["missing_book_id"] == 1
    assert report["missing_abstract"] == 1

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["source_url"] == "https://example.org/doab.csv"
    assert manifest["books_written"] == 2
    assert len(manifest["parquet_sha256"]) == 64
    assert (tmp_path / "README.md").exists()


def test_prepare_catalog_rejects_a_suspiciously_small_feed(tmp_path):
    with pytest.raises(ValueError, match="below minimum"):
        prepare_catalog([_row("a", "First")], tmp_path, source_url="test", min_books=2)

    assert not (tmp_path / "manifest.json").exists()
    assert (tmp_path / "quality_report.json").exists()
