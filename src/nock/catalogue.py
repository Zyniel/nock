"""The grid catalogue: the grids this server knows and what players may see of them."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    model_validator,
)

from nock.grid import ClueCell, Grid
from nock.grid_import import import_grid

GridNumber = Annotated[int, Field(ge=1, le=999_999_999, strict=True)]
Force = Annotated[int, Field(ge=1, le=4, strict=True)]

PUBLISHED_ON_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

GRIDS_DIR: Path = Path(__file__).resolve().parents[2] / "grids"


class CatalogueEntry(BaseModel):
    """One grid of the catalogue and its listing data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    number: GridNumber
    published_on: date
    force: Force
    published: StrictBool
    grid: Grid


class GridSummary(BaseModel):
    """What a player may see of a grid in the catalogue: never the clues."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    number: GridNumber
    published_on: date
    force: Force
    width: int = Field(gt=0, strict=True)
    height: int = Field(gt=0, strict=True)
    word_count: int = Field(ge=1, strict=True)


def _count_clues(grid: Grid) -> int:
    """Count the clues of `grid`: one word per clue."""
    clue_count = 0
    for cell in grid.cells:
        if isinstance(cell, ClueCell):
            clue_count += len(cell.clues)
    return clue_count


def _newest_first_key(entry: CatalogueEntry) -> tuple[date, int]:
    """Sort key putting the latest publication date first, then the highest number.

    Use it with `reverse=True`.
    """
    return (entry.published_on, entry.number)


def summarize(entry: CatalogueEntry) -> GridSummary:
    """Return the summary of `entry`.

    Args:
        entry: The catalogue entry to describe.

    Returns:
        Its number, date, force, dimensions and word count, without any clue.
    """
    return GridSummary(
        number=entry.number,
        published_on=entry.published_on,
        force=entry.force,
        width=entry.grid.width,
        height=entry.grid.height,
        word_count=_count_clues(entry.grid),
    )


class Catalogue(BaseModel):
    """Every grid this server knows, published or not."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: tuple[CatalogueEntry, ...] = ()

    @model_validator(mode="after")
    def check_numbers_are_unique(self) -> Catalogue:
        """Reject two entries with the same number."""
        seen_numbers: set[int] = set()
        for entry in self.entries:
            if entry.number in seen_numbers:
                raise ValueError(f"duplicate grid number {entry.number}")
            seen_numbers.add(entry.number)
        return self

    def published_summaries(self, force: int | None = None) -> list[GridSummary]:
        """Summaries of the published entries, newest first.

        Args:
            force: Keep only the entries of that force. None keeps them all.

        Returns:
            The summaries ordered by publication date then number, both
            descending. A force with no entry gives an empty list.
        """
        shown_entries: list[CatalogueEntry] = []
        for entry in self.entries:
            if not entry.published:
                continue
            if force is not None and entry.force != force:
                continue
            shown_entries.append(entry)
        shown_entries.sort(key=_newest_first_key, reverse=True)
        summaries: list[GridSummary] = []
        for entry in shown_entries:
            summaries.append(summarize(entry))
        return summaries

    def find_published(self, number: int) -> CatalogueEntry | None:
        """Return the published entry `number`, or None if unknown or unpublished."""
        for entry in self.entries:
            if entry.number == number and entry.published:
                return entry
        return None


class CatalogueError(ValueError):
    """A catalogue directory holds a file that cannot be loaded."""


def _check_published_on(value: object) -> None:
    """Accept only a text written YYYY-MM-DD (no number, boolean or null).

    Raises:
        ValueError: The value is not a text matching that pattern.
    """
    # The JSON value can be of any type, which is why it is typed `object`.
    if not isinstance(value, str) or PUBLISHED_ON_PATTERN.fullmatch(value) is None:
        raise ValueError("'published_on' must be a text written YYYY-MM-DD")


def _read_entry(path: Path) -> CatalogueEntry:
    """Read one catalogue file.

    Raises:
        OSError: The file cannot be read.
        ValueError: The text is not valid JSON, or the file is not valid
            (pydantic's ValidationError and GridImportError are ValueErrors).
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("the file must hold a JSON object")
    if "grid" not in payload:
        raise ValueError("the key 'grid' is missing")
    if "published_on" in payload:
        _check_published_on(payload["published_on"])
    report = import_grid(json.dumps(payload["grid"]))
    payload["grid"] = report.grid
    return CatalogueEntry.model_validate(payload)


def _catalogue_paths(directory: Path) -> list[Path]:
    """List the catalogue files of `directory`, sorted by name in code-point order."""
    names: list[str] = []
    for path in directory.iterdir():
        if path.name.startswith("."):
            continue
        if not path.name.endswith(".json"):
            continue
        names.append(path.name)
    names.sort()
    paths: list[Path] = []
    for name in names:
        paths.append(directory / name)
    return paths


def load_catalogue(directory: Path) -> Catalogue:
    """Load every `*.json` file directly inside `directory`, in file-name order.

    Files are read in code-point order of their names. A missing directory gives
    an empty catalogue. Sub-directories, dot files and names that do not end in
    lower-case ".json" are ignored.

    Args:
        directory: The directory holding one JSON file per grid.

    Returns:
        The catalogue of those files.

    Raises:
        CatalogueError: At the first file that is not valid, or when two files
            hold the same number. The message contains the file name.
    """
    if not directory.is_dir():
        return Catalogue()
    paths = _catalogue_paths(directory)
    entries: list[CatalogueEntry] = []
    numbers_seen: set[int] = set()
    for path in paths:
        if not path.is_file():
            continue
        try:
            entry = _read_entry(path)
        except (OSError, ValueError) as error:
            message = f"{path.name}: invalid catalogue file: {error}"
            raise CatalogueError(message) from error
        if entry.number in numbers_seen:
            raise CatalogueError(f"{path.name}: duplicate grid number {entry.number}")
        numbers_seen.add(entry.number)
        entries.append(entry)
    return Catalogue(entries=tuple(entries))
