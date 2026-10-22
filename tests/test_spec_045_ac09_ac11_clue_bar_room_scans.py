"""Tests of spec 045, AC-9 to AC-11: the clue bar, the room page's guarantees and
the scans.

AC-9: the clue bar shows only the clue, in every mode, and no file under
`web/src` names `clue-bar-author` or `author-mark`. AC-10: with spec 043's `H8`
and the mode on, spec 013 AC-6's checks hold at every window size of spec 006
AC-5 in desktop and touch contexts, and the legend lies in the window and in
`grid-area`, 8 px under the grid, overlapping neither the grid nor `clue-bar`; the
same on a FX-02 snapshot at 568 by 320. AC-11: spec 035's contrast and language
scans find no offending element with the mode on, and `fr.json` holds the
mode's keys. The shared setup is in `spec045_harness`.

Choices where the spec leaves room:

- AC-10's "letters by four of the players": (1, 0) `T` by `p1`, (1, 1) `A` by
  `p2`, (2, 1) `V` by `p3` and (3, 1) `A` by `p4`, as spec 019 AC-5's tests.
- AC-10's FX-02 snapshot: FX-02 with no letter and `p1` to `p8`, nothing tapped.
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

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import Direction, grid_view
from spec019_harness import (
    CONTEXT_KINDS,
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
    ChangeList,
    contrast_ratio,
    mix_over_white,
)
from spec043_harness import (
    COMPUTER,
    DISPLAY_NICKNAMES,
    PHONE,
    WHITE,
    box_inside,
    fx01_view,
    load_fr,
    open_h8,
    open_room,
    player,
    players_up_to,
    press_cell,
    seed_value,
    selecting,
    snapshot_frame,
    window_box,
)
from spec045_harness import (
    AUTHORS_KEY,
    INKS,
    ac3_frame,
    authors_switch,
    boxes_of,
    eight_frame,
    ink_probe,
    legend_of,
    legend_place_problems,
    open_page,
    overlap_area,
    required_box,
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


def legend_guarantee_problems(page: Page) -> list[str]:
    """The legend inside the window and `grid-area`, 8 px under the grid, alone."""
    boxes = boxes_of(page, ["authors-legend", "grid-area", "grid", "clue-bar"])
    legend = required_box(boxes, "authors-legend")
    area = required_box(boxes, "grid-area")
    grid = required_box(boxes, "grid")
    bar = required_box(boxes, "clue-bar")
    problems = legend_place_problems(page)
    if not box_inside(legend, window_box(page)):
        problems.append(f"legend {legend} is not inside the window")
    if not box_inside(legend, area):
        problems.append(f"legend {legend} is not inside grid-area {area}")
    if overlap_area(legend, grid) > 0:
        problems.append(f"legend {legend} overlaps the grid {grid}")
    if overlap_area(legend, bar) > 0:
        problems.append(f"legend {legend} overlaps clue-bar {bar}")
    return problems


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
def test_ac10_the_legend_lies_in_the_window_under_the_grid_and_covers_nothing(
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

    assert legend_guarantee_problems(page) == []


def open_fx02_low(window: OpenWindow, base_url: str, grid: Grid) -> Page:
    """FX-02 with `p1` to `p8` at 568 by 320, desktop context, the mode on."""
    width, height = LOW_WINDOW
    page = window(width, height, False)
    seed_value(page, AUTHORS_KEY, "true")
    open_room(page, base_url, snapshot_frame(grid_view(grid), players_up_to(8)))
    expect(legend_of(page)).to_be_visible()
    settle_layout(page)
    return page


def test_ac10_fx02_at_568_by_320_spec_013_ac6_checks_hold_with_the_mode_on(
    window: OpenWindow, live_server: str, fx02_grid: Grid
) -> None:
    page = open_fx02_low(window, live_server, fx02_grid)

    assert layout_problems(page, False) == []


def test_ac10_fx02_at_568_by_320_the_legend_lies_under_the_grid_alone(
    window: OpenWindow, live_server: str, fx02_grid: Grid
) -> None:
    page = open_fx02_low(window, live_server, fx02_grid)

    assert legend_guarantee_problems(page) == []


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
