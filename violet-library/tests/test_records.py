from libraries_data.records import normalize_book


def test_normalize_book_preserves_multilingual_metadata_and_search_fields():
    row = {
        "id": "book-1",
        "dc.type": "book",
        "dc.title": "  Études   sur   日本語 ",
        "dc.title.alternative": "Japanese Studies||Estudios japoneses",
        "dc.contributor.author": "Smith, Ana||山田 太郎",
        "dc.subject.other": "linguistics||日本語",
        "dc.subject.classification": "Language and Linguistics||Asia",
        "dc.description.abstract": "<p>Research on <em>language</em> &amp; culture.</p>",
        "oapen.abstract.otherlanguage": "日本語の研究",
        "dc.language": "French[fre]||Japanese[jpn]",
        "dc.date.issued": "2021-04",
        "BITSTREAM ISBN": "9781111111111",
        "oapen.relation.isbn": "9782222222222",
        "oapen.identifier.doi": "https://doi.org/10.1234/example",
        "dc.identifier.uri": "https://directory.doabooks.org/handle/123",
        "BITSTREAM Download URL": "https://example.org/book.pdf",
        "BITSTREAM License": "https://creativecommons.org/licenses/by/4.0/",
        "oapen.relation.isPublishedBy_publisher.name": "Test Press",
    }

    book = normalize_book(row)

    assert book["book_id"] == "book-1"
    assert book["title"] == "Études sur 日本語"
    assert book["alternate_titles"] == ["Japanese Studies", "Estudios japoneses"]
    assert book["authors"] == ["Smith, Ana", "山田 太郎"]
    assert book["subjects"] == ["linguistics", "日本語"]
    assert book["classifications"] == ["Language and Linguistics", "Asia"]
    assert book["abstract"] == "Research on language & culture."
    assert book["other_language_abstract"] == "日本語の研究"
    assert book["languages"] == ["fre", "jpn"]
    assert book["publication_year"] == 2021
    assert book["isbns"] == ["9781111111111", "9782222222222"]
    assert book["doi"] == "10.1234/example"
    assert book["publisher"] == "Test Press"
    assert book["download_url"] == "https://example.org/book.pdf"
    assert book["license_url"] == "https://creativecommons.org/licenses/by/4.0/"
    assert "Études sur 日本語" in book["semantic_text"]
    assert "日本語の研究" in book["semantic_text"]
    assert "Language and Linguistics" not in book["semantic_text"]


def test_chapters_are_excluded_and_missing_identity_is_rejected():
    assert normalize_book({"id": "chapter-1", "dc.type": "book chapter", "dc.title": "A"}) is None

    try:
        normalize_book({"id": "", "dc.type": "book", "dc.title": "A"})
    except ValueError as error:
        assert str(error) == "missing_book_id"
    else:
        raise AssertionError("A missing ID must be rejected")


def test_distinct_editions_keep_distinct_ids():
    base = {"dc.type": "book", "dc.title": "Same title", "oapen.identifier.doi": "10.1/x"}
    first = normalize_book({**base, "id": "edition-1"})
    second = normalize_book({**base, "id": "edition-2"})
    assert first["book_id"] != second["book_id"]
