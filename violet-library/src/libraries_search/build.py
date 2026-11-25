"""Build aligned keyword and semantic indexes from a checked book snapshot."""

import argparse
import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pyarrow.parquet as pq

from libraries_search.config import (
    EMBEDDING_DIMENSIONS,
    INDEX_VERSION,
    MODEL_REPO,
    MODEL_REVISION,
    SOURCE_DATASET_REPO,
    SOURCE_REVISION,
)
from libraries_search.lexical import create_database, insert_books
from libraries_search.model import load_model
from libraries_search.source import download_source, sha256_file, validate_source


class TextEncoder(Protocol):
    """Small interface shared by the real model and synthetic test encoders."""

    def encode(self, texts: list[str], **kwargs: Any) -> np.ndarray: ...


def write_index_manifest(
    output_dir: Path,
    source_manifest: dict[str, Any],
    *,
    book_count: int,
    source_revision: str,
    model_repo: str,
    model_revision: str,
    dimensions: int,
    source_dataset_repo: str = SOURCE_DATASET_REPO,
) -> dict[str, Any]:
    """Record the same final artifact contract for serial and parallel builds."""
    database_path = output_dir / "books.sqlite"
    vectors_path = output_dir / "vectors.npy"
    manifest: dict[str, Any] = {
        "index_version": INDEX_VERSION,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "source_dataset_repo": source_dataset_repo,
        "source_revision": source_revision,
        "source_parquet_sha256": source_manifest["parquet_sha256"],
        "books_indexed": book_count,
        "model_repo": model_repo,
        "model_revision": model_revision,
        "dimensions": dimensions,
        "books_sqlite_sha256": sha256_file(database_path),
        "vectors_npy_sha256": sha256_file(vectors_path),
        "books_sqlite_bytes": database_path.stat().st_size,
        "vectors_npy_bytes": vectors_path.stat().st_size,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return manifest


def build_index(
    parquet_path: Path,
    source_manifest: dict[str, Any],
    output_dir: Path,
    encoder: TextEncoder,
    *,
    source_revision: str,
    model_repo: str,
    model_revision: str,
    dimensions: int = EMBEDDING_DIMENSIONS,
    batch_size: int = 128,
    source_dataset_repo: str = SOURCE_DATASET_REPO,
) -> dict[str, Any]:
    """Build one vector and one numbered keyword row per verified book."""
    parquet_path = Path(parquet_path)
    book_count = validate_source(parquet_path, source_manifest)
    if dimensions < 1 or batch_size < 1:
        raise ValueError("dimensions and batch_size must be positive")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    database_path = output_dir / "books.sqlite"
    vectors_path = output_dir / "vectors.npy"
    vectors = np.lib.format.open_memmap(
        vectors_path, mode="w+", dtype=np.float32, shape=(book_count, dimensions)
    )
    connection = create_database(database_path)
    next_row = 0
    try:
        for batch in pq.ParquetFile(parquet_path).iter_batches(batch_size=batch_size):
            books = batch.to_pylist()
            texts = [f"passage: {book['semantic_text']}" for book in books]
            encoded = np.asarray(
                encoder.encode(
                    texts,
                    batch_size=min(32, batch_size),
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                ),
                dtype=np.float32,
            )
            if encoded.shape != (len(books), dimensions):
                raise ValueError("Model returned the wrong vector count or dimension")
            if not np.isfinite(encoded).all():
                raise ValueError("Model returned a non-finite vector")
            norms = np.linalg.norm(encoded, axis=1)
            if not np.allclose(norms, 1.0, atol=0.02):
                raise ValueError("Model returned a vector that is not normalized")
            try:
                insert_books(connection, books, next_row + 1)
            except sqlite3.IntegrityError as error:
                raise ValueError("Source has duplicate book IDs or row numbers") from error
            vectors[next_row : next_row + len(books)] = encoded
            next_row += len(books)
            connection.commit()
            if next_row % 5_000 < len(books) or next_row == book_count:
                print(f"Indexed {next_row}/{book_count} books", flush=True)
        if next_row != book_count:
            raise ValueError("Indexed book count differs from source manifest")
        sqlite_count = connection.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        fts_count = connection.execute("SELECT COUNT(*) FROM books_fts").fetchone()[0]
        if sqlite_count != book_count or fts_count != book_count:
            raise ValueError("Keyword rows do not align with the vector count")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError(f"SQLite integrity check failed: {integrity}")
    finally:
        vectors.flush()
        del vectors
        connection.close()

    return write_index_manifest(
        output_dir,
        source_manifest,
        book_count=book_count,
        source_revision=source_revision,
        model_repo=model_repo,
        model_revision=model_revision,
        dimensions=dimensions,
        source_dataset_repo=source_dataset_repo,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build our own DOAB keyword and semantic indexes")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("Full-data builds run only in GitHub Actions to keep data off laptops")
    parquet_path, source_manifest = download_source(args.cache_dir)
    model = load_model()
    manifest = build_index(
        parquet_path,
        source_manifest,
        args.output_dir,
        model,
        source_revision=SOURCE_REVISION,
        model_repo=MODEL_REPO,
        model_revision=MODEL_REVISION,
    )
    print(json.dumps({"books_indexed": manifest["books_indexed"]}), flush=True)


if __name__ == "__main__":
    main()
