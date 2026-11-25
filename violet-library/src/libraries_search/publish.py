"""Validate and atomically publish only the search artifacts to Hugging Face."""

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
from huggingface_hub import CommitOperationAdd, HfApi

from libraries_search.config import INDEX_PREFIX, INDEX_VERSION, SOURCE_DATASET_REPO
from libraries_search.source import sha256_file

ARTIFACTS = ("manifest.json", "books.sqlite", "vectors.npy")


def validate_index_bundle(
    input_dir: Path, *, expected_version: int | None = INDEX_VERSION
) -> dict[str, Any]:
    """Reject missing, corrupt, or misaligned index files before upload or search."""
    input_dir = Path(input_dir)
    for name in ARTIFACTS:
        if not (input_dir / name).is_file():
            raise ValueError(f"Missing search artifact: {name}")
    manifest = json.loads((input_dir / "manifest.json").read_text())
    supported = {1, INDEX_VERSION} if expected_version is None else {expected_version}
    if manifest.get("index_version") not in supported:
        raise ValueError("Search index version is unsupported")
    count = manifest.get("books_indexed")
    dimensions = manifest.get("dimensions")
    if not isinstance(count, int) or count < 1:
        raise ValueError("Search manifest has no valid book count")
    if not isinstance(dimensions, int) or dimensions < 1:
        raise ValueError("Search manifest has no valid vector dimensions")
    for name, checksum_key in (
        ("books.sqlite", "books_sqlite_sha256"),
        ("vectors.npy", "vectors_npy_sha256"),
    ):
        if sha256_file(input_dir / name) != manifest.get(checksum_key):
            raise ValueError(f"Search artifact checksum mismatch: {name}")

    vectors = np.load(input_dir / "vectors.npy", mmap_mode="r", allow_pickle=False)
    if vectors.shape != (count, dimensions) or vectors.dtype != np.float32:
        raise ValueError("Search vectors have wrong count, dimension, or type")
    if not np.isfinite(vectors).all():
        raise ValueError("Search vectors contain non-finite values")
    with sqlite3.connect(f"{(input_dir / 'books.sqlite').as_uri()}?mode=ro", uri=True) as db:
        book_count = db.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        fts_count = db.execute("SELECT COUNT(*) FROM books_fts").fetchone()[0]
        first, last = db.execute("SELECT MIN(ordinal), MAX(ordinal) FROM books").fetchone()
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    if (book_count, fts_count, first, last) != (count, count, 1, count):
        raise ValueError("Search keyword rows and vectors are not aligned")
    if integrity != "ok":
        raise ValueError(f"Search SQLite integrity check failed: {integrity}")
    return manifest


def publish_index(input_dir: Path, token: str) -> str:
    """Commit the three verified files under the current versioned search path."""
    if not token:
        raise ValueError("HF_TOKEN is required to publish the search index")
    manifest = validate_index_bundle(input_dir)
    input_dir = Path(input_dir)
    operations = [
        CommitOperationAdd(path_in_repo=f"{INDEX_PREFIX}/{name}", path_or_fileobj=input_dir / name)
        for name in ARTIFACTS
    ]
    commit = HfApi(token=token).create_commit(
        repo_id=SOURCE_DATASET_REPO,
        repo_type="dataset",
        operations=operations,
        commit_message=(
            f"Publish search index v{INDEX_VERSION}: {manifest['books_indexed']} books, "
            f"{manifest['model_repo']}"
        ),
    )
    return str(commit.commit_url)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish verified DOAB search artifacts")
    parser.add_argument("--input-dir", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ.get("HF_TOKEN", "")
    if not token:
        parser.error("HF_TOKEN is not set")
    print(publish_index(args.input_dir, token))


if __name__ == "__main__":
    main()
