"""Text helpers.

Implements spec 001 (specs/001-slugify.md).
"""

from __future__ import annotations

SEPARATOR = "-"
ALLOWED_CHARACTERS = "abcdefghijklmnopqrstuvwxyz0123456789"


def slugify(text: str) -> str:
    """Turn a human-readable text into a short, URL-safe identifier.

    Args:
        text: Text to convert, for example a title.

    Returns:
        The text in lower case, where every run of characters that are not
        ASCII letters or digits is replaced by a single hyphen, without a
        hyphen at the start or at the end.

    Raises:
        ValueError: If the text contains no ASCII letter or digit.
    """
    words: list[str] = []
    current_word = ""

    for character in text.lower():
        if character in ALLOWED_CHARACTERS:
            current_word = current_word + character
            continue
        # Any other character ends the word being built.
        if current_word:
            words.append(current_word)
            current_word = ""

    if current_word:
        words.append(current_word)

    if not words:
        raise ValueError(f"Cannot slugify {text!r}: it contains no letter or digit.")

    return SEPARATOR.join(words)
