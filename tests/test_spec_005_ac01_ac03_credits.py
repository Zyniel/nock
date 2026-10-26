"""Tests of spec 005, AC-1 to AC-3: the credits of a catalogue entry.

These are the tests of grid-files AC-3. `source` and `licence` are in the index
and `author` in the grid file. An entry or a file without them is refused (AC-1),
a credit that is blank, null, of the wrong type or too long is refused and the
others are stripped (AC-2), and a complete grid loads with its credits and its
`withdrawn` flag (AC-3). The shared setup is in `spec005_harness` and
`grid_files_harness`.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from grid_files_harness import (
    fx01_ipuz_data,
    index_entry,
    write_grid_file,
    write_index,
    write_one_grid,
)
from nock.catalogue import (
    CatalogueEntry,
    CatalogueError,
    GridSummary,
    load_catalogue,
    summarize,
)
from nock.grid import Grid
from spec005_harness import credits, grid_from_text, make_entry

AUTHOR = "Équipe Nock"
SOURCE = "Commande Nock 2026"
LICENCE = "Contrat d'auteur Nock n° 1"

# The credits of the index are refused naming `catalogue.json`, the author of the
# grid file naming the file.
INDEX_CREDITS = ["source", "licence"]
ALL_CREDITS = ["author", "source", "licence"]


# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def write_credit(directory: Path, field: str, value: object) -> str:
    """Write grid number 1 with `value` as the credit `field`.

    Returns:
        The name the error of a refused credit must hold.
    """
    if field == "author":
        data = fx01_ipuz_data()
        data["author"] = value
        write_one_grid(directory, data)
        return "g1.ipuz"
    write_one_grid(directory, **{field: value})
    return "catalogue.json"


def loaded_credit(directory: Path, field: str) -> str:
    """Return the credit `field` of the only entry of the catalogue in `directory`."""
    entry = load_catalogue(directory).entries[0]
    return str(getattr(entry, field))


# ---- AC-1: missing credits refuse the grid ----------------------------------


@pytest.mark.parametrize("field", INDEX_CREDITS)
def test_ac1_an_index_entry_without_a_credit_is_refused(
    tmp_path: Path, field: str
) -> None:
    write_grid_file(tmp_path, "g1.ipuz")
    entry = index_entry()
    del entry[field]
    write_index(tmp_path, [entry])

    with pytest.raises(CatalogueError, match=r"catalogue\.json"):
        load_catalogue(tmp_path)


def test_ac1_a_grid_file_without_an_author_is_refused(tmp_path: Path) -> None:
    data = fx01_ipuz_data()
    del data["author"]
    write_one_grid(tmp_path, data)

    with pytest.raises(CatalogueError, match=r"g1\.ipuz"):
        load_catalogue(tmp_path)


def test_ac1_the_american_spelling_license_is_an_unknown_key(tmp_path: Path) -> None:
    write_grid_file(tmp_path, "g1.ipuz")
    entry = index_entry()
    del entry["licence"]
    entry["license"] = LICENCE
    write_index(tmp_path, [entry])

    with pytest.raises(CatalogueError, match=r"catalogue\.json"):
        load_catalogue(tmp_path)


@pytest.mark.parametrize("field", ALL_CREDITS)
def test_ac1_an_entry_built_in_code_without_a_credit_is_refused(
    fx01_grid: Grid, field: str
) -> None:
    values = {"author": AUTHOR, "source": SOURCE, "licence": LICENCE}
    del values[field]

    with pytest.raises(ValidationError, match=field):
        CatalogueEntry(
            number=1,
            published_on=date(2026, 10, 1),
            force=2,
            published=True,
            grid=fx01_grid,
            **values,
        )


# ---- AC-2: blank, null, wrong type or too long ------------------------------


@pytest.mark.parametrize("field", ALL_CREDITS)
@pytest.mark.parametrize(
    "bad_value",
    [
        pytest.param("", id="empty"),
        pytest.param("   ", id="blank"),
        pytest.param("\n\t ", id="whitespace-only"),
        pytest.param("a" * 201, id="201-characters"),
        pytest.param("é" * 201, id="201-code-points"),
        pytest.param(" " + "a" * 201 + " ", id="201-after-stripping"),
        pytest.param(None, id="null"),
        pytest.param(42, id="number"),
        pytest.param(["Équipe Nock"], id="list"),
    ],
)
def test_ac2_a_blank_or_invalid_credit_is_refused(
    tmp_path: Path, field: str, bad_value: object
) -> None:
    refused_name = write_credit(tmp_path, field, bad_value)

    with pytest.raises(CatalogueError, match=refused_name.replace(".", r"\.")):
        load_catalogue(tmp_path)


def test_ac2_a_credit_is_stripped_at_both_ends(tmp_path: Path) -> None:
    write_credit(tmp_path, "author", "  Équipe Nock  ")

    assert loaded_credit(tmp_path, "author") == "Équipe Nock"


@pytest.mark.parametrize("field", ALL_CREDITS)
def test_ac2_every_credit_is_stripped(tmp_path: Path, field: str) -> None:
    write_credit(tmp_path, field, "\t texte \n")

    assert loaded_credit(tmp_path, field) == "texte"


@pytest.mark.parametrize("field", ALL_CREDITS)
def test_ac2_a_credit_of_200_characters_is_accepted(tmp_path: Path, field: str) -> None:
    write_credit(tmp_path, field, "a" * 200)

    assert loaded_credit(tmp_path, field) == "a" * 200


@pytest.mark.parametrize("field", ALL_CREDITS)
def test_ac2_the_limit_counts_the_characters_after_stripping(
    tmp_path: Path, field: str
) -> None:
    write_credit(tmp_path, field, "  " + "a" * 200 + "  ")

    assert loaded_credit(tmp_path, field) == "a" * 200


@pytest.mark.parametrize("field", ALL_CREDITS)
def test_ac2_the_limit_counts_code_points_not_bytes(tmp_path: Path, field: str) -> None:
    write_credit(tmp_path, field, "é" * 200)

    assert loaded_credit(tmp_path, field) == "é" * 200


@pytest.mark.parametrize("field", ALL_CREDITS)
def test_ac2_a_single_character_credit_is_accepted(tmp_path: Path, field: str) -> None:
    write_credit(tmp_path, field, "x")

    assert loaded_credit(tmp_path, field) == "x"


@pytest.mark.parametrize("field", ALL_CREDITS)
def test_ac2_line_breaks_inside_a_credit_are_kept(tmp_path: Path, field: str) -> None:
    write_credit(tmp_path, field, "Contrat\nn° 1")

    assert loaded_credit(tmp_path, field) == "Contrat\nn° 1"


# ---- AC-3: a complete grid loads with its credits ---------------------------


def test_ac3_a_complete_grid_loads_with_its_credits_and_is_not_withdrawn(
    tmp_path: Path,
) -> None:
    write_one_grid(tmp_path)

    loaded = load_catalogue(tmp_path)

    assert len(loaded.entries) == 1
    entry = loaded.entries[0]
    assert entry.author == AUTHOR
    assert entry.source == SOURCE
    assert entry.licence == LICENCE
    assert entry.withdrawn is False


@pytest.mark.parametrize("withdrawn", [True, False])
def test_ac3_withdrawn_is_read_from_the_index(tmp_path: Path, withdrawn: bool) -> None:
    write_one_grid(tmp_path, withdrawn=withdrawn)

    loaded = load_catalogue(tmp_path)

    assert loaded.entries[0].withdrawn is withdrawn


@pytest.mark.parametrize(
    "bad_value",
    [
        pytest.param("yes", id="string-yes"),
        pytest.param(1, id="number-1"),
        pytest.param(0, id="number-0"),
        pytest.param("true", id="string-true"),
    ],
)
def test_ac3_withdrawn_must_be_a_strict_boolean(
    tmp_path: Path, bad_value: object
) -> None:
    write_one_grid(tmp_path, withdrawn=bad_value)

    with pytest.raises(CatalogueError, match=r"catalogue\.json"):
        load_catalogue(tmp_path)


def test_ac3_withdrawn_is_false_by_default_on_an_entry_built_in_code(
    fx01_grid: Grid,
) -> None:
    entry = CatalogueEntry(
        number=1,
        published_on=date(2026, 10, 1),
        force=2,
        published=True,
        **credits(),
        grid=fx01_grid,
    )

    assert entry.withdrawn is False


def test_ac3_the_summary_does_not_carry_the_credits(fx01_grid: Grid) -> None:
    entry = make_entry(fx01_grid, 7)

    summary = summarize(entry)

    assert summary == GridSummary(
        number=7,
        published_on=date(2026, 10, 1),
        force=2,
        width=5,
        height=5,
        word_count=8,
    )
    assert set(summary.model_dump()) == {
        "number",
        "published_on",
        "force",
        "width",
        "height",
        "word_count",
    }
