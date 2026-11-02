"""Tests of content/ipuz AC-1, AC-3 to AC-5, AC-12 and AC-13: the structure of a file.

A file is read as a whole (`read_ipuz`): FX-01 as an ipuz file, the kind, the
block and empty values, the shape of the puzzle, the keys the reader supports and
the plain text of a clue. The shared setup is in `grid_files_harness`.

Choices where the spec leaves room:

- AC-4, `block` ".": the `solution` is written with "." as well, since rule 2
  derives it with the block value.
- AC-5: the `solution` is left out, so that only the shape of `puzzle` can be
  the problem.
- AC-4, a `dashed` value of "" or "X" is only expected to be refused.
"""

from __future__ import annotations

from datetime import date

import pytest

from grid_files_harness import (
    FX01_IPUZ_PATH,
    JsonData,
    cell_with_clues,
    clue_named,
    dashed_cell,
    fx01_ipuz_data,
    fx01_model_grid,
    read_data,
    read_error,
)
from nock.grid import Arrow, ClueCell, Grid
from nock.ipuz import read_ipuz

# ---- AC-1: FX-01 as an ipuz file ---------------------------------------------


def clue_arrows(grid: Grid) -> dict[str, Arrow]:
    """Return the arrow of each clue of a grid, by clue text."""
    arrows: dict[str, Arrow] = {}
    for cell in grid.cells:
        if isinstance(cell, ClueCell):
            for clue in cell.clues:
                arrows[clue.text] = clue.arrow
    return arrows


def test_ac1_fx01_ipuz_loads_as_the_fx01_grid(fx01_text: str) -> None:
    grid_file = read_ipuz(FX01_IPUZ_PATH.read_text(encoding="utf-8"))

    assert grid_file.grid == fx01_model_grid(fx01_text)
    assert grid_file.author == "Équipe Nock"
    assert grid_file.published_on == date(2026, 10, 1)
    assert grid_file.force == 2


@pytest.mark.parametrize(
    ("text", "arrow"),
    [
        ("Passoire fine", Arrow.DOWN_THEN_RIGHT),
        ("De la marine", Arrow.RIGHT_THEN_DOWN),
        ("Artiste muet", Arrow.DOWN),
        ("Fatales à César", Arrow.DOWN),
        ("Flaire", Arrow.DOWN),
        ("Sans contenu", Arrow.RIGHT),
        ("Fin de prière", Arrow.RIGHT),
        ("Alourdit le ballon", Arrow.RIGHT),
    ],
)
def test_ac1_each_clue_of_fx01_gets_the_arrow_of_the_reference(
    text: str, arrow: Arrow
) -> None:
    grid_file = read_data(fx01_ipuz_data())

    assert clue_arrows(grid_file.grid)[text] == arrow


# ---- AC-3: the kind of file --------------------------------------------------

ARROWWORD_KIND = "http://ipuz.org/crossword/arrowword#1"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        pytest.param("version", "http://ipuz.org/v1", id="version-1"),
        pytest.param("kind", ["http://ipuz.org/crossword#1"], id="crossword-kind"),
        pytest.param(
            "kind", [ARROWWORD_KIND, "http://ipuz.org/crossword#1"], id="two-kinds"
        ),
        pytest.param("clueplacement", "after", id="clueplacement-after"),
    ],
)
def test_ac3_a_file_of_another_kind_is_refused_naming_the_key(
    key: str, value: object
) -> None:
    data = fx01_ipuz_data()
    data[key] = value

    message = read_error(data)

    assert key in message


# ---- AC-4: block, empty and the values of the puzzle -------------------------


def test_ac4_a_dot_block_with_a_puzzle_written_with_dots_loads_equal() -> None:
    data = fx01_ipuz_data()
    data["block"] = "."
    for grid_name in ("puzzle", "solution"):
        for row in data[grid_name]:
            for column, value in enumerate(row):
                if value == "#":
                    row[column] = "."

    assert read_data(data) == read_data(fx01_ipuz_data())


def test_ac4_a_block_equal_to_empty_is_refused() -> None:
    data = fx01_ipuz_data()
    data["block"] = "0"

    read_error(data)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(None, id="null"),
        pytest.param(1, id="clue-number"),
        pytest.param({"cell": 0}, id="object-without-style"),
        pytest.param(
            {"cell": 0, "style": {"dashed": "R", "color": 1}}, id="object-with-color"
        ),
    ],
)
def test_ac4_another_puzzle_value_is_refused_naming_the_cell(value: object) -> None:
    data = fx01_ipuz_data()
    data["puzzle"][1][0] = value

    message = read_error(data)

    assert "(1, 0)" in message


def test_ac4_a_text_zero_is_the_same_value_as_a_number_zero() -> None:
    data = fx01_ipuz_data()
    for row in data["puzzle"]:
        for column, value in enumerate(row):
            if value == 0:
                row[column] = "0"

    assert read_data(data) == read_data(fx01_ipuz_data())


@pytest.mark.parametrize("letters", ["", "X"])
def test_ac4_a_dashed_value_that_is_not_made_of_t_r_b_l_is_refused(
    letters: str,
) -> None:
    data = fx01_ipuz_data()
    data["puzzle"][1][0] = dashed_cell(letters)

    read_error(data)


# ---- AC-5: the shape of the puzzle ------------------------------------------


def test_ac5_a_row_cut_short_is_refused_as_a_missing_cell() -> None:
    data = fx01_ipuz_data()
    del data["solution"]
    data["puzzle"][2] = data["puzzle"][2][:4]

    message = read_error(data)

    assert "(2, 4)" in message
    assert "missing" in message


def test_ac5_a_sixth_value_in_a_row_is_refused_as_an_outside_cell() -> None:
    data = fx01_ipuz_data()
    del data["solution"]
    data["puzzle"][2].append(0)

    message = read_error(data)

    assert "(2, 5)" in message
    assert "outside" in message


# ---- AC-12: keys the reader supports ------------------------------------------


def with_key(where: str, key: str, value: object) -> JsonData:
    """Return FX-01 as ipuz data with one more key at the top, in `clues` or in W5."""
    data = fx01_ipuz_data()
    if where == "top":
        data[key] = value
    elif where == "clues":
        data["clues"][key] = value
    else:
        clue_named(data, "Flaire")[key] = value
    return data


@pytest.mark.parametrize(
    ("where", "key", "value"),
    [
        ("top", "saved", []),
        ("top", "styles", {}),
        ("top", "rating", 3),
        ("top", "checksum", ["abc"]),
        ("top", "zones", []),
        ("clues", "Across", []),
        ("clue", "number", 5),
    ],
)
def test_ac12_a_key_the_reader_does_not_support_is_refused_naming_it(
    where: str, key: str, value: object
) -> None:
    message = read_error(with_key(where, key, value))

    assert key in message


@pytest.mark.parametrize(
    ("where", "key", "value"),
    [
        ("top", "notes", "x"),
        ("top", "intro", "x"),
        ("top", "explanation", "x"),
        ("top", "annotation", "x"),
        ("top", "charset", "x"),
        ("top", "showenumerations", True),
        ("top", "com.example:rating", 3),
        ("clues", "com.example:x", 1),
        ("clue", "com.example:x", 1),
    ],
)
def test_ac12_a_descriptive_or_namespace_key_is_ignored(
    where: str, key: str, value: object
) -> None:
    data = with_key(where, key, value)

    assert read_data(data) == read_data(fx01_ipuz_data())


def test_ac12_a_namespace_key_in_place_of_clues_leaves_clues_missing() -> None:
    data = fx01_ipuz_data()
    data["clues"] = {"Clues:Définitions": data["clues"]["Clues"]}

    message = read_error(data)

    assert "Clues" in message


@pytest.mark.parametrize(
    "written",
    [
        pytest.param("Flaire", id="text"),
        pytest.param([5, "Flaire"], id="pair"),
    ],
)
def test_ac12_a_clue_written_as_a_text_or_a_pair_is_refused(written: object) -> None:
    data = fx01_ipuz_data()
    clues = data["clues"]["Clues"]
    clues[clues.index(clue_named(data, "Flaire"))] = written

    read_error(data)


# ---- AC-13: a clue text is plain ----------------------------------------------


def test_ac13_html_entities_of_a_clue_are_decoded() -> None:
    data = fx01_ipuz_data()
    clue_named(data, "Fatales à César")["clue"] = "Fatales &amp; César"

    grid_file = read_data(data)

    assert cell_with_clues(grid_file.grid, 0, 3).clues[0].text == "Fatales & César"


def test_ac13_an_encoded_tag_is_kept_as_literal_text() -> None:
    data = fx01_ipuz_data()
    clue_named(data, "Flaire")["clue"] = "&lt;b&gt;Flaire&lt;/b&gt;"

    grid_file = read_data(data)

    assert cell_with_clues(grid_file.grid, 0, 4).clues[0].text == "<b>Flaire</b>"


@pytest.mark.parametrize("text", ["<b>Flaire</b>", "Flaire >", "Flaire <"])
def test_ac13_a_raw_angle_bracket_is_refused_naming_the_clue_cell(text: str) -> None:
    data = fx01_ipuz_data()
    clue_named(data, "Flaire")["clue"] = text

    message = read_error(data)

    assert "(0, 4)" in message
