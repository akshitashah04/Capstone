from io import StringIO

import pytest

from libraries_data.source import parse_csv, restore_newlines


def test_parse_csv_reads_quoted_multiline_descriptions():
    content = (
        "id,dc.type,dc.title,dc.description.abstract,dc.subject.other,dc.language,dc.identifier.uri\n"
        '1,book,Example,"First line\nsecond line",learning,English[eng],https://example.org/1\n'
    )
    rows = list(parse_csv(StringIO(content)))
    assert rows == [
        {
            "id": "1",
            "dc.type": "book",
            "dc.title": "Example",
            "dc.description.abstract": "First line\nsecond line",
            "dc.subject.other": "learning",
            "dc.language": "English[eng]",
            "dc.identifier.uri": "https://example.org/1",
        }
    ]


def test_parse_csv_rejects_a_changed_required_header():
    with pytest.raises(ValueError, match="Missing required DOAB columns") as error:
        list(parse_csv(StringIO("id,dc.title\n1,Example\n")))
    assert "dc.type" in str(error.value)


def test_http_line_iterator_preserves_newlines_inside_quoted_fields():
    lines = [
        "id,dc.type,dc.title,dc.description.abstract,dc.subject.other,dc.language,dc.identifier.uri",
        '1,book,Example,"First line',
        'second line",learning,English[eng],https://example.org/1',
    ]
    row = next(parse_csv(restore_newlines(iter(lines))))
    assert row["dc.description.abstract"] == "First line\nsecond line"
