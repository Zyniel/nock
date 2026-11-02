"""Tests of grid-files AC-17: the optional fields a file carries beside its grid.

The optional fields of rule 11. The shared setup is in `grid_files_harness`.

Choices where the spec leaves room:

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
