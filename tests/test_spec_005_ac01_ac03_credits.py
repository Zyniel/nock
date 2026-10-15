"""Tests of spec 005, AC-1 to AC-3: the credits of a catalogue entry.

A grid file without author, source and licence is refused (AC-1), a credit that is
blank, null, of the wrong type or too long is refused and the others are stripped
(AC-2), and a complete file loads with its credits and its `withdrawn` flag (AC-3).
The shared setup is in `spec005_harness`.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

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


# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def write_grid_file(
    directory: Path,
    fx01_text: str,
    drop: tuple[str, ...] = (),
    overrides: dict[str, object] | None = None,
) -> Path:
    """Write `g1.json`: number 1, FX-01 and CREDITS, minus `drop`, plus `overrides`."""
    payload: dict[str, object] = {
        "number": 1,
        "published_on": "2026-10-01",
        "force": 2,
        "published": True,
        **credits(),
        "grid": json.loads(fx01_text),
    }
    for key in drop:
        del payload[key]
    if overrides is not None:
        payload.update(overrides)
    path = directory / "g1.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def error_text(error: pytest.ExceptionInfo[CatalogueError]) -> ValidationError:
    """Return the pydantic error behind a CatalogueError, failing when absent."""
    cause = error.value.__cause__
    assert isinstance(cause, ValidationError)
    return cause


# ---- AC-1: missing credits refuse the file ----------------------------------


@pytest.mark.parametrize("field", ["author", "source", "licence"])
def test_ac1_a_file_without_a_credit_key_is_refused(
    tmp_path: Path, fx01_text: str, field: str
) -> None:
    write_grid_file(tmp_path, fx01_text, drop=(field,))

    with pytest.raises(CatalogueError, match=r"g1\.json") as error_info:
        load_catalogue(tmp_path)

    cause = error_text(error_info)
    assert field in str(cause)


def test_ac1_the_american_spelling_license_is_an_unknown_key(
    tmp_path: Path, fx01_text: str
) -> None:
    write_grid_file(
        tmp_path, fx01_text, drop=("licence",), overrides={"license": LICENCE}
    )

    with pytest.raises(CatalogueError, match=r"g1\.json"):
        load_catalogue(tmp_path)


def test_ac1_a_file_with_none_of_the_credits_is_refused(
    tmp_path: Path, fx01_text: str
) -> None:
    write_grid_file(tmp_path, fx01_text, drop=("author", "source", "licence"))

    with pytest.raises(CatalogueError, match=r"g1\.json"):
        load_catalogue(tmp_path)


@pytest.mark.parametrize("field", ["author", "source", "licence"])
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


@pytest.mark.parametrize("field", ["author", "source", "licence"])
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
    tmp_path: Path, fx01_text: str, field: str, bad_value: object
) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={field: bad_value})

    with pytest.raises(CatalogueError, match=r"g1\.json") as error_info:
        load_catalogue(tmp_path)

    assert isinstance(error_info.value.__cause__, ValidationError)


def test_ac2_a_credit_is_stripped_at_both_ends(tmp_path: Path, fx01_text: str) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={"author": "  Équipe Nock  "})

    loaded = load_catalogue(tmp_path)

    assert loaded.entries[0].author == "Équipe Nock"


@pytest.mark.parametrize("field", ["source", "licence"])
def test_ac2_every_credit_is_stripped(
    tmp_path: Path, fx01_text: str, field: str
) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={field: "\t texte \n"})

    loaded = load_catalogue(tmp_path)

    assert getattr(loaded.entries[0], field) == "texte"


@pytest.mark.parametrize("field", ["author", "source", "licence"])
def test_ac2_a_credit_of_200_characters_is_accepted(
    tmp_path: Path, fx01_text: str, field: str
) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={field: "a" * 200})

    loaded = load_catalogue(tmp_path)

    assert getattr(loaded.entries[0], field) == "a" * 200


def test_ac2_the_limit_counts_the_characters_after_stripping(
    tmp_path: Path, fx01_text: str
) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={"author": "  " + "a" * 200 + "  "})

    loaded = load_catalogue(tmp_path)

    assert loaded.entries[0].author == "a" * 200


def test_ac2_the_limit_counts_code_points_not_bytes(
    tmp_path: Path, fx01_text: str
) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={"source": "é" * 200})

    loaded = load_catalogue(tmp_path)

    assert loaded.entries[0].source == "é" * 200


def test_ac2_a_single_character_credit_is_accepted(
    tmp_path: Path, fx01_text: str
) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={"licence": "x"})

    loaded = load_catalogue(tmp_path)

    assert loaded.entries[0].licence == "x"


def test_ac2_line_breaks_inside_a_credit_are_kept(
    tmp_path: Path, fx01_text: str
) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={"licence": "Contrat\nn° 1"})

    loaded = load_catalogue(tmp_path)

    assert loaded.entries[0].licence == "Contrat\nn° 1"


# ---- AC-3: a complete file loads with its credits ---------------------------


def test_ac3_a_complete_file_loads_with_its_credits_and_is_not_withdrawn(
    tmp_path: Path, fx01_text: str
) -> None:
    write_grid_file(tmp_path, fx01_text)

    loaded = load_catalogue(tmp_path)

    assert len(loaded.entries) == 1
    entry = loaded.entries[0]
    assert entry.author == AUTHOR
    assert entry.source == SOURCE
    assert entry.licence == LICENCE
    assert entry.withdrawn is False


def test_ac3_withdrawn_true_is_read(tmp_path: Path, fx01_text: str) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={"withdrawn": True})

    loaded = load_catalogue(tmp_path)

    assert loaded.entries[0].withdrawn is True


def test_ac3_withdrawn_false_is_read(tmp_path: Path, fx01_text: str) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={"withdrawn": False})

    loaded = load_catalogue(tmp_path)

    assert loaded.entries[0].withdrawn is False


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
    tmp_path: Path, fx01_text: str, bad_value: object
) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={"withdrawn": bad_value})

    with pytest.raises(CatalogueError, match=r"g1\.json"):
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
