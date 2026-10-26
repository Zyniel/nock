"""Tests of grid-files AC-16 and AC-17: the fields a file carries beside its grid.

The force (`difficulty`), the publication date (`date`) and the optional fields of
rule 11. The shared setup is in `grid_files_harness`.

Choices where the spec leaves room:

- AC-16: a missing `difficulty` or `date` is refused (rule 10: the three fields
  are required); only the refusal is expected, not the message.
- AC-17: the fields are recorded "as written" (rule 11), so surrounding spaces
  are kept, unlike the credits.
- AC-17: "a non-text value is refused" is tried with a number and a list; `null`
  is not tried.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from grid_files_harness import (
    fx01_ipuz_data,
    read_data,
    read_error,
    write_one_grid,
)
from nock.catalogue import load_catalogue
from nock.grid import Grid
from spec004_harness import make_client, make_dist_dir, make_entry

# ---- AC-16: the force and the date ----------------------------------------------


@pytest.mark.parametrize("difficulty", [3, "3"])
def test_ac16_a_difficulty_of_one_digit_loads_as_the_force(
    difficulty: int | str,
) -> None:
    data = fx01_ipuz_data()
    data["difficulty"] = difficulty

    assert read_data(data).force == 3


@pytest.mark.parametrize("difficulty", ["Force 3", 5, "03", 3.0])
def test_ac16_another_difficulty_is_refused(difficulty: object) -> None:
    data = fx01_ipuz_data()
    data["difficulty"] = difficulty

    read_error(data)


@pytest.mark.parametrize("key", ["difficulty", "date"])
def test_ac16_a_missing_difficulty_or_date_is_refused(key: str) -> None:
    data = fx01_ipuz_data()
    del data[key]

    read_error(data)


@pytest.mark.parametrize(
    ("written", "published_on"),
    [
        ("10/01/2026", date(2026, 10, 1)),
        ("12/31/2026", date(2026, 12, 31)),
    ],
)
def test_ac16_a_date_written_month_day_year_loads_as_the_publication_date(
    written: str, published_on: date
) -> None:
    data = fx01_ipuz_data()
    data["date"] = written

    assert read_data(data).published_on == published_on


@pytest.mark.parametrize("written", ["2026-10-01", "1/1/2026", "02/30/2026"])
def test_ac16_another_date_is_refused(written: str) -> None:
    data = fx01_ipuz_data()
    data["date"] = written

    read_error(data)


def test_ac16_the_summary_keeps_the_date_written_year_month_day(
    tmp_path: Path,
) -> None:
    grids_dir = tmp_path / "grids"
    grids_dir.mkdir()
    write_one_grid(grids_dir)
    client = make_client(load_catalogue(grids_dir), make_dist_dir(tmp_path))

    response = client.get("/api/grids/1")

    assert response.status_code == 200
    assert response.json()["published_on"] == "2026-10-01"


# ---- AC-17: the optional fields -----------------------------------------------------

OPTIONAL_FIELDS = {
    "title": "Grille du jour",
    "editor": "Jeanne Éditrice",
    "publisher": "Le Journal",
    "publication": "Le Journal du dimanche",
    "url": "https://example.org/g/1",
    "uniqueid": "lj-2026-001",
    "origin": "Atelier Nock",
    "copyright": "© 2026 Équipe Nock",
}


def test_ac17_the_fields_are_recorded_as_written_and_an_absent_one_is_none() -> None:
    data = fx01_ipuz_data()
    data.update(OPTIONAL_FIELDS)
    data["title"] = "  Grille du jour  "

    with_fields = read_data(data)
    without_fields = read_data(fx01_ipuz_data())

    for name, value in OPTIONAL_FIELDS.items():
        expected = "  Grille du jour  " if name == "title" else value
        assert getattr(with_fields, name) == expected, name
        assert getattr(without_fields, name) is None, name


def test_ac17_an_entry_built_in_code_has_none_of_the_fields(
    fx01_text: str,
) -> None:
    entry = make_entry(
        Grid.model_validate_json(fx01_text), 1, date(2026, 10, 1), 2, True
    )

    for name in OPTIONAL_FIELDS:
        assert getattr(entry, name) is None, name


def test_ac17_the_fields_reach_the_catalogue_entry(tmp_path: Path) -> None:
    data = fx01_ipuz_data()
    data.update(OPTIONAL_FIELDS)
    write_one_grid(tmp_path, data)

    entry = load_catalogue(tmp_path).entries[0]

    for name, value in OPTIONAL_FIELDS.items():
        assert getattr(entry, name) == value, name


@pytest.mark.parametrize("name", sorted(OPTIONAL_FIELDS))
@pytest.mark.parametrize("value", [7, ["Grille du jour"]], ids=["number", "list"])
def test_ac17_a_field_that_is_not_a_text_is_refused(name: str, value: object) -> None:
    data = fx01_ipuz_data()
    data[name] = value

    read_error(data)


def test_ac17_the_summary_of_a_grid_holds_none_of_the_fields(tmp_path: Path) -> None:
    grids_dir = tmp_path / "grids"
    grids_dir.mkdir()
    data = fx01_ipuz_data()
    data.update(OPTIONAL_FIELDS)
    write_one_grid(grids_dir, data)
    client = make_client(load_catalogue(grids_dir), make_dist_dir(tmp_path))

    detail = client.get("/api/grids/1")
    listing = client.get("/api/grids")

    assert set(detail.json()) == {
        "number",
        "published_on",
        "force",
        "width",
        "height",
        "word_count",
    }
    for response in (detail, listing):
        body_text = json.dumps(response.json(), ensure_ascii=False)
        for name, value in OPTIONAL_FIELDS.items():
            assert value not in body_text, name
