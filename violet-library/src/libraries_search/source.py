"""Fetch and verify the pinned public DOAB snapshot on a cloud runner."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

from libraries_data.schema import BOOK_SCHEMA, SCHEMA_VERSION
from libraries_search.config import SOURCE_DATASET_REPO, SOURCE_REVISION


def sha256_file(path: Path) -> str:
    """Hash a file in bounded blocks."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_source(parquet_path: Path, manifest: dict[str, Any]) -> int:
    """Reject changed, truncated, or incompatible input before creating an index."""
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Source schema version does not match the search builder")
    expected_count = manifest.get("books_written")
    if not isinstance(expected_count, int) or expected_count < 1:
        raise ValueError("Source manifest has no valid book count")
    if sha256_file(parquet_path) != manifest.get("parquet_sha256"):
        raise ValueError("Source checksum does not match its manifest")
    parquet = pq.ParquetFile(parquet_path)
    if parquet.metadata.num_rows != expected_count:
        raise ValueError("Source Parquet row count does not match its manifest")
    if not parquet.schema_arrow.equals(BOOK_SCHEMA):
        raise ValueError("Source Parquet schema does not match the prepared book schema")
    return expected_count


def download_source(cache_dir: Path) -> tuple[Path, dict[str, Any]]:
    """Download only the pinned source files into temporary runner cache."""
    cache_dir = Path(cache_dir)
    manifest_path = Path(
        hf_hub_download(
            repo_id=SOURCE_DATASET_REPO,
            repo_type="dataset",
            revision=SOURCE_REVISION,
            filename="manifest.json",
            cache_dir=cache_dir,
        )
    )
    parquet_path = Path(
        hf_hub_download(
            repo_id=SOURCE_DATASET_REPO,
            repo_type="dataset",
            revision=SOURCE_REVISION,
            filename="data/books.parquet",
            cache_dir=cache_dir,
        )
    )
    manifest = json.loads(manifest_path.read_text())
    validate_source(parquet_path, manifest)
    return parquet_path, manifest
