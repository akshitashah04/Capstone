"""Stream DOAB records into a checked, compact Hugging Face upload bundle."""

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from libraries_data.records import normalize_book
from libraries_data.schema import BOOK_SCHEMA, SCHEMA_VERSION
from libraries_data.source import DOAB_EXPORT_URL, fetch_rows

BATCH_SIZE = 5_000
DEFAULT_MIN_BOOKS = 90_000


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _dataset_card(source_url: str, books_written: int) -> str:
    return (
        "---\n"
        "license: cc0-1.0\n"
        "task_categories:\n- text-retrieval\n"
        "---\n\n"
        "# Libraries DOAB book metadata\n\n"
        f"This snapshot contains {books_written:,} book metadata records prepared from "
        f"[DOAB]({source_url}). It contains metadata, not the books' full text. "
        "DOAB metadata is CC0; linked books have separate licenses.\n\n"
        "The `semantic_text` column combines titles, subject keywords, and available abstracts "
        "for later model experiments. The separate source fields remain available. "
        "This is the book subset of one official export snapshot; DOAB's live site may "
        "contain titles absent from that export. "
        "This dataset provides no relevance labels, NYU holdings, or calibrated "
        "confidence scores.\n\n"
        "See `manifest.json` for the snapshot count and checksum, and `quality_report.json` "
        "for missing-field and exclusion counts. Processing code and documentation: "
        "https://github.com/VeedantBrahmbhatt/Libraries.\n"
    )


def prepare_catalog(
    rows: Iterable[Mapping[str, str | list[str] | None]],
    output_dir: Path,
    *,
    source_url: str,
    min_books: int = DEFAULT_MIN_BOOKS,
) -> dict[str, object]:
    """Prepare a complete catalog from streamed rows, failing before publish if too small."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    data_dir.mkdir(exist_ok=True)
    parquet_path = data_dir / "books.parquet"

    counts: Counter[str] = Counter()
    seen_ids: set[str] = set()
    batch: list[dict[str, object]] = []
    writer: pq.ParquetWriter | None = None
    try:
        for row in rows:
            counts["source_rows"] += 1
            try:
                book = normalize_book(row)
            except ValueError as error:
                reason = str(error)
                if reason not in {"missing_book_id", "missing_title"}:
                    raise
                counts[reason] += 1
                continue
            if book is None:
                counts["non_book_rows"] += 1
                continue

            book_id = str(book["book_id"])
            if book_id in seen_ids:
                counts["duplicate_ids"] += 1
                continue
            seen_ids.add(book_id)
            for name, field in (
                ("missing_abstract", "abstract"),
                ("missing_subjects", "subjects"),
                ("missing_languages", "languages"),
                ("missing_book_url", "book_url"),
            ):
                if not book[field]:
                    counts[name] += 1

            batch.append(book)
            counts["books_written"] += 1
            if len(batch) >= BATCH_SIZE:
                if writer is None:
                    writer = pq.ParquetWriter(parquet_path, BOOK_SCHEMA, compression="zstd")
                writer.write_table(pa.Table.from_pylist(batch, schema=BOOK_SCHEMA))
                batch.clear()

        if batch:
            if writer is None:
                writer = pq.ParquetWriter(parquet_path, BOOK_SCHEMA, compression="zstd")
            writer.write_table(pa.Table.from_pylist(batch, schema=BOOK_SCHEMA))
    finally:
        if writer is not None:
            writer.close()

    report = {
        key: counts[key]
        for key in (
            "source_rows",
            "books_written",
            "non_book_rows",
            "duplicate_ids",
            "missing_book_id",
            "missing_title",
            "missing_abstract",
            "missing_subjects",
            "missing_languages",
            "missing_book_url",
        )
    }
    _write_json(output_dir / "quality_report.json", report)
    if counts["books_written"] < min_books:
        raise ValueError(
            f"Prepared book count {counts['books_written']} is below minimum {min_books}; "
            "publication stopped"
        )

    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "source_url": source_url,
        "prepared_at_utc": datetime.now(UTC).isoformat(),
        "source_rows": counts["source_rows"],
        "books_written": counts["books_written"],
        "parquet_sha256": _sha256(parquet_path),
    }
    _write_json(output_dir / "manifest.json", manifest)
    (output_dir / "README.md").write_text(_dataset_card(source_url, counts["books_written"]))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare DOAB book metadata for Hugging Face")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-url", default=DOAB_EXPORT_URL)
    parser.add_argument("--minimum-books", type=int, default=DEFAULT_MIN_BOOKS)
    args = parser.parse_args()
    if args.minimum_books < 1:
        parser.error("--minimum-books must be at least 1")
    manifest = prepare_catalog(
        fetch_rows(args.source_url),
        args.output_dir,
        source_url=args.source_url,
        min_books=args.minimum_books,
    )
    print(
        json.dumps({"books_written": manifest["books_written"], "output_dir": str(args.output_dir)})
    )


if __name__ == "__main__":
    main()
