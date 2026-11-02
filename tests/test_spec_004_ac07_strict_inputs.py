"""Tests of spec 004, AC-7: inputs are read strictly.

Dates (the `date` of a grid file) and the `force` parameter of the list route are
read the same way on every platform. The date tests belong to content/ipuz AC-11
and the force tests to library rule 4. The shared setup is in `spec004_harness` and
`grid_files_harness`.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from grid_files_harness import fx01_ipuz_data, write_one_grid
from nock.catalogue import Catalogue, CatalogueError, load_catalogue
from nock.grid import Grid
from spec004_harness import (
    grid_from_text,
    json_numbers,
    make_client,
    make_dist_dir,
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


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def client(catalogue: Catalogue, dist_dir: Path) -> TestClient:
    return make_client(catalogue, dist_dir)


# ---- AC-7: strict inputs -----------------------------------------------------


@pytest.mark.parametrize(
    "bad_date",
    [
        pytest.param("2026-10-01", id="year-month-day"),
        pytest.param("2026-10-01T00:00:00", id="datetime"),
        pytest.param("1/1/2026", id="no-zero-padding"),
        pytest.param("10/01/26", id="two-digit-year"),
        pytest.param("10-01-2026", id="dashes"),
        pytest.param("02/30/2026", id="no-such-day"),
        pytest.param("13/01/2026", id="no-such-month"),
        pytest.param(20261001, id="int"),
        pytest.param(1790035200.0, id="float-timestamp"),
        pytest.param(True, id="boolean"),
        pytest.param(None, id="null"),
    ],
)
def test_ac7_the_date_of_a_file_must_be_exactly_month_day_year(
    tmp_path: Path, bad_date: object
) -> None:
    data = fx01_ipuz_data()
    data["date"] = bad_date
    write_one_grid(tmp_path, data)

    with pytest.raises(CatalogueError, match=r"g1\.ipuz"):
        load_catalogue(tmp_path)


def test_ac7_a_date_in_the_exact_form_is_read(tmp_path: Path) -> None:
    data = fx01_ipuz_data()
    data["date"] = "01/09/2026"
    write_one_grid(tmp_path, data)

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
