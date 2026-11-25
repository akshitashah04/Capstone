"""Cloud-only, pinned embedding comparisons using the project's own search code."""

import argparse
import csv
import json
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

import numpy as np
from huggingface_hub import hf_hub_download

from libraries_evaluation.config import INDEX_DATASET_REPO
from libraries_evaluation.queries import load_queries
from libraries_evaluation.rerank_diagnostic import RUN_FIELDS
from libraries_search.assemble import validate_shard
from libraries_search.build import write_index_manifest
from libraries_search.config import SOURCE_DATASET_REPO, SOURCE_REVISION
from libraries_search.publish import validate_index_bundle
from libraries_search.search import SearchEngine
from libraries_search.shards import build_shard, shard_bounds
from libraries_search.source import download_source, sha256_file

BASELINE_INDEX_REVISION = "b745902168aca10589fd0b376b58eb8019291b37"
INDEX_PATH = "search/v2"
TOKEN_LIMIT = 512
MODES = ("semantic", "hybrid")


@dataclass(frozen=True)
class TrialModel:
    key: str
    repo: str
    revision: str
    dimensions: int
    use_e5_prefix: bool


TRIAL_MODELS = {
    "e5-base": TrialModel(
        "e5-base", "intfloat/multilingual-e5-base",
        "d128750597153bb5987e10b1c3493a34e5a4502a", 768, True,
    ),
    "gte-base": TrialModel(
        "gte-base", "Alibaba-NLP/gte-multilingual-base",
        "9bbca17d9273fd0d03d5725c7a4b0f6b45142062", 768, False,
    ),
}


class Encoder(Protocol):
    def encode(self, texts: list[str], **kwargs: Any) -> np.ndarray: ...


class TrialEncoder:
    """Translate only E5-specific prefixes; retain identical source text."""

    def __init__(self, model: Encoder, spec: TrialModel):
        self.model = model
        self.spec = spec

    def encode(self, texts: list[str], **kwargs: Any) -> np.ndarray:
        if self.spec.use_e5_prefix:
            prepared = texts
        else:
            prepared = []
            for text in texts:
                prefix = next((p for p in ("query: ", "passage: ") if text.startswith(p)), None)
                if prefix is None:
                    raise ValueError("Trial input has no recognized query or passage prefix")
                prepared.append(text[len(prefix):])
        return self.model.encode(prepared, **kwargs)


def check_transformers_compatibility(spec: TrialModel, version: str) -> None:
    """Prevent GTE's known silent position-buffer corruption under Transformers 5."""
    if spec.key == "gte-base" and int(version.split(".", 1)[0]) >= 5:
        raise RuntimeError("GTE requires transformers<5 for correct position IDs")


def load_trial_encoder(spec: TrialModel) -> TrialEncoder:
    """Load an exact model revision only on temporary cloud runners."""
    import transformers
    from sentence_transformers import SentenceTransformer

    check_transformers_compatibility(spec, transformers.__version__)
    model = SentenceTransformer(
        spec.repo, revision=spec.revision, device="cpu",
        trust_remote_code=not spec.use_e5_prefix,
    )
    model.max_seq_length = TOKEN_LIMIT
    return TrialEncoder(model, spec)


def assemble_trial(
    shards_dir: Path,
    output_dir: Path,
    source_manifest: dict[str, Any],
    baseline_manifest: dict[str, Any],
    baseline_database: Path,
    spec: TrialModel,
    *,
    shard_count: int,
    source_revision: str = SOURCE_REVISION,
) -> dict[str, Any]:
    """Join verified vectors with the exact pinned v2 keyword database."""
    count = source_manifest.get("books_written")
    if not isinstance(count, int) or count < 1:
        raise ValueError("Source manifest has no valid book count")
    expected = {
        "index_version": 2,
        "source_revision": source_revision,
        "source_parquet_sha256": source_manifest.get("parquet_sha256"),
        "books_indexed": count,
    }
    for key, value in expected.items():
        if baseline_manifest.get(key) != value:
            raise ValueError(f"Pinned baseline has wrong {key}")
    if sha256_file(baseline_database) != baseline_manifest.get("books_sqlite_sha256"):
        raise ValueError("Pinned baseline database checksum mismatch")
    shards_dir = Path(shards_dir)
    names = {path.name for path in shards_dir.iterdir() if path.is_dir()}
    if names != {f"shard-{index}" for index in range(shard_count)}:
        raise ValueError("Trial shard directories are missing or unexpected")
    for index in range(shard_count):
        validate_shard(
            shards_dir / f"shard-{index}", shard_index=index,
            shard_count=shard_count, book_count=count,
            source_revision=source_revision,
            source_parquet_sha256=source_manifest["parquet_sha256"],
            model_repo=spec.repo, model_revision=spec.revision,
            dimensions=spec.dimensions,
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    vectors = np.lib.format.open_memmap(
        output_dir / "vectors.npy", mode="w+", dtype=np.float32,
        shape=(count, spec.dimensions),
    )
    try:
        for index in range(shard_count):
            start, end = shard_bounds(count, index, shard_count)
            shard = np.load(
                shards_dir / f"shard-{index}" / "vectors.npy",
                mmap_mode="r", allow_pickle=False,
            )
            vectors[start:end] = shard
            print(f"Assembled {spec.key} shard {index + 1}/{shard_count}", flush=True)
    finally:
        vectors.flush()
        del vectors
    shutil.copyfile(baseline_database, output_dir / "books.sqlite")
    manifest = write_index_manifest(
        output_dir, source_manifest, book_count=count,
        source_revision=source_revision, model_repo=spec.repo,
        model_revision=spec.revision, dimensions=spec.dimensions,
        source_dataset_repo=SOURCE_DATASET_REPO,
    )
    validate_index_bundle(output_dir)
    return manifest


class Searcher(Protocol):
    manifest: dict[str, Any]

    def search(self, query: str, *, mode: str, limit: int) -> list[dict[str, Any]]: ...


def collect_trial(
    engine: Searcher, queries_path: Path, output_dir: Path, spec: TrialModel
) -> dict[str, Any]:
    """Save rank and timing evidence; leave relevance judgments unfilled."""
    if engine.manifest["index_version"] != 2:
        raise ValueError("Trial requires the v2 keyword database")
    queries = load_queries(queries_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    for mode in MODES:
        engine.search(queries[0].text, mode=mode, limit=1)
    rows = []
    for query in queries:
        for mode in MODES:
            started = perf_counter()
            books = engine.search(query.text, mode=mode, limit=10)
            latency_ms = round((perf_counter() - started) * 1_000, 3)
            if len(books) != 10 or len({book["book_id"] for book in books}) != 10:
                raise ValueError(
                    f"Trial returned incomplete or duplicate results: {query.query_id}"
                )
            for rank, book in enumerate(books, 1):
                rows.append({
                    "query_id": query.query_id, "mode": mode, "rank": rank,
                    "book_id": book["book_id"], "title": book["title"],
                    "authors": "; ".join(book["authors"]),
                    "subjects": "; ".join(book["subjects"]),
                    "book_languages": "; ".join(book["languages"]),
                    "publication_year": book["publication_year"],
                    "book_url": book["book_url"],
                    "description_excerpt": book["description_excerpt"],
                    "description_source": book["description_source"],
                    "rank_score": book["rank_score"],
                    "score_kind": book["score_kind"], "latency_ms": latency_ms,
                })
    runs_path = output_dir / "runs.csv"
    with runs_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=RUN_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "model_key": spec.key, "model_repo": spec.repo,
        "model_revision": spec.revision, "token_limit": TOKEN_LIMIT,
        "input_prefix": "e5" if spec.use_e5_prefix else "none",
        "baseline_index_revision": BASELINE_INDEX_REVISION,
        "index_vectors_sha256": engine.manifest["vectors_npy_sha256"],
        "query_count": len(queries), "queries_sha256": sha256_file(queries_path),
        "modes": list(MODES), "top_k": 10, "judgment_status": "unjudged",
        "runs_sha256": sha256_file(runs_path),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run pinned embedding trials in GitHub Actions")
    subcommands = parser.add_subparsers(dest="command", required=True)
    encode = subcommands.add_parser("encode")
    encode.add_argument("--model", choices=TRIAL_MODELS, required=True)
    encode.add_argument("--shard-index", type=int, required=True)
    encode.add_argument("--shard-count", type=int, required=True)
    encode.add_argument("--cache-dir", type=Path, required=True)
    encode.add_argument("--output-dir", type=Path, required=True)
    evaluate = subcommands.add_parser("evaluate")
    evaluate.add_argument("--model", choices=TRIAL_MODELS, required=True)
    evaluate.add_argument("--shard-count", type=int, required=True)
    evaluate.add_argument("--shards-dir", type=Path, required=True)
    evaluate.add_argument("--cache-dir", type=Path, required=True)
    evaluate.add_argument("--index-dir", type=Path, required=True)
    evaluate.add_argument("--queries", type=Path, required=True)
    evaluate.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("Full-catalog model trials run only in GitHub Actions")
    spec = TRIAL_MODELS[args.model]
    if args.command == "encode":
        source_path, source_manifest = download_source(args.cache_dir)
        encoder = load_trial_encoder(spec)
        result = build_shard(
            source_path, source_manifest, args.output_dir, encoder,
            shard_index=args.shard_index, shard_count=args.shard_count,
            source_revision=SOURCE_REVISION, model_repo=spec.repo,
            model_revision=spec.revision, dimensions=spec.dimensions,
            batch_size=16,
        )
        print(json.dumps({"model": spec.key, "books_encoded": result["books_encoded"]}))
        return

    source_manifest_path = hf_hub_download(
        repo_id=SOURCE_DATASET_REPO, repo_type="dataset",
        revision=SOURCE_REVISION, filename="manifest.json", cache_dir=args.cache_dir,
    )
    baseline_manifest_path = hf_hub_download(
        repo_id=INDEX_DATASET_REPO, repo_type="dataset",
        revision=BASELINE_INDEX_REVISION, filename=f"{INDEX_PATH}/manifest.json",
        cache_dir=args.cache_dir,
    )
    baseline_database = Path(hf_hub_download(
        repo_id=INDEX_DATASET_REPO, repo_type="dataset",
        revision=BASELINE_INDEX_REVISION, filename=f"{INDEX_PATH}/books.sqlite",
        cache_dir=args.cache_dir,
    ))
    assemble_trial(
        args.shards_dir, args.index_dir,
        json.loads(Path(source_manifest_path).read_text()),
        json.loads(Path(baseline_manifest_path).read_text()),
        baseline_database, spec, shard_count=args.shard_count,
    )
    encoder = load_trial_encoder(spec)
    with SearchEngine(args.index_dir, encoder) as engine:
        result = collect_trial(engine, args.queries, args.output_dir, spec)
    print(json.dumps({"model": spec.key, "query_count": result["query_count"]}))


if __name__ == "__main__":
    main()
