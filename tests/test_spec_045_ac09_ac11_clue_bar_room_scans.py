"""Tests of spec 045, AC-9 to AC-11: the clue bar, the room page's guarantees and
the scans.

AC-9: the clue bar shows only the clue, in every mode, and no file under
`web/src` names `clue-bar-author` or `author-mark`. AC-10: with spec 043's `H8`
and the mode on, spec 013 AC-6's checks hold at every window size of spec 006
AC-5 in desktop and touch contexts; the legend lies in the window, no wider than
`clue-bar`, centred on `grid-area`'s content box, overlapping none of the top
bar, the clue bar, the status, the keyboard and the Salon; it sits 8 px under the
grid off its box when the grid gave it its room, or else over the viewport's
bottom (8 px above it) with `grid-viewport` keeping its box of the mode off; in
the sheet layout it lies over the grid exactly when `V - max(38, h + 8)` is
under 100, as at 568 by 320 in the touch context. The same checks hold on a
FX-02 snapshot at 568 by 320, and on a FX-02 snapshot with 8 players of
20-character nicknames at 568 by 320 and 740 by 360 (desktop), where `clue-bar`
also keeps its width of the mode off. AC-11: spec 035's contrast and language
scans find no offending element with the mode on, and `fr.json` holds the
mode's keys. The shared setup is in `spec045_harness`.

Choices where the spec leaves room:

- AC-10's "letters by four of the players": (1, 0) `T` by `p1`, (1, 1) `A` by
  `p2`, (2, 1) `V` by `p3` and (3, 1) `A` by `p4`, as spec 019 AC-5's tests.
- AC-10's FX-02 snapshots: FX-02 with no letter, nothing tapped, the Salon open.
- AC-10's checks that need no reading with the mode off (spec 013 AC-6's, the
  width, the centre and the overlaps) run on `H8` opened with the mode seeded on;
  the two cases and the sheet layout's rule run on `H8` read with the mode off,
  then turned on in the Menu (once spec 043's 3-second note of the last line
  event has gone, as it covers the Menu's button). The FX-02 runs all turn the
  mode on in the Menu.
- "In the sheet layout" is the windows of spec 006 AC-5 where spec 043 AC-1 sets
  `data-layout="sheet"` (`SHEET_WINDOWS`); the test checks the attribute.
- The case is not told by "the legend's top at or below `grid-viewport`'s
  bottom": in the sheet layout on a portrait window the grid is centred in a
  viewport taller than itself, so the legend, 8 px under the grid (AC-7) in a
  viewport 38 px less high (AC-8), lies inside the viewport's box with the room
  given. At every window the legend must follow one of the two cases (under the
  grid, or over it with `grid-viewport` keeping its box of the mode off); in the
  sheet layout the case is the one `V - max(38, h + 8)` names, as AC-10 states,
  and the legend must follow that one.
- AC-11 also computes, from the page's tokens, that each ink reaches 4.5:1 on
  each cell background the spec names (white, word blue, selected blue, locked
  grey and each other player's word tint, `--player-colour-M` at 16 % over
  white), by spec 035's formula; the scans then see the inks on the page.
- AC-11's language scan accepts the room code, its link, the nicknames as the
  page shows them and their two first letters, and FX-01's clue texts (spec 024's
  `language_data`).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import Direction, PlayerView, grid_view
from room_panels import expect_open
from spec019_harness import (
    CONTEXT_KINDS,
    MIN_GRID_VIEWPORT_PX,
    WINDOW_IDS,
    WINDOW_SIZES,
    OpenWindow,
    layout_problems,
    window_opener,
)
from spec024_harness import contrast_problems, language_data, language_problems
from spec042_harness import (
    LOCKED,
    PLAYER_COLOURS,
    SELECTED,
    WORD,
    Box,
    ChangeList,
    contrast_ratio,
    mix_over_white,
    to_box,
)
from spec043_harness import (
    COMPUTER,
    DISPLAY_NICKNAMES,
    PHONE,
    POSITION_TOLERANCE_PX,
    SIZE_TOLERANCE_PX,
    WHITE,
    fx01_view,
    layout_of,
    load_fr,
    open_h8,
    open_room,
    player,
    players_up_to,
    press_cell,
    same_box,
    seed_value,
    selecting,
    snapshot_frame,
)
from spec045_harness import (
    AUTHORS_KEY,
    INKS,
    LEGEND_GAP_PX,
    ONE_LINE_ROOM_PX,
    ac3_frame,
    authors_switch,
    boxes_of,
    eight_frame,
    ink_probe,
    legend_cover_problems,
    legend_of,
    legend_over_problems,
    legend_reading,
    legend_under_problems,
    long_name_players,
    open_page,
    required_box,
    set_mode,
    settle_layout,
)

WEB_SRC = Path(__file__).resolve().parents[1] / "web" / "src"
GONE_NAMES = ["clue-bar-author", "author-mark"]
CLUE_OF_TAMIS = "Passoire fine"
AC9_WINDOWS = [((1280, 720), False), ((568, 320), True)]
AC9_IDS = ["1280x720-desktop", "568x320-touch"]
SCAN_SIZES = [COMPUTER, PHONE]
SCAN_IDS = ["1280x720", "360x740"]
MIN_TEXT_CONTRAST = 4.5
TINT_SHARE = 0.16
LOW_WINDOW = (568, 320)
# Spec 043's 3-second note of H8's last line event covers the top bar while it
# shows; it leaves the page 3,350 ms after it showed.
NOTE_GONE_TIMEOUT_MS = 5000

# The windows of spec 006 AC-5 where `room-page` has `data-layout="sheet"` (spec
# 043 AC-1): the portrait ones, and the low touch ones with the keyboard shown.
SHEET_WINDOWS = [
    pytest.param(320, 568, "desktop", id="320x568-desktop"),
    pytest.param(360, 740, "desktop", id="360x740-desktop"),
    pytest.param(768, 1024, "desktop", id="768x1024-desktop"),
    pytest.param(320, 568, "touch", id="320x568-touch"),
    pytest.param(568, 320, "touch", id="568x320-touch"),
    pytest.param(360, 740, "touch", id="360x740-touch"),
    pytest.param(740, 360, "touch", id="740x360-touch"),
    pytest.param(768, 1024, "touch", id="768x1024-touch"),
]
LONG_NAME_WINDOWS = [(568, 320), (740, 360)]
LONG_NAME_IDS = ["568x320-desktop", "740x360-desktop"]

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return Grid.model_validate_json(fx02_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- AC-9: the clue bar shows only the clue ----


def open_ac9(
    window: OpenWindow,
    base_url: str,
    grid: Grid,
    size: tuple[int, int],
    touch: bool,
    mode_on: bool,
) -> Page:
    page, _ = open_page(
        window, base_url, ac3_frame(grid), size, touch=touch, mode_on=mode_on
    )
    if mode_on:
        expect(legend_of(page)).to_be_visible()
    else:
        expect(authors_switch(page)).to_have_attribute("aria-pressed", "false")
    return page


def expect_only_the_clue(page: Page) -> None:
    expect(page.get_by_test_id("clue-bar-author")).to_have_count(0)
    expect(page.get_by_test_id("clue-bar-text")).to_have_text(CLUE_OF_TAMIS)


@pytest.mark.parametrize("mode_on", [True, False], ids=["mode-on", "mode-off"])
@pytest.mark.parametrize(("size", "touch"), AC9_WINDOWS, ids=AC9_IDS)
def test_ac9_after_a_tap_on_a_letter_by_a_player_the_bar_holds_only_the_clue(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    size: tuple[int, int],
    touch: bool,
    mode_on: bool,
) -> None:
    page = open_ac9(window, live_server, fx01_grid, size, touch, mode_on)

    press_cell(page, 1, 1, touch)

    expect_only_the_clue(page)


@pytest.mark.parametrize("mode_on", [True, False], ids=["mode-on", "mode-off"])
@pytest.mark.parametrize(("size", "touch"), AC9_WINDOWS, ids=AC9_IDS)
def test_ac9_after_a_tap_on_a_letter_with_no_finder_the_bar_holds_only_the_clue(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    size: tuple[int, int],
    touch: bool,
    mode_on: bool,
) -> None:
    page = open_ac9(window, live_server, fx01_grid, size, touch, mode_on)
    press_cell(page, 1, 1, touch)

    press_cell(page, 1, 2, touch)

    expect_only_the_clue(page)


def files_naming(names: list[str]) -> list[str]:
    """The files under `web/src` whose text holds one of `names`."""
    found: list[str] = []
    for path in sorted(WEB_SRC.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for name in names:
            if name in text:
                found.append(f"{path.relative_to(WEB_SRC)}: {name}")
    return found


def test_ac9_static_no_file_under_web_src_names_the_author_line_or_the_band() -> None:
    assert WEB_SRC.is_dir()

    assert files_naming(GONE_NAMES) == []


# ---- AC-10: the room page's guarantees with the mode on ----


def four_letters() -> ChangeList:
    """Letters by four of the players (`p1` to `p4`)."""
    return [
        (1, 0, {"letter": "T", "author": "p1"}),
        (1, 1, {"letter": "A", "author": "p2"}),
        (2, 1, {"letter": "V", "author": "p3"}),
        (3, 1, {"letter": "A", "author": "p4"}),
    ]


class ModeRun(NamedTuple):
    """A page turned from the mode off to the mode on, with what it showed off."""

    page: Page
    viewport_off: Box
    bar_off: Box


def turn_on_after_reading(page: Page, touch: bool) -> ModeRun:
    """Note `grid-viewport`'s and `clue-bar`'s boxes, then turn the mode on.

    Both readings are made once the layout has settled; the mode is turned on in
    the Menu, which is closed again.
    """
    settle_layout(page)
    found_off = boxes_of(page, ["grid-viewport", "clue-bar"])
    set_mode(page, True, touch)
    expect(legend_of(page)).to_be_visible()
    settle_layout(page)
    viewport_off = required_box(found_off, "grid-viewport")
    bar_off = required_box(found_off, "clue-bar")
    return ModeRun(page, viewport_off, bar_off)


def open_h8_with_the_mode_on(
    window: OpenWindow, base_url: str, grid: Grid, width: int, height: int, touch: bool
) -> Page:
    """`H8` with letters by four players, `nock.authors` seeded `"true"`."""
    page = window(width, height, touch)
    seed_value(page, AUTHORS_KEY, "true")
    open_h8(page, base_url, grid, touch, view=fx01_view(grid, four_letters()))
    expect(legend_of(page)).to_be_visible()
    settle_layout(page)
    return page


def open_h8_off_then_on(
    window: OpenWindow, base_url: str, grid: Grid, width: int, height: int, touch: bool
) -> ModeRun:
    """`H8` with letters by four players, read with the mode off, then turned on.

    The page waits until spec 043's 3-second note of the last line event has
    gone, since it covers the top bar, where the Menu's button is.
    """
    page = window(width, height, touch)
    open_h8(page, base_url, grid, touch, view=fx01_view(grid, four_letters()))
    expect(page.get_by_test_id("room-note")).to_have_count(
        0, timeout=NOTE_GONE_TIMEOUT_MS
    )
    return turn_on_after_reading(page, touch)


def legend_frame_problems(page: Page) -> list[str]:
    """How the legend breaks AC-10's width and centre (empty: none).

    It is at most as wide as `clue-bar` (0.5 px), and its horizontal centre is
    within 1 px of the centre of `grid-area`'s content box.
    """
    reading = legend_reading(page)
    legend = to_box(reading["box"])
    bar = required_box(boxes_of(page, ["clue-bar"]), "clue-bar")
    problems: list[str] = []
    if legend.width > bar.width + SIZE_TOLERANCE_PX:
        problems.append(f"legend {legend.width} px wide, clue-bar {bar.width} px")
    if reading["areaContent"] is None:
        problems.append("no grid-area")
        return problems
    content = to_box(reading["areaContent"])
    if abs(legend.centre_x - content.centre_x) > POSITION_TOLERANCE_PX:
        problems.append(
            f"legend centre x {legend.centre_x}, grid-area's content centre x"
            f" {content.centre_x}"
        )
    return problems


def viewport_kept_problems(run: ModeRun) -> list[str]:
    """How `grid-viewport` differs from its box with the mode off (1 px)."""
    boxes = boxes_of(run.page, ["grid-viewport"])
    viewport = required_box(boxes, "grid-viewport")
    if same_box(viewport, run.viewport_off):
        return []
    return [
        f"grid-viewport is {viewport} with the mode on and was"
        f" {run.viewport_off} with it off"
    ]


def over_the_grid_problems(run: ModeRun) -> list[str]:
    """How the legend breaks AC-10's case "it lies over the grid" (empty: none).

    Its bottom is 8 px above `grid-viewport`'s bottom (1 px), and `grid-viewport`
    has its box of the mode off (1 px).
    """
    problems = legend_over_problems(run.page)
    problems.extend(viewport_kept_problems(run))
    return problems


def legend_place_rule_problems(run: ModeRun) -> list[str]:
    """How the legend breaks both of AC-10's cases (empty: it follows one).

    Under the grid: its top 8 px below the grid's bottom, off the grid's box. Over
    the grid: its bottom 8 px above `grid-viewport`'s bottom, `grid-viewport`
    keeping its box of the mode off.
    """
    under = legend_under_problems(run.page)
    if under == []:
        return []
    over = over_the_grid_problems(run)
    if over == []:
        return []
    return [f"not under the grid: {under}", f"not over the grid: {over}"]


def room_given_problems(run: ModeRun) -> list[str]:
    """How `grid-viewport` fails to give the legend its room (empty: it did).

    In the sheet layout `grid-viewport` is less high than with the mode off by
    `R = max(38, h + 8)` (1 px).
    """
    boxes = boxes_of(run.page, ["grid-viewport", "authors-legend"])
    viewport = required_box(boxes, "grid-viewport")
    legend = required_box(boxes, "authors-legend")
    room = max(ONE_LINE_ROOM_PX, legend.height + LEGEND_GAP_PX)
    lost = run.viewport_off.height - viewport.height
    if abs(lost - room) <= POSITION_TOLERANCE_PX:
        return []
    return [
        f"grid-viewport is {lost} px less high than with the mode off and R is"
        f" {room} px (h {legend.height})"
    ]


def case_problems(run: ModeRun, over: bool) -> list[str]:
    """How the legend breaks the one of AC-10's cases that `over` names.

    Used in the sheet layout: when the grid gives the legend its room, the
    viewport must have lost `R` as well as the legend lying under the grid.
    """
    if over:
        return over_the_grid_problems(run)
    problems = legend_under_problems(run.page)
    problems.extend(room_given_problems(run))
    return problems


def room_rule_says_over(run: ModeRun) -> tuple[bool, str]:
    """Whether `V - max(38, h + 8)` is under 100, and the numbers, for messages."""
    legend = required_box(boxes_of(run.page, ["authors-legend"]), "authors-legend")
    room = max(ONE_LINE_ROOM_PX, legend.height + LEGEND_GAP_PX)
    room_would_leave = run.viewport_off.height - room
    numbers = (
        f"V {run.viewport_off.height}, h {legend.height}: the room would leave"
        f" {room_would_leave} px"
    )
    return room_would_leave < MIN_GRID_VIEWPORT_PX, numbers


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac10_spec_013_ac6_checks_hold_with_the_mode_on(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page = open_h8_with_the_mode_on(
        window, live_server, fx01_grid, width, height, touch
    )

    assert layout_problems(page, touch) == []


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac10_the_legend_is_centred_and_no_wider_than_the_clue_bar(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page = open_h8_with_the_mode_on(
        window, live_server, fx01_grid, width, height, touch
    )

    assert legend_frame_problems(page) == []


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac10_the_legend_lies_in_the_window_and_covers_no_bar_keyboard_or_salon(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page = open_h8_with_the_mode_on(
        window, live_server, fx01_grid, width, height, touch
    )

    assert legend_cover_problems(page) == []


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac10_the_legend_sits_under_the_grid_or_over_the_viewports_bottom(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    run = open_h8_off_then_on(window, live_server, fx01_grid, width, height, touch)

    assert legend_place_rule_problems(run) == []


@pytest.mark.parametrize(("width", "height", "context_kind"), SHEET_WINDOWS)
def test_ac10_in_the_sheet_layout_the_legend_is_over_the_grid_when_room_leaves_lt_100(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    run = open_h8_off_then_on(window, live_server, fx01_grid, width, height, touch)

    assert layout_of(run.page) == "sheet"
    over, numbers = room_rule_says_over(run)
    assert case_problems(run, over) == [], f"{numbers}; over the grid: {over}"


def test_ac10_at_568_by_320_in_the_touch_context_the_legend_lies_over_the_grid(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    width, height = LOW_WINDOW
    run = open_h8_off_then_on(window, live_server, fx01_grid, width, height, True)

    over, numbers = room_rule_says_over(run)
    assert over is True, numbers
    assert over_the_grid_problems(run) == []


# ---- AC-10: FX-02 snapshots on a low desktop window ----


def open_fx02_off_then_on(
    window: OpenWindow,
    base_url: str,
    grid: Grid,
    players: list[PlayerView],
    size: tuple[int, int],
) -> ModeRun:
    """FX-02 (no letter) with `players` in the desktop context, the Salon open."""
    width, height = size
    page = window(width, height, False)
    open_room(page, base_url, snapshot_frame(grid_view(grid), players))
    expect_open(page.get_by_test_id("salon"))
    return turn_on_after_reading(page, False)


def open_fx02_low(window: OpenWindow, base_url: str, grid: Grid) -> ModeRun:
    """FX-02 with `p1` to `p8` at 568 by 320, desktop context, the mode turned on."""
    return open_fx02_off_then_on(window, base_url, grid, players_up_to(8), LOW_WINDOW)


def test_ac10_fx02_at_568_by_320_spec_013_ac6_checks_hold_with_the_mode_on(
    window: OpenWindow, live_server: str, fx02_grid: Grid
) -> None:
    run = open_fx02_low(window, live_server, fx02_grid)

    assert layout_problems(run.page, False) == []


def test_ac10_fx02_at_568_by_320_the_legend_is_centred_and_covers_nothing(
    window: OpenWindow, live_server: str, fx02_grid: Grid
) -> None:
    run = open_fx02_low(window, live_server, fx02_grid)

    problems = legend_frame_problems(run.page)
    problems.extend(legend_cover_problems(run.page))
    assert problems == []


def test_ac10_fx02_at_568_by_320_the_legend_sits_under_the_grid_or_over_its_bottom(
    window: OpenWindow, live_server: str, fx02_grid: Grid
) -> None:
    run = open_fx02_low(window, live_server, fx02_grid)

    assert legend_place_rule_problems(run) == []


def open_fx02_long_names(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int]
) -> ModeRun:
    """FX-02 with 8 players of 20-character nicknames, desktop, the mode turned on."""
    return open_fx02_off_then_on(window, base_url, grid, long_name_players(), size)


@pytest.mark.parametrize("size", LONG_NAME_WINDOWS, ids=LONG_NAME_IDS)
def test_ac10_fx02_long_names_spec_013_ac6_checks_hold_with_the_mode_on(
    window: OpenWindow, live_server: str, fx02_grid: Grid, size: tuple[int, int]
) -> None:
    run = open_fx02_long_names(window, live_server, fx02_grid, size)

    assert layout_of(run.page) == "column"
    assert layout_problems(run.page, False) == []


@pytest.mark.parametrize("size", LONG_NAME_WINDOWS, ids=LONG_NAME_IDS)
def test_ac10_fx02_long_names_the_legend_is_centred_and_covers_nothing(
    window: OpenWindow, live_server: str, fx02_grid: Grid, size: tuple[int, int]
) -> None:
    run = open_fx02_long_names(window, live_server, fx02_grid, size)

    problems = legend_frame_problems(run.page)
    problems.extend(legend_cover_problems(run.page))
    assert problems == []


@pytest.mark.parametrize("size", LONG_NAME_WINDOWS, ids=LONG_NAME_IDS)
def test_ac10_fx02_long_names_the_legend_sits_under_the_grid_or_over_its_bottom(
    window: OpenWindow, live_server: str, fx02_grid: Grid, size: tuple[int, int]
) -> None:
    run = open_fx02_long_names(window, live_server, fx02_grid, size)

    assert legend_place_rule_problems(run) == []


@pytest.mark.parametrize("size", LONG_NAME_WINDOWS, ids=LONG_NAME_IDS)
def test_ac10_fx02_long_names_the_clue_bar_keeps_its_width(
    window: OpenWindow, live_server: str, fx02_grid: Grid, size: tuple[int, int]
) -> None:
    run = open_fx02_long_names(window, live_server, fx02_grid, size)

    bar_on = required_box(boxes_of(run.page, ["clue-bar"]), "clue-bar")
    assert abs(bar_on.width - run.bar_off.width) <= SIZE_TOLERANCE_PX, (
        run.bar_off,
        bar_on,
    )


# ---- AC-11: the scans and fr.json ----


def scan_frame(grid: Grid) -> str:
    """`EIGHT` with `p2` on (3, 2) `down`, a lock, a pencil and a wrong letter."""
    players = players_up_to(8)
    players[1] = player("p2", selection=selecting(3, 2, Direction.DOWN))
    replaced: ChangeList = [
        (1, 3, {"letter": "I", "author": "p4", "locked": True}),
        (2, 3, {"letter": "D", "author": "p8", "pencil": True}),
        (4, 4, {"letter": "X", "author": "p1", "wrong": True}),
    ]
    return eight_frame(grid, players=players, replaced=replaced)


def open_scan_page(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int]
) -> Page:
    page, _ = open_page(window, base_url, scan_frame(grid), size, mode_on=True)
    press_cell(page, 1, 0)
    expect(legend_of(page)).to_be_visible()
    return page


@pytest.mark.parametrize("size", SCAN_SIZES, ids=SCAN_IDS)
def test_ac11_the_contrast_scan_finds_no_offender_with_the_mode_on(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_scan_page(window, live_server, fx01_grid, size)

    assert contrast_problems(page) == []


@pytest.mark.parametrize("size", SCAN_SIZES, ids=SCAN_IDS)
def test_ac11_the_language_scan_finds_no_offender_with_the_mode_on(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_scan_page(window, live_server, fx01_grid, size)
    expect(page.locator("html")).to_have_attribute("lang", "fr")

    data = language_data(live_server, DISPLAY_NICKNAMES)

    assert language_problems(page, data) == []


def cell_backgrounds(other_than: int) -> dict[str, tuple[float, float, float]]:
    """The cell backgrounds of AC-11, by name, for the ink of colour `other_than`."""
    backgrounds: dict[str, tuple[float, float, float]] = {
        "white": (float(WHITE[0]), float(WHITE[1]), float(WHITE[2])),
        "word": (float(WORD[0]), float(WORD[1]), float(WORD[2])),
        "selected": (float(SELECTED[0]), float(SELECTED[1]), float(SELECTED[2])),
        "locked": (float(LOCKED[0]), float(LOCKED[1]), float(LOCKED[2])),
    }
    for colour_index, colour in enumerate(PLAYER_COLOURS):
        if colour_index != other_than:
            tint = mix_over_white(colour, TINT_SHARE)
            backgrounds[f"tint of colour {colour_index}"] = tint
    return backgrounds


def test_ac11_every_ink_reaches_4_5_to_1_on_each_cell_background(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_page(window, live_server, eight_frame(fx01_grid))

    problems: list[str] = []
    for colour_index in range(8):
        probe = ink_probe(page, colour_index)
        ink = (probe[0], probe[1], probe[2])
        if ink != tuple(float(channel) for channel in INKS[colour_index]):
            problems.append(f"--player-ink-{colour_index} is {probe}")
        for name, background in cell_backgrounds(colour_index).items():
            ratio = contrast_ratio(ink, background)
            if ratio < MIN_TEXT_CONTRAST:
                problems.append(f"ink {colour_index} on {name}: {ratio:.2f}")
    assert problems == []


def test_ac11_static_fr_json_holds_authors_legend() -> None:
    assert load_fr().get("authors.legend") == "Auteurs :"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("authors.switch", "Auteurs"),
        ("authors.on", "activé"),
        ("authors.off", "désactivé"),
    ],
)
def test_ac11_static_fr_json_still_holds_the_switchs_keys(key: str, value: str) -> None:
    assert load_fr().get(key) == value


def test_ac11_static_fr_json_has_no_authors_selected() -> None:
    assert "authors.selected" not in load_fr()
