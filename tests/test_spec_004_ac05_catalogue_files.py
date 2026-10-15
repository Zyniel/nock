"""Tests of spec 004, AC-5: the catalogue files and `load_catalogue`.

The shared setup is in `spec004_harness`.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from nock.catalogue import GRIDS_DIR, Catalogue, CatalogueError, load_catalogue
from nock.grid import Grid
from nock.grid_import import GridImportError
from spec004_harness import (
    PROJECT_ROOT,
    grid_from_text,
    make_entry,
    make_reference_catalogue,
    write_catalogue_file,
)

# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of the spec (also served by live_server)."""
    return make_reference_catalogue(fx01_grid)


# ---- AC-5: catalogue files ---------------------------------------------------


def test_ac5_grids_dir_is_the_grids_directory_of_the_repository() -> None:
    assert GRIDS_DIR == PROJECT_ROOT / "grids"


def test_ac5_files_load_in_file_name_order(tmp_path: Path, fx01_text: str) -> None:
    write_catalogue_file(tmp_path, "b.json", fx01_text, number=2)
    write_catalogue_file(tmp_path, "a.json", fx01_text, number=1)

    loaded = load_catalogue(tmp_path)

    numbers = []
    for entry in loaded.entries:
        numbers.append(entry.number)
    assert numbers == [1, 2]
    expected_grid = Grid.model_validate_json(fx01_text)
    for entry in loaded.entries:
        assert entry.grid == expected_grid


def test_ac5_file_fields_are_read(tmp_path: Path, fx01_text: str) -> None:
    write_catalogue_file(
        tmp_path,
        "g.json",
        fx01_text,
        number=42,
        published_on="2026-02-03",
        force=4,
        published=False,
    )

    loaded = load_catalogue(tmp_path)

    assert len(loaded.entries) == 1
    entry = loaded.entries[0]
    assert entry.number == 42
    assert entry.published_on == date(2026, 2, 3)
    assert entry.force == 4
    assert entry.published is False


def test_ac5_missing_directory_is_an_empty_catalogue(tmp_path: Path) -> None:
    assert load_catalogue(tmp_path / "absent") == Catalogue()


def test_ac5_empty_directory_is_an_empty_catalogue(tmp_path: Path) -> None:
    assert load_catalogue(tmp_path) == Catalogue()


def test_ac5_other_extensions_and_sub_directories_are_ignored(
    tmp_path: Path, fx01_text: str
) -> None:
    write_catalogue_file(tmp_path, "a.json", fx01_text, number=1)
    (tmp_path / "notes.txt").write_text("not a catalogue file", encoding="utf-8")
    old_directory = tmp_path / "old"
    old_directory.mkdir()
    write_catalogue_file(old_directory, "z.json", fx01_text, number=9)

    loaded = load_catalogue(tmp_path)

    numbers = []
    for entry in loaded.entries:
        numbers.append(entry.number)
    assert numbers == [1]


def test_ac5_a_rejected_grid_raises_a_catalogue_error_from_the_import_error(
    tmp_path: Path, fx01_text: str
) -> None:
    broken_text = fx01_text.replace('"MIME"', '"MIMA"')
    assert broken_text != fx01_text
    write_catalogue_file(tmp_path, "good.json", fx01_text, number=1)
    write_catalogue_file(tmp_path, "bad.json", broken_text, number=2)

    with pytest.raises(CatalogueError, match=r"bad\.json") as error_info:
        load_catalogue(tmp_path)

    assert isinstance(error_info.value.__cause__, GridImportError)


def test_ac5_catalogue_error_is_a_value_error() -> None:
    assert issubclass(CatalogueError, ValueError)


INVALID_OVERRIDES = [
    pytest.param({"force": 5}, id="force-5"),
    pytest.param({"force": 0}, id="force-0"),
    pytest.param({"force": "2"}, id="force-string"),
    pytest.param({"number": 0}, id="number-0"),
    pytest.param({"number": 1_000_000_000}, id="number-too-big"),
    pytest.param({"number": "1"}, id="number-string"),
    pytest.param({"published": "yes"}, id="published-string"),
    pytest.param({"published": 1}, id="published-int"),
    pytest.param({"published_on": "01/10/2026"}, id="date-format"),
    pytest.param({"colour": "red"}, id="extra-key"),
]


@pytest.mark.parametrize("overrides", INVALID_OVERRIDES)
def test_ac5_an_invalid_value_or_key_names_the_file(
    tmp_path: Path, fx01_text: str, overrides: dict[str, object]
) -> None:
    write_catalogue_file(tmp_path, "bad.json", fx01_text, **overrides)

    with pytest.raises(CatalogueError, match=r"bad\.json") as error_info:
        load_catalogue(tmp_path)

    assert error_info.value.__cause__ is not None


@pytest.mark.parametrize(
    "missing_key", ["number", "published_on", "force", "published"]
)
def test_ac5_a_missing_key_names_the_file(
    tmp_path: Path, fx01_text: str, missing_key: str
) -> None:
    path = write_catalogue_file(tmp_path, "bad.json", fx01_text)
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload[missing_key]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CatalogueError, match=r"bad\.json"):
        load_catalogue(tmp_path)


def test_ac5_a_missing_grid_key_names_the_file(tmp_path: Path, fx01_text: str) -> None:
    path = write_catalogue_file(tmp_path, "bad.json", fx01_text)
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["grid"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CatalogueError, match=r"bad\.json"):
        load_catalogue(tmp_path)


def test_ac5_text_that_is_not_json_names_the_file(tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_text("this is not json", encoding="utf-8")

    with pytest.raises(CatalogueError, match=r"bad\.json") as error_info:
        load_catalogue(tmp_path)

    assert error_info.value.__cause__ is not None


def test_ac5_two_files_with_the_same_number_name_the_second_file(
    tmp_path: Path, fx01_text: str
) -> None:
    write_catalogue_file(tmp_path, "a.json", fx01_text, number=3)
    write_catalogue_file(tmp_path, "b.json", fx01_text, number=3)

    with pytest.raises(CatalogueError, match=r"b\.json"):
        load_catalogue(tmp_path)


def test_ac5_duplicate_numbers_are_rejected_by_the_model(
    catalogue: Catalogue,
) -> None:
    first = catalogue.entries[0]
    copy = first.model_copy()

    with pytest.raises(ValidationError, match="duplicate") as error_info:
        Catalogue(entries=(first, copy))

    assert "1" in str(error_info.value)


def test_ac5_duplicate_number_message_holds_the_number(fx01_grid: Grid) -> None:
    first = make_entry(fx01_grid, 424242, date(2026, 10, 1), 1, True)
    second = make_entry(fx01_grid, 424242, date(2026, 10, 2), 2, False)

    with pytest.raises(ValidationError, match=r"duplicate.*424242|424242.*duplicate"):
        Catalogue(entries=(first, second))
