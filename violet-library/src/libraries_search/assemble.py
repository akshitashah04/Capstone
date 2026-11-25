"""Verify encoded shards and join them with our own keyword index."""

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq

from libraries_search.build import write_index_manifest
from libraries_search.config import (
    EMBEDDING_DIMENSIONS,
    MODEL_REPO,
    MODEL_REVISION,
    SOURCE_REVISION,
)
from libraries_search.lexical import create_database, insert_books
from libraries_search.shards import shard_bounds
from libraries_search.source import download_source, sha256_file, validate_source


def validate_shard(
    shard_dir: Path,
    *,
    shard_index: int,
    shard_count: int,
    book_count: int,
    source_revision: str,
    source_parquet_sha256: str,
    model_repo: str,
    model_revision: str,
    dimensions: int,
) -> dict[str, Any]:
    """Reject an incomplete, changed, or misidentified shard."""
    manifest_path = shard_dir / "manifest.json"
    vectors_path = shard_dir / "vectors.npy"
    if not manifest_path.is_file() or not vectors_path.is_file():
        raise ValueError(f"Missing shard files: {shard_dir.name}")
    manifest = json.loads(manifest_path.read_text())
    start, end = shard_bounds(book_count, shard_index, shard_count)
    expected = {
        "shard_index": shard_index,
        "shard_count": shard_count,
        "start_row": start,
        "end_row_exclusive": end,
        "books_encoded": end - start,
        "source_revision": source_revision,
        "source_parquet_sha256": source_parquet_sha256,
        "model_repo": model_repo,
        "model_revision": model_revision,
        "dimensions": dimensions,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f"Shard {shard_index} has wrong {key}")
    if vectors_path.stat().st_size != manifest.get("vectors_npy_bytes"):
        raise ValueError(f"Shard {shard_index} has wrong vector file size")
    if sha256_file(vectors_path) != manifest.get("vectors_npy_sha256"):
        raise ValueError(f"Shard {shard_index} vector checksum mismatch")
    vectors = np.load(vectors_path, mmap_mode="r", allow_pickle=False)
    if vectors.shape != (end - start, dimensions) or vectors.dtype != np.float32:
        raise ValueError(f"Shard {shard_index} has wrong vector shape or type")
    if not np.isfinite(vectors).all():
        raise ValueError(f"Shard {shard_index} has non-finite vectors")
    if not np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=0.02):
        raise ValueError(f"Shard {shard_index} has non-normalized vectors")
    return manifest


def assemble_index(
    parquet_path: Path,
    source_manifest: dict[str, Any],
    shards_dir: Path,
    output_dir: Path,
    *,
    shard_count: int,
    source_revision: str,
    model_repo: str,
    model_revision: str,
    dimensions: int = EMBEDDING_DIMENSIONS,
    batch_size: int = 1_024,
) -> dict[str, Any]:
    """Assemble exact source-order vectors and book rows after shard validation."""
    parquet_path = Path(parquet_path)
    book_count = validate_source(parquet_path, source_manifest)
    shard_bounds(book_count, 0, shard_count)
    if dimensions < 1 or batch_size < 1:
        raise ValueError("Dimensions and batch size must be positive")
    shards_dir = Path(shards_dir)
    expected_names = {f"shard-{index}" for index in range(shard_count)}
    actual_names = {path.name for path in shards_dir.iterdir() if path.is_dir()}
    if actual_names != expected_names:
        raise ValueError("Shard directories are missing or unexpected")
    for index in range(shard_count):
        validate_shard(
            shards_dir / f"shard-{index}",
            shard_index=index,
            shard_count=shard_count,
            book_count=book_count,
            source_revision=source_revision,
            source_parquet_sha256=source_manifest["parquet_sha256"],
            model_repo=model_repo,
            model_revision=model_revision,
            dimensions=dimensions,
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    vectors = np.lib.format.open_memmap(
        output_dir / "vectors.npy", mode="w+", dtype=np.float32, shape=(book_count, dimensions)
    )
    try:
        for index in range(shard_count):
            start, end = shard_bounds(book_count, index, shard_count)
            shard_vectors = np.load(
                shards_dir / f"shard-{index}" / "vectors.npy",
                mmap_mode="r",
                allow_pickle=False,
            )
            vectors[start:end] = shard_vectors
            print(f"Assembled shard {index + 1}/{shard_count}: rows {start}:{end}", flush=True)
    finally:
        vectors.flush()
        del vectors

    connection = create_database(output_dir / "books.sqlite")
    next_ordinal = 1
    try:
        for batch in pq.ParquetFile(parquet_path).iter_batches(batch_size=batch_size):
            books = batch.to_pylist()
            try:
                insert_books(connection, books, next_ordinal)
            except sqlite3.IntegrityError as error:
                raise ValueError("Source has duplicate book IDs or row numbers") from error
            next_ordinal += len(books)
            connection.commit()
        books_written = next_ordinal - 1
        fts_count = connection.execute("SELECT COUNT(*) FROM books_fts").fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if books_written != book_count or fts_count != book_count or integrity != "ok":
            raise ValueError("Assembled keyword index does not match the verified source")
    finally:
        connection.close()

    return write_index_manifest(
        output_dir,
        source_manifest,
        book_count=book_count,
        source_revision=source_revision,
        model_repo=model_repo,
        model_revision=model_revision,
        dimensions=dimensions,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify and assemble book-index shards")
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--shards-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--shard-count", type=int, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("Full-data builds run only in GitHub Actions to keep data off laptops")
    parquet_path, source_manifest = download_source(args.cache_dir)
    manifest = assemble_index(
        parquet_path,
        source_manifest,
        args.shards_dir,
        args.output_dir,
        shard_count=args.shard_count,
        source_revision=SOURCE_REVISION,
        model_repo=MODEL_REPO,
        model_revision=MODEL_REVISION,
    )
    print(json.dumps({"books_indexed": manifest["books_indexed"]}), flush=True)


if __name__ == "__main__":
    main()
