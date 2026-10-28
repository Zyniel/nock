"""Tests of grid-files AC-7: a grid file survives load, write and load.

The writer of rule 14 (`write_ipuz`) writes the text of a loaded file; reading it
again gives the same file. The shared setup is in `grid_files_harness`.

Choices where the spec leaves room:

- A written `puzzle` is compared with `0` and `"0"` taken as the same value
  (rule 6), since rule 14 only says `#` and `0`.
- Rule 11's fields that are absent are expected to be left out of the text
  ("the fields of rule 11 that are present").
"""

from __future__ import annotations

import json

import pytest

from grid_files_harness import (
    JsonData,
    clue_named,
    fx01_ipuz_data,
    mini_data,
    read_data,
)
from nock.ipuz import read_ipuz, write_ipuz


def written_json(data: JsonData) -> JsonData:
    """Read ipuz data, write it back and return the JSON the writer wrote."""
    return json.loads(write_ipuz(read_data(data)))


def vide_across_data(answer: str = "VI-DE", enumeration: str = "2-2") -> JsonData:
    """FX-01 with `VI-DE` across from (2, 1), the clue `Sans contenu` at (2, 0)."""
    data = fx01_ipuz_data()
    clue = clue_named(data, "Sans contenu")
    clue["answer"] = answer
    clue["enumeration"] = enumeration
    return data


def test_ac7_a_file_with_title_and_publisher_survives_write_and_read() -> None:
    data = fx01_ipuz_data()
    data["title"] = "Grille du jour"
    data["publisher"] = "Le Journal"
    first = read_data(data)

    second = read_ipuz(write_ipuz(first))

    assert second == first
    assert second.grid == first.grid
    assert second.author == first.author
    assert second.published_on == first.published_on
    assert second.force == first.force
    assert second.title == "Grille du jour"
    assert second.publisher == "Le Journal"


def test_ac7_the_writer_writes_the_fields_of_rule_5_and_the_clues() -> None:
    expected = fx01_ipuz_data()

    written = written_json(fx01_ipuz_data())

    for key in ("version", "kind", "clueplacement", "dimensions", "author", "date"):
        assert written[key] == expected[key], key
    assert written["difficulty"] == 2
    assert type(written["difficulty"]) is int
    assert written["solution"] == expected["solution"]
    assert written["clues"] == expected["clues"]


def test_ac7_the_writer_writes_the_puzzle_with_hash_and_zero() -> None:
    expected = fx01_ipuz_data()

    written = written_json(fx01_ipuz_data())

    written_rows = []
    for row in written["puzzle"]:
        written_rows.append([str(value) for value in row])
    expected_rows = []
    for row in expected["puzzle"]:
        expected_rows.append([str(value) for value in row])
    assert written_rows == expected_rows


def test_ac7_the_writer_writes_the_fields_of_rule_11_that_are_present() -> None:
    data = fx01_ipuz_data()
    data["title"] = "Grille du jour"
    data["publisher"] = "Le Journal"

    written = written_json(data)

    assert written["title"] == "Grille du jour"
    assert written["publisher"] == "Le Journal"
    assert "editor" not in written
    assert "url" not in written


@pytest.mark.parametrize(
    ("answer", "enumeration"),
    [("VI-DE", "2-2"), ("VI.DE", "2.2"), ("VI DE", "2 2")],
)
def test_ac7_a_word_is_written_with_its_separator_and_its_dashed_edge(
    answer: str, enumeration: str
) -> None:
    first = read_data(vide_across_data(answer, enumeration))

    written = json.loads(write_ipuz(first))

    clue = clue_named(written, "Sans contenu")
    assert clue["answer"] == answer
    assert clue["enumeration"] == enumeration
    dashed_cell = written["puzzle"][2][2]
    assert dashed_cell["style"] == {"dashed": "R"}
    assert str(dashed_cell["cell"]) == "0"
    assert read_ipuz(write_ipuz(first)) == first


@pytest.mark.parametrize(
    ("answer", "letters", "enumeration"),
    [
        ("A.I", "AI", "1.1"),
        ("A I", "AI", "1 1"),
        ("A-I", "AI", "1-1"),
        ("AUJOURD'HUI", "AUJOURDHUI", "7'3"),
        ("AUJOURD" + chr(0x2019) + "HUI", "AUJOURDHUI", "7'3"),
        ("ARC-EN CIEL", "ARCENCIEL", "3-2 4"),
    ],
)
def test_ac7_the_writer_derives_the_enumeration_from_the_answer(
    answer: str, letters: str, enumeration: str
) -> None:
    first = read_data(mini_data(answer, letters))

    written = json.loads(write_ipuz(first))

    clue = clue_named(written, "Indice")
    assert clue["answer"] == answer
    assert clue["enumeration"] == enumeration
    assert read_ipuz(write_ipuz(first)) == first


def test_ac7_a_down_hyphen_is_written_as_dashed_b_on_the_letter_above() -> None:
    data = fx01_ipuz_data()
    clue = clue_named(data, "De la marine")
    clue["answer"] = "NA-VAL"
    clue["enumeration"] = "2-3"
    first = read_data(data)

    written = json.loads(write_ipuz(first))

    assert written["puzzle"][1][1]["style"] == {"dashed": "B"}
    assert read_ipuz(write_ipuz(first)) == first


def shared_edge_data() -> JsonData:
    """A 4 by 2 grid whose two words share one hyphen edge.

    `AB-C` runs across from (1, 1) to (1, 3) (clue cell (1, 0)), and `B-C` across
    from (1, 2) to (1, 3) (clue cell (0, 2)): both break between (1, 2) and (1, 3).
    """
    data = fx01_ipuz_data()
    data["dimensions"] = {"width": 4, "height": 2}
    data["puzzle"] = [["#", "#", "#", "#"], ["#", 0, 0, 0]]
    data["solution"] = [["#", "#", "#", "#"], ["#", "A", "B", "C"]]
    data["clues"] = {
        "Clues": [
            {
                "clue": "Long",
                "location": [0, 1],
                "cells": [[1, 1], [2, 1], [3, 1]],
                "answer": "AB-C",
                "enumeration": "2-1",
            },
            {
                "clue": "Court",
                "location": [2, 0],
                "cells": [[2, 1], [3, 1]],
                "answer": "B-C",
                "enumeration": "1-1",
            },
        ]
    }
    return data


def test_ac7_a_hyphen_edge_shared_by_two_words_is_written_once() -> None:
    first = read_data(shared_edge_data())

    written = json.loads(write_ipuz(first))

    assert written["puzzle"][1][2]["style"] == {"dashed": "R"}
    assert read_ipuz(write_ipuz(first)) == first
