"""Tests of grid-files AC-23 and AC-24: safe file names, a former grids folder.

AC-23: the `file` of an index entry has no `:`, and two entries naming files
whose names are equal once case-folded name the same file. AC-24: a `grids/`
folder with former `.json` files and no index starts as an empty catalogue and
logs one warning naming the converter command. The shared setup is in
`grid_files_harness`.

Choice where the spec leaves room: the warning is a record of level WARNING of
a logger under `nock`; the tests read it through `caplog`.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from grid_files_harness import (
    index_entry,
    write_grid_file,
    write_index,
    write_one_grid,
)
from nock.catalogue import CatalogueError, load_catalogue

CONVERTER_COMMAND = "uv run python -m nock.ipuz_convert"

# ---- Helpers ----------------------------------------------------------------------


def warnings_of_nock(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return the messages of the warnings logged so far by the `nock` loggers."""
    messages: list[str] = []
    for record in caplog.records:
        is_nock = record.name == "nock" or record.name.startswith("nock.")
        if is_nock and record.levelno >= logging.WARNING:
            messages.append(record.getMessage())
    return messages


# ---- AC-23: safe file names -------------------------------------------------------


def test_ac23_a_file_name_with_a_colon_is_refused_naming_the_index(
    tmp_path: Path,
) -> None:
    write_grid_file(tmp_path, "a:b.ipuz")
    write_index(tmp_path, [index_entry(1, "a:b.ipuz")])

    with pytest.raises(CatalogueError, match=r"catalogue\.json"):
        load_catalogue(tmp_path)


def test_ac23_two_entries_naming_files_equal_once_case_folded_are_refused(
    tmp_path: Path,
) -> None:
    write_grid_file(tmp_path, "A.ipuz")
    write_grid_file(tmp_path, "a.ipuz")
    write_index(tmp_path, [index_entry(1, "A.ipuz"), index_entry(2, "a.ipuz")])

    with pytest.raises(CatalogueError, match=r"catalogue\.json"):
        load_catalogue(tmp_path)


# ---- AC-24: a former grids folder -------------------------------------------------


def test_ac24_former_files_and_no_index_log_one_warning_naming_the_command(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "g1.json").write_text("{}", encoding="utf-8")
    caplog.set_level(logging.DEBUG)

    catalogue = load_catalogue(tmp_path)

    assert catalogue.entries == ()
    messages = warnings_of_nock(caplog)
    assert len(messages) == 1
    assert CONVERTER_COMMAND in messages[0]
    assert list(tmp_path.iterdir()) == [tmp_path / "g1.json"]


def test_ac24_only_a_notes_file_logs_no_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "notes.txt").write_text("not a grid", encoding="utf-8")
    caplog.set_level(logging.DEBUG)

    catalogue = load_catalogue(tmp_path)

    assert catalogue.entries == ()
    assert warnings_of_nock(caplog) == []


def test_ac24_a_former_file_next_to_a_valid_index_logs_no_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    write_one_grid(tmp_path)
    (tmp_path / "g1.json").write_text("{}", encoding="utf-8")
    caplog.set_level(logging.DEBUG)

    catalogue = load_catalogue(tmp_path)

    assert [entry.number for entry in catalogue.entries] == [1]
    assert warnings_of_nock(caplog) == []
