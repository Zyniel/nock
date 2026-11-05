"""Tests of `client/shell.md` AC-31: the code that only one page uses is fetched only
on that page's route (rule 20).

AC-31: `/` fetches none of the code that only the room page or the operator page uses,
and `/r/ABC123` none of the code that only the catalogue or the operator page uses.

Browser tests on the live server serving the reference catalogue. What a page fetches
is every script request it makes from `page.goto` on (`shell_harness.FetchedScripts`),
read back from the built files of `web/dist/assets`.

Readings where the spec leaves room:

- "The code that only one page uses" is identified by marker strings that only that
  page's components write, and that the built scripts keep: the test ids the other
  tests of the client use. For the room page, `nickname-form` and `room-topbar`; for
  the operator page, `ops-token-input`, `ops-replay-code` and `ops-period`; for the
  catalogue, `catalogue-filter`, `my-room-title` and `history-title`. A page "fetches
  none of" that code when no script it fetched holds any of the page's markers.
- The checks that these markers exist in the build, and that a page does fetch its
  own, keep the absence from passing for want of a marker: a marker that moved or
  was renamed fails there first.
- "On `/`" is the catalogue `ready`; "on `/r/ABC123`" is the room's nickname form on a
  mocked socket; the operator page is `/ops` answered with the built `index.html`
  (the live server has no operator token), locked. Each page is read once the network
  is idle.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser

from shell_harness import FetchedScripts, built_files, open_locked_ops
from spec046_harness import (
    OpenWindow,
    open_catalogue,
    open_nickname_card,
    window_opener,
)

ROOM_MARKERS = ["nickname-form", "room-topbar"]
OPS_MARKERS = ["ops-token-input", "ops-replay-code", "ops-period"]
CATALOGUE_MARKERS = ["catalogue-filter", "my-room-title", "history-title"]


CATALOGUE_KIND = "reference"


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


def markers_fetched(fetched: FetchedScripts, markers: list[str]) -> list[str]:
    """The markers that a script the page fetched holds."""
    found: list[str] = []
    for marker in markers:
        if fetched.holding(marker) != []:
            found.append(marker)
    return found


# ---- The markers ---------------------------------------------------------------------


@pytest.mark.parametrize("marker", ROOM_MARKERS + OPS_MARKERS + CATALOGUE_MARKERS)
def test_ac31_the_build_holds_each_marker(marker: str) -> None:
    holding: list[str] = []
    for path in built_files(".js"):
        if marker in path.read_text(encoding="utf-8"):
            holding.append(path.name)

    assert holding != [], f"no built script holds {marker}"


# ---- AC-31  --------------------------------------------------------------------------


def test_ac31_the_catalogue_fetches_its_code_and_not_the_room_page_or_operator_code(
    window: OpenWindow, live_server: str
) -> None:
    page = window(1280, 720)
    fetched = FetchedScripts(page)

    open_catalogue(page, live_server)
    page.wait_for_load_state("networkidle")

    assert markers_fetched(fetched, CATALOGUE_MARKERS) == CATALOGUE_MARKERS
    assert markers_fetched(fetched, ROOM_MARKERS) == []
    assert markers_fetched(fetched, OPS_MARKERS) == []


def test_ac31_the_room_page_fetches_its_code_and_not_the_catalogue_or_operator_code(
    window: OpenWindow, live_server: str
) -> None:
    page = window(1280, 720)
    fetched = FetchedScripts(page)

    open_nickname_card(page, live_server)
    page.wait_for_load_state("networkidle")

    assert markers_fetched(fetched, ROOM_MARKERS) == ROOM_MARKERS
    assert markers_fetched(fetched, CATALOGUE_MARKERS) == []
    assert markers_fetched(fetched, OPS_MARKERS) == []


def test_ac31_the_operator_page_fetches_its_own_code(
    window: OpenWindow, live_server: str
) -> None:
    page = window(1280, 720)
    fetched = FetchedScripts(page)

    open_locked_ops(page, live_server)
    page.wait_for_load_state("networkidle")

    assert markers_fetched(fetched, OPS_MARKERS) == OPS_MARKERS
