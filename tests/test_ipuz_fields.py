"""Tests of content/ipuz AC-11: the force and the date of a file.

The force (`difficulty`) and the publication date (`date`) a file carries beside
its grid. The shared setup is in `grid_files_harness`.

Choices where the spec leaves room:

- AC-11: a missing `difficulty` or `date` is refused (rule 6: the three fields
  are required); only the refusal is expected, not the message.
"""

from __future__ import annotations

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
from spec004_harness import make_client, make_dist_dir

# ---- AC-11: the force and the date ----------------------------------------------


@pytest.mark.parametrize("difficulty", [3, "3"])
def test_ac11_a_difficulty_of_one_digit_loads_as_the_force(
    difficulty: int | str,
) -> None:
    data = fx01_ipuz_data()
    data["difficulty"] = difficulty

    assert read_data(data).force == 3


@pytest.mark.parametrize("difficulty", ["Force 3", 5, "03", 3.0])
def test_ac11_another_difficulty_is_refused(difficulty: object) -> None:
    data = fx01_ipuz_data()
    data["difficulty"] = difficulty

    read_error(data)


@pytest.mark.parametrize("key", ["difficulty", "date"])
def test_ac11_a_missing_difficulty_or_date_is_refused(key: str) -> None:
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
def test_ac11_a_date_written_month_day_year_loads_as_the_publication_date(
    written: str, published_on: date
) -> None:
    data = fx01_ipuz_data()
    data["date"] = written

    assert read_data(data).published_on == published_on


@pytest.mark.parametrize("written", ["2026-10-01", "1/1/2026", "02/30/2026"])
def test_ac11_another_date_is_refused(written: str) -> None:
    data = fx01_ipuz_data()
    data["date"] = written

    read_error(data)


def test_ac11_the_summary_keeps_the_date_written_year_month_day(
    tmp_path: Path,
) -> None:
    grids_dir = tmp_path / "grids"
    grids_dir.mkdir()
    write_one_grid(grids_dir)
    client = make_client(load_catalogue(grids_dir), make_dist_dir(tmp_path))

    response = client.get("/api/grids/1")

    assert response.status_code == 200
    assert response.json()["published_on"] == "2026-10-01"
