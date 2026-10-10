"""Tests for spec 001 (specs/001-slugify.md).

Each test name starts with the acceptance criterion it covers: test_ac1_...
checks AC-1, and so on. The quality gate relies on that naming.
"""

from __future__ import annotations

import pytest

from nock.text import slugify


def test_ac1_lowercases_text() -> None:
    assert slugify("Hello") == "hello"


def test_ac1_keeps_text_that_is_already_lower_case() -> None:
    assert slugify("hello") == "hello"


def test_ac2_replaces_a_run_of_separators_with_one_hyphen() -> None:
    assert slugify("Hello,   World") == "hello-world"


def test_ac2_keeps_digits() -> None:
    assert slugify("Version 2") == "version-2"


def test_ac2_treats_accented_characters_as_separators() -> None:
    assert slugify("crème brûlée") == "cr-me-br-l-e"


def test_ac3_has_no_hyphen_at_the_start_or_the_end() -> None:
    assert slugify("  Hello World!  ") == "hello-world"


@pytest.mark.parametrize("text", ["", "   ", "!?...", "é"])
def test_ac4_rejects_text_without_letter_or_digit(text: str) -> None:
    with pytest.raises(ValueError, match="no letter or digit"):
        slugify(text)
