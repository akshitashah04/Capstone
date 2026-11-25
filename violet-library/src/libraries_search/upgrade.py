"""Build a richer v2 book database while retaining checked v1 embeddings."""

import argparse
import json
import os
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

from libraries_search.build import write_index_manifest
from libraries_search.config import SOURCE_DATASET_REPO
from libraries_search.lexical import create_database, insert_books
from libraries_search.publish import ARTIFACTS, validate_index_bundle
from libraries_search.source import download_source, validate_source

PRIOR_INDEX_REVISION = "f54ded49b97a92ca8e5dce0463500043ea2a19a4"


def download_prior_index(cache_dir: Path) -> Path:
    """Fetch only the three pinned v1 index files on a temporary cloud runner."""
    paths = [Path(hf_hub_download(
        repo_id=SOURCE_DATASET_REPO,
        repo_type="dataset",
        revision=PRIOR_INDEX_REVISION,
        filename=f"search/v1/{name}",
        cache_dir=cache_dir,
    )) for name in ARTIFACTS]
    if len({path.parent for path in paths}) != 1:
        raise ValueError("Prior index files were not downloaded into one directory")
    validate_index_bundle(paths[0].parent, expected_version=1)
    return paths[0].parent


def upgrade_index(
    parquet_path: Path,
    source_manifest: dict[str, Any],
    prior_dir: Path,
    output_dir: Path,
    *,
    batch_size: int = 1_024,
) -> dict[str, Any]:
    """Check every source ID against v1 before reusing its exact vectors."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    count = validate_source(parquet_path, source_manifest)
    prior_dir = Path(prior_dir)
    prior = validate_index_bundle(prior_dir, expected_version=1)
    if prior["books_indexed"] != count or prior["source_parquet_sha256"] != source_manifest[
        "parquet_sha256"
    ]:
        raise ValueError("Prior index and source snapshot differ")
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Output index already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix="index-upgrade-", dir=output_dir.parent) as temporary:
        staged = Path(temporary)
        new_database = create_database(staged / "books.sqlite")
        next_ordinal = 1
        try:
            with closing(sqlite3.connect(
                f"{(prior_dir / 'books.sqlite').as_uri()}?mode=ro&immutable=1", uri=True
            )) as old_database:
                for batch in pq.ParquetFile(parquet_path).iter_batches(batch_size=batch_size):
                    books = batch.to_pylist()
                    end_ordinal = next_ordinal + len(books) - 1
                    old_ids = [row[0] for row in old_database.execute(
                        "SELECT book_id FROM books WHERE ordinal BETWEEN ? AND ? ORDER BY ordinal",
                        (next_ordinal, end_ordinal),
                    )]
                    if old_ids != [book["book_id"] for book in books]:
                        raise ValueError("Prior index and source book order differ")
                    insert_books(new_database, books, next_ordinal)
                    new_database.commit()
                    next_ordinal = end_ordinal + 1
            if next_ordinal - 1 != count:
                raise ValueError("Upgraded index book count differs from source")
        finally:
            new_database.close()

        shutil.copyfile(prior_dir / "vectors.npy", staged / "vectors.npy")
        manifest = write_index_manifest(
            staged, source_manifest,
            book_count=count,
            source_revision=prior["source_revision"],
            model_repo=prior["model_repo"],
            model_revision=prior["model_revision"],
            dimensions=prior["dimensions"],
        )
        if manifest["vectors_npy_sha256"] != prior["vectors_npy_sha256"]:
            raise ValueError("Copied vectors differ from the pinned prior index")
        validate_index_bundle(staged)
        staged.replace(output_dir)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Upgrade pinned search index on a cloud runner")
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("Full index upgrades run only in GitHub Actions")
    parquet_path, source_manifest = download_source(args.cache_dir)
    prior_dir = download_prior_index(args.cache_dir)
    manifest = upgrade_index(parquet_path, source_manifest, prior_dir, args.output_dir)
    print(json.dumps({"books_indexed": manifest["books_indexed"],
                      "index_version": manifest["index_version"]}), flush=True)


if __name__ == "__main__":
    main()
