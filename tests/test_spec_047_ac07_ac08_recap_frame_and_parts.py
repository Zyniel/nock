"""Tests of spec 047, AC-7 and AC-8: the recap's frame and the order and type of
its parts.

On `SOLVED` (spec 044's) with the recap route answering `RECAP` (spec 028 AC-2's
recap with `share_path` `/recap/tok_ABCDEFGHIJKLMNOP`), after a click on
`recap-open`, in the desktop context. AC-7: a 440 px dialog in the column layout
(1280 by 720, and 568 by 320 where it scrolls inside), a bottom sheet in the
sheet layout (360 by 740), over the `--nock-scrim-dialog` backdrop that covers the
whole window. AC-8: its parts in the design's order, 14 px apart, with the
design's type.

Readings where the spec leaves room:

- Every measure waits for `recap-time`, so that it reads the loaded recap and not
  `recap-loading` (spec 028 AC-10's test does the same).
- "The children of `recap` that show" are its element children with a box, read
  through an anonymous wrapper (a `div`, `section`, `header`, `footer` or `form`
  with no test id and no `id`), so that a wrapper the dialog may hold does not
  hide its parts; each is named by its test id, else its `id`, and the `h2` by its
  tag. The players' heading keeps spec 028's `id="recap-players-heading"` (it may
  also carry the test id).
- "Each the next one's top 14 px or more above": the gap between one part's bottom
  and the next one's top is at least 14 px (1 px).
- "Centred in the window": both centres within 1 px of the window's.
- "`recap-close` can be scrolled into view inside it": after
  `scroll_into_view_if_needed`, its box lies inside the dialog's box and the
  window (1 px).
- "The dialog's content right edge": `recap`'s box less its right border and
  padding.
- The section headings' texts are read as text content: `text-transform` draws
  them in capitals, which `inner_text` would return in some engines.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import pairwise

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from spec019_harness import OpenWindow, window_opener
from spec042_harness import box_of
from spec043_harness import INK, box_inside, fr_value, px, same_position, style_of
from spec043_harness import window_box as window_of
from spec044_harness import solved_frame
from spec046_harness import button_colour_problems
from spec047_harness import (
    COMPUTER,
    LOW,
    MUTED,
    NAVY,
    PHONE,
    SIZE_IDS,
    SIZES,
    backdrop_problems,
    column_frame_problems,
    open_loaded_recap,
    open_solved,
    parts_of,
    players_heading,
    right_on_content_edge,
    sheet_frame_problems,
    tabular_problems,
    type_problems,
)

PARTS = [
    "h2",
    "recap-time",
    "recap-lines",
    "recap-players-heading",
    "recap-players",
    "recap-share-heading",
    "recap-share-row",
    "recap-close",
]
LINES = ["recap-checks", "recap-reveals", "recap-revealed"]
LOW_MAX_HEIGHT_PX = 288.0  # 320 less 32
SIZE_TOLERANCE_PX = 0.5
LETTER_SPACING_TOLERANCE_PX = 0.01

# Whether `elementFromPoint` at (x, y) is `room-topbar` or inside it.
TOP_BAR_HIT_SCRIPT = r"""
([x, y]) => {
  const bar = document.querySelector('[data-testid="room-topbar"]');
  const hit = document.elementFromPoint(x, y);
  return {
    inBar: bar !== null && hit !== null && bar.contains(hit),
    hit: hit === null ? null : (hit.getAttribute('data-testid') || hit.tagName),
  };
}
"""

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- Setup -------------------------------------------------------------------------


def open_recap_at(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int]
) -> Page:
    """`SOLVED` at `size` (desktop) with `RECAP`, the recap open and loaded."""
    page = window(size[0], size[1], False)
    open_solved(page, base_url, solved_frame(grid))
    open_loaded_recap(page)
    return page


# ---- AC-7: the frame -------------------------------------------------------------


def test_ac7_at_1280_the_recap_is_an_open_dialog(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_recap_at(window, live_server, fx01_grid, COMPUTER)
    recap = page.get_by_test_id("recap")

    assert recap.evaluate("element => element.tagName") == "DIALOG"
    expect(recap).to_have_attribute("open", "")


def test_ac7_at_1280_the_dialog_is_440_px_wide_and_centred_with_the_designs_look(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_recap_at(window, live_server, fx01_grid, COMPUTER)

    assert column_frame_problems(page) == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac7_the_backdrop_is_the_dialog_scrim(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_recap_at(window, live_server, fx01_grid, size)

    assert backdrop_problems(page) == []


def test_ac7_at_568_by_320_the_dialog_is_440_px_wide_and_inside_the_window(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_recap_at(window, live_server, fx01_grid, LOW)

    box = box_of(page.get_by_test_id("recap"))

    assert same_position(box.width, 440.0), box
    assert box_inside(box, window_of(page)), box
    assert box.height <= LOW_MAX_HEIGHT_PX + SIZE_TOLERANCE_PX, box


def test_ac7_at_568_by_320_fermer_can_be_scrolled_into_view_inside_the_dialog(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_recap_at(window, live_server, fx01_grid, LOW)
    close = page.get_by_test_id("recap-close")

    close.scroll_into_view_if_needed()

    close_box = box_of(close)
    assert box_inside(close_box, box_of(page.get_by_test_id("recap"))), close_box
    assert box_inside(close_box, window_of(page)), close_box


def test_ac7_at_360_the_recap_is_a_bottom_sheet_without_a_handle(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_recap_at(window, live_server, fx01_grid, PHONE)
    recap = page.get_by_test_id("recap")

    assert sheet_frame_problems(page) == []
    expect(recap.get_by_test_id("salon-handle")).to_have_count(0)


def test_ac7_at_360_the_scrim_covers_the_top_bar(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_recap_at(window, live_server, fx01_grid, PHONE)

    found = page.evaluate(TOP_BAR_HIT_SCRIPT, [180, 20])

    assert isinstance(found, dict), found
    assert found["inBar"] is False, found


# ---- AC-8: the parts and their type ----------------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac8_the_parts_come_in_the_designs_order_14_px_apart(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_recap_at(window, live_server, fx01_grid, size)

    parts = parts_of(page.get_by_test_id("recap"))

    assert [part.name for part in parts] == PARTS
    short_gaps: list[str] = []
    for upper, lower in pairwise(parts):
        gap = lower.box.top - upper.box.bottom
        if gap < 14.0 - 1.0:
            short_gaps.append(f"{upper.name} -> {lower.name}: {gap} px")
    assert short_gaps == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac8_the_heading_has_the_designs_type(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_recap_at(window, live_server, fx01_grid, size)
    heading = page.get_by_test_id("recap").locator("h2")

    expect(heading).to_have_text(fr_value("recap.heading"))
    assert type_problems(heading, "h2", size=19.2, weight="700", colour=NAVY) == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac8_the_time_has_the_designs_type(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_recap_at(window, live_server, fx01_grid, size)
    time = page.get_by_test_id("recap-time")

    expect(time).to_have_text("Temps : 12:34")
    problems = type_problems(
        time, "recap-time", size=33.6, weight="700", colour=NAVY, line_height=33.6
    )
    problems += tabular_problems(time, "recap-time")
    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac8_the_lines_hold_the_checks_the_reveals_and_the_revealed_letters(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_recap_at(window, live_server, fx01_grid, size)
    lines = page.get_by_test_id("recap-lines")

    parts = parts_of(lines)

    assert [part.name for part in parts] == LINES
    gaps = [lower.box.top - upper.box.bottom for upper, lower in pairwise(parts)]
    assert all(same_position(gap, 4.0) for gap in gaps), gaps
    checks = lines.get_by_test_id("recap-checks")
    expect(checks).to_have_text("Vérifications : 2")
    reveals = lines.get_by_test_id("recap-reveals")
    expect(reveals).to_have_text("Révélations : 1 lettres et 1 mots")
    revealed = lines.get_by_test_id("recap-revealed")
    expect(revealed).to_have_text("Lettres révélées : 5")


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac8_each_line_is_ink_at_15_2_px(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_recap_at(window, live_server, fx01_grid, size)

    problems: list[str] = []
    for test_id in LINES:
        line = page.get_by_test_id(test_id)
        problems += type_problems(line, test_id, size=15.2, weight="400", colour=INK)

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac8_the_section_headings_are_muted_uppercase(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_recap_at(window, live_server, fx01_grid, size)
    headings = {
        "recap-players-heading": (players_heading(page), "recap.players_heading"),
        "recap-share-heading": (
            page.get_by_test_id("recap-share-heading"),
            "recap.share_label",
        ),
    }

    problems: list[str] = []
    for name, (heading, key) in headings.items():
        expect(heading).to_have_count(1)
        text = str(heading.text_content()).strip()
        if text != fr_value(key):
            problems.append(f"{name} reads {text!r}")
        problems += type_problems(heading, name, size=12.48, weight="600", colour=MUTED)
        if style_of(heading, "textTransform") != "uppercase":
            problems.append(
                f"{name}: text-transform {style_of(heading, 'textTransform')}"
            )
        spacing = style_of(heading, "letterSpacing")
        wrong_spacing = not spacing.endswith("px") or (
            abs(px(spacing) - 0.8736) > LETTER_SPACING_TOLERANCE_PX
        )
        if wrong_spacing:
            problems.append(f"{name}: letter-spacing {spacing}")

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac8_fermer_is_primary_on_the_dialogs_content_right_edge(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_recap_at(window, live_server, fx01_grid, size)
    close = page.get_by_test_id("recap-close")

    expect(close).to_have_text(fr_value("recap.close"))
    problems = button_colour_problems(close, "primary")
    problems += right_on_content_edge(page, "recap-close")

    assert problems == []
