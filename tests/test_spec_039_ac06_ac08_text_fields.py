"""Tests of spec 039, AC-6 to AC-8: the text fields.

AC-6: the letter of a cell edit. AC-7: the nickname of a join. AC-8: the text
of a chat message. The shared setup is in `spec039_harness`.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from nock.protocol import (
    Chat,
    EditLetter,
    Join,
    LetterCellView,
    PencilEdit,
    Snapshot,
    parse_client_message,
    parse_server_message,
)
from spec039_harness import client_data, server_data, with_key, without_key

# ---- AC-6 ---------------------------------------------------------------


def edit_letter_with(letter: object) -> str:  # raw JSON value: any
    """Return the edit_letter example with another letter."""
    return json.dumps(with_key(client_data("edit_letter"), "letter", letter))


def pencil_edit_with(letter: object) -> str:  # raw JSON value: any
    """Return the pencil_edit example with another letter."""
    return json.dumps(with_key(client_data("pencil_edit"), "letter", letter))


@pytest.mark.parametrize("letter", ["A", "Z", "M"])
def test_ac6_edit_letter_accepts_uppercase_letter(letter: str) -> None:
    message = parse_client_message(edit_letter_with(letter))

    assert isinstance(message, EditLetter)
    assert message.letter == letter


@pytest.mark.parametrize("letter", ["A", "Z", "M"])
def test_ac6_pencil_edit_accepts_uppercase_letter(letter: str) -> None:
    message = parse_client_message(pencil_edit_with(letter))

    assert isinstance(message, PencilEdit)
    assert message.letter == letter


BAD_LETTERS: list[Any] = ["a", "É", "AB", "", "1", " ", None, "A\n", "z", "[", "@"]


@pytest.mark.parametrize("letter", BAD_LETTERS)
def test_ac6_edit_letter_rejects_bad_letter(letter: object) -> None:
    with pytest.raises(ValidationError):
        parse_client_message(edit_letter_with(letter))


@pytest.mark.parametrize("letter", BAD_LETTERS)
def test_ac6_pencil_edit_rejects_bad_letter(letter: object) -> None:
    with pytest.raises(ValidationError):
        parse_client_message(pencil_edit_with(letter))


def test_ac6_edit_letter_without_letter_is_rejected() -> None:
    data = without_key(client_data("edit_letter"), "letter")

    with pytest.raises(ValidationError):
        parse_client_message(json.dumps(data))


def test_ac6_letter_changed_rejects_lowercase() -> None:
    data = with_key(server_data("letter_changed"), "letter", "a")

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


def test_ac6_cell_locked_rejects_lowercase_and_null() -> None:
    lowercase = with_key(server_data("cell_locked"), "letter", "t")
    null_letter = with_key(server_data("cell_locked"), "letter", None)

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(lowercase))
    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(null_letter))


def test_ac6_letter_cell_view_rejects_lowercase() -> None:
    data = server_data("snapshot")
    data["grid"]["cells"][1]["letter"] = "t"

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))


def test_ac6_letter_cell_view_accepts_uppercase() -> None:
    data = server_data("snapshot")
    data["grid"]["cells"][1]["letter"] = "T"

    message = parse_server_message(json.dumps(data))

    assert isinstance(message, Snapshot)
    letter_cell = message.grid.cells[1]
    assert isinstance(letter_cell, LetterCellView)
    assert letter_cell.letter == "T"


# ---- AC-7 ---------------------------------------------------------------


def join_with(nickname: str) -> str:
    """Return the join example with another nickname."""
    return json.dumps(with_key(client_data("join"), "nickname", nickname))


@pytest.mark.parametrize(
    ("sent", "expected"),
    [
        ("  Ana  ", "Ana"),
        ("Ana", "Ana"),
        ("Al", "Al"),
        ("  Al\t", "Al"),
        ("x" * 20, "x" * 20),
        ("  " + "x" * 20 + "  ", "x" * 20),
        ("Jean Luc", "Jean Luc"),
    ],
)
def test_ac7_nickname_is_trimmed_and_accepted(sent: str, expected: str) -> None:
    message = parse_client_message(join_with(sent))

    assert isinstance(message, Join)
    assert message.nickname == expected


@pytest.mark.parametrize("sent", ["A", "  A  ", "", "   ", "x" * 21, "  " + "x" * 21])
def test_ac7_nickname_outside_two_to_twenty_is_rejected(sent: str) -> None:
    with pytest.raises(ValidationError):
        parse_client_message(join_with(sent))


def test_ac7_join_without_nickname_is_rejected() -> None:
    data = without_key(client_data("join"), "nickname")

    with pytest.raises(ValidationError):
        parse_client_message(json.dumps(data))


def test_ac7_player_view_nickname_uses_the_same_rule() -> None:
    too_long = server_data("player_joined")
    too_long["player"]["nickname"] = "x" * 21
    too_short = server_data("player_joined")
    too_short["player"]["nickname"] = "A"

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(too_long))
    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(too_short))


# Code points written as escapes: a thumbs up with a skin tone is 2 code points,
# a family emoji (three people joined by two zero width joiners) is 5.
THUMBS_UP = "👍"
SKIN_TONE = "🏽"
FAMILY = "👨‍👩‍👧"


def test_ac7_emoji_of_two_code_points_counts_as_two() -> None:
    message = parse_client_message(join_with(THUMBS_UP + SKIN_TONE))

    assert isinstance(message, Join)
    assert message.nickname == THUMBS_UP + SKIN_TONE


def test_ac7_emoji_of_one_code_point_counts_as_one() -> None:
    with pytest.raises(ValidationError):
        parse_client_message(join_with(THUMBS_UP))


def test_ac7_four_family_emoji_are_twenty_code_points() -> None:
    message = parse_client_message(join_with(FAMILY * 4))

    assert isinstance(message, Join)
    assert message.nickname == FAMILY * 4


def test_ac7_four_family_emoji_and_one_letter_are_twenty_one_code_points() -> None:
    with pytest.raises(ValidationError):
        parse_client_message(join_with(FAMILY * 4 + "x"))


# ---- AC-8 ---------------------------------------------------------------


def chat_with(text: str) -> str:
    """Return the chat example with another text."""
    return json.dumps(with_key(client_data("chat"), "text", text))


@pytest.mark.parametrize(
    ("sent", "expected"),
    [
        ("a" * 280, "a" * 280),
        (" salut ", "salut"),
        ("a", "a"),
        ("  " + "a" * 280 + "  ", "a" * 280),
        ("<b>salut</b>", "<b>salut</b>"),
    ],
)
def test_ac8_chat_text_is_trimmed_and_accepted(sent: str, expected: str) -> None:
    message = parse_client_message(chat_with(sent))

    assert isinstance(message, Chat)
    assert message.text == expected


@pytest.mark.parametrize("sent", ["", " ", "   \t\n", "a" * 281, " " + "a" * 281])
def test_ac8_chat_text_outside_range_is_rejected(sent: str) -> None:
    with pytest.raises(ValidationError):
        parse_client_message(chat_with(sent))


def test_ac8_chat_without_text_is_rejected() -> None:
    data = without_key(client_data("chat"), "text")

    with pytest.raises(ValidationError):
        parse_client_message(json.dumps(data))


def test_ac8_chat_markup_round_trips_unchanged() -> None:
    message = parse_client_message(chat_with("<b>salut</b>"))

    again = parse_client_message(message.model_dump_json())

    assert isinstance(again, Chat)
    assert again.text == "<b>salut</b>"


def test_ac8_server_chat_message_uses_the_same_rule() -> None:
    too_long = with_key(server_data("chat_message"), "text", "a" * 281)
    blank = with_key(server_data("chat_message"), "text", "  ")

    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(too_long))
    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(blank))


def test_ac8_fifty_six_family_emoji_are_280_code_points() -> None:
    message = parse_client_message(chat_with(FAMILY * 56))

    assert isinstance(message, Chat)
    assert message.text == FAMILY * 56


def test_ac8_family_emoji_over_280_code_points_are_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_client_message(chat_with(FAMILY * 56 + "x"))
