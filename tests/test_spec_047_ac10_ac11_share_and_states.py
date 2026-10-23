"""Tests of spec 047, AC-10 (without the clipboard) and AC-11: the share link's
URL box beside « Copier le lien », and the recap's loading and unavailable states.

On `SOLVED` (spec 044's), in the desktop context. AC-10: with the route answering
`RECAP`, at 1280 by 720 `recap-share-row` holds the URL box `recap-share-link`
then `recap-copy` on one line; at 360 by 740 the button goes under the
full-width link; with `share_path` null there is no share heading and no row. The
clipboard check of AC-10 is in `test_spec_047_ac10_copied_line.py`. AC-11: with
the route held unanswered, then answering 404, the dialog has the frame of AC-7
and holds its title, one line and « Fermer ».

Readings where the spec leaves room:

- "One line" for the share row: `recap-share-link` and `recap-copy` are the
  row's parts that show, in that order, their vertical centres within 1 px.
- "`overflow` `hidden`": both computed `overflow-x` and `overflow-y`.
- "With the same gap" (AC-11): the parts are at least 14 px apart (1 px), as
  AC-8 reads the loaded parts.
- The loading state is read once `recap-loading` shows, the route still held.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import pairwise

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from spec019_harness import OpenWindow, window_opener
from spec028_harness import recap_body
from spec042_harness import box_of
from spec043_harness import fr_value, same_position, style_of
from spec044_harness import solved_frame
from spec046_harness import button_colour_problems
from spec047_harness import (
    COMPUTER,
    MUTED,
    PHONE,
    RECAP,
    RED,
    RULE,
    SHARE_PATH,
    SIZE_IDS,
    SIZES,
    border_problems,
    click_recap_open,
    frame_problems,
    open_loaded_recap,
    open_solved,
    open_solved_held,
    padding_problems,
    parts_of,
    radius_problems,
    right_on_content_edge,
    type_problems,
)

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- Setup -------------------------------------------------------------------------


def open_share(
    window: OpenWindow,
    base_url: str,
    grid: Grid,
    size: tuple[int, int],
    body: object = RECAP,
) -> Page:
    """`SOLVED` at `size` (desktop) with the route answering `body`, recap open."""
    page = window(size[0], size[1], False)
    open_solved(page, base_url, solved_frame(grid), body=body)
    open_loaded_recap(page)
    return page


def open_loading(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int]
) -> Page:
    """`SOLVED` at `size` with the route held; the recap open and loading."""
    page = window(size[0], size[1], False)
    open_solved_held(page, base_url, solved_frame(grid))
    click_recap_open(page)
    expect(page.get_by_test_id("recap-loading")).to_be_visible()
    return page


def open_unavailable(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int]
) -> Page:
    """`SOLVED` at `size` with the route answering 404; the recap open."""
    page = window(size[0], size[1], False)
    open_solved(
        page, base_url, solved_frame(grid), body={"detail": "Not Found"}, status=404
    )
    click_recap_open(page)
    expect(page.get_by_test_id("recap-error")).to_be_visible()
    return page


def short_gaps(page: Page) -> list[str]:
    """The gaps of the dialog's parts under 14 px (1 px)."""
    found: list[str] = []
    for upper, lower in pairwise(parts_of(page.get_by_test_id("recap"))):
        gap = lower.box.top - upper.box.bottom
        if gap < 14.0 - 1.0:
            found.append(f"{upper.name} -> {lower.name}: {gap} px")
    return found


# ---- AC-10: the share row ------------------------------------------------------


def test_ac10_at_1280_the_link_and_copy_share_one_row_8_px_apart(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_share(window, live_server, fx01_grid, COMPUTER)
    row = page.get_by_test_id("recap-share-row")

    parts = parts_of(row)

    assert [part.name for part in parts] == ["recap-share-link", "recap-copy"]
    link_box, copy_box = parts[0].box, parts[1].box
    assert abs(link_box.centre_y - copy_box.centre_y) <= 1.0, parts
    assert same_position(copy_box.left - link_box.right, 8.0), parts
    assert same_position(link_box.left, box_of(row).left), (link_box, box_of(row))


def test_ac10_the_link_holds_the_share_url(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_share(window, live_server, fx01_grid, COMPUTER)
    link = page.get_by_test_id("recap-share-link")

    url = f"{live_server}{SHARE_PATH}"
    expect(link).to_have_attribute("href", url)
    expect(link).to_have_text(url)


def test_ac10_the_link_is_the_designs_url_box(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_share(window, live_server, fx01_grid, COMPUTER)
    link = page.get_by_test_id("recap-share-link")

    problems = border_problems(link, "recap-share-link", "1px", RULE)
    problems += radius_problems(link, "recap-share-link", ["6px"] * 4)
    problems += padding_problems(link, "recap-share-link", "8px 10px")
    problems += type_problems(link, "recap-share-link", size=13.6)
    styles = {
        "whiteSpace": "nowrap",
        "overflowX": "hidden",
        "overflowY": "hidden",
        "textOverflow": "ellipsis",
    }
    for name, expected in styles.items():
        if style_of(link, name) != expected:
            problems.append(f"recap-share-link: {name} {style_of(link, name)}")

    assert problems == []


def test_ac10_copy_reads_copier_le_lien_and_is_secondary(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_share(window, live_server, fx01_grid, COMPUTER)
    copy = page.get_by_test_id("recap-copy")

    expect(copy).to_have_text(fr_value("room.share.copy"))
    problems = button_colour_problems(copy, "secondary")
    problems += padding_problems(copy, "recap-copy", "8px 12px")

    assert problems == []


def test_ac10_at_360_copy_goes_under_the_full_width_link(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_share(window, live_server, fx01_grid, PHONE)
    row = page.get_by_test_id("recap-share-row")

    expect(row).to_have_count(1)
    row_box = box_of(row)
    link_box = box_of(page.get_by_test_id("recap-share-link"))
    copy_box = box_of(page.get_by_test_id("recap-copy"))

    assert same_position(link_box.width, row_box.width), (link_box, row_box)
    assert same_position(copy_box.left, row_box.left), (copy_box, row_box)
    assert same_position(copy_box.top - link_box.bottom, 8.0), (link_box, copy_box)


def test_ac10_without_a_share_path_no_share_heading_and_no_row(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_share(
        window, live_server, fx01_grid, COMPUTER, body=recap_body(share_path=None)
    )

    expect(page.get_by_test_id("recap-players")).to_be_visible()
    expect(page.get_by_test_id("recap-share-heading")).to_have_count(0)
    expect(page.get_by_test_id("recap-share-row")).to_have_count(0)


# ---- AC-11: loading --------------------------------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac11_while_loading_the_dialog_has_the_frame_of_ac7(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_loading(window, live_server, fx01_grid, size)

    assert frame_problems(page, size) == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac11_while_loading_it_holds_the_title_the_loading_line_and_fermer(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_loading(window, live_server, fx01_grid, size)

    names = [part.name for part in parts_of(page.get_by_test_id("recap"))]

    assert names == ["h2", "recap-loading", "recap-close"]
    assert short_gaps(page) == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac11_the_loading_line_is_a_muted_status(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_loading(window, live_server, fx01_grid, size)
    loading = page.get_by_test_id("recap-loading")

    expect(loading).to_have_text(fr_value("recap.loading"))
    expect(loading).to_have_attribute("role", "status")
    assert type_problems(loading, "recap-loading", size=15.2, colour=MUTED) == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac11_while_loading_fermer_is_primary_and_right_aligned(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_loading(window, live_server, fx01_grid, size)
    close = page.get_by_test_id("recap-close")

    problems = button_colour_problems(close, "primary")
    problems += right_on_content_edge(page, "recap-close")

    assert problems == []


# ---- AC-11: unavailable -----------------------------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac11_when_unavailable_the_dialog_has_the_frame_of_ac7(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_unavailable(window, live_server, fx01_grid, size)

    assert frame_problems(page, size) == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac11_when_unavailable_it_holds_the_title_the_error_line_and_fermer(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_unavailable(window, live_server, fx01_grid, size)

    names = [part.name for part in parts_of(page.get_by_test_id("recap"))]

    assert names == ["h2", "recap-error", "recap-close"]
    assert short_gaps(page) == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac11_the_error_line_is_a_red_alert(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_unavailable(window, live_server, fx01_grid, size)
    error = page.get_by_test_id("recap-error")

    expect(error).to_have_text(fr_value("recap.error"))
    expect(error).to_have_attribute("role", "alert")
    problems = type_problems(
        error, "recap-error", size=13.6, weight="500", colour=RED, line_height=17.68
    )
    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac11_when_unavailable_fermer_is_primary_and_right_aligned(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_unavailable(window, live_server, fx01_grid, size)
    close = page.get_by_test_id("recap-close")

    problems = button_colour_problems(close, "primary")
    problems += right_on_content_edge(page, "recap-close")

    assert problems == []
