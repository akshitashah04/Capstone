"""Cloud-only, unfiltered Open Textbook Library coverage experiment."""

import argparse
import csv
import hashlib
import io
import json
import os
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import requests

from libraries_data.records import clean_text
from libraries_data.schema import BOOK_SCHEMA, SCHEMA_VERSION
from libraries_evaluation.queries import load_queries
from libraries_search.build import build_index
from libraries_search.config import (
    EMBEDDING_DIMENSIONS,
    MODEL_REPO,
    MODEL_REVISION,
)
from libraries_search.model import load_model, load_reranker
from libraries_search.search import SearchEngine
from libraries_search.source import sha256_file

OTL_CSV_URL = "https://open.umn.edu/opentextbooks/download.csv"
OTL_SOURCE = "Open Textbook Library cumulative CSV"
REQUIRED_COLUMNS = {"Otl id", "Title", "Description", "Library URL", "Subject 1"}
RESULT_FIELDS = (
    "query_id", "query_text", "rank", "book_id", "title", "subjects",
    "book_url", "description_excerpt", "rank_score", "score_kind"
)


def normalize_otl_row(row: Mapping[str, str]) -> dict[str, Any] | None:
    """Map CC0 catalog metadata into our book schema without guessing language."""
    book_id = clean_text(row.get("Otl id"))
    title = clean_text(row.get("Title"))
    url = clean_text(row.get("Library URL"))
    if not book_id or not title or not url.startswith("https://open.umn.edu/"):
        return None
    subjects = list(dict.fromkeys(
        value for field in ("Subject 1", "Subject 2")
        if (value := clean_text(row.get(field)))
    ))
    description = clean_text(row.get("Description"))
    contributors = [item.strip() for item in clean_text(row.get("Contributors")).split(";")
                    if item.strip()]
    isbns = list(dict.fromkeys(
        value for field in ("ISBN13", "ISBN10")
        if (value := clean_text(row.get(field)))
    ))
    year_text = clean_text(row.get("Copyright year"))
    year = int(year_text) if re.fullmatch(r"\d{4}", year_text) else None
    text_parts = [f"Title: {title}", *(f"Subject: {item}" for item in subjects)]
    if description:
        text_parts.append(f"Description: {description}")
    return {
        "book_id": f"otl:{book_id}",
        "title": title,
        "alternate_titles": [],
        "authors": contributors,
        "subjects": subjects,
        "classifications": [],
        "abstract": description,
        "other_language_abstract": "",
        "languages": [],
        "publication_year": year,
        "isbns": isbns,
        "doi": "",
        "publisher": clean_text(row.get("Publisher")),
        "book_url": url,
        "download_url": "",
        "license_url": "",
        "semantic_text": "\n".join(text_parts),
    }


def fetch_otl_books() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Download one full catalog file, never a provider-selected search result."""
    response = requests.get(OTL_CSV_URL, timeout=(10, 120))
    response.raise_for_status()
    raw = response.content
    source_sha = hashlib.sha256(raw).hexdigest()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if not REQUIRED_COLUMNS.issubset(reader.fieldnames or []):
        raise ValueError("Open Textbook Library CSV columns changed")
    books: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    seen: set[str] = set()
    for row in reader:
        counts["source_rows"] += 1
        book = normalize_otl_row(row)
        if book is None:
            counts["rejected_rows"] += 1
            continue
        if book["book_id"] in seen:
            counts["duplicate_ids"] += 1
            continue
        seen.add(book["book_id"])
        books.append(book)
        if not book["abstract"]:
            counts["missing_description"] += 1
        if not book["subjects"]:
            counts["missing_subjects"] += 1
    if len(books) < 1_000 or len(books) > 10_000:
        raise ValueError("Supplementary catalog size is outside the expected range")
    quality = {
        "source": OTL_SOURCE,
        "source_url": OTL_CSV_URL,
        "source_csv_sha256": source_sha,
        "source_rows": counts["source_rows"],
        "books_valid": len(books),
        "rejected_rows": counts["rejected_rows"],
        "duplicate_ids": counts["duplicate_ids"],
        "missing_description": counts["missing_description"],
        "missing_subjects": counts["missing_subjects"],
        "language_status": "not supplied by cumulative CSV; left unknown",
    }
    return books, quality


def run_coverage(output_dir: Path, queries_path: Path, miss_report_path: Path) -> dict[str, Any]:
    """Index the small supplement on a runner and inspect the 19 topic misses."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    books, quality = fetch_otl_books()
    (output_dir / "source-quality.json").write_text(
        json.dumps(quality, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    source_path = output_dir / "otl-books.parquet"
    pq.write_table(pa.Table.from_pylist(books, schema=BOOK_SCHEMA), source_path,
                   compression="zstd")
    source_manifest = {
        "schema_version": SCHEMA_VERSION,
        "books_written": len(books),
        "parquet_sha256": sha256_file(source_path),
    }
    encoder = load_model()
    index_dir = output_dir / "otl-index"
    index_manifest = build_index(
        source_path, source_manifest, index_dir, encoder,
        source_revision=quality["source_csv_sha256"],
        model_repo=MODEL_REPO,
        model_revision=MODEL_REVISION,
        dimensions=EMBEDDING_DIMENSIONS,
        source_dataset_repo=OTL_CSV_URL,
    )
    miss_report = json.loads(Path(miss_report_path).read_text(encoding="utf-8"))
    miss_ids = {row["query_id"] for row in miss_report["per_query"]
                if row["category"] == "no_topic_fit_in_judged_pool"}
    queries = [query for query in load_queries(queries_path) if query.query_id in miss_ids]
    if len(queries) != len(miss_ids):
        raise ValueError("Coverage report contains unknown or duplicate query IDs")
    reranker = load_reranker()
    rows = []
    with SearchEngine(index_dir, encoder, reranker=reranker) as engine:
        for query in queries:
            for rank, book in enumerate(engine.search(query.text, mode="reranked", limit=5), 1):
                rows.append({
                    "query_id": query.query_id,
                    "query_text": query.text,
                    "rank": rank,
                    "book_id": book["book_id"],
                    "title": book["title"],
                    "subjects": "; ".join(book["subjects"]),
                    "book_url": book["book_url"],
                    "description_excerpt": book["description_excerpt"],
                    "rank_score": book["rank_score"],
                    "score_kind": book["score_kind"],
                })
    with (output_dir / "coverage-results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "source_csv_sha256": quality["source_csv_sha256"],
        "source_parquet_sha256": source_manifest["parquet_sha256"],
        "index_vectors_sha256": index_manifest["vectors_npy_sha256"],
        "books_indexed": len(books),
        "queries_examined": len(queries),
        "queries_sha256": sha256_file(queries_path),
        "miss_report_sha256": sha256_file(miss_report_path),
        "results_sha256": sha256_file(output_dir / "coverage-results.csv"),
        "judgment_status": "unjudged",
        "limits": (
            "Potential matches only; deduplication against DOAB and human fit ratings remain."
        ),
    }
    (output_dir / "coverage-manifest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Test unfiltered textbook catalog coverage")
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--miss-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("Supplementary catalog processing runs only in GitHub Actions")
    report = run_coverage(args.output_dir, args.queries, args.miss_report)
    print(json.dumps({"books_indexed": report["books_indexed"],
                      "queries_examined": report["queries_examined"]}), flush=True)


if __name__ == "__main__":
    main()
