import json

import pytest

from libraries_data.prepare import prepare_catalog
from libraries_data.publish import validate_bundle


def test_validate_bundle_rejects_changed_parquet(tmp_path):
    row = {"id": "a", "dc.type": "book", "dc.title": "First"}
    prepare_catalog([row], tmp_path, source_url="test", min_books=1)
    assert validate_bundle(tmp_path)["books_written"] == 1

    parquet = tmp_path / "data" / "books.parquet"
    parquet.write_bytes(parquet.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="checksum"):
        validate_bundle(tmp_path)


def test_validate_bundle_requires_all_artifacts(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"books_written": 1}))
    with pytest.raises(ValueError, match="Missing prepared artifact"):
        validate_bundle(tmp_path)
