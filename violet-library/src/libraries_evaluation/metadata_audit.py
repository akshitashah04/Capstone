"""Count source metadata that could support better search without inventing fields."""

import argparse
import json
import os
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from libraries_search.source import validate_source

FIELDS = (
    "abstract", "other_language_abstract", "subjects", "classifications", "alternate_titles"
)


def summarize_book_fields(books: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Report which gaps have an alternative value in the same published source."""
    counts: Counter[str] = Counter()
    for book in books:
        counts["books"] += 1
        primary = bool(book["abstract"])
        alternate = bool(book["other_language_abstract"])
        subjects = bool(book["subjects"])
        if not primary:
            counts["missing_primary_abstract"] += 1
            if alternate:
                counts["alternate_abstract_available_for_missing_primary"] += 1
            else:
                counts["no_abstract_in_either_field"] += 1
        if not subjects:
            counts["missing_subjects"] += 1
            if book["classifications"]:
                counts["classifications_available_for_missing_subjects"] += 1
        if book["alternate_titles"]:
            counts["alternate_titles_available"] += 1
    return {name: counts[name] for name in (
        "books", "missing_primary_abstract", "alternate_abstract_available_for_missing_primary",
        "no_abstract_in_either_field", "missing_subjects",
        "classifications_available_for_missing_subjects", "alternate_titles_available"
    )}


def audit_source(parquet_path: Path, source_manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate and scan the pinned Parquet source in bounded cloud-runner batches."""
    expected = validate_source(parquet_path, source_manifest)
    parquet = pq.ParquetFile(parquet_path)
    books = (book for batch in parquet.iter_batches(batch_size=4_096, columns=list(FIELDS))
             for book in batch.to_pylist())
    report: dict[str, Any] = summarize_book_fields(books)
    if report["books"] != expected:
        raise ValueError("Metadata audit count differs from source manifest")
    report["source_parquet_sha256"] = source_manifest["parquet_sha256"]
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit available fields in the pinned DOAB source")
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("Full-source metadata audits run only in GitHub Actions")
    from libraries_search.source import download_source

    parquet_path, source_manifest = download_source(args.cache_dir)
    report = audit_source(parquet_path, source_manifest)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
