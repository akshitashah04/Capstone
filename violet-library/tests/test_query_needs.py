"""Explicit requests are retained without inventing a student profile."""

from libraries_search.query_needs import parse_query_needs


def test_business_request_identifies_intro_examples_and_no_code():
    needs = parse_query_needs(
        "I'm a business major and want to understand AI, but I don't code. "
        "Any beginner book with real business examples?"
    )
    assert needs.level == "introductory"
    assert needs.wants_examples is True
    assert needs.avoids_code is True
    assert needs.avoids_math is False


def test_graduate_method_request_keeps_advanced_goal():
    needs = parse_query_needs(
        "For my economics thesis, I need methods for difference-in-differences "
        "with assumptions and examples."
    )
    assert needs.level == "advanced"
    assert needs.wants_methods is True
    assert needs.wants_examples is True


def test_multilingual_explicit_level_requests():
    assert parse_query_needs("Busco un libro sencillo con ejemplos.").level == "introductory"
    assert (
        parse_query_needs("Je commence la philosophie, avec des exemples.").level
        == "introductory"
    )
    assert (
        parse_query_needs("Ich suche eine verständliche Einführung mit Beispielen.").level
        == "introductory"
    )


def test_topic_alone_does_not_imply_reading_level_or_format():
    needs = parse_query_needs("Climate adaptation in cities")
    assert needs.level is None
    assert needs.wants_examples is False
    assert needs.wants_methods is False
    assert needs.avoids_code is False
