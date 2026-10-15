"""Tests of spec 016, AC-2: the flash of a replaced letter.

Checked on the page with a mocked socket. The shared setup is in `spec016_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Locator, Page, expect

from nock.grid import Grid
from spec016_harness import (
    SETTLE_MS,
    ChangeList,
    cell_at,
    cell_locked_frame,
    cell_selector,
    default_players,
    expect_letter,
    grid_from_text,
    letter_changed_frame,
    open_fx01,
)

FLASH_SECONDS = 1.0
FLASH_MIN_MS = 800
FLASH_MAX_MS = 2000


# ---- Fixtures ---------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- Helpers of the flash tests -----------------------------------------------


def own_letter_in_1_0() -> ChangeList:
    """Cell (1, 0) holds `T`, confirmed, written by `p1` (you)."""
    return [(1, 0, {"letter": "T", "author": "p1"})]


def start_flash_log(page: Page, row: int, column: int) -> None:
    """Record in the page every change of data-flash on one cell, with its time."""
    page.evaluate(
        """selector => {
            window.__flashLog = [];
            const observer = new MutationObserver(records => {
                for (const record of records) {
                    if (record.target.matches(selector)) {
                        window.__flashLog.push([
                            record.target.getAttribute("data-flash"),
                            performance.now(),
                        ]);
                    }
                }
            });
            observer.observe(document.body, {
                subtree: true,
                attributes: true,
                attributeFilter: ["data-flash"],
            });
        }""",
        cell_selector(row, column),
    )


def read_flash_log(page: Page) -> list[tuple[str, float]]:
    """The (data-flash value, page time in ms) changes seen since start_flash_log."""
    raw_log = page.evaluate("window.__flashLog")
    return [(str(value), float(at)) for value, at in raw_log]


def background_colours(cell: Locator) -> list[str]:
    """The computed background colour of the cell and of every element inside it."""
    found = cell.evaluate(
        "el => [el, ...el.querySelectorAll('*')]"
        ".map(e => getComputedStyle(e).backgroundColor)"
    )
    assert isinstance(found, list)
    colours: list[str] = []
    for colour in found:
        assert isinstance(colour, str)
        colours.append(colour)
    return colours


def swatch_colour(page: Page, player_id: str) -> str:
    """The computed background colour of the roster swatch of `player_id`."""
    item = page.locator(f'[data-testid="roster-player"][data-player-id="{player_id}"]')
    swatch = item.get_by_test_id("roster-colour")
    colour = swatch.evaluate("el => getComputedStyle(el).backgroundColor")
    assert isinstance(colour, str)
    return colour


# ---- AC-2: the flash --------------------------------------------------------------


def test_ac2_a_replaced_letter_flashes_in_the_colour_of_the_replacer_for_a_second(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=own_letter_in_1_0(),
        players=default_players(),
    )
    cell = cell_at(page, 1, 0)
    expect(cell).to_have_attribute("data-flash", "")
    colour_of_p2 = swatch_colour(page, "p2")
    assert colour_of_p2 not in background_colours(cell)

    start_flash_log(page, 1, 0)
    mock.send(letter_changed_frame(6, 1, 0, "A", "p2"))

    expect(cell).to_have_attribute("data-flash", "3")
    assert colour_of_p2 in background_colours(cell)
    expect(cell).to_have_attribute("data-flash", "", timeout=3000)
    flash_log = read_flash_log(page)
    assert [value for value, _ in flash_log] == ["3", ""]
    flash_ms = flash_log[1][1] - flash_log[0][1]
    assert FLASH_MIN_MS <= flash_ms <= FLASH_MAX_MS
    assert colour_of_p2 not in background_colours(cell)
    expect_letter(page, 1, 0, "A")


def test_ac2_the_flash_uses_a_different_colour_for_each_replacer(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=own_letter_in_1_0(),
        players=default_players(),
    )
    cell = cell_at(page, 1, 0)

    mock.send(letter_changed_frame(6, 1, 0, "A", "p3"))

    expect(cell).to_have_attribute("data-flash", "5")
    assert swatch_colour(page, "p3") in background_colours(cell)
    assert swatch_colour(page, "p2") not in background_colours(cell)


def test_ac2_erasing_my_letter_flashes_in_the_erasers_colour(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=own_letter_in_1_0(),
        players=default_players(),
    )

    mock.send(letter_changed_frame(6, 1, 0, None, "p2"))

    cell = cell_at(page, 1, 0)
    expect(cell).to_have_attribute("data-flash", "3")
    expect_letter(page, 1, 0, "")
    assert swatch_colour(page, "p2") in background_colours(cell)


def test_ac2_the_same_letter_written_by_another_player_flashes(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=own_letter_in_1_0(),
        players=default_players(),
    )

    mock.send(letter_changed_frame(6, 1, 0, "T", "p2"))

    expect(cell_at(page, 1, 0)).to_have_attribute("data-flash", "3")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-author", "p2")


def test_ac2_a_player_who_is_gone_flashes_in_colour_index_0(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=own_letter_in_1_0(),
        players=default_players(),
    )

    mock.send(letter_changed_frame(6, 1, 0, "A", "p9"))

    cell = cell_at(page, 1, 0)
    expect(cell).to_have_attribute("data-flash", "0")
    assert swatch_colour(page, "p1") in background_colours(cell)


def test_ac2_a_new_flash_on_the_same_cell_restarts_the_second(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=own_letter_in_1_0(),
        players=default_players(),
    )
    cell = cell_at(page, 1, 0)
    mock.send(letter_changed_frame(6, 1, 0, "A", "p2"))
    expect(cell).to_have_attribute("data-flash", "3")
    page.wait_for_timeout(600)
    assert cell.get_attribute("data-flash") == "3"

    start_flash_log(page, 1, 0)
    mock.send(letter_changed_frame(7, 1, 0, "T", "p1"))
    mock.send(letter_changed_frame(8, 1, 0, "X", "p3"))

    expect(cell).to_have_attribute("data-flash", "5")
    expect(cell).to_have_attribute("data-flash", "", timeout=3000)
    flash_log = read_flash_log(page)
    # The first flash is never cleared on its own: the second one replaces it
    # and runs a full second from its own start, so it was restarted.
    assert [value for value, _ in flash_log] == ["5", ""]
    flash_ms = flash_log[1][1] - flash_log[0][1]
    assert FLASH_MIN_MS <= flash_ms <= FLASH_MAX_MS


@pytest.mark.parametrize(
    ("before", "event_letter", "event_player"),
    [
        pytest.param(("T", "p2"), "A", "p3", id="other-replaces-other"),
        pytest.param((None, None), "A", "p2", id="empty-cell"),
        pytest.param(("T", "p1"), "A", "p1", id="my-own-replacement"),
        pytest.param(("T", "p1"), None, "p1", id="my-own-erase"),
        pytest.param(("T", "p2"), None, "p3", id="other-erases-other"),
        pytest.param((None, None), None, "p2", id="erase-of-an-empty-cell"),
    ],
)
def test_ac2_no_flash_unless_another_player_replaces_my_confirmed_letter(
    page: Page,
    live_server: str,
    fx01_grid: Grid,
    before: tuple[str | None, str | None],
    event_letter: str | None,
    event_player: str,
) -> None:
    letter, author = before
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=[(1, 0, {"letter": letter, "author": author})],
        players=default_players(),
    )
    cell = cell_at(page, 1, 0)

    mock.send(letter_changed_frame(6, 1, 0, event_letter, event_player))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect_letter(page, 1, 0, event_letter or "")
    assert cell.get_attribute("data-flash") == ""
    page.wait_for_timeout(SETTLE_MS)
    assert cell.get_attribute("data-flash") == ""


def test_ac2_my_own_typed_letter_never_flashes_my_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=own_letter_in_1_0(),
        players=default_players(),
    )
    cell = cell_at(page, 1, 0)
    cell.click()
    page.keyboard.press("a")
    expect_letter(page, 1, 0, "A")

    mock.send(letter_changed_frame(6, 1, 0, "A", "p1"))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect(cell).to_have_attribute("data-unconfirmed", "false")
    assert cell.get_attribute("data-flash") == ""
    page.wait_for_timeout(SETTLE_MS)
    assert cell.get_attribute("data-flash") == ""


def test_ac2_a_cell_locked_on_my_letter_does_not_flash(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=own_letter_in_1_0(),
        players=default_players(),
    )
    cell = cell_at(page, 1, 0)

    mock.send(cell_locked_frame(6, 1, 0, "T", revealed=False))

    expect(cell).to_have_attribute("data-locked", "true")
    assert cell.get_attribute("data-flash") == ""
    page.wait_for_timeout(SETTLE_MS)
    assert cell.get_attribute("data-flash") == ""
