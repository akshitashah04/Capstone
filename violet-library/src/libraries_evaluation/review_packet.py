"""Freeze rank-blind human-review packets from compact, verified search runs."""

import argparse
import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from libraries_evaluation.queries import EvaluationQuery, load_queries

TOP_K = 5
DOAB_MODES = ("keyword", "semantic", "hybrid", "reranked")
SHEET_FIELDS = (
    "query_id", "query_text", "query_language", "book_id", "title", "authors",
    "subjects", "book_languages", "book_url", "description_excerpt",
    "description_source", "topic_grade", "reading_fit", "language_fit",
    "overall_grade",
)
IMMUTABLE_FIELDS = SHEET_FIELDS[:-4]
DOAB_FIELDS = (
    "query_id", "mode", "rank", "book_id", "title", "authors", "subjects",
    "book_languages", "publication_year", "book_url", "description_excerpt",
    "description_source", "rank_score", "score_kind", "latency_ms",
)
TEXTBOOK_FIELDS = (
    "query_id", "query_text", "rank", "book_id", "title", "subjects",
    "book_url", "description_excerpt", "rank_score", "score_kind",
)
GRADES = {"", "0", "1", "2"}
READING_FIT = {"", "yes", "no", "unknown", "not_requested"}
LANGUAGE_FIT = {"", "yes", "no", "unknown"}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_csv(data: bytes, fields: tuple[str, ...]) -> list[dict[str, str]]:
    with io.StringIO(data.decode("utf-8"), newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != fields:
            raise ValueError("Unexpected columns in source results or review sheet")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("Malformed CSV row")
    return rows


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=SHEET_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _source_rows(
    kind: str, archive_path: Path, queries_path: Path, queries: list[EvaluationQuery],
    miss_report: Path | None,
) -> tuple[dict[str, Any], list[dict[str, str]], list[str]]:
    if kind not in {"doab", "textbook"}:
        raise ValueError("kind must be doab or textbook")
    with ZipFile(archive_path) as archive:
        names = archive.namelist()
        expected = (
            {"runs.csv", "query-needs.json", "manifest.json"}
            if kind == "doab" else
            {"coverage-results.csv", "coverage-manifest.json", "source-quality.json"}
        )
        if set(names) != expected or len(names) != len(expected):
            raise ValueError("Source archive has missing, duplicate, or extra members")
        if any(archive.getinfo(name).file_size > 5_000_000 for name in names):
            raise ValueError("Source archive member is too large")
        manifest_name = "manifest.json" if kind == "doab" else "coverage-manifest.json"
        results_name = "runs.csv" if kind == "doab" else "coverage-results.csv"
        manifest = json.loads(archive.read(manifest_name))
        result_bytes = archive.read(results_name)
        if manifest.get("results_sha256" if kind == "textbook" else "runs_sha256") != _sha(
            result_bytes
        ):
            raise ValueError("Source archive results checksum changed")
        if kind == "doab":
            if manifest.get("query_needs_sha256") != _sha(archive.read("query-needs.json")):
                raise ValueError("Source archive query-needs checksum changed")
            if (
                manifest.get("index_path") != "search/v2"
                or not manifest.get("index_revision")
                or manifest.get("modes") != list(DOAB_MODES)
                or manifest.get("query_count") != len(queries)
            ):
                raise ValueError("Source archive is not the expected v2 diagnostic")
            fields = DOAB_FIELDS
            selected_ids = [query.query_id for query in queries]
        else:
            if miss_report is None or manifest.get("miss_report_sha256") != _sha_file(miss_report):
                raise ValueError("Textbook source archive does not match the miss report")
            misses = json.loads(miss_report.read_text(encoding="utf-8"))
            miss_ids = {
                row["query_id"] for row in misses["per_query"]
                if row["category"] == "no_topic_fit_in_judged_pool"
            }
            selected_ids = [query.query_id for query in queries if query.query_id in miss_ids]
            if len(selected_ids) != manifest.get("queries_examined"):
                raise ValueError("Textbook source archive has a different miss count")
            fields = TEXTBOOK_FIELDS
        if manifest.get("queries_sha256") != _sha_file(queries_path):
            raise ValueError("Source archive does not match the question file")
    rows = _read_csv(result_bytes, fields)
    by_query = {query.query_id: query for query in queries}
    expected_ids = set(selected_ids)
    ranks: dict[tuple[str, str], set[int]] = defaultdict(set)
    seen_books: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        query_id = row["query_id"]
        mode = row["mode"] if kind == "doab" else "textbook"
        if query_id not in expected_ids or mode not in (
            DOAB_MODES if kind == "doab" else ("textbook",)
        ):
            raise ValueError("Source archive has an unknown question or mode")
        if kind == "textbook" and row["query_text"] != by_query[query_id].text:
            raise ValueError("Textbook source archive question text changed")
        try:
            rank = int(row["rank"])
        except ValueError as error:
            raise ValueError("Source archive has an invalid rank") from error
        key = (query_id, mode)
        if rank < 1 or rank > 10 or rank in ranks[key] or not row["book_id"]:
            raise ValueError("Source archive has an invalid or duplicate rank")
        if row["book_id"] in seen_books[key]:
            raise ValueError("Source archive repeats a book in one search")
        ranks[key].add(rank)
        seen_books[key].add(row["book_id"])
    for query_id in selected_ids:
        for mode in (DOAB_MODES if kind == "doab" else ("textbook",)):
            observed = ranks[(query_id, mode)]
            if len(observed) < TOP_K or observed != set(range(1, len(observed) + 1)):
                raise ValueError("Source archive has incomplete first-five results")
    return manifest, rows, selected_ids


def _sheet_row(
    row: dict[str, str], query: EvaluationQuery, kind: str
) -> dict[str, str]:
    return {
        "query_id": query.query_id,
        "query_text": query.text,
        "query_language": query.language,
        "book_id": row["book_id"],
        "title": row["title"],
        "authors": row["authors"] if kind == "doab" else "",
        "subjects": row["subjects"],
        "book_languages": row["book_languages"] if kind == "doab" else "",
        "book_url": row["book_url"],
        "description_excerpt": row["description_excerpt"],
        "description_source": row["description_source"] if kind == "doab" else "",
        "topic_grade": "", "reading_fit": "", "language_fit": "",
        "overall_grade": "",
    }


def _hash_rows(rows: dict[tuple[str, str], dict[str, str]]) -> tuple[str, str]:
    pairs = "".join(f"{qid}\0{bid}\n" for qid, bid in sorted(rows))
    metadata = [
        {field: rows[key][field] for field in IMMUTABLE_FIELDS}
        for key in sorted(rows)
    ]
    canonical = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha(pairs.encode("utf-8")), _sha(canonical.encode("utf-8"))


def _expected_rows(
    kind: str, source_rows: list[dict[str, str]], queries: list[EvaluationQuery]
) -> dict[tuple[str, str], dict[str, str]]:
    by_query = {query.query_id: query for query in queries}
    result: dict[tuple[str, str], dict[str, str]] = {}
    for row in source_rows:
        if int(row["rank"]) > TOP_K:
            continue
        key = row["query_id"], row["book_id"]
        prepared = _sheet_row(row, by_query[row["query_id"]], kind)
        if key in result and any(
            result[key][field] != prepared[field] for field in IMMUTABLE_FIELDS
        ):
            raise ValueError("Source archive has inconsistent book metadata")
        result[key] = prepared
    return result


def initialize_packet(
    kind: str, archive: Path, queries_path: Path, packet_dir: Path,
    *, miss_report: Path | None = None,
) -> dict[str, Any]:
    """Create rank-blind, ungraded CSV sheets from one verified frozen archive."""
    archive, queries_path, packet_dir = map(Path, (archive, queries_path, packet_dir))
    queries = load_queries(queries_path)
    source, source_rows, selected_ids = _source_rows(
        kind, archive, queries_path, queries, miss_report
    )
    rows = _expected_rows(kind, source_rows, queries)
    pair_sha, metadata_sha = _hash_rows(rows)
    manifest = {
        "schema_version": 1,
        "kind": kind,
        "source_archive_sha256": _sha_file(archive),
        "source_results_sha256": source["runs_sha256" if kind == "doab" else "results_sha256"],
        "queries_sha256": _sha_file(queries_path),
        "miss_report_sha256": _sha_file(miss_report) if miss_report else None,
        "index_revision": source.get("index_revision"),
        "source_csv_sha256": source.get("source_csv_sha256"),
        "query_ids": selected_ids,
        "candidate_count": len(rows),
        "pair_sha256": pair_sha,
        "metadata_sha256": metadata_sha,
        "top_k": TOP_K,
        "rating_status": "ungraded",
    }
    packet_dir.mkdir(parents=True, exist_ok=False)
    for query_id in selected_ids:
        sheet_rows = [rows[key] for key in sorted(rows) if key[0] == query_id]
        _write_csv(packet_dir / f"{query_id}.csv", sheet_rows)
    (packet_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _read_packet(
    queries_path: Path, packet_dir: Path, archive: Path,
    miss_report: Path | None,
) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, str]], list[dict[str, str]]]:
    queries_path, packet_dir, archive = map(Path, (queries_path, packet_dir, archive))
    manifest = json.loads((packet_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("top_k") != TOP_K:
        raise ValueError("Review packet has an unsupported manifest")
    if manifest.get("source_archive_sha256") != _sha_file(archive):
        raise ValueError("Source archive changed since packet creation")
    if manifest.get("queries_sha256") != _sha_file(queries_path):
        raise ValueError("Review packet question file changed")
    if manifest.get("miss_report_sha256") != (
        _sha_file(miss_report) if miss_report else None
    ):
        raise ValueError("Review packet miss report changed")
    queries = load_queries(queries_path)
    kind = manifest.get("kind")
    source, source_rows, selected_ids = _source_rows(
        kind, archive, queries_path, queries, miss_report
    )
    expected = _expected_rows(kind, source_rows, queries)
    if (
        manifest.get("query_ids") != selected_ids
        or manifest.get("candidate_count") != len(expected)
        or manifest.get("source_results_sha256") != source[
            "runs_sha256" if kind == "doab" else "results_sha256"
        ]
        or manifest.get("index_revision") != source.get("index_revision")
        or manifest.get("source_csv_sha256") != source.get("source_csv_sha256")
    ):
        raise ValueError("Review packet provenance changed")
    expected_files = {f"{qid}.csv" for qid in selected_ids}
    if {path.name for path in packet_dir.glob("*.csv")} != expected_files:
        raise ValueError("Review packet has missing or extra sheets")
    sheets: dict[tuple[str, str], dict[str, str]] = {}
    for query_id in selected_ids:
        rows = _read_csv((packet_dir / f"{query_id}.csv").read_bytes(), SHEET_FIELDS)
        for row in rows:
            key = row["query_id"], row["book_id"]
            if row["query_id"] != query_id or key in sheets:
                raise ValueError("Review sheet has an unknown or duplicate book")
            if row["topic_grade"] not in GRADES or row["overall_grade"] not in GRADES:
                raise ValueError("Review sheet has an invalid grade")
            if row["reading_fit"] not in READING_FIT or row["language_fit"] not in LANGUAGE_FIT:
                raise ValueError("Review sheet has an invalid grade")
            if row["overall_grade"] == "2" and (
                row["topic_grade"] != "2"
                or row["reading_fit"] in {"no", "unknown"}
                or row["language_fit"] in {"no", "unknown"}
            ):
                raise ValueError("Clearly useful grade conflicts with stated fit")
            sheets[key] = row
    if set(sheets) != set(expected):
        raise ValueError("Review packet candidate pool changed")
    pair_sha, metadata_sha = _hash_rows(sheets)
    if manifest.get("pair_sha256") != pair_sha:
        raise ValueError("Review packet pair checksum changed")
    if manifest.get("metadata_sha256") != metadata_sha or any(
        any(sheets[key][field] != expected[key][field] for field in IMMUTABLE_FIELDS)
        for key in expected
    ):
        raise ValueError("Review packet book metadata changed")
    return manifest, sheets, source_rows


def packet_progress(
    queries_path: Path, packet_dir: Path, archive: Path,
    *, miss_report: Path | None = None,
) -> dict[str, Any]:
    """Validate edited sheets and count complete human judgments."""
    manifest, sheets, _ = _read_packet(queries_path, packet_dir, archive, miss_report)
    complete = sum(all(row[field] for field in SHEET_FIELDS[-4:]) for row in sheets.values())
    return {
        "kind": manifest["kind"],
        "index_revision": manifest["index_revision"],
        "query_count": len(manifest["query_ids"]),
        "candidate_count": len(sheets),
        "graded_count": complete,
        "remaining_count": len(sheets) - complete,
        "complete": complete == len(sheets),
        "by_query": {
            query_id: {
                "graded": sum(
                    all(row[field] for field in SHEET_FIELDS[-4:])
                    for key, row in sheets.items() if key[0] == query_id
                ),
                "total": sum(key[0] == query_id for key in sheets),
            }
            for query_id in manifest["query_ids"]
        },
    }


def score_packet(
    queries_path: Path, packet_dir: Path, archive: Path,
    *, miss_report: Path | None = None,
) -> dict[str, Any]:
    """Score frozen top-five rankings only after every pair has a human grade."""
    manifest, sheets, source_rows = _read_packet(
        queries_path, packet_dir, archive, miss_report
    )
    if any(not all(row[field] for field in SHEET_FIELDS[-4:]) for row in sheets.values()):
        raise ValueError("Review packet is incomplete; metrics are withheld")
    modes = DOAB_MODES if manifest["kind"] == "doab" else ("textbook",)
    ranked: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
    for row in source_rows:
        rank = int(row["rank"])
        if rank <= TOP_K:
            mode = row["mode"] if manifest["kind"] == "doab" else "textbook"
            ranked[(row["query_id"], mode)].append((rank, row["book_id"]))

    def metrics_for(query_ids: list[str]) -> dict[str, dict[str, Any]]:
        metrics = {}
        for mode in modes:
            first_useful: list[int] = []
            top_one = 0
            for query_id in query_ids:
                ordered = sorted(ranked[(query_id, mode)])
                useful = [
                    rank for rank, book_id in ordered
                    if sheets[(query_id, book_id)]["overall_grade"] == "2"
                ]
                if useful:
                    first_useful.append(min(useful))
                    top_one += min(useful) == 1
            metrics[mode] = {
                "top_one_success_count": top_one,
                "top_five_success_count": len(first_useful),
                "top_five_success_rate": round(len(first_useful) / len(query_ids), 4),
                "mean_first_useful_rank": (
                    round(sum(first_useful) / len(first_useful), 3) if first_useful else None
                ),
            }
        return metrics

    splits = {query.query_id: query.split for query in load_queries(queries_path)}
    by_split = {}
    for split in ("development", "holdout"):
        query_ids = [qid for qid in manifest["query_ids"] if splits[qid] == split]
        if query_ids:
            by_split[split] = {"query_count": len(query_ids), "modes": metrics_for(query_ids)}
    return {
        "kind": manifest["kind"],
        "source_archive_sha256": manifest["source_archive_sha256"],
        "question_count": len(manifest["query_ids"]),
        "human_judgments": len(sheets),
        "modes": metrics_for(manifest["query_ids"]),
        "by_split": by_split,
        "grade_counts": {
            field: dict(sorted(Counter(row[field] for row in sheets.values()).items()))
            for field in SHEET_FIELDS[-4:]
        },
        "limits": (
            "Holdout scores are separate; verify question provenance and reviewer independence "
            "before an acceptance claim."
            if "holdout" in by_split else
            "No holdout questions in this packet; these scores are development evidence only."
        ),
    }


def _summary(progress: dict[str, Any]) -> str:
    lines = [
        f"## {progress['kind']} human-review progress", "",
        f"{progress['graded_count']} / {progress['candidate_count']} pairs fully graded; "
        f"{progress['remaining_count']} remain.", "",
        "| Question | Graded | Total |", "| --- | ---: | ---: |",
    ]
    lines.extend(
        f"| {qid} | {counts['graded']} | {counts['total']} |"
        for qid, counts in progress["by_query"].items()
    )
    if not progress["complete"]:
        lines.extend(["", "Quality metrics are withheld until all pairs are graded."])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage rank-blind v2 human-review packets")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "progress", "score"):
        command = commands.add_parser(name)
        command.add_argument("--queries", type=Path, required=True)
        command.add_argument("--archive", type=Path, required=True)
        command.add_argument("--packet-dir", type=Path, required=True)
        command.add_argument("--miss-report", type=Path)
        if name == "init":
            command.add_argument("--kind", choices=("doab", "textbook"), required=True)
        if name == "progress":
            command.add_argument("--summary", type=Path)
            command.add_argument("--score-output", type=Path)
        if name == "score":
            command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    kwargs = {"miss_report": args.miss_report}
    if args.command == "init":
        result = initialize_packet(
            args.kind, args.archive, args.queries, args.packet_dir, **kwargs
        )
    elif args.command == "progress":
        if args.score_output:
            args.score_output.unlink(missing_ok=True)
        result = packet_progress(args.queries, args.packet_dir, args.archive, **kwargs)
        if args.summary:
            with args.summary.open("a", encoding="utf-8") as stream:
                stream.write(_summary(result))
        if args.score_output and result["complete"]:
            report = score_packet(args.queries, args.packet_dir, args.archive, **kwargs)
            args.score_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    else:
        args.output.unlink(missing_ok=True)
        result = score_packet(args.queries, args.packet_dir, args.archive, **kwargs)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
