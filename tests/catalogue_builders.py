"""Catalogues that many test modules serve, all built on one grid (FX-01).

The `catalogue` fixture of `conftest.py` picks one of them for a test module that
sets `CATALOGUE_KIND` to one of the names of `CATALOGUE_BUILDERS`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path

from nock.catalogue import Catalogue, CatalogueEntry
from nock.grid import Grid

CREDITS_PATH = Path(__file__).parent / "fixtures" / "credits.json"


def make_entry(
    grid: Grid, number: int, published_on: date, force: int, published: bool
) -> CatalogueEntry:
    """Return a catalogue entry on `grid` with the credits of the fixtures."""
    credits = json.loads(CREDITS_PATH.read_text(encoding="utf-8"))
    return CatalogueEntry(
        number=number,
        published_on=published_on,
        force=force,
        published=published,
        **credits,
        grid=grid,
    )


def published_catalogue(grid: Grid) -> Catalogue:
    """Return a catalogue holding `grid` as published entry 1, force 2."""
    entry = make_entry(grid, 1, date(2026, 10, 1), 2, True)
    return Catalogue(entries=(entry,))


def published_force_1_catalogue(grid: Grid) -> Catalogue:
    """Return a catalogue holding `grid` as published entry 1, force 1."""
    entry = make_entry(grid, 1, date(2026, 10, 1), 1, True)
    return Catalogue(entries=(entry,))


def reference_catalogue(grid: Grid) -> Catalogue:
    """Return the reference catalogue CAT of spec 004, built on `grid`.

    Entries 1 to 3 are published (forces 1, 2 and 1); entry 4 is not.
    """
    entries = (
        make_entry(grid, 1, date(2026, 9, 1), 1, True),
        make_entry(grid, 2, date(2026, 10, 1), 2, True),
        make_entry(grid, 3, date(2026, 10, 1), 1, True),
        make_entry(grid, 4, date(2026, 10, 5), 3, False),
    )
    return Catalogue(entries=entries)


CATALOGUE_BUILDERS: dict[str, Callable[[Grid], Catalogue]] = {
    "published": published_catalogue,
    "published_force_1": published_force_1_catalogue,
    "reference": reference_catalogue,
}
