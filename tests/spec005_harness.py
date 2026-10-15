"""Shared setup of the tests of spec 005: licensed content only.

This module is not a test file: pytest does not collect it. The tests of spec 005
are in `tests/test_spec_005_*.py`, one file per criterion group:

- AC-1 to AC-3: the credits of a catalogue entry and the `withdrawn` flag;
- AC-4 and AC-5: no outgoing connection from `src/`, no third-party URL in `web/`;
- AC-6 and AC-7: no new room on a withdrawn grid, open rooms can finish.

This module holds what more than one of those files uses. What only one file uses
stays in that file, next to its tests. The fixture `fx01_grid` is defined in each
file that needs it as a thin wrapper around `grid_from_text`: a fixture imported
from here would be an unused import for ruff.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from nock.catalogue import CatalogueEntry
from nock.grid import Grid


def credits() -> dict[str, str]:
    """Return the credit fields of a catalogue entry (tests/fixtures/credits.json)."""
    credits_path = Path(__file__).parent / "fixtures" / "credits.json"
    return json.loads(credits_path.read_text(encoding="utf-8"))


def grid_from_text(fx01_text: str) -> Grid:
    """Return the FX-01 grid parsed from its JSON text."""
    return Grid.model_validate_json(fx01_text)


def make_entry(
    grid: Grid, number: int, published: bool = True, withdrawn: bool = False
) -> CatalogueEntry:
    return CatalogueEntry(
        number=number,
        published_on=date(2026, 10, 1),
        force=2,
        published=published,
        **credits(),
        withdrawn=withdrawn,
        grid=grid,
    )
