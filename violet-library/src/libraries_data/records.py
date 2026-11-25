"""Normalize one DOAB CSV row without changing its language or meaning."""

import html
import re
import unicodedata
from collections.abc import Mapping

_SPACE = re.compile(r"\s+")
_TAG = re.compile(r"<[^>]+>")
_YEAR = re.compile(r"^(\d{4})")
_LANGUAGE_CODE = re.compile(r"\[([A-Za-z]{2,3}(?:-[A-Za-z]+)?)\]$")


def clean_text(value: str | None) -> str:
    """Remove markup and extra whitespace while retaining Unicode characters."""
    if not value:
        return ""
    without_tags = _TAG.sub(" ", html.unescape(value))
    return _SPACE.sub(" ", unicodedata.normalize("NFC", without_tags)).strip()


def split_values(value: str | list[str] | None) -> list[str]:
    """Keep each value in DOAB's double-pipe list fields separate."""
    values: list[str] = []
    seen: set[str] = set()
    raw_values = value if isinstance(value, list) else (value or "").split("||")
    for raw_value in raw_values:
        item = clean_text(raw_value)
        if item and item.casefold() not in seen:
            values.append(item)
            seen.add(item.casefold())
    return values


def _first_value(row: Mapping[str, str | list[str] | None], *keys: str) -> str:
    for key in keys:
        raw_value = row.get(key)
        value = clean_text(raw_value if isinstance(raw_value, str) else None)
        if value:
            return value
    return ""


def _http_url(value: str | None) -> str:
    url = clean_text(value)
    return url if url.startswith(("https://", "http://")) else ""


def normalize_book(row: Mapping[str, str | list[str] | None]) -> dict[str, object] | None:
    """Return a model-neutral book record, or None for non-book rows.

    Missing IDs and titles are errors so the pipeline can count them separately.
    """
    if clean_text(row.get("dc.type")).casefold() != "book":
        return None

    book_id = clean_text(row.get("id"))
    title = clean_text(row.get("dc.title"))
    if not book_id:
        raise ValueError("missing_book_id")
    if not title:
        raise ValueError("missing_title")

    alternate_titles = split_values(row.get("dc.title.alternative"))
    authors = split_values(row.get("dc.contributor.author"))
    subjects = split_values(row.get("dc.subject.other"))
    classifications = split_values(row.get("dc.subject.classification"))
    for code in split_values(row.get("dc.subject")):
        if code.casefold() not in {item.casefold() for item in classifications}:
            classifications.append(code)
    abstract = clean_text(row.get("dc.description.abstract"))
    other_language_abstract = clean_text(row.get("oapen.abstract.otherlanguage"))
    languages = []
    for item in split_values(row.get("dc.language")):
        match = _LANGUAGE_CODE.search(item)
        languages.append(match.group(1).casefold() if match else item.casefold())
    year_match = _YEAR.match(clean_text(row.get("dc.date.issued")))
    publication_year = int(year_match.group(1)) if year_match else None

    isbns = split_values(row.get("BITSTREAM ISBN"))
    for isbn in split_values(row.get("oapen.relation.isbn")):
        if isbn.casefold() not in {item.casefold() for item in isbns}:
            isbns.append(isbn)

    doi = _first_value(row, "oapen.identifier.doi")
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", "", doi, flags=re.I)
    semantic_parts = [
        f"Title: {title}",
        *(f"Alternative title: {item}" for item in alternate_titles),
        *(f"Subject: {item}" for item in subjects),
    ]
    if abstract:
        semantic_parts.append(f"Description: {abstract}")
    if other_language_abstract:
        semantic_parts.append(f"Other-language description: {other_language_abstract}")

    return {
        "book_id": book_id,
        "title": title,
        "alternate_titles": alternate_titles,
        "authors": authors,
        "subjects": subjects,
        "classifications": classifications,
        "abstract": abstract,
        "other_language_abstract": other_language_abstract,
        "languages": languages,
        "publication_year": publication_year,
        "isbns": isbns,
        "doi": doi,
        "publisher": _first_value(
            row, "oapen.relation.isPublishedBy_publisher.name", "oapen.imprint"
        ),
        "book_url": _http_url(row.get("dc.identifier.uri")),
        "download_url": _http_url(
            _first_value(row, "BITSTREAM Download URL", "oapen.identifier.downloadUrl")
        ),
        "license_url": _http_url(_first_value(row, "BITSTREAM License", "dc.rights.licenseurl")),
        "semantic_text": "\n".join(semantic_parts),
    }
