"""Validate a prepared bundle and upload it to the one shared dataset repository."""

import argparse
import hashlib
import json
import os
from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import HfApi

from libraries_data.schema import BOOK_SCHEMA, SCHEMA_VERSION

HF_DATASET_REPO = "Tox1/LibrariesBookData"
ARTIFACTS = ("README.md", "manifest.json", "quality_report.json", "data/books.parquet")


def validate_bundle(input_dir: Path) -> dict[str, object]:
    """Check the bundle's required files, checksum, row count, and schema."""
    input_dir = Path(input_dir)
    for relative_path in ARTIFACTS:
        if not (input_dir / relative_path).is_file():
            raise ValueError(f"Missing prepared artifact: {relative_path}")

    manifest = json.loads((input_dir / "manifest.json").read_text())
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Prepared schema version does not match this publisher")
    parquet_path = input_dir / "data" / "books.parquet"
    digest = hashlib.sha256()
    with parquet_path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != manifest.get("parquet_sha256"):
        raise ValueError("Prepared Parquet checksum does not match manifest")

    parquet = pq.ParquetFile(parquet_path)
    if parquet.metadata.num_rows != manifest.get("books_written"):
        raise ValueError("Prepared Parquet row count does not match manifest")
    if not parquet.schema_arrow.equals(BOOK_SCHEMA):
        raise ValueError("Prepared Parquet schema does not match this publisher")
    return manifest


def publish_bundle(input_dir: Path, token: str) -> str:
    """Upload exactly the validated artifacts in one Hub commit."""
    if not token:
        raise ValueError("HF_TOKEN is required to publish")
    manifest = validate_bundle(input_dir)
    api = HfApi(token=token)
    commit = api.upload_folder(
        folder_path=str(input_dir),
        repo_id=HF_DATASET_REPO,
        repo_type="dataset",
        allow_patterns=list(ARTIFACTS),
        commit_message=f"Publish DOAB metadata: {manifest['books_written']} books",
    )
    return str(commit)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish checked DOAB metadata to Hugging Face")
    parser.add_argument("--input-dir", type=Path, required=True)
    args = parser.parse_args()
    token = os.environ.get("HF_TOKEN", "")
    if not token:
        parser.error("HF_TOKEN is not set")
    print(publish_bundle(args.input_dir, token))


if __name__ == "__main__":
    main()
