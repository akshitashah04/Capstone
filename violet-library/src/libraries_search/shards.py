"""Encode one deterministic, contiguous part of the pinned book snapshot."""

import argparse
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq

from libraries_search.build import TextEncoder
from libraries_search.config import (
    EMBEDDING_DIMENSIONS,
    MODEL_REPO,
    MODEL_REVISION,
    SOURCE_REVISION,
)
from libraries_search.model import load_model
from libraries_search.source import download_source, sha256_file, validate_source


def shard_bounds(book_count: int, shard_index: int, shard_count: int) -> tuple[int, int]:
    """Divide source row positions into balanced, non-overlapping ranges."""
    if shard_count < 1 or shard_count > book_count:
        raise ValueError("Shard count must be between one and the book count")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("Shard index is out of range")
    return book_count * shard_index // shard_count, book_count * (shard_index + 1) // shard_count


def build_shard(
    parquet_path: Path,
    source_manifest: dict[str, Any],
    output_dir: Path,
    encoder: TextEncoder,
    *,
    shard_index: int,
    shard_count: int,
    source_revision: str,
    model_repo: str,
    model_revision: str,
    dimensions: int = EMBEDDING_DIMENSIONS,
    batch_size: int = 128,
) -> dict[str, Any]:
    """Encode one row range, preserving its source positions and input identity."""
    book_count = validate_source(Path(parquet_path), source_manifest)
    start, end = shard_bounds(book_count, shard_index, shard_count)
    if dimensions < 1 or batch_size < 1:
        raise ValueError("Dimensions and batch size must be positive")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    vectors_path = output_dir / "vectors.npy"
    vectors = np.lib.format.open_memmap(
        vectors_path, mode="w+", dtype=np.float32, shape=(end - start, dimensions)
    )
    source_row = 0
    encoded_rows = 0
    try:
        for batch in pq.ParquetFile(parquet_path).iter_batches(batch_size=batch_size):
            batch_length = len(batch)
            if source_row >= end:
                break
            begin = max(0, start - source_row)
            stop = min(batch_length, end - source_row)
            if begin < stop:
                books = batch.slice(begin, stop - begin).to_pylist()
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
                if not np.allclose(np.linalg.norm(encoded, axis=1), 1.0, atol=0.02):
                    raise ValueError("Model returned a vector that is not normalized")
                vectors[encoded_rows : encoded_rows + len(books)] = encoded
                encoded_rows += len(books)
                if encoded_rows % 2_500 < len(books) or encoded_rows == end - start:
                    print(
                        f"Shard {shard_index}: encoded {encoded_rows}/{end - start} books",
                        flush=True,
                    )
            source_row += batch_length
        if encoded_rows != end - start:
            raise ValueError("Encoded shard count differs from its source row range")
    finally:
        vectors.flush()
        del vectors

    manifest: dict[str, Any] = {
        "shard_index": shard_index,
        "shard_count": shard_count,
        "start_row": start,
        "end_row_exclusive": end,
        "books_encoded": encoded_rows,
        "source_revision": source_revision,
        "source_parquet_sha256": source_manifest["parquet_sha256"],
        "model_repo": model_repo,
        "model_revision": model_revision,
        "dimensions": dimensions,
        "vectors_npy_sha256": sha256_file(vectors_path),
        "vectors_npy_bytes": vectors_path.stat().st_size,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Encode one verified book-index shard")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("Full-data builds run only in GitHub Actions to keep data off laptops")
    parquet_path, source_manifest = download_source(args.cache_dir)
    encoder = load_model()
    manifest = build_shard(
        parquet_path,
        source_manifest,
        args.output_dir,
        encoder,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
        source_revision=SOURCE_REVISION,
        model_repo=MODEL_REPO,
        model_revision=MODEL_REVISION,
    )
    print(json.dumps({"shard_index": args.shard_index, "books_encoded": manifest["books_encoded"]}))


if __name__ == "__main__":
    main()
