"""Tests of spec 021, AC-9 and AC-10: the marker's look, and the flag button from
the keyboard and in French.

AC-9 on the page with a mocked socket: the `clue-flag` of IDES on FX-01 at 1280 by
720, and of the first clue of FX-02 at 360 by 740 and 568 by 320, lies inside its
clue cell, is visible, is a square of side `max(8, 0.22 s)`, and leaves the
`clue-text` where it was before the flag arrived; at 1280 by 720 spec 035's
contrast scan finds no offender. AC-9 also measures the marker of NAVAL, the clue
of index 1 of (0, 0), at 1280 by 720: the same checks, and the marker just under
the cell's `clue-separator`. AC-10: the three `fr.json` texts; `tab_to` reaches
`flag-button` with spec 035 AC-2's outline and `Enter` flags MIME; the language
and contrast scans with `p2`'s flag on IDES at 1280 by 720 and 360 by 740. The
shared setup is in `spec021_harness`.

Spec 042 (the design's grid cells) refines AC-1, AC-9 and AC-10: `clue-flag`
holds the flag icon and no text (`fr.json["flag.marker"]` is gone); AC-9 checks
the square's side (`s` the clue cell's side, 0.5 px) instead of a font size and
drops the check that NAVAL's marker is clear of its text (the design draws the
flag over the text's corner); the scans of AC-9 and AC-10 no longer meet the
marker's glyph.

Spec 043 (the design's room layout) refines AC-10: the button shows no text, so the
scans meet its `aria-label` and no longer `Je bloque` (`flag.button` is removed);
its focus ring is the white ring of the navy clue bar, which spec 035 AC-2 now
measures against the surface behind it (`tests/colour_contrast.js`); and spec 035
AC-9's checker flags the sample `Salle` where it flagged `Salon`, which is now
`fr.json["topbar.salon"]`.
"""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import ClueCell, Grid
from nock.protocol import ClueRef, Flag, FlagView, grid_view, parse_client_message
from spec021_harness import (
    FLAG_BUTTON_LABEL,
    IDES,
    MIME,
    NAVAL,
    clue_at,
    expect_marker,
    flag_changed_frame,
    flag_label,
    frames_sent_by,
    open_flag_room,
    select_word,
)
from spec024_harness import (
    contrast_problems,
    expect_seq,
    grid_from_text,
    language_data,
    language_problems,
    load_fr,
    make_catalogue,
    make_walker,
    open_context_page,
    outline_problems,
)
from spec035_harness import (
    LANGUAGE_SCAN_SCRIPT,
    contrast_measurements,
    unknown_texts,
)

TOLERANCE_PX = 1.0
SIZE_TOLERANCE_PX = 0.5
NICKNAMES = ["Ana", "Bob", "Cy"]
MARKER_CASES = [("FX-01", 1280, 720), ("FX-02", 360, 740), ("FX-02", 568, 320)]

# The boxes of a clue's cell, the cell's `clue-separator` (null when it has
# none), the clue's `clue-text` and its `clue-flag`, with the marker's computed
# visibility. A box is [left, top, right, bottom].
GEOMETRY_SCRIPT = r"""
clue => {
  const box = (element) => {
    const rect = element.getBoundingClientRect();
    return [rect.left, rect.top, rect.right, rect.bottom];
  };
  const cell = clue.closest('[data-testid="cell"]');
  const separator = cell.querySelector('[data-testid="clue-separator"]');
  const text = clue.querySelector('[data-testid="clue-text"]');
  const markers = clue.querySelectorAll('[data-testid="clue-flag"]');
  const result = {
    cell: box(cell),
    separator: separator === null ? null : box(separator),
    text: box(text),
    markers: markers.length,
  };
  if (markers.length === 1) {
    const style = getComputedStyle(markers[0]);
    result.marker = box(markers[0]);
    result.visibility = style.visibility;
  }
  return result;
}
"""

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return grid_from_text(fx02_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


# ---- Helpers ----


def first_clue_of(grid: Grid) -> ClueRef:
    """The first clue of a grid: its first clue cell in row-major order, index 0."""
    positions: list[tuple[int, int]] = []
    for cell in grid.cells:
        if isinstance(cell, ClueCell):
            positions.append((cell.row, cell.column))
    row, column = min(positions)
    return ClueRef(row=row, column=column, clue_index=0)


def read_geometry(page: Page, clue: ClueRef) -> dict[str, Any]:
    """The boxes of a clue (a JSON object from the page, hence `Any`)."""
    reading = clue_at(page, clue).evaluate(GEOMETRY_SCRIPT)
    assert isinstance(reading, dict)
    return reading


def marker_problems(reading: dict[str, Any]) -> list[str]:
    """How a clue's `clue-flag` breaks "Look" of "Client: the clue marker"."""
    if reading["markers"] != 1:
        return [f"{reading['markers']} clue-flag elements"]
    problems: list[str] = []
    cell_left, cell_top, cell_right, cell_bottom = reading["cell"]
    left, top, right, bottom = reading["marker"]
    inside = (
        left >= cell_left - TOLERANCE_PX
        and top >= cell_top - TOLERANCE_PX
        and right <= cell_right + TOLERANCE_PX
        and bottom <= cell_bottom + TOLERANCE_PX
    )
    if not inside:
        problems.append(f"marker {reading['marker']} outside cell {reading['cell']}")
    if reading["visibility"] != "visible":
        problems.append(f"visibility {reading['visibility']!r}")
    # Spec 042: the marker is a square of side max(8px, 0.22 s), s the clue
    # cell's side.
    side = max(8.0, 0.22 * (cell_right - cell_left))
    for name, size in (("width", right - left), ("height", bottom - top)):
        if abs(size - side) > SIZE_TOLERANCE_PX:
            problems.append(f"{name} {size} px, expected {side:.2f}")
    return problems


def moved_edges(before: list[float], after: list[float]) -> list[str]:
    """The edges of a box that moved by more than TOLERANCE_PX."""
    names = ["left", "top", "right", "bottom"]
    moved: list[str] = []
    for index, name in enumerate(names):
        if abs(after[index] - before[index]) > TOLERANCE_PX:
            moved.append(f"{name}: {before[index]} -> {after[index]}")
    return moved


def under_separator_problems(reading: dict[str, Any]) -> list[str]:
    """How a clue's `clue-flag` is not just under its cell's `clue-separator`.

    Its top must be at least the separator's bottom minus TOLERANCE_PX, and at
    most a tenth of the cell's height below the separator's bottom (AC-9).
    """
    if reading["separator"] is None:
        return ["the clue cell has no clue-separator"]
    separator_bottom = reading["separator"][3]
    marker_top = reading["marker"][1]
    cell_height = reading["cell"][3] - reading["cell"][1]
    problems: list[str] = []
    if marker_top < separator_bottom - TOLERANCE_PX:
        problems.append(f"marker top {marker_top} above separator {separator_bottom}")
    if marker_top > separator_bottom + cell_height / 10:
        problems.append(
            f"marker top {marker_top} more than a tenth of the cell's height"
            f" ({cell_height}) under separator {separator_bottom}"
        )
    return problems


def measured_texts(page: Page) -> list[str]:
    """The texts that spec 035's contrast scan measured."""
    texts: list[str] = []
    for measurement in contrast_measurements(page):
        texts.append(measurement["text"])
    return texts


def language_texts(page: Page) -> list[str]:
    """The texts that spec 035's language scan reads."""
    texts = page.evaluate(LANGUAGE_SCAN_SCRIPT)
    assert isinstance(texts, list)
    return texts


def assert_scans_pass_with_the_flag_texts(page: Page, live_server: str) -> None:
    """The language and contrast scans pass, and they read the flag texts.

    Spec 042: the marker shows no glyph any more, so the scans do not meet it.
    """
    texts = language_texts(page)
    for expected in (FLAG_BUTTON_LABEL, flag_label(["Bob"])):
        assert expected in texts, expected
    data = language_data(live_server, NICKNAMES)
    assert language_problems(page, data) == []
    assert contrast_problems(page) == []


# ---- AC-9 ----


@pytest.mark.parametrize(
    ("grid_name", "width", "height"),
    MARKER_CASES,
    ids=[f"{name}-{width}x{height}" for name, width, height in MARKER_CASES],
)
def test_ac9_browser_the_marker_sits_in_its_clue_cell_and_keeps_the_clue_text(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    fx02_grid: Grid,
    grid_name: str,
    width: int,
    height: int,
) -> None:
    grid = fx01_grid if grid_name == "FX-01" else fx02_grid
    clue = IDES if grid_name == "FX-01" else first_clue_of(fx02_grid)
    page, close = open_context_page(browser, browser_name, width, height, False)
    try:
        mock = open_flag_room(page, live_server, grid_view(grid))
        before = read_geometry(page, clue)
        assert before["markers"] == 0

        mock.send(flag_changed_frame(6, "p2", clue))
        expect_seq(page, 6)
        expect(clue_at(page, clue)).to_have_attribute("data-flagged", "true")
        page.wait_for_timeout(300)
        after = read_geometry(page, clue)

        assert marker_problems(after) == []
        assert moved_edges(before["text"], after["text"]) == []
        if grid_name == "FX-01":
            assert contrast_problems(page) == []
    finally:
        close()


def test_ac9_browser_the_marker_of_a_second_clue_sits_just_under_the_separator(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> None:
    page, close = open_context_page(browser, browser_name, 1280, 720, False)
    try:
        mock = open_flag_room(page, live_server, grid_view(fx01_grid))
        before = read_geometry(page, NAVAL)
        assert before["markers"] == 0

        mock.send(flag_changed_frame(6, "p2", NAVAL))
        expect_seq(page, 6)
        expect(clue_at(page, NAVAL)).to_have_attribute("data-flagged", "true")
        page.wait_for_timeout(300)
        after = read_geometry(page, NAVAL)

        assert marker_problems(after) == []
        assert moved_edges(before["text"], after["text"]) == []
        assert under_separator_problems(after) == []
    finally:
        close()


# ---- AC-10 ----


def test_ac10_fr_json_holds_the_three_flag_texts() -> None:
    fr = load_fr()

    assert "flag.button" not in fr
    assert fr.get("flag.button_label") == "Je bloque sur ce mot"
    # Spec 042: the marker is a drawn icon, so `flag.marker` is removed.
    assert "flag.marker" not in fr
    assert fr.get("flag.marker_label") == "Bloqué : {names}"
    english = ["Loading…", "Salle", "Check word"]
    assert unknown_texts(english, set()) == english


def test_ac10_browser_tab_reaches_the_flag_button_and_enter_flags_the_word(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> None:
    page, close = open_context_page(browser, browser_name, 1280, 720, False)
    try:
        ides_flag = FlagView(player_id="p2", clue=IDES)
        flags = [ides_flag]
        mock = open_flag_room(page, live_server, grid_view(fx01_grid), flags=flags)
        expect_marker(page, IDES, "p2", ["Bob"])
        select_word(page, MIME)
        walker = make_walker(page)

        walker.tab_to("flag-button")
        reached = walker.reached[-1]
        frames = frames_sent_by(page, mock, lambda: page.keyboard.press("Enter"))

        assert reached.test_id == "flag-button"
        problems = outline_problems(
            reached.outline_style, reached.outline_width, reached.outline_contrast
        )
        assert problems == []
        assert len(frames) == 1, frames
        assert parse_client_message(frames[0]) == Flag(clue=MIME)
        assert_scans_pass_with_the_flag_texts(page, live_server)
    finally:
        close()


def test_ac10_browser_on_a_phone_window_the_flag_texts_are_french_and_readable(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> None:
    page, close = open_context_page(browser, browser_name, 360, 740, False)
    try:
        ides_flag = FlagView(player_id="p2", clue=IDES)
        open_flag_room(page, live_server, grid_view(fx01_grid), flags=[ides_flag])
        expect_marker(page, IDES, "p2", ["Bob"])
        expect(page.get_by_test_id("flag-button")).to_have_count(1)

        assert_scans_pass_with_the_flag_texts(page, live_server)
    finally:
        close()
