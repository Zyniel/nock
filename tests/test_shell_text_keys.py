"""Tests of `client/shell.md` AC-29: the list separator and the units the client adds
are `fr.json` keys (rule 2).

AC-29: `fr.json` holds `list.separator` « , » then a space, `unit.hours` « h » and
`unit.minutes` « min »; the shared recap's team reads « Ana, Bob, Cy » and the settings
card's out-of-bounds line for a room life « Valeur hors limites (24 à 8760 h). », and
no client module joins shown names with a literal separator or adds a literal unit a
user reads after a shown number.

Three kinds of proof:

- `fr.json` itself, read as a file.
- The two screens the criterion names. To prove they read the keys, and not the same
  text written in the code, a second run serves the page's scripts with the key's value
  reworded (`shell_harness.ReworkedValues`): the team then reads « Ana / Bob / Cy » and
  the line « (24 à 8760 heures) ». The test first checks that the built scripts hold the
  entry, so that a missing key fails on that and not on a text.
- A scan of the client's sources, narrow to what the criterion says: a `.join(` whose
  literal separator holds a comma (shown names), and a literal `h` or `min` written as
  a string, or after a `{...}` expression, that a user reads after a shown number.
  The templates of `fr.json` (`duration.*`, `ops.hours_value`) and CSS lengths are not
  in `.ts` and `.svelte` code, so they are not scanned. The scan of the names' joins
  leaves out the two modules that join CSS (`NOT_SHOWN_NAMES`), and its own tests
  (`test_ac29_the_scan_*`) show what it flags.

The unit the scan can miss, a unit built from pieces, is covered by the reworded run on
the settings card, the one place the client adds a unit outside a template.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, expect

from lifetime_harness import CREATOR
from nock.catalogue import Catalogue
from nock.recap import PublicRecap
from overrides_harness import (
    INTERVAL,
    SETTING_BY_NAME,
    open_card,
    row_of,
    settings_server,
    type_and_save,
)
from shell_harness import Rewording, ReworkedValues
from spec041_harness import (
    WEB_SRC_DIR,
    remove_script_comments,
    source_files,
    split_svelte,
)
from spec043_harness import fr_format, fr_value
from spec046_harness import OpenWindow, window_opener
from spec048_harness import open_share

TEAM = PublicRecap(grid_number=12, elapsed_ms=754000, team=("ANA", "BOB", "CY"))
NEW_SEPARATOR = " / "
NEW_HOURS = "heures"
NEW_MINUTES = "mn"

# Modules whose `.join(", ")` builds CSS, not a list of names a user reads.
NOT_SHOWN_NAMES = {
    "gridLayout.ts": "the stops of a CSS gradient",
    "scrollingLists.ts": "a CSS selector list",
}
SEPARATOR_JOIN = re.compile(r"""\.join\(\s*(["'`])[^"'`]*,[^"'`]*\1\s*\)""")
# A string that is only a unit (`'h'`, `' min'`), or a unit right after a `{...}`
# expression, as in `{hours} h` or `${minutes} min`.
LITERAL_UNIT = re.compile(r"""(["'`])\s?(?:h|min)\1|\}\s?(?:h|min)(?![\w-])""")


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


# ---- The sources the criterion is about ---------------------------------------------


def client_code(path: Path) -> str:
    """The script and markup of a `.ts` or `.svelte` file, comments removed."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".ts":
        return remove_script_comments(text)
    parts = split_svelte(text)
    return "\n".join([*parts.scripts, parts.markup])


def separator_joins(code: str) -> list[str]:
    """The joins of `code` that use a literal separator holding a comma."""
    found: list[str] = []
    for match in SEPARATOR_JOIN.finditer(code):
        found.append(match.group(0))
    return found


def literal_units(code: str) -> list[str]:
    """The literal `h` or `min` units of `code`."""
    found: list[str] = []
    for match in LITERAL_UNIT.finditer(code):
        found.append(match.group(0))
    return found


# ---- fr.json  ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "value"),
    [("list.separator", ", "), ("unit.hours", "h"), ("unit.minutes", "min")],
)
def test_ac29_fr_json_holds_the_separator_and_the_units(key: str, value: str) -> None:
    assert fr_value(key) == value


# ---- The two screens the criterion names ---------------------------------------------


def test_ac29_the_shared_recap_team_reads_ana_bob_cy(
    window: OpenWindow, live_server: str
) -> None:
    page = window(1280, 720)

    open_share(page, live_server, TEAM)

    expect(page.get_by_test_id("share-team")).to_have_text("Équipe : Ana, Bob, Cy")


def test_ac29_the_shared_recap_joins_the_team_with_the_separator_key(
    window: OpenWindow, live_server: str
) -> None:
    page = window(1280, 720)
    rework = ReworkedValues(page, [Rewording("list.separator", ", ", NEW_SEPARATOR)])

    open_share(page, live_server, TEAM)

    assert rework.counts == {"list.separator": 1}
    expected = fr_format("share.team", names=NEW_SEPARATOR.join(["Ana", "Bob", "Cy"]))
    expect(page.get_by_test_id("share-team")).to_have_text(expected)


def test_ac29_the_bounds_line_of_a_room_life_reads_24_to_8760_h(
    window: OpenWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
) -> None:
    with settings_server(monkeypatch, tmp_path, catalogue) as server:
        page = window(1280, 720)
        open_card(page, server.base_url)

        type_and_save(page, CREATOR.field, "23")

        alert = row_of(page, CREATOR.field).get_by_role("alert")
        expect(alert).to_have_text("Valeur hors limites (24 à 8760 h).")


@pytest.mark.parametrize(
    ("name", "typed", "key", "new_unit"),
    [
        pytest.param(CREATOR.field, "23", "unit.hours", NEW_HOURS, id="hours"),
        pytest.param(INTERVAL, "0", "unit.minutes", NEW_MINUTES, id="minutes"),
    ],
)
def test_ac29_the_bounds_line_reads_its_unit_from_the_unit_keys(
    window: OpenWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
    name: str,
    typed: str,
    key: str,
    new_unit: str,
) -> None:
    old_unit = fr_value(key)
    with settings_server(monkeypatch, tmp_path, catalogue) as server:
        page = window(1280, 720)
        rework = ReworkedValues(page, [Rewording(key, old_unit, new_unit)])
        open_card(page, server.base_url)

        type_and_save(page, name, typed)

        alert = row_of(page, name).get_by_role("alert")
        setting = SETTING_BY_NAME[name]
        expected = fr_format(
            "ops.setting_out_of_bounds",
            min=setting.minimum,
            max=setting.maximum,
            unit=new_unit,
        )
        expect(alert).to_have_text(expected)
        assert rework.counts == {key: 1}


# ---- The client's sources  -----------------------------------------------------------


def test_ac29_no_module_joins_shown_names_with_a_literal_separator() -> None:
    offenders: list[str] = []
    for path in source_files(".ts", ".svelte"):
        if path.name in NOT_SHOWN_NAMES:
            continue
        for join in separator_joins(client_code(path)):
            offenders.append(f"{path.relative_to(WEB_SRC_DIR)}: {join}")

    assert offenders == []


def test_ac29_no_module_adds_a_literal_unit_after_a_shown_number() -> None:
    offenders: list[str] = []
    for path in source_files(".ts", ".svelte"):
        for unit in literal_units(client_code(path)):
            offenders.append(f"{path.relative_to(WEB_SRC_DIR)}: {unit}")

    assert offenders == []


@pytest.mark.parametrize(
    "code",
    [
        "names.join(', ')",
        'players.map(displayNickname).join(", ")',
        "names.join(`, `)",
        "names.join(' / ,')",
    ],
)
def test_ac29_the_scan_flags_a_join_with_a_literal_comma(code: str) -> None:
    assert separator_joins(code) == [code[code.index(".join") :]]


@pytest.mark.parametrize(
    "code",
    [
        "names.join(t('list.separator'))",
        "names.join(' ')",
        "ids.join('-')",
        "// names.join(', ')",
    ],
)
def test_ac29_the_scan_passes_other_joins(code: str) -> None:
    assert separator_joins(client_code_of(code)) == []


@pytest.mark.parametrize(
    ("code", "flagged"),
    [
        ("const SHORT = { hours: 'h', minutes: 'min' }", ["'h'", "'min'"]),
        ("return `${hours} h`", ["} h"]),
        ("<p>{limit} min</p>", ["} min"]),
        ("const unit = ' min'", ["' min'"]),
    ],
)
def test_ac29_the_scan_flags_a_literal_unit(code: str, flagged: list[str]) -> None:
    assert literal_units(code) == flagged


@pytest.mark.parametrize(
    "code",
    [
        "const key = setting.unit === 'hours' ? 'ops.hours_value' : 'x'",
        "<p>{t('duration.minutes', { minutes })}</p>",
        "<p>{count} heures</p>",
        "const query = '(min-width: 600px)'",
        "return `${width}px`",
    ],
)
def test_ac29_the_scan_passes_other_code(code: str) -> None:
    assert literal_units(code) == []


def client_code_of(text: str) -> str:
    """A snippet as the scan reads a `.ts` file: comments removed."""
    return remove_script_comments(text)
