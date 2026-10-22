"""Tests of spec 044, AC-9 to AC-11: the keyboard on a solved page, the place of
the completion status, and the scans.

AC-9: once the grid is solved the keyboard goes away, « Clavier » is disabled, and
`grid-status` is the band under the clue bar with the primary « Voir le bilan »;
a page opened solved never shows a keyboard, and a phone held sideways is then in
the column layout. AC-10: the full-but-wrong status shares the clue bar's row only
while the keyboard shows on a low window. AC-11: spec 035's contrast and language
scans in the keyboard's states, and the `fr.json` keys.

Also tested, from "Edge cases and errors": solving keeps the stored choice and the
top bar's buttons in place, and a portrait low window without the keyboard (a
desktop window 480 by 480) has the band.

Choices where the spec leaves room:

- "Never shows a `keyboard`" (AC-9): an observer, installed before the page's
  scripts, records whether an element with `data-testid="keyboard"` is ever added
  to the document; it is read once the snapshot shows and 300 ms more passed.
- "Under the clue bar" (AC-9 at 740 by 360 and 568 by 320) is AC-9's own reading
  at 360 by 740: the status's top on `clue-bar`'s bottom (1 px), its bottom at
  most `window.innerHeight` (1 px).
- AC-11's language scan accepts the room code, its link, the nicknames as the
  page shows them and their two first letters, and FX-01's clue texts (spec 024's
  `language_data`).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from spec019_harness import OpenWindow, window_opener
from spec024_harness import contrast_problems, language_data, language_problems
from spec042_harness import box_of, to_box
from spec043_harness import (
    DISPLAY_NICKNAMES,
    MUTED,
    NAVY,
    PHONE,
    WHITE,
    Box,
    RoomMock,
    colour_matches,
    expect_colour,
    expect_layout,
    load_fr,
    open_room,
    parts_of,
    press_cell,
    same_position,
    stored_value,
    style_of,
)
from spec044_harness import (
    KEYBOARD_HIDDEN_KEY,
    LOW_TOUCH_IDS,
    LOW_TOUCH_WINDOWS,
    bar_buttons,
    disabled_clavier_problems,
    expect_keyboard_shows,
    expect_no_keyboard,
    full_wrong_frame,
    fx01_frame,
    open_fx01,
    solve_frames,
    solved_frame,
    tap_toggle,
    window_height,
)

FOLLOW_MS = 300  # "within 300 ms"
QUIET_MS = 300
PORTRAIT_LOW_WINDOW = (480, 480)

# Records whether a `keyboard` element is ever added to the document.
KEYBOARD_WATCH_SCRIPT = r"""
(() => {
  window.__spec044KeyboardSeen = false;
  const seen = node => node.nodeType === Node.ELEMENT_NODE
    && (node.matches('[data-testid="keyboard"]')
      || node.querySelector('[data-testid="keyboard"]') !== null);
  const observer = new MutationObserver(records => {
    for (const record of records) {
      for (const node of record.addedNodes) {
        if (seen(node)) {
          window.__spec044KeyboardSeen = true;
        }
      }
    }
  });
  observer.observe(document, {childList: true, subtree: true});
})();
"""

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def solve(page: Page, mock: RoomMock) -> None:
    """The mock sends `p2`'s `T` at (4, 4) (seq 6), then `grid_solved` (seq 7)."""
    for frame in solve_frames():
        mock.send(frame)


def expect_status(page: Page, state: str) -> None:
    expect(page.get_by_test_id("grid-status")).to_have_attribute("data-state", state)


def band_problems(page: Page) -> list[str]:
    """How `grid-status` differs from the band under the clue bar (1 px)."""
    status = box_of(page.get_by_test_id("grid-status"))
    bar = box_of(page.get_by_test_id("clue-bar"))
    problems: list[str] = []
    if not same_position(status.top, bar.bottom):
        problems.append(f"grid-status {status} is not on clue-bar's bottom {bar}")
    if status.bottom > window_height(page) + 1.0:
        problems.append(f"grid-status {status} goes below the window")
    return problems


def primary_recap_problems(page: Page) -> list[str]:
    """`recap-open` inside `grid-status`, with the primary button's colours."""
    button = page.get_by_test_id("grid-status").get_by_test_id("recap-open")
    if button.count() != 1:
        return [f"{button.count()} recap-open in grid-status"]
    parts = parts_of(button)
    problems: list[str] = []
    if not colour_matches(parts["background"], NAVY):
        problems.append(f"recap-open background {parts['background']}")
    expect_colour(button, "color", WHITE)
    return problems


def in_row_problems(page: Page) -> list[str]:
    """How `grid-status` is not inside `clue-bar`, after its text, before Réagir."""
    status = box_of(page.get_by_test_id("grid-status"))
    bar = box_of(page.get_by_test_id("clue-bar"))
    text = box_of(page.get_by_test_id("clue-bar-text"))
    react = box_of(page.get_by_test_id("react-button"))
    problems: list[str] = []
    inside = (
        status.left >= bar.left - 1.0
        and status.right <= bar.right + 1.0
        and status.top >= bar.top - 1.0
        and status.bottom <= bar.bottom + 1.0
    )
    if not inside:
        problems.append(f"grid-status {status} is not inside clue-bar {bar}")
    if status.left < text.right - 1.0:
        problems.append(f"grid-status {status} starts left of clue-bar-text {text}")
    if status.right > react.left + 1.0:
        problems.append(f"grid-status {status} ends right of react-button {react}")
    return problems


def bar_button_boxes(page: Page) -> dict[str, Box]:
    boxes: dict[str, Box] = {}
    for item in bar_buttons(page):
        boxes[str(item["testId"])] = to_box(item["box"])
    return boxes


# ---- AC-9: the keyboard goes away once the grid is solved ----


def test_ac9_solving_removes_the_keyboard_and_disables_clavier(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_fx01(window, live_server, full_wrong_frame(fx01_grid))
    expect_status(page, "full_wrong")
    expect_keyboard_shows(page)

    solve(page, mock)

    expect_no_keyboard(page, timeout=FOLLOW_MS)
    expect(page.get_by_test_id("keyboard-toggle")).to_be_disabled()
    assert disabled_clavier_problems(page) == []
    assert stored_value(page, KEYBOARD_HIDDEN_KEY) is None


def test_ac9_once_solved_the_status_is_the_band_with_the_primary_voir_le_bilan(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_fx01(window, live_server, full_wrong_frame(fx01_grid))
    expect_keyboard_shows(page)

    solve(page, mock)
    expect_status(page, "solved")
    expect_no_keyboard(page)

    assert band_problems(page) == []
    assert primary_recap_problems(page) == []


def test_ac9_disabled_clavier_has_a_muted_icon_and_the_not_allowed_cursor(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    # « Clavier » "Once the grid is solved": spec 043's disabled top-bar look.
    page, mock = open_fx01(window, live_server, full_wrong_frame(fx01_grid))
    expect_keyboard_shows(page)

    solve(page, mock)
    toggle = page.get_by_test_id("keyboard-toggle")
    expect(toggle).to_be_disabled()

    svgs = parts_of(toggle)["svgs"]
    assert len(svgs) == 1, svgs
    problems: list[str] = []
    for shape in svgs[0]["shapes"]:
        stroke = shape["strokeColour"]
        if stroke is None or not colour_matches(stroke, MUTED):
            problems.append(f"{shape['tag']} stroke {shape['stroke']}")
    assert problems == []
    assert style_of(toggle, "cursor") == "not-allowed"


def test_ac9_solving_keeps_the_stored_choice_and_the_top_bar_in_place(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    # Edge case "Solving": the top bar does not move; the stored choice stays.
    page, mock = open_fx01(
        window, live_server, full_wrong_frame(fx01_grid), keyboard_hidden=True
    )
    expect_status(page, "full_wrong")
    expect_no_keyboard(page)
    before = bar_button_boxes(page)

    solve(page, mock)
    expect(page.get_by_test_id("keyboard-toggle")).to_be_disabled()

    after = bar_button_boxes(page)
    assert stored_value(page, KEYBOARD_HIDDEN_KEY) == "true"
    assert list(after) == list(before)
    for test_id, box in before.items():
        moved = after[test_id]
        assert same_position(moved.left, box.left), (test_id, box, moved)
        assert same_position(moved.top, box.top), (test_id, box, moved)


def test_ac9_a_page_opened_solved_never_shows_a_keyboard(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(PHONE[0], PHONE[1], True)
    page.context.add_init_script(KEYBOARD_WATCH_SCRIPT)
    open_room(page, live_server, solved_frame(fx01_grid))
    expect_status(page, "solved")
    press_cell(page, 1, 0, touch=True)
    page.wait_for_timeout(QUIET_MS)

    seen = page.evaluate("() => window.__spec044KeyboardSeen")

    assert seen is False
    expect(page.get_by_test_id("keyboard")).to_have_count(0)


@pytest.mark.parametrize(("width", "height"), LOW_TOUCH_WINDOWS, ids=LOW_TOUCH_IDS)
def test_ac9_a_solved_phone_held_sideways_has_the_column_layout_and_the_band(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page, _ = open_fx01(window, live_server, solved_frame(fx01_grid), (width, height))
    expect_status(page, "solved")

    expect_layout(page, "column")
    expect(page.get_by_test_id("keyboard")).to_have_count(0)
    assert band_problems(page) == []
    assert primary_recap_problems(page) == []


# ---- AC-10: the status in the clue bar's row only while the keyboard shows ----


@pytest.mark.parametrize(("width", "height"), LOW_TOUCH_WINDOWS, ids=LOW_TOUCH_IDS)
def test_ac10_full_but_wrong_with_the_keyboard_on_a_low_window_sits_in_the_row(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page, _ = open_fx01(
        window, live_server, full_wrong_frame(fx01_grid), (width, height)
    )
    press_cell(page, 1, 1, touch=True)
    expect_status(page, "full_wrong")

    expect_layout(page, "sheet")
    expect_keyboard_shows(page)
    assert in_row_problems(page) == []
    expect(page.get_by_test_id("recap-open")).to_have_count(0)


@pytest.mark.parametrize(("width", "height"), LOW_TOUCH_WINDOWS, ids=LOW_TOUCH_IDS)
def test_ac10_with_the_keyboard_hidden_on_a_low_window_the_status_is_the_band(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page, _ = open_fx01(
        window,
        live_server,
        full_wrong_frame(fx01_grid),
        (width, height),
        keyboard_hidden=True,
    )
    press_cell(page, 1, 1, touch=True)
    expect_status(page, "full_wrong")

    expect_layout(page, "column")
    status = box_of(page.get_by_test_id("grid-status"))
    bar = box_of(page.get_by_test_id("clue-bar"))
    assert same_position(status.top, bar.bottom), (status, bar)


def test_ac10_on_a_phone_the_band_sits_between_the_clue_bar_and_the_keyboard(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_fx01(window, live_server, full_wrong_frame(fx01_grid))
    expect_status(page, "full_wrong")
    expect_keyboard_shows(page)

    status = box_of(page.get_by_test_id("grid-status"))
    bar = box_of(page.get_by_test_id("clue-bar"))
    keyboard = box_of(page.get_by_test_id("keyboard"))

    assert same_position(status.top, bar.bottom), (status, bar)
    assert same_position(keyboard.top, status.bottom), (keyboard, status)


def test_ac10_a_portrait_low_desktop_window_has_the_band_under_the_clue_bar(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    # Edge case "A portrait low window without the keyboard".
    page, _ = open_fx01(
        window,
        live_server,
        full_wrong_frame(fx01_grid),
        PORTRAIT_LOW_WINDOW,
        touch=False,
    )
    expect_status(page, "full_wrong")

    assert band_problems(page) == []


# ---- AC-11: the scans and fr.json ----

SCAN_STATES = [
    "shown",
    "pencil",
    "hidden",
    "hidden-sideways",
    "full-wrong",
]


def open_scan_state(window: OpenWindow, base_url: str, grid: Grid, state: str) -> Page:
    """Open the page of AC-11 in one of its states, the touch context."""
    if state == "full-wrong":
        page, _ = open_fx01(window, base_url, full_wrong_frame(grid))
        expect_status(page, "full_wrong")
        expect_keyboard_shows(page)
        return page
    size = (740, 360) if state == "hidden-sideways" else PHONE
    page, _ = open_fx01(window, base_url, fx01_frame(grid), size)
    expect_keyboard_shows(page)
    if state == "pencil":
        page.get_by_test_id("key-pencil").tap()
        expect(page.get_by_test_id("key-pencil")).to_have_attribute(
            "aria-pressed", "true"
        )
    elif state.startswith("hidden"):
        tap_toggle(page)
        expect_no_keyboard(page)
        if state == "hidden-sideways":
            expect_layout(page, "column")
    return page


@pytest.mark.parametrize("state", SCAN_STATES)
def test_ac11_the_contrast_scan_finds_no_offender(
    window: OpenWindow, live_server: str, fx01_grid: Grid, state: str
) -> None:
    page = open_scan_state(window, live_server, fx01_grid, state)

    assert contrast_problems(page) == []


@pytest.mark.parametrize("state", SCAN_STATES)
def test_ac11_the_language_scan_finds_no_offender(
    window: OpenWindow, live_server: str, fx01_grid: Grid, state: str
) -> None:
    page = open_scan_state(window, live_server, fx01_grid, state)
    expect(page.locator("html")).to_have_attribute("lang", "fr")

    data = language_data(live_server, DISPLAY_NICKNAMES)

    assert language_problems(page, data) == []


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("keyboard.swap", "Changer de sens"),
        ("keyboard.label", "Clavier"),
        ("keyboard.delete", "Effacer"),
    ],
)
def test_ac11_fr_json_holds_the_keys_of_the_keyboard(key: str, value: str) -> None:
    assert load_fr().get(key) == value
