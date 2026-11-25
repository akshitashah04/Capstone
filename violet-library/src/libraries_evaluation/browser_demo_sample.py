"""Export only a small, checksum-checked browser demo from cloud indexes."""

import argparse
import csv
import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

from libraries_evaluation.embedding_model_trial import (
    BASELINE_INDEX_REVISION,
    INDEX_PATH,
    TRIAL_MODELS,
)
from libraries_search.assemble import validate_shard
from libraries_search.config import (
    EMBEDDING_DIMENSIONS,
    MODEL_REPO,
    MODEL_REVISION,
    SOURCE_DATASET_REPO,
    SOURCE_REVISION,
)
from libraries_search.source import download_source, sha256_file

EXPECTED_BOOKS = 1_884
QUERY_COUNT = 50
MISSING_DESCRIPTIONS = {"", "undefined", "null", "none", "nan", "n/a"}


def clean_description(value: object) -> str:
    """Treat placeholder metadata as missing instead of publishing it as prose."""
    if not isinstance(value, str):
        return ""
    cleaned = " ".join(value.split())
    return "" if cleaned.casefold() in MISSING_DESCRIPTIONS else cleaned


def _read_csv(data: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(data.decode("utf-8"))))


def select_ids(v2_zip: Path, e5_dir: Path, gte_dir: Path) -> set[str]:
    """Use only checked, saved top-ten rankings from the same question set."""
    with zipfile.ZipFile(v2_zip) as archive:
        v2_manifest = json.loads(archive.read("manifest.json"))
        v2_bytes = archive.read("runs.csv")
    if hashlib.sha256(v2_bytes).hexdigest() != v2_manifest["runs_sha256"]:
        raise ValueError("V2 result checksum mismatch")
    if v2_manifest["index_revision"] != BASELINE_INDEX_REVISION:
        raise ValueError("V2 results came from another index")
    queries_sha = v2_manifest["queries_sha256"]
    all_rows = [_read_csv(v2_bytes)]
    for key, folder in (("e5-base", e5_dir), ("gte-base", gte_dir)):
        manifest = json.loads((folder / "manifest.json").read_text())
        raw = (folder / "runs.csv").read_bytes()
        if (manifest["model_key"] != key
                or manifest["baseline_index_revision"] != BASELINE_INDEX_REVISION
                or manifest["queries_sha256"] != queries_sha
                or hashlib.sha256(raw).hexdigest() != manifest["runs_sha256"]):
            raise ValueError(f"{key} result provenance mismatch")
        all_rows.append(_read_csv(raw))
    ids: set[str] = set()
    for rows in all_rows:
        if {row["query_id"] for row in rows} != {
            f"student-{i:02d}" for i in range(1, QUERY_COUNT + 1)
        }:
            raise ValueError("A result source has incomplete questions")
        for row in rows:
            if not row["book_id"] or not 1 <= int(row["rank"]) <= 10:
                raise ValueError("A result row has invalid book or rank")
            ids.add(row["book_id"])
    if len(ids) != EXPECTED_BOOKS:
        raise ValueError(f"Expected {EXPECTED_BOOKS} distinct books, got {len(ids)}")
    return ids


def selected_source_rows(parquet_path: Path, ids: set[str]) -> tuple[list[int], list[dict]]:
    """Keep selected books in the exact source order used by every vector index."""
    positions: list[int] = []
    books: list[dict] = []
    row_number = 0
    for batch in pq.ParquetFile(parquet_path).iter_batches(batch_size=1024):
        for book in batch.to_pylist():
            if book["book_id"] in ids:
                positions.append(row_number)
                description = (clean_description(book.get("abstract"))
                               or clean_description(book.get("other_language_abstract")))
                books.append({
                    "id": book["book_id"], "title": book["title"],
                    "authors": book.get("authors") or [],
                    "subjects": book.get("subjects") or [],
                    "languages": book.get("languages") or [],
                    "year": book.get("publication_year"),
                    "url": book["book_url"],
                    "description": description[:500],
                })
            row_number += 1
    if len(books) != len(ids) or len({book["id"] for book in books}) != len(ids):
        raise ValueError("Selected IDs do not match exactly one source row each")
    if any(not book["url"].startswith("https://") for book in books):
        raise ValueError("A selected book has no HTTPS source")
    return positions, books


def write_half_vectors(vectors: np.ndarray, positions: list[int], path: Path) -> None:
    """Save only selected normalized vectors as little-endian float16."""
    selected = np.asarray(vectors[positions], dtype=np.float32)
    if not np.isfinite(selected).all() or not np.allclose(
        np.linalg.norm(selected, axis=1), 1.0, atol=0.02
    ):
        raise ValueError("Selected vectors are invalid or not normalized")
    selected.astype("<f2").tofile(path)


def extract_shard_vectors(
    root: Path, spec_key: str, positions: list[int], book_count: int,
    source_sha: str, shard_count: int, output: Path,
) -> None:
    """Validate all trial shards and extract source-aligned selected rows."""
    spec = TRIAL_MODELS[spec_key]
    result = np.empty((len(positions), spec.dimensions), dtype=np.float32)
    filled = np.zeros(len(positions), dtype=bool)
    for shard in range(shard_count):
        folder = root / f"{spec_key}-shard-{shard}"
        manifest = validate_shard(
            folder, shard_index=shard, shard_count=shard_count,
            book_count=book_count, source_revision=SOURCE_REVISION,
            source_parquet_sha256=source_sha, model_repo=spec.repo,
            model_revision=spec.revision, dimensions=spec.dimensions,
        )
        start, end = manifest["start_row"], manifest["end_row_exclusive"]
        matches = [(i, position - start) for i, position in enumerate(positions)
                   if start <= position < end]
        if matches:
            shard_vectors = np.load(folder / "vectors.npy", mmap_mode="r", allow_pickle=False)
            for output_row, shard_row in matches:
                result[output_row] = shard_vectors[shard_row]
                filled[output_row] = True
    if not filled.all():
        raise ValueError(f"{spec_key} shards did not cover every selected book")
    write_half_vectors(result, list(range(len(result))), output)


def build_sample(args: argparse.Namespace) -> dict:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("The real catalog and indexes may be read only on GitHub Actions")
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=False)
    ids = select_ids(args.v2_zip, args.e5_dir, args.gte_dir)
    parquet_path, source_manifest = download_source(args.cache_dir)
    positions, books = selected_source_rows(parquet_path, ids)
    (output / "catalog.json").write_text(
        json.dumps(books, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    base_manifest_path = hf_hub_download(
        repo_id=SOURCE_DATASET_REPO, repo_type="dataset",
        revision=BASELINE_INDEX_REVISION, filename=f"{INDEX_PATH}/manifest.json",
        cache_dir=args.cache_dir,
    )
    base_manifest = json.loads(Path(base_manifest_path).read_text())
    base_vectors_path = Path(hf_hub_download(
        repo_id=SOURCE_DATASET_REPO, repo_type="dataset",
        revision=BASELINE_INDEX_REVISION, filename=f"{INDEX_PATH}/vectors.npy",
        cache_dir=args.cache_dir,
    ))
    if (base_manifest["source_parquet_sha256"] != source_manifest["parquet_sha256"]
            or base_manifest["books_indexed"] != source_manifest["books_written"]
            or base_manifest["model_repo"] != MODEL_REPO
            or base_manifest["model_revision"] != MODEL_REVISION
            or base_manifest["dimensions"] != EMBEDDING_DIMENSIONS
            or sha256_file(base_vectors_path) != base_manifest["vectors_npy_sha256"]):
        raise ValueError("Published E5 small index provenance mismatch")
    full_vectors = np.load(base_vectors_path, mmap_mode="r", allow_pickle=False)
    if full_vectors.shape != (source_manifest["books_written"], EMBEDDING_DIMENSIONS):
        raise ValueError("Published E5 small vector shape mismatch")
    write_half_vectors(full_vectors, positions, output / "e5-small.f16")
    extract_shard_vectors(
        args.e5_shards, "e5-base", positions, source_manifest["books_written"],
        source_manifest["parquet_sha256"], 4, output / "e5-base.f16",
    )
    extract_shard_vectors(
        args.gte_shards, "gte-base", positions, source_manifest["books_written"],
        source_manifest["parquet_sha256"], 8, output / "gte-base.f16",
    )
    manifest = {
        "schema": 1, "books": len(books), "source_revision": SOURCE_REVISION,
        "source_parquet_sha256": source_manifest["parquet_sha256"],
        "baseline_index_revision": BASELINE_INDEX_REVISION,
        "vector_encoding": "float16-le-row-major", "models": {
            "e5-small": {"dimensions": EMBEDDING_DIMENSIONS, "repo": MODEL_REPO,
                         "revision": MODEL_REVISION},
            **{key: {"dimensions": spec.dimensions, "repo": spec.repo,
                     "revision": spec.revision}
               for key, spec in TRIAL_MODELS.items()},
        },
        "files": {name: {"sha256": sha256_file(output / name),
                         "bytes": (output / name).stat().st_size}
                  for name in ("catalog.json", "e5-small.f16", "e5-base.f16", "gte-base.f16")},
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("v2-zip", "e5-dir", "gte-dir", "e5-shards", "gte-shards",
                 "cache-dir", "output-dir"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    manifest = build_sample(parser.parse_args())
    print(json.dumps({"sample_books": manifest["books"], "files": manifest["files"]}))


if __name__ == "__main__":
    main()
