"""Supplementary textbook records retain source links and avoid guessed fields."""

from libraries_evaluation.otl_coverage import normalize_otl_row


def test_normalize_otl_row_preserves_description_and_library_link():
    row = {
        "Otl id": "42", "Title": "Introduction to Biology",
        "Contributors": "Ada Example; Ben Example", "Subject 1": "Biology",
        "Subject 2": "Life Sciences", "Description": "A practical starting guide.",
        "Copyright year": "2024", "ISBN10": "1234567890", "ISBN13": "9781234567890",
        "Publisher": "Open Press", "Library URL": "https://open.umn.edu/opentextbooks/textbooks/42",
        "License": "Attribution",
    }
    book = normalize_otl_row(row)
    assert book is not None
    assert book["book_id"] == "otl:42"
    assert book["subjects"] == ["Biology", "Life Sciences"]
    assert book["abstract"] == "A practical starting guide."
    assert book["languages"] == []
    assert book["book_url"] == row["Library URL"]
    assert book["semantic_text"].startswith("Title: Introduction to Biology")


def test_normalize_otl_row_rejects_missing_identity_or_link():
    assert normalize_otl_row({"Otl id": "", "Title": "Book"}) is None
    assert normalize_otl_row({"Otl id": "1", "Title": "Book", "Library URL": "file:///x"}) is None
