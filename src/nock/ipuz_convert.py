"""Convert a directory of the former grid files to `.ipuz` files and an index.

Run it with `uv run python -m nock.ipuz_convert SOURCE TARGET`. It is the only
code that reads the former format (`specs/content/grid-files.md`, rule 15).
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, StrictBool, field_validator

from nock.catalogue import (
    GRID_FILE_SUFFIX,
    INDEX_FILE_NAME,
    CreditText,
    Force,
    GridNumber,
    IndexEntry,
)
from nock.grid import Grid
from nock.grid_import import import_grid
from nock.ipuz import GridFile, write_ipuz

FORMER_SUFFIX = ".json"
PUBLISHED_ON_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


class _FormerFile(BaseModel):
    """The content of a file of the former format."""

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

    @field_validator("published_on", mode="before")
    @classmethod
    def check_published_on_is_written_year_month_day(cls, value: object) -> object:
        """Accept only a text written YYYY-MM-DD (no number, boolean or null)."""
        if not isinstance(value, str) or PUBLISHED_ON_PATTERN.fullmatch(value) is None:
            raise ValueError("'published_on' must be a text written YYYY-MM-DD")
        return value


class _Conversion(NamedTuple):
    """One converted file: the name of its `.ipuz` file, its text and its entry."""

    file_name: str
    ipuz_text: str
    index_entry: IndexEntry


def _former_file_names(source: Path) -> list[str]:
    """List the names of the former files of `source`, in code-point order."""
    names: list[str] = []
    for path in source.iterdir():
        if path.name.startswith("."):
            continue
        if not path.name.endswith(FORMER_SUFFIX):
            continue
        if not path.is_file():
            continue
        names.append(path.name)
    names.sort()
    return names


def _read_former_file(path: Path) -> _FormerFile:
    """Read a file of the former format.

    Raises:
        OSError: The file cannot be read.
        ValueError: The text is not valid JSON, or the file is not valid.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("the file must hold a JSON object")
    if "grid" not in payload:
        raise ValueError("the key 'grid' is missing")
    report = import_grid(json.dumps(payload["grid"]))
    payload["grid"] = report.grid
    return _FormerFile.model_validate(payload)


def _convert_file(path: Path) -> _Conversion:
    """Convert one former file to the text of its `.ipuz` file and its index entry."""
    former = _read_former_file(path)
    grid_file = GridFile(
        grid=former.grid,
        published_on=former.published_on,
        force=former.force,
        author=former.author,
    )
    file_name = path.name.removesuffix(FORMER_SUFFIX) + GRID_FILE_SUFFIX
    index_entry = IndexEntry(
        number=former.number,
        file=file_name,
        published=former.published,
        source=former.source,
        licence=former.licence,
        withdrawn=former.withdrawn,
    )
    return _Conversion(file_name, write_ipuz(grid_file), index_entry)


def _convert_all(source: Path) -> list[_Conversion]:
    """Convert every former file of `source`, refusing at the first bad one."""
    conversions: list[_Conversion] = []
    for name in _former_file_names(source):
        try:
            conversions.append(_convert_file(source / name))
        except (OSError, ValueError) as error:
            raise ValueError(f"{name}: invalid former grid file: {error}") from error
    return conversions


def _check_nothing_is_overwritten(target: Path, conversions: list[_Conversion]) -> None:
    """Refuse to write over the index or a `.ipuz` file; the index comes first."""
    if (target / INDEX_FILE_NAME).exists():
        raise ValueError(f"{INDEX_FILE_NAME} already exists in {target}")
    for conversion in conversions:
        if (target / conversion.file_name).exists():
            raise ValueError(f"{conversion.file_name} already exists in {target}")


def _write_text(path: Path, text: str) -> None:
    """Write a UTF-8 text file with LF line endings."""
    path.write_bytes(text.encode("utf-8"))


def convert(source: Path, target: Path) -> None:
    """Convert the former grid files of `source` into `target`.

    Each `<name>.json` of `source` (lower-case, not starting with `.`) becomes
    `<name>.ipuz`, and `catalogue.json` lists them in the order of the names.

    Args:
        source: The directory of former grid files.
        target: The directory to write into.

    Raises:
        ValueError: `target` exists and is not a directory, a source file is
            refused, or `catalogue.json` or one of the
            `.ipuz` files to write exists in `target`. The message names the
            file, and nothing is written.
    """
    if not source.is_dir():
        raise ValueError(f"{source} is not a directory")
    if target.exists() and not target.is_dir():
        raise ValueError(f"{target} exists and is not a directory")
    conversions = _convert_all(source)
    _check_nothing_is_overwritten(target, conversions)

    target.mkdir(parents=True, exist_ok=True)
    index: list[dict[str, object]] = []
    for conversion in conversions:
        _write_text(target / conversion.file_name, conversion.ipuz_text)
        index.append(conversion.index_entry.model_dump(mode="json"))
    index_text = json.dumps(index, ensure_ascii=False, indent=2) + "\n"
    _write_text(target / INDEX_FILE_NAME, index_text)


def main(argv: list[str] | None = None) -> None:
    """Run the converter from the command line.

    Args:
        argv: The arguments (SOURCE and TARGET). None reads `sys.argv`.

    Raises:
        SystemExit: With a non-zero code and the message when the conversion is
            refused.
    """
    parser = argparse.ArgumentParser(
        prog="python -m nock.ipuz_convert",
        description="Convert former grid files (.json) to .ipuz files and an index.",
    )
    parser.add_argument("source", type=Path, help="directory of former grid files")
    parser.add_argument("target", type=Path, help="directory to write into")
    arguments = parser.parse_args(argv)
    try:
        convert(arguments.source, arguments.target)
    except ValueError as error:
        raise SystemExit(f"error: {error}") from error


if __name__ == "__main__":
    main()
