"""Store book display fields and our own SQLite full-text candidate index."""

import json
import re
import sqlite3
from pathlib import Path


def create_database(path: Path) -> sqlite3.Connection:
    """Create numbered book rows and a separate weighted full-text table."""
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=DELETE")
    connection.execute(
        """CREATE TABLE books (
            ordinal INTEGER PRIMARY KEY,
            book_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            authors TEXT NOT NULL,
            subjects TEXT NOT NULL,
            abstract TEXT NOT NULL,
            languages TEXT NOT NULL,
            publication_year INTEGER,
            book_url TEXT NOT NULL,
            alternate_titles TEXT NOT NULL,
            description_source TEXT NOT NULL
        )"""
    )
    connection.execute(
        "CREATE VIRTUAL TABLE books_fts USING "
        "fts5(title, alternate_titles, authors, subjects, abstract)"
    )
    return connection


def insert_books(
    connection: sqlite3.Connection, books: list[dict[str, object]], start_ordinal: int
) -> None:
    """Insert each display row and its matching full-text row at the same number."""
    for offset, book in enumerate(books):
        ordinal = start_ordinal + offset
        authors = list(book["authors"])
        subjects = list(book["subjects"])
        alternate_titles = list(book["alternate_titles"])
        abstract = str(book["abstract"] or book["other_language_abstract"] or "")
        description_source = (
            "abstract" if book["abstract"] else
            "other_language_abstract" if book["other_language_abstract"] else ""
        )
        connection.execute(
            "INSERT INTO books VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ordinal,
                book["book_id"],
                book["title"],
                json.dumps(authors, ensure_ascii=False),
                json.dumps(subjects, ensure_ascii=False),
                abstract,
                json.dumps(book["languages"], ensure_ascii=False),
                book["publication_year"],
                book["book_url"],
                json.dumps(alternate_titles, ensure_ascii=False),
                description_source,
            ),
        )
        connection.execute(
            "INSERT INTO books_fts(rowid, title, alternate_titles, authors, subjects, abstract) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                ordinal,
                book["title"],
                " ".join(alternate_titles),
                " ".join(authors),
                " ".join(subjects),
                abstract,
            ),
        )


def keyword_candidates(
    connection: sqlite3.Connection, query: str, limit: int, *, index_version: int = 2
) -> list[int]:
    """Return our BM25-ranked book row numbers using safe literal query terms."""
    terms = re.findall(r"\w+", query, flags=re.UNICODE)[:16]
    if not terms:
        return []
    expression = " OR ".join(f'"{term}"' for term in terms)
    if index_version not in {1, 2}:
        raise ValueError("Unsupported keyword index version")
    weights = "8.0, 5.0, 4.0, 1.0" if index_version == 1 else "8.0, 6.0, 5.0, 4.0, 1.0"
    rows = connection.execute(
        "SELECT rowid FROM books_fts WHERE books_fts MATCH ? "
        f"ORDER BY bm25(books_fts, {weights}), rowid LIMIT ?",
        (expression, limit),
    )
    return [int(row[0]) for row in rows]
