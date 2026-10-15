"""Tests of spec 020, AC-7: the pencil controls and pencil letters meet spec 035
and keep the grid's room.

Four parts, all on the page with a mocked socket:

- the toolbar at the eight window sizes of spec 006 AC-5, in desktop and touch
  contexts, with spec 013 AC-6's setup: spec 013 AC-6's layout checks, the
  relative order (`undo-button`, `pencil-toggle`, `confirm-pencil`, then
  spec 024's `check-letter`; the lead's note of 2026-10-15 on spec 024 AC-8),
  one row on small windows, the keyboard focus of `pencil-toggle` (desktop) and
  `elementFromPoint` at each button's centre. One page per size and context, so
  that the suite stays lean;
- the keyboard-only run at 1280 by 720 (spec 035's walker);
- the contrast states of the spec's "Test harness" (spec 035's contrast scan) and
  the language scan of the two buttons' texts, with the new `fr.json` keys;
- the edge case "Solved grid" (AC-3, AC-7): both controls disabled, and spec
  026's input lock sends nothing in pencil mode.

Not tested: the keyboard focus of `confirm-pencil` in spec 013 AC-6's setup. The
tapped (3, 1) is empty, so the button is disabled there (it is enabled only on a
pencil letter) and cannot take the focus; the keyboard-only run checks its
outline instead. The shared setup is in `spec020_harness` and `spec024_harness`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import (
    CheckResult,
    ConfirmPencil,
    Direction,
    GridTarget,
    PencilEdit,
    PlayerState,
    PlayerView,
    Selection,
)
from spec020_harness import (
    confirm_button,
    edit_messages_after_a_pause,
    expect_cell_shows,
    grid_solved_frame,
    letter_changed_frame,
    pencil_toggle,
    tap,
    turn_pencil_mode_on,
    wait_for_edit_messages,
)
from spec024_harness import (
    COLOUR_CONTRAST_JS,
    LAST_CELL,
    ROW_MAJOR,
    SETTLE_MS,
    SOLUTION,
    WAIT_TIMEOUT_MS,
    ChangeList,
    cell_at,
    contrast_problems,
    expect_selection,
    expect_seq,
    grid_from_text,
    language_data,
    load_fr,
    make_catalogue,
    make_walker,
    open_context_page,
    open_room,
    outline_problems,
    player_view,
)
from spec035_harness import LANGUAGE_SCAN_SCRIPT, unknown_texts

WINDOW_SIZES = [
    (320, 568),
    (568, 320),
    (360, 740),
    (740, 360),
    (768, 1024),
    (1024, 768),
    (1280, 800),
    (1920, 1080),
]
SMALL_WINDOWS = WINDOW_SIZES[:4]
CONTEXTS = ["desktop", "touch"]
PENCIL_BUTTONS = ["pencil-toggle", "confirm-pencil"]
SPEC024_BUTTONS = [
    "undo-button",
    "check-letter",
    "check-word",
    "check-grid",
    "reveal-letter",
    "reveal-word",
]
# Relative document order (spec 024's toolbar: the pencil controls come right
# after the undo control and before `check-panel`).
TOOLBAR_ORDER = ["undo-button", "pencil-toggle", "confirm-pencil", "check-letter"]
EIGHT_NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve", "Fay", "Gus", "Hal"]
FEED_ITEMS = 100
MIN_GRID_VIEWPORT_PX = 100.0
EPSILON = 1.0
MAX_TABS = 60
WORD_W1 = "0,0,0"
WORD_W7 = "3,0,0"
COLOURS = list(range(8))
NEW_KEYS = {
    "pencil.toggle": "Crayon",
    "pencil.confirm": "Confirmer",
    "pencil.confirm_label": "Confirmer la lettre au crayon",
}


def size_ids(sizes: list[tuple[int, int]]) -> list[str]:
    return [f"{width}x{height}" for width, height in sizes]


def pencil_letter(letter: str, author: str) -> dict[str, object]:
    """The update of a snapshot cell that holds a pencil letter."""
    return {"letter": letter, "pencil": True, "author": author}


# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


@pytest.fixture
def new_page(browser: Browser) -> Iterator[Callable[[int, int], Page]]:
    """Return `new_page(width, height)`, a page in a fresh context of that size."""
    contexts: list[BrowserContext] = []

    def make(width: int, height: int) -> Page:
        context = browser.new_context(viewport={"width": width, "height": height})
        contexts.append(context)
        return context.new_page()

    yield make
    for context in contexts:
        context.close()


# ---- The setup of spec 013 AC-6 (as spec 024 AC-8) ----


def eight_players() -> list[PlayerView]:
    players = [player_view("p1", "Ana", 0, is_host=True)]
    for number in range(2, 9):
        nickname = EIGHT_NICKNAMES[number - 1]
        players.append(player_view(f"p{number}", nickname, number - 1))
    return players


def check_frame(seq: int) -> str:
    event = CheckResult(
        seq=seq, player_id="p2", target=GridTarget(), correct=(), wrong=()
    )
    return event.model_dump_json()


def open_toolbar_room(
    browser: Browser,
    browser_name: str,
    live_server: str,
    grid: Grid,
    width: int,
    height: int,
    touch: bool,
) -> tuple[Page, Callable[[], None]]:
    """Open the room of the setup with (3, 1) tapped; return the page, its closer."""
    page, close = open_context_page(browser, browser_name, width, height, touch)
    try:
        mock = open_room(page, live_server, grid, players=eight_players())
        expect(page.get_by_test_id("room-toolbar")).to_be_visible()
        last_seq = 5 + FEED_ITEMS
        for seq in range(6, last_seq + 1):
            mock.send(check_frame(seq))
        expect_seq(page, last_seq)
        cell = cell_at(page, 3, 1)
        if touch:
            cell.tap(timeout=WAIT_TIMEOUT_MS)
        else:
            cell.click(timeout=WAIT_TIMEOUT_MS)
        expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", WORD_W7)
        expect(pencil_toggle(page)).to_be_visible()
        expect(confirm_button(page)).to_be_visible()
    except BaseException:
        close()
        raise
    return page, close


def spec013_layout_problems(page: Page, touch: bool) -> list[str]:
    """How the page breaks spec 013 AC-6's checks (as spec 024 AC-8 reads them)."""
    viewport = page.get_by_test_id("grid-viewport")
    viewport_box = viewport.bounding_box()
    bar_box = page.get_by_test_id("clue-bar").bounding_box()
    grid_box = page.get_by_test_id("grid").bounding_box()
    assert viewport_box is not None
    assert bar_box is not None
    assert grid_box is not None
    sizes = page.evaluate(
        "() => [document.documentElement.scrollWidth, window.innerWidth,"
        " document.documentElement.scrollHeight, window.innerHeight]"
    )
    scroll_width, window_width, scroll_height, window_height = sizes
    zoom = viewport.get_attribute("data-zoom")

    problems: list[str] = []
    if viewport_box["height"] < MIN_GRID_VIEWPORT_PX:
        problems.append(f"grid-viewport {viewport_box['height']} px high")
    if scroll_width > window_width:
        problems.append(f"horizontal page scroll {scroll_width} > {window_width}")
    if scroll_height > window_height:
        problems.append(f"vertical page scroll {scroll_height} > {window_height}")
    if zoom != "1":
        problems.append(f"zoom {zoom}")
    grid_right = grid_box["x"] + grid_box["width"]
    grid_bottom = grid_box["y"] + grid_box["height"]
    viewport_right = viewport_box["x"] + viewport_box["width"]
    viewport_bottom = viewport_box["y"] + viewport_box["height"]
    grid_inside = (
        grid_box["x"] >= viewport_box["x"] - EPSILON
        and grid_box["y"] >= viewport_box["y"] - EPSILON
        and grid_right <= viewport_right + EPSILON
        and grid_bottom <= viewport_bottom + EPSILON
    )
    if not grid_inside:
        problems.append(f"grid {grid_box} outside grid-viewport {viewport_box}")
    bar_bottom = bar_box["y"] + bar_box["height"]
    bar_inside = (
        bar_box["x"] >= -EPSILON
        and bar_box["x"] + bar_box["width"] <= window_width + EPSILON
        and bar_box["y"] >= -EPSILON
        and bar_bottom <= window_height + EPSILON
    )
    if not bar_inside:
        problems.append(f"clue-bar {bar_box} outside the window")
    if touch:
        keyboard_box = page.get_by_test_id("keyboard").bounding_box()
        assert keyboard_box is not None
        keyboard_bottom = keyboard_box["y"] + keyboard_box["height"]
        if bar_bottom > keyboard_box["y"] + EPSILON:
            problems.append("clue-bar below the top of the in-app keyboard")
        if keyboard_bottom > window_height + EPSILON:
            problems.append("in-app keyboard below the window")
    return problems


# ---- Order, one row, keyboard focus and hit test ----

ORDER_SCRIPT = """
testIds => {
  const byTestId = (id) => document.querySelectorAll(`[data-testid="${id}"]`);
  const follows = (first, second) => Boolean(
    first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING
  );
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  const counts = {};
  const outside = [];
  for (const id of testIds) {
    const found = byTestId(id);
    counts[id] = found.length;
    if (found.length === 1 && (toolbar === null || !toolbar.contains(found[0]))) {
      outside.push(id);
    }
  }
  const outOfOrder = [];
  for (let index = 0; index + 1 < testIds.length; index += 1) {
    const first = byTestId(testIds[index])[0];
    const second = byTestId(testIds[index + 1])[0];
    if (first && second && !follows(first, second)) {
      outOfOrder.push([testIds[index], testIds[index + 1]]);
    }
  }
  return {counts: counts, outside: outside, outOfOrder: outOfOrder};
}
"""
RANGES_SCRIPT = """
testIds => {
  const ranges = [];
  for (const id of testIds) {
    const box = document.querySelector(`[data-testid="${id}"]`).getBoundingClientRect();
    ranges.push([id, box.top, box.bottom]);
  }
  return ranges;
}
"""
FOCUSED_TEST_ID_SCRIPT = (
    "() => document.activeElement && document.activeElement.getAttribute('data-testid')"
)
FOCUS_SHARE_LINK_SCRIPT = """
() => document.querySelector('[data-testid="share-link"]').focus()
"""
# Spec 024 AC-8's measure: the focused button's box, the toolbar's client area,
# the outline (spec 035 AC-2), how much of the outline's outer edge is cut ("Not
# clipped" of spec 035, with the toolbar always among the clipping ancestors) and
# whether the edge fade is visible.
FOCUS_IN_TOOLBAR_SCRIPT = "() => {\n" + COLOUR_CONTRAST_JS + r"""
  const element = document.activeElement;
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  const fade = document.querySelector('[data-testid="room-toolbar-more"]');
  const box = element.getBoundingClientRect();
  const toolbarBox = toolbar.getBoundingClientRect();
  const area = {
    left: toolbarBox.left + toolbar.clientLeft,
    top: toolbarBox.top + toolbar.clientTop,
    right: toolbarBox.left + toolbar.clientLeft + toolbar.clientWidth,
    bottom: toolbarBox.top + toolbar.clientTop + toolbar.clientHeight,
  };
  const style = getComputedStyle(element);
  const width = parseFloat(style.outlineWidth);
  const offset = parseFloat(style.outlineOffset);
  const grow = offset + width;
  const outer = {
    left: box.left - grow, top: box.top - grow,
    right: box.right + grow, bottom: box.bottom + grow,
  };
  const clip = {left: 0, top: 0, right: innerWidth, bottom: innerHeight};
  for (let node = element.parentElement; node; node = node.parentElement) {
    const nodeStyle = getComputedStyle(node);
    const clips = nodeStyle.overflowX !== 'visible'
      || nodeStyle.overflowY !== 'visible';
    if (!clips && node !== toolbar) {
      continue;
    }
    const rect = node.getBoundingClientRect();
    clip.left = Math.max(clip.left, rect.left + node.clientLeft);
    clip.top = Math.max(clip.top, rect.top + node.clientTop);
    clip.right = Math.min(clip.right, rect.left + node.clientLeft + node.clientWidth);
    clip.bottom = Math.min(clip.bottom, rect.top + node.clientTop + node.clientHeight);
  }
  let fadeVisible = false;
  if (fade !== null) {
    const fadeStyle = getComputedStyle(fade);
    fadeVisible = fadeStyle.visibility === 'visible' && fadeStyle.display !== 'none';
  }
  const outline = readFocusOutline();
  return {
    testId: element.getAttribute('data-testid'),
    box: [box.left, box.top, box.right, box.bottom],
    area: [area.left, area.top, area.right, area.bottom],
    cut: {
      top: Math.max(clip.top - outer.top, 0),
      right: Math.max(outer.right - clip.right, 0),
      bottom: Math.max(outer.bottom - clip.bottom, 0),
      left: Math.max(clip.left - outer.left, 0),
    },
    outline: outline,
    fadeVisible: fadeVisible,
  };
}
"""
SCROLL_INTO_VIEW_SCRIPT = """
testId => {
  const button = document.querySelector(`[data-testid="${testId}"]`);
  button.scrollIntoView({block: 'nearest', inline: 'nearest'});
}
"""
HIT_AT_CENTRE_SCRIPT = """
testId => {
  const button = document.querySelector(`[data-testid="${testId}"]`);
  const box = button.getBoundingClientRect();
  const hit = document.elementFromPoint(
    box.left + box.width / 2, box.top + box.height / 2
  );
  return {
    hits: hit !== null && (hit === button || button.contains(hit)),
    hit: hit === null ? null : (hit.getAttribute('data-testid') || hit.tagName),
  };
}
"""


def one_row_problems(page: Page) -> list[str]:
    """The pairs of a pencil button and another toolbar button on different rows."""
    ranges = page.evaluate(RANGES_SCRIPT, [*SPEC024_BUTTONS, *PENCIL_BUTTONS])
    problems: list[str] = []
    for index, (first_id, first_top, first_bottom) in enumerate(ranges):
        for second_id, second_top, second_bottom in ranges[index + 1 :]:
            if first_id not in PENCIL_BUTTONS and second_id not in PENCIL_BUTTONS:
                continue
            overlap_top = max(first_top, second_top)
            overlap_bottom = min(first_bottom, second_bottom)
            if overlap_top >= overlap_bottom:
                problems.append(f"{first_id} and {second_id} are on different rows")
    return problems


def keyboard_focus_problems(reading: dict[str, object]) -> list[str]:
    """How a button with the keyboard focus breaks spec 024 AC-8's keyboard rules."""
    problems: list[str] = []
    box = reading["box"]
    area = reading["area"]
    assert isinstance(box, list)
    assert isinstance(area, list)
    left, top, right, bottom = box
    area_left, area_top, area_right, area_bottom = area
    inside = (
        left >= area_left - EPSILON
        and top >= area_top - EPSILON
        and right <= area_right + EPSILON
        and bottom <= area_bottom + EPSILON
    )
    if not inside:
        problems.append(f"box {box} outside the toolbar's client area {area}")
    outline = reading["outline"]
    assert isinstance(outline, dict)
    problems.extend(
        outline_problems(outline["style"], outline["width"], outline["ratio"])
    )
    cut = reading["cut"]
    assert isinstance(cut, dict)
    for side, pixels in cut.items():
        if round(pixels) != 0:
            problems.append(f"outline cut by {pixels} px on the {side}")
    if reading["fadeVisible"] is not False:
        problems.append("room-toolbar-more is visible")
    return problems


def pencil_toggle_focus_problems(page: Page) -> list[str]:
    """Tab from `share-link` to `pencil-toggle`, then measure it (desktop context)."""
    page.evaluate(FOCUS_SHARE_LINK_SCRIPT)
    for _ in range(MAX_TABS):
        page.keyboard.press("Tab")
        if page.evaluate(FOCUSED_TEST_ID_SCRIPT) == "pencil-toggle":
            page.wait_for_timeout(SETTLE_MS)
            reading = page.evaluate(FOCUS_IN_TOOLBAR_SCRIPT)
            return keyboard_focus_problems(reading)
    return [f"pencil-toggle not focused in {MAX_TABS} presses of Tab"]


def hit_problems(page: Page) -> list[str]:
    """The pencil buttons that `elementFromPoint` misses after `scrollIntoView`."""
    problems: list[str] = []
    for test_id in PENCIL_BUTTONS:
        page.evaluate(SCROLL_INTO_VIEW_SCRIPT, test_id)
        page.wait_for_timeout(SETTLE_MS)
        result = page.evaluate(HIT_AT_CENTRE_SCRIPT, test_id)
        if result["hits"] is not True:
            problems.append(f"{test_id}: elementFromPoint gives {result['hit']}")
    return problems


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac7_the_pencil_buttons_keep_the_grid_room_and_the_toolbar_rules(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    small = (width, height) in SMALL_WINDOWS
    page, close = open_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        layout = spec013_layout_problems(page, touch)
        order = page.evaluate(ORDER_SCRIPT, TOOLBAR_ORDER)
        row = one_row_problems(page) if small else []
        focus = [] if touch else pencil_toggle_focus_problems(page)
        hits = hit_problems(page)
    finally:
        close()

    assert layout == []
    assert order == {
        "counts": dict.fromkeys(TOOLBAR_ORDER, 1),
        "outside": [],
        "outOfOrder": [],
    }
    assert row == []
    assert focus == []
    assert hits == []


# ---- The keyboard-only run at 1280 by 720 ----


def test_ac7_keyboard_only_turns_pencil_mode_on_types_and_confirms(
    new_page: Callable[[int, int], Page], live_server: str, fx01_grid: Grid
) -> None:
    page = new_page(1280, 720)
    mock = open_room(page, live_server, fx01_grid)
    walker = make_walker(page)

    walker.tab_to("pencil-toggle")
    page.keyboard.press("Enter")
    expect(pencil_toggle(page)).to_have_attribute("aria-pressed", "true")
    walker.tab_to("grid")
    page.keyboard.press("Tab")
    expect_selection(page, 1, 0, "across", WORD_W1)
    page.keyboard.press("t")
    expect_selection(page, 1, 1, "across", WORD_W1)
    typed = wait_for_edit_messages(page, mock.frames_without_pings, 1)
    page.keyboard.press("ArrowLeft")
    expect_selection(page, 1, 0, "across", WORD_W1)
    # The grid has the focus, so `tab_to` presses Escape first (spec 035).
    walker.tab_to("confirm-pencil")
    expect(confirm_button(page)).to_be_enabled()
    expect(confirm_button(page)).to_be_focused()
    page.keyboard.press("Enter")
    sent = wait_for_edit_messages(page, mock.frames_without_pings, 2)

    assert typed == [PencilEdit(row=1, column=0, letter="T")]
    assert sent == [
        PencilEdit(row=1, column=0, letter="T"),
        ConfirmPencil(row=1, column=0, base_seq=5),
    ]
    reached = {step.test_id: step for step in walker.reached}
    for test_id in PENCIL_BUTTONS:
        step = reached[test_id]
        problems = outline_problems(
            step.outline_style, step.outline_width, step.outline_contrast
        )
        assert problems == [], step


# ---- Contrast states and the language scan ----


def test_ac7_fr_json_holds_the_three_pencil_keys() -> None:
    fr = load_fr()
    found: dict[str, str | None] = {}
    for key in NEW_KEYS:
        found[key] = fr.get(key)

    assert found == NEW_KEYS


def test_ac7_scans_pass_with_pencil_letters_plain_selected_and_in_my_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: ChangeList = [
        (1, 0, pencil_letter("T", "p2")),
        (1, 2, pencil_letter("M", "p2")),
        (2, 2, pencil_letter("I", "p2")),
    ]
    open_room(page, live_server, fx01_grid, changes=changes)
    tap(page, 1, 0)
    for row, column in [(1, 0), (1, 2), (2, 2)]:
        expect(cell_at(page, row, column)).to_have_attribute("data-pencil", "true")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-selected", "true")
    expect(cell_at(page, 1, 2)).to_have_attribute("data-in-word", "true")
    expect(cell_at(page, 2, 2)).to_have_attribute("data-in-word", "false")
    expect(cell_at(page, 2, 2)).to_have_attribute("data-tinted-by", "")
    expect(confirm_button(page)).to_be_enabled()

    offenders = contrast_problems(page)
    scanned = page.evaluate(LANGUAGE_SCAN_SCRIPT)
    toggle_text = pencil_toggle(page).inner_text(timeout=WAIT_TIMEOUT_MS).strip()
    confirm_text = confirm_button(page).inner_text(timeout=WAIT_TIMEOUT_MS).strip()
    confirm_label = confirm_button(page).get_attribute(
        "aria-label", timeout=WAIT_TIMEOUT_MS
    )

    assert offenders == []
    assert confirm_label is not None
    button_texts = [toggle_text, confirm_text, confirm_label]
    assert button_texts == list(NEW_KEYS.values())
    for text in button_texts:
        assert text in scanned
    data = language_data(live_server, ["Ana", "Bob"])
    assert unknown_texts(button_texts, data) == []


def tinting_players(colour: int) -> list[PlayerView]:
    """`p1` (`you`, host) in a colour other than `colour`, `p2` in `colour` on W7."""
    my_colour = 1 if colour == 0 else 0
    on_amen = Selection(row=3, column=1, direction=Direction.ACROSS)
    bob = PlayerView(
        player_id="p2",
        nickname="Bob",
        colour=colour,
        state=PlayerState.ACTIVE,
        is_host=False,
        muted=False,
        selection=on_amen,
    )
    return [player_view("p1", "Ana", my_colour, is_host=True), bob]


@pytest.mark.parametrize("colour", COLOURS)
def test_ac7_contrast_scan_passes_on_pencil_letters_tinted_and_flashed_by_colour(
    page: Page, live_server: str, fx01_grid: Grid, colour: int
) -> None:
    changes: ChangeList = [
        (3, 2, pencil_letter("M", "p2")),
        (4, 3, {"letter": "S", "author": "p1"}),
    ]
    mock = open_room(
        page, live_server, fx01_grid, changes=changes, players=tinting_players(colour)
    )
    tinted = cell_at(page, 3, 2)
    expect(tinted).to_have_attribute("data-tinted-by", "p2")
    expect(tinted).to_have_attribute("data-pencil", "true")

    mock.send(letter_changed_frame(6, 4, 3, "X", "p2", pencil=True))
    flashing = cell_at(page, 4, 3)
    expect(flashing).to_have_attribute("data-flash", str(colour))
    expect(flashing).to_have_attribute("data-pencil", "true")

    offenders = contrast_problems(page)
    flash_after_scan = flashing.get_attribute("data-flash")

    assert offenders == [], f"colour {colour}: {offenders}"
    # The scan ran within the 1-second flash (spec 016).
    assert flash_after_scan == str(colour)


# ---- Solved grid (edge case, AC-3 and AC-7) ----


def seventeen_right_letters() -> ChangeList:
    """Confirmed right letters by `p2` in every FX-01 letter cell but (4, 4)."""
    changes: ChangeList = []
    for row, column in ROW_MAJOR:
        if (row, column) == LAST_CELL:
            continue
        update: dict[str, object] = {"letter": SOLUTION[(row, column)], "author": "p2"}
        changes.append((row, column, update))
    return changes


def solve_from_the_mock_frames() -> list[str]:
    """`p2` writes the last letter (seq 6), then the grid is solved (seq 7)."""
    return [
        letter_changed_frame(6, 4, 4, "T", "p2", pencil=False),
        grid_solved_frame(7),
    ]


def test_ac7_both_pencil_buttons_are_disabled_once_the_grid_is_solved(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes = seventeen_right_letters()
    changes.append((1, 0, pencil_letter("T", "p2")))
    mock = open_room(page, live_server, fx01_grid, changes=changes)
    tap(page, 1, 0)
    expect(confirm_button(page)).to_be_enabled()
    expect(pencil_toggle(page)).to_be_enabled()

    for frame in solve_from_the_mock_frames():
        mock.send(frame)
    expect_seq(page, 7)

    expect(pencil_toggle(page)).to_be_disabled()
    expect(confirm_button(page)).to_be_disabled()


def test_ac7_typing_in_pencil_mode_on_the_solved_grid_sends_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, changes=seventeen_right_letters())
    turn_pencil_mode_on(page)
    tap(page, 1, 1)
    for frame in solve_from_the_mock_frames():
        mock.send(frame)
    expect_seq(page, 7)

    page.keyboard.press("x")

    assert edit_messages_after_a_pause(page, mock.frames_without_pings) == []
    expect_cell_shows(page, 1, 1, "A", pencil=False, unconfirmed=False)
