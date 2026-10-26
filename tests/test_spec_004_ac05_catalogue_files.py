"""Tests of spec 004, AC-5: the index, the grid files and `load_catalogue`.

These are the tests of grid-files AC-1 and AC-2. A catalogue directory holds the
index `catalogue.json` and one `.ipuz` file per grid; the shared setup is in
`spec004_harness` and `grid_files_harness`.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from grid_files_harness import (
    INDEX_NAME,
    clue_named,
    fx01_ipuz_data,
    index_entry,
    write_grid_file,
    write_index,
    write_one_grid,
)
from nock.catalogue import (
    GRIDS_DIR,
    INDEX_FILE_NAME,
    Catalogue,
    CatalogueError,
    IndexEntry,
    load_catalogue,
)
from nock.grid import Grid
from spec004_harness import (
    PROJECT_ROOT,
    grid_from_text,
    make_entry,
    make_reference_catalogue,
)

# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of the spec (also served by live_server)."""
    return make_reference_catalogue(fx01_grid)


def loaded_numbers(directory: Path) -> list[int]:
    numbers: list[int] = []
    for entry in load_catalogue(directory).entries:
        numbers.append(entry.number)
    return numbers


# ---- AC-5: the index and the grid files ----------------------------------------


def test_ac5_grids_dir_is_the_grids_directory_of_the_repository() -> None:
    assert GRIDS_DIR == PROJECT_ROOT / "grids"


def test_ac5_the_index_is_the_file_catalogue_json() -> None:
    assert INDEX_FILE_NAME == "catalogue.json"


def test_ac5_an_index_entry_is_a_frozen_model_of_the_keys_of_rule_2() -> None:
    entry = IndexEntry(
        number=1, file="a.ipuz", published=True, source="Source", licence="Licence"
    )

    assert entry.withdrawn is False
    field_name = "number"
    with pytest.raises(ValidationError):
        setattr(entry, field_name, 2)
    with pytest.raises(ValidationError):
        IndexEntry.model_validate(
            {
                "number": 1,
                "file": "a.ipuz",
                "published": True,
                "source": "Source",
                "licence": "Licence",
                "colour": "red",
            }
        )


def test_ac5_grids_load_in_the_order_of_the_index(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    write_grid_file(tmp_path, "b.ipuz")
    write_grid_file(tmp_path, "a.ipuz")
    write_index(tmp_path, [index_entry(2, "b.ipuz"), index_entry(1, "a.ipuz")])

    loaded = load_catalogue(tmp_path)

    assert loaded_numbers(tmp_path) == [2, 1]
    for entry in loaded.entries:
        assert entry.grid == fx01_grid


def test_ac5_what_the_index_does_not_name_is_ignored(tmp_path: Path) -> None:
    write_one_grid(tmp_path)
    (tmp_path / "x.ipuz").write_text("this is not json", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not a grid file", encoding="utf-8")
    old_directory = tmp_path / "old"
    old_directory.mkdir()
    write_grid_file(old_directory, "z.ipuz")

    assert loaded_numbers(tmp_path) == [1]


def test_ac5_file_fields_are_read(tmp_path: Path) -> None:
    data = fx01_ipuz_data()
    data["date"] = "02/03/2026"
    data["difficulty"] = 4
    write_one_grid(tmp_path, data, number=42, published=False)

    loaded = load_catalogue(tmp_path)

    assert len(loaded.entries) == 1
    entry = loaded.entries[0]
    assert entry.number == 42
    assert entry.published_on == date(2026, 2, 3)
    assert entry.force == 4
    assert entry.published is False


def test_ac5_missing_directory_is_an_empty_catalogue(tmp_path: Path) -> None:
    assert load_catalogue(tmp_path / "absent") == Catalogue()


def test_ac5_a_directory_without_index_is_an_empty_catalogue(tmp_path: Path) -> None:
    assert load_catalogue(tmp_path) == Catalogue()
    write_grid_file(tmp_path, "g1.ipuz")

    assert load_catalogue(tmp_path) == Catalogue()


def test_ac5_a_rejected_grid_names_its_file(tmp_path: Path) -> None:
    broken_data = fx01_ipuz_data()
    clue_named(broken_data, "Artiste muet")["answer"] = "MIMA"
    write_grid_file(tmp_path, "good.ipuz")
    write_grid_file(tmp_path, "bad.ipuz", broken_data)
    write_index(tmp_path, [index_entry(1, "good.ipuz"), index_entry(2, "bad.ipuz")])

    with pytest.raises(CatalogueError, match=r"bad\.ipuz"):
        load_catalogue(tmp_path)


def test_ac5_a_grid_file_that_is_not_json_names_its_file(tmp_path: Path) -> None:
    (tmp_path / "g1.ipuz").write_text("this is not json", encoding="utf-8")
    write_index(tmp_path, [index_entry()])

    with pytest.raises(CatalogueError, match=r"g1\.ipuz"):
        load_catalogue(tmp_path)


def test_ac5_an_entry_naming_a_missing_file_names_that_file(tmp_path: Path) -> None:
    write_index(tmp_path, [index_entry(1, "missing.ipuz")])

    with pytest.raises(CatalogueError, match=r"missing\.ipuz"):
        load_catalogue(tmp_path)


def test_ac5_catalogue_error_is_a_value_error() -> None:
    assert issubclass(CatalogueError, ValueError)


INVALID_OVERRIDES = [
    pytest.param({"number": 0}, id="number-0"),
    pytest.param({"number": 1_000_000_000}, id="number-too-big"),
    pytest.param({"number": "1"}, id="number-string"),
    pytest.param({"published": "yes"}, id="published-string"),
    pytest.param({"published": 1}, id="published-int"),
    pytest.param({"colour": "red"}, id="extra-key"),
    pytest.param({"file": "old/a.ipuz"}, id="file-in-a-directory"),
    pytest.param({"file": "old\\a.ipuz"}, id="file-with-a-backslash"),
    pytest.param({"file": "g1.json"}, id="file-not-ipuz"),
    pytest.param({"file": 5}, id="file-not-text"),
]


@pytest.mark.parametrize("overrides", INVALID_OVERRIDES)
def test_ac5_an_invalid_value_or_key_of_the_index_names_the_index(
    tmp_path: Path, overrides: dict[str, object]
) -> None:
    write_one_grid(tmp_path, **overrides)

    with pytest.raises(CatalogueError, match=r"catalogue\.json"):
        load_catalogue(tmp_path)


@pytest.mark.parametrize("missing_key", ["number", "file", "published"])
def test_ac5_a_missing_key_of_an_index_entry_names_the_index(
    tmp_path: Path, missing_key: str
) -> None:
    write_grid_file(tmp_path, "g1.ipuz")
    entry = index_entry()
    del entry[missing_key]
    write_index(tmp_path, [entry])

    with pytest.raises(CatalogueError, match=r"catalogue\.json"):
        load_catalogue(tmp_path)


@pytest.mark.parametrize(
    "index_text",
    [
        pytest.param("this is not json", id="not-json"),
        pytest.param('{"number": 1}', id="an-object"),
        pytest.param('["g1.ipuz"]', id="a-list-of-names"),
    ],
)
def test_ac5_an_index_that_is_not_a_list_of_entries_names_the_index(
    tmp_path: Path, index_text: str
) -> None:
    write_grid_file(tmp_path, "g1.ipuz")
    (tmp_path / INDEX_NAME).write_text(index_text, encoding="utf-8")

    with pytest.raises(CatalogueError, match=r"catalogue\.json"):
        load_catalogue(tmp_path)


@pytest.mark.parametrize(
    "entries",
    [
        pytest.param(
            [index_entry(3, "a.ipuz"), index_entry(3, "b.ipuz")], id="same-number"
        ),
        pytest.param(
            [index_entry(1, "a.ipuz"), index_entry(2, "a.ipuz")], id="same-file"
        ),
    ],
)
def test_ac5_two_entries_with_the_same_number_or_file_name_the_index(
    tmp_path: Path, entries: list[dict[str, object]]
) -> None:
    write_grid_file(tmp_path, "a.ipuz")
    write_grid_file(tmp_path, "b.ipuz")
    write_index(tmp_path, entries)

    with pytest.raises(CatalogueError, match=r"catalogue\.json"):
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
