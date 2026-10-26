"""The grid catalogue: the grids this server knows and what players may see of them.

A grid enters through the index `grids/catalogue.json` and the `.ipuz` file it
names (`specs/content/grid-files.md`).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    model_validator,
)

from nock.grid import ClueCell, Grid
from nock.ipuz import read_ipuz

GridNumber = Annotated[int, Field(ge=1, le=999_999_999, strict=True)]
Force = Annotated[int, Field(ge=1, le=4, strict=True)]

CreditText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]

INDEX_FILE_NAME = "catalogue.json"
GRID_FILE_SUFFIX = ".ipuz"

GRIDS_DIR: Path = Path(__file__).resolve().parents[2] / "grids"


def _check_file_name(name: str) -> str:
    """Accept a name directly inside `grids/` that ends in ".ipuz".

    Raises:
        ValueError: The name holds a slash or a backslash, or does not end in
            ".ipuz".
    """
    if "/" in name or "\\" in name:
        raise ValueError("'file' must be a name directly inside grids/")
    if not name.endswith(GRID_FILE_SUFFIX):
        raise ValueError(f"'file' must end in {GRID_FILE_SUFFIX!r}")
    return name


class IndexEntry(BaseModel):
    """One entry of the index: what Nock decides about a grid file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    number: GridNumber
    file: Annotated[str, Field(strict=True), AfterValidator(_check_file_name)]
    published: StrictBool
    source: CreditText
    licence: CreditText
    withdrawn: StrictBool = False


class CatalogueEntry(BaseModel):
    """One grid of the catalogue: the index entry joined to its grid file.

    The eight optional texts are recorded as the file writes them. They are never
    shown to players.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    number: GridNumber
    published_on: date
    force: Force
    published: StrictBool
    author: CreditText
    source: CreditText
    licence: CreditText
    withdrawn: StrictBool = False
    grid: Grid
    title: str | None = None
    editor: str | None = None
    publisher: str | None = None
    publication: str | None = None
    url: str | None = None
    uniqueid: str | None = None
    origin: str | None = None
    copyright: str | None = None


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
        """Summaries of the published, not withdrawn entries, newest first.

        Args:
            force: Keep only the entries of that force. None keeps them all.

        Returns:
            The summaries ordered by publication date then number, both
            descending. A force with no entry gives an empty list.
        """
        shown_entries: list[CatalogueEntry] = []
        for entry in self.entries:
            if not entry.published or entry.withdrawn:
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
        """Return entry `number` if published and not withdrawn, else None."""
        for entry in self.entries:
            if entry.withdrawn:
                continue
            if entry.number == number and entry.published:
                return entry
        return None


class CatalogueError(ValueError):
    """The index or a grid file cannot be loaded. The message names the file."""


def _read_index(directory: Path) -> list[IndexEntry]:
    """Read the index of `directory`.

    Raises:
        OSError: The index cannot be read.
        ValueError: The text is not valid JSON, an entry is not valid, or two
            entries name the same number or the same file.
    """
    text = (directory / INDEX_FILE_NAME).read_text(encoding="utf-8")
    payload = json.loads(text)
    if not isinstance(payload, list):
        raise ValueError("the index must be a JSON array of entries")
    index_entries: list[IndexEntry] = []
    numbers_seen: set[int] = set()
    files_seen: set[str] = set()
    for item in payload:
        index_entry = IndexEntry.model_validate(item)
        if index_entry.number in numbers_seen:
            raise ValueError(f"duplicate grid number {index_entry.number}")
        if index_entry.file in files_seen:
            raise ValueError(f"duplicate file {index_entry.file}")
        numbers_seen.add(index_entry.number)
        files_seen.add(index_entry.file)
        index_entries.append(index_entry)
    return index_entries


def _read_grid_file(directory: Path, index_entry: IndexEntry) -> CatalogueEntry:
    """Read the grid file an index entry names and join the two.

    Raises:
        OSError: The file is missing or cannot be read.
        ValueError: The file is not valid (`IpuzError` is a ValueError).
    """
    text = (directory / index_entry.file).read_text(encoding="utf-8")
    grid_file = read_ipuz(text)
    return CatalogueEntry(
        number=index_entry.number,
        published_on=grid_file.published_on,
        force=grid_file.force,
        published=index_entry.published,
        author=grid_file.author,
        source=index_entry.source,
        licence=index_entry.licence,
        withdrawn=index_entry.withdrawn,
        grid=grid_file.grid,
        title=grid_file.title,
        editor=grid_file.editor,
        publisher=grid_file.publisher,
        publication=grid_file.publication,
        url=grid_file.url,
        uniqueid=grid_file.uniqueid,
        origin=grid_file.origin,
        copyright=grid_file.copyright,
    )


def load_catalogue(directory: Path) -> Catalogue:
    """Load the grids that the index of `directory` names, in the index's order.

    A missing directory or a missing index gives an empty catalogue. A file the
    index does not name is ignored.

    Args:
        directory: The directory holding `catalogue.json` and the `.ipuz` files.

    Returns:
        The catalogue of those grids.

    Raises:
        CatalogueError: At the first problem. The message names
            `catalogue.json` for an index problem, else the grid file (a missing
            one included).
    """
    index_path = directory / INDEX_FILE_NAME
    if not index_path.is_file():
        return Catalogue()
    try:
        index_entries = _read_index(directory)
    except (OSError, ValueError) as error:
        message = f"{INDEX_FILE_NAME}: invalid index: {error}"
        raise CatalogueError(message) from error

    entries: list[CatalogueEntry] = []
    for index_entry in index_entries:
        try:
            entry = _read_grid_file(directory, index_entry)
        except (OSError, ValueError) as error:
            message = f"{index_entry.file}: invalid grid file: {error}"
            raise CatalogueError(message) from error
        entries.append(entry)
    return Catalogue(entries=tuple(entries))
