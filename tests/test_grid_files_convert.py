"""Tests of grid-files AC-20: the converter of the former grid files.

`convert(source, target)` turns a directory of `<name>.json` files (the former
format: listing data, credits and a grid in the model's JSON) into `.ipuz` files
and an index. `main` and `python -m nock.ipuz_convert` run it from the command
line. The shared setup is in `grid_files_harness`.

Choices where the spec leaves room:

- The target directory exists before the converter runs.
- A name that does not end in lower-case `.json` (`d.JSON`) and a dot file are
  taken as ignored by the converter, as rule 15 says.
- `main` reports a refusal either as the argument of `SystemExit` or on its
  standard output or error; the tests look at all of them.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from grid_files_harness import JsonData
from nock.catalogue import CatalogueEntry, load_catalogue
from nock.grid import Grid
from nock.ipuz_convert import convert, main
from spec004_harness import credits

# ---- Fixtures and helpers -------------------------------------------------------


def former_payload(fx01_text: str, number: int = 1, **overrides: object) -> JsonData:
    """Return the content of a former grid file: FX-01, force 2, 2026-10-01."""
    payload: JsonData = {
        "number": number,
        "published_on": "2026-10-01",
        "force": 2,
        "published": True,
        **credits(),
        "grid": json.loads(fx01_text),
    }
    payload.update(overrides)
    return payload


def write_former(source: Path, name: str, payload: JsonData) -> None:
    """Write a former grid file `name` into `source`."""
    (source / name).write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def source(tmp_path: Path) -> Path:
    directory = tmp_path / "source"
    directory.mkdir()
    return directory


@pytest.fixture
def target(tmp_path: Path) -> Path:
    directory = tmp_path / "target"
    directory.mkdir()
    return directory


def file_names(directory: Path) -> list[str]:
    names = []
    for path in directory.iterdir():
        names.append(path.name)
    return sorted(names)


def contents(directory: Path) -> dict[str, bytes]:
    """Return the bytes of each file of a directory, by name."""
    files: dict[str, bytes] = {}
    for path in directory.iterdir():
        files[path.name] = path.read_bytes()
    return files


def assert_entry(entry: CatalogueEntry, number: int, grid: Grid) -> None:
    """Check the fields of an entry that every converted FX-01 file shares."""
    assert entry.number == number
    assert entry.grid == grid
    assert entry.author == credits()["author"]
    assert entry.source == credits()["source"]
    assert entry.licence == credits()["licence"]


# ---- AC-20: the converter ---------------------------------------------------------


def test_ac20_a_former_file_becomes_an_ipuz_file_and_an_index(
    source: Path, target: Path, fx01_text: str
) -> None:
    write_former(source, "g1.json", former_payload(fx01_text))

    convert(source, target)

    assert file_names(target) == ["catalogue.json", "g1.ipuz"]
    entries = load_catalogue(target).entries
    assert len(entries) == 1
    entry = entries[0]
    assert_entry(entry, 1, Grid.model_validate_json(fx01_text))
    assert entry.force == 2
    assert entry.published_on == date(2026, 10, 1)
    assert entry.published is True
    assert entry.withdrawn is False


def test_ac20_files_are_converted_in_name_order_with_their_flags(
    source: Path, target: Path, fx01_text: str
) -> None:
    write_former(
        source,
        "b.json",
        former_payload(
            fx01_text,
            number=5,
            published_on="2026-01-02",
            force=4,
            published=False,
            withdrawn=True,
        ),
    )
    write_former(source, "a.json", former_payload(fx01_text, number=9))
    (source / "d.JSON").write_text("not json", encoding="utf-8")
    (source / ".hidden.json").write_text("not json", encoding="utf-8")
    (source / "notes.txt").write_text("not json", encoding="utf-8")

    convert(source, target)

    assert file_names(target) == ["a.ipuz", "b.ipuz", "catalogue.json"]
    first, second = load_catalogue(target).entries
    grid = Grid.model_validate_json(fx01_text)
    assert_entry(first, 9, grid)
    assert_entry(second, 5, grid)
    assert second.published_on == date(2026, 1, 2)
    assert second.force == 4
    assert second.published is False
    assert second.withdrawn is True


def test_ac20_a_second_run_writes_nothing_and_names_the_index(
    source: Path, target: Path, fx01_text: str
) -> None:
    write_former(source, "g1.json", former_payload(fx01_text))
    convert(source, target)
    before = contents(target)

    with pytest.raises(ValueError, match=r"catalogue\.json"):
        convert(source, target)

    assert contents(target) == before


def test_ac20_an_ipuz_file_that_exists_is_named_and_nothing_is_written(
    source: Path, target: Path, fx01_text: str
) -> None:
    write_former(source, "g1.json", former_payload(fx01_text))
    (target / "g1.ipuz").write_text("keep me", encoding="utf-8")

    with pytest.raises(ValueError, match=r"g1\.ipuz"):
        convert(source, target)

    assert contents(target) == {"g1.ipuz": b"keep me"}


def test_ac20_the_index_is_checked_before_the_ipuz_files(
    source: Path, target: Path, fx01_text: str
) -> None:
    write_former(source, "g1.json", former_payload(fx01_text))
    (target / "g1.ipuz").write_text("keep me", encoding="utf-8")
    (target / "catalogue.json").write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match=r"catalogue\.json") as error_info:
        convert(source, target)

    message = str(error_info.value)
    assert "catalogue.json" in message
    assert "g1.ipuz" not in message


def test_ac20_a_refused_source_file_is_named_and_nothing_is_written(
    source: Path, target: Path, fx01_text: str
) -> None:
    write_former(source, "g1.json", former_payload(fx01_text))
    write_former(
        source, "g2.json", former_payload(fx01_text.replace('"MIME"', '"MIMA"'), 2)
    )

    with pytest.raises(ValueError, match=r"g2\.json"):
        convert(source, target)

    assert file_names(target) == []


def test_ac20_main_converts_the_directories_of_its_arguments(
    source: Path, target: Path, fx01_text: str
) -> None:
    write_former(source, "g1.json", former_payload(fx01_text))

    main([str(source), str(target)])

    assert file_names(target) == ["catalogue.json", "g1.ipuz"]


def test_ac20_main_exits_with_a_non_zero_code_naming_the_file(
    source: Path,
    target: Path,
    fx01_text: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_former(source, "g1.json", former_payload(fx01_text))
    main([str(source), str(target)])
    capsys.readouterr()

    with pytest.raises(SystemExit) as exit_info:
        main([str(source), str(target)])

    captured = capsys.readouterr()
    reported = f"{exit_info.value.code} {captured.out} {captured.err}"
    assert exit_info.value.code not in (0, None)
    assert "catalogue.json" in reported


def test_ac20_the_module_runs_as_a_command(
    tmp_path: Path, source: Path, target: Path, fx01_text: str
) -> None:
    write_former(source, "g1.json", former_payload(fx01_text))
    command = [sys.executable, "-m", "nock.ipuz_convert", str(source), str(target)]

    first = subprocess.run(
        command, capture_output=True, text=True, cwd=tmp_path, check=False
    )
    second = subprocess.run(
        command, capture_output=True, text=True, cwd=tmp_path, check=False
    )

    assert first.returncode == 0, first.stderr
    assert file_names(target) == ["catalogue.json", "g1.ipuz"]
    assert second.returncode != 0
    assert "catalogue.json" in second.stdout + second.stderr
