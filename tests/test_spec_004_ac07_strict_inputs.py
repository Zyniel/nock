"""Tests of spec 004, AC-7: inputs are read strictly.

Dates, the `force` parameter, file extensions and file order are read the same
way on every platform. The shared setup is in `spec004_harness`.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nock.catalogue import Catalogue, CatalogueError, load_catalogue
from nock.grid import Grid
from spec004_harness import (
    grid_from_text,
    json_numbers,
    make_client,
    make_dist_dir,
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


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def client(catalogue: Catalogue, dist_dir: Path) -> TestClient:
    return make_client(catalogue, dist_dir)


# ---- AC-7: strict inputs -----------------------------------------------------


def loaded_numbers(directory: Path) -> list[int]:
    numbers: list[int] = []
    for entry in load_catalogue(directory).entries:
        numbers.append(entry.number)
    return numbers


@pytest.mark.parametrize(
    "bad_date",
    [
        pytest.param("2026-10-01T00:00:00", id="datetime"),
        pytest.param("2026-1-1", id="no-zero-padding"),
        pytest.param("01/10/2026", id="slashes"),
        pytest.param("20261001", id="compact-form"),
        pytest.param(0, id="int-zero"),
        pytest.param(1790035200, id="int-timestamp"),
        pytest.param(1790035200.0, id="float-timestamp"),
        pytest.param(True, id="boolean"),
        pytest.param(None, id="null"),
    ],
)
def test_ac7_published_on_must_be_exactly_year_month_day(
    tmp_path: Path, fx01_text: str, bad_date: object
) -> None:
    write_catalogue_file(tmp_path, "bad.json", fx01_text, published_on=bad_date)

    with pytest.raises(CatalogueError, match=r"bad\.json"):
        load_catalogue(tmp_path)


def test_ac7_published_on_in_the_exact_form_is_read(
    tmp_path: Path, fx01_text: str
) -> None:
    write_catalogue_file(tmp_path, "ok.json", fx01_text, published_on="2026-01-09")

    loaded = load_catalogue(tmp_path)

    assert loaded.entries[0].published_on == date(2026, 1, 9)


@pytest.mark.parametrize(
    "force", ["2.0", "01", "%201", "%2B1", "1%20", "0", "5", "x", ""]
)
def test_ac7_http_force_must_be_exactly_one_digit_1_to_4(
    client: TestClient, force: str
) -> None:
    response = client.get(f"/api/grids?force={force}")

    assert response.status_code == 422
    assert "detail" in response.json()


def test_ac7_http_force_1_is_accepted(client: TestClient) -> None:
    response = client.get("/api/grids?force=1")

    assert response.status_code == 200
    assert json_numbers(response.json()) == [3, 1]


def test_ac7_upper_case_extension_is_ignored(tmp_path: Path, fx01_text: str) -> None:
    write_catalogue_file(tmp_path, "A.JSON", fx01_text, number=7)
    write_catalogue_file(tmp_path, "b.json", fx01_text, number=2)

    assert loaded_numbers(tmp_path) == [2]


def test_ac7_dot_files_are_ignored(tmp_path: Path, fx01_text: str) -> None:
    write_catalogue_file(tmp_path, ".x.json", fx01_text, number=7)
    write_catalogue_file(tmp_path, "b.json", fx01_text, number=2)

    assert loaded_numbers(tmp_path) == [2]


def test_ac7_only_ignored_files_give_an_empty_catalogue(
    tmp_path: Path, fx01_text: str
) -> None:
    write_catalogue_file(tmp_path, "A.JSON", fx01_text, number=7)
    write_catalogue_file(tmp_path, ".x.json", fx01_text, number=8)

    assert load_catalogue(tmp_path) == Catalogue()


def test_ac7_ignored_files_are_not_parsed(tmp_path: Path) -> None:
    (tmp_path / "A.JSON").write_text("not json", encoding="utf-8")
    (tmp_path / ".x.json").write_text("not json", encoding="utf-8")

    assert load_catalogue(tmp_path) == Catalogue()


def test_ac7_files_load_in_code_point_order_of_their_names(
    tmp_path: Path, fx01_text: str
) -> None:
    write_catalogue_file(tmp_path, "a.json", fx01_text, number=1)
    write_catalogue_file(tmp_path, "B.json", fx01_text, number=2)

    assert loaded_numbers(tmp_path) == [2, 1]
