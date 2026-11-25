"""Versioned public schema for the prepared book catalog."""

import pyarrow as pa

SCHEMA_VERSION = 1

BOOK_SCHEMA = pa.schema(
    [
        pa.field("book_id", pa.string(), nullable=False),
        pa.field("title", pa.string(), nullable=False),
        pa.field("alternate_titles", pa.list_(pa.string())),
        pa.field("authors", pa.list_(pa.string())),
        pa.field("subjects", pa.list_(pa.string())),
        pa.field("classifications", pa.list_(pa.string())),
        pa.field("abstract", pa.string()),
        pa.field("other_language_abstract", pa.string()),
        pa.field("languages", pa.list_(pa.string())),
        pa.field("publication_year", pa.int32()),
        pa.field("isbns", pa.list_(pa.string())),
        pa.field("doi", pa.string()),
        pa.field("publisher", pa.string()),
        pa.field("book_url", pa.string()),
        pa.field("download_url", pa.string()),
        pa.field("license_url", pa.string()),
        pa.field("semantic_text", pa.string(), nullable=False),
    ]
)
