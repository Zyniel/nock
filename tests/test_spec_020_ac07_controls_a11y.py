"""Tests of spec 020, AC-7: the pencil controls and pencil letters meet spec 035
and keep the grid's room.

Four parts, all on the page with a mocked socket:

- the top bar at the eight window sizes of spec 006 AC-5, in desktop and touch
  contexts, with spec 013 AC-6's setup and (1, 0) holding a pencil letter: spec
  013 AC-6's layout checks with `pencil-toggle` in `room-topbar` (right after
  `undo-button` in the computer top bar, right after `chat-toggle` in the phone
  top bar), and, with (1, 0) selected, `confirm-pencil` the first item of the
  open `aide-menu`; spec 043 AC-28's checks for both (inside the window,
  `elementFromPoint` at their centre returns them). One page per size and context,
  so that the suite stays lean;
- the keyboard-only run at 1280 by 720 (spec 035's walker), which reaches
  `confirm-pencil` by opening the Aide menu from the keyboard;
- the contrast states of the spec's "Test harness" (spec 035's contrast scan) and
  the language scan of the two buttons' texts, with the `fr.json` keys; outside a
  flash, a pencil letter's colour differs from a normal letter's in the same
  state (selected, tinted; AC-1 checks the plain cell and my word); in the flash
  states (decision 12), the flashing pencil cell's `data-flash`, `data-pencil`,
  italics and 4.5:1 contrast against the flash composite (spec 041, AC-16);
- the edge case "Solved grid" (AC-3, AC-7): `pencil-toggle` disabled and
  `confirm-pencil` gone, and spec 026's input lock sends nothing in pencil mode.

Refined by spec 043 (the design's room layout): this read "both are in
`room-toolbar` right after `undo-button`, and spec 024 AC-8's toolbar rules hold
for them" and "`tab_to` `confirm-pencil` and `Enter`"; `confirm-pencil` is now
present only while it applies, with the text `fr.json["pencil.confirm"]` (« Confirmer
la lettre au crayon ») and no `aria-label`. Spec 044 (the design's keyboard) refines
the touch context's sheet layout once more (`key-pencil` in place of
`pencil-toggle`); until it is built, `pencil-toggle` holds the phone top bar's
fourth slot there too (spec 043, Decision 6).

The shared setup is in `spec020_harness`, `spec024_harness` and `spec043_harness`.
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
from room_panels import open_aide
from spec013_harness import swatch_colour
from spec020_harness import (
    confirm_button,
    edit_messages_after_a_pause,
    expect_cell_shows,
    expect_selected_cell,
    grid_solved_frame,
    letter_changed_frame,
    pencil_toggle,
    tap,
    text_colour,
    turn_pencil_mode_on,
    wait_for_edit_messages,
)
from spec024_harness import (
    COLOUR_CONTRAST_JS,
    LAST_CELL,
    ROW_MAJOR,
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
from spec035_harness import LANGUAGE_SCAN_SCRIPT, MIN_TEXT_CONTRAST, unknown_texts
from spec042_harness import box_of
from spec043_harness import box_inside, hit_problem, shown_test_ids, window_box

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
EIGHT_NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve", "Fay", "Gus", "Hal"]
FEED_ITEMS = 100
MIN_GRID_VIEWPORT_PX = 100.0
EPSILON = 1.0
MAX_TABS = 60
WORD_W1 = "0,0,0"
WORD_W7 = "3,0,0"
COLOURS = list(range(8))
# Spec 043 changed `pencil.confirm` and removed `pencil.confirm_label`.
NEW_KEYS = {
    "pencil.toggle": "Crayon",
    "pencil.confirm": "Confirmer la lettre au crayon",
}
REMOVED_KEYS = ["pencil.confirm_label"]


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


def open_top_bar_room(
    browser: Browser,
    browser_name: str,
    live_server: str,
    grid: Grid,
    width: int,
    height: int,
    touch: bool,
) -> tuple[Page, Callable[[], None]]:
    """Open the room of the setup with (3, 1) tapped; return the page, its closer.

    The snapshot also has a pencil `T` by `p2` in (1, 0), for `confirm-pencil`.
    """
    page, close = open_context_page(browser, browser_name, width, height, touch)
    try:
        mock = open_room(
            page,
            live_server,
            grid,
            players=eight_players(),
            changes=[(1, 0, pencil_letter("T", "p2"))],
        )
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


# ---- The top bar's place and the Aide menu's first item ----


def top_bar_place_problems(page: Page) -> list[str]:
    """`pencil-toggle` right after `undo-button` (computer top bar) or right after
    `chat-toggle` (phone top bar, the one without `topbar-brand`)."""
    shown = shown_test_ids(page.get_by_test_id("room-topbar"))
    if "pencil-toggle" not in shown:
        return [f"pencil-toggle does not show in the top bar: {shown}"]
    before = "undo-button" if "topbar-brand" in shown else "chat-toggle"
    index = shown.index("pencil-toggle")
    if index == 0 or shown[index - 1] != before:
        return [f"pencil-toggle is not right after {before}: {shown}"]
    return []


def reach_problems(page: Page, test_id: str) -> list[str]:
    """Spec 043 AC-28's checks for one control: inside the window, and hit."""
    problems: list[str] = []
    box = box_of(page.get_by_test_id(test_id))
    if not box_inside(box, window_box(page)):
        problems.append(f"{test_id} {box} is not inside the window")
    found = hit_problem(page, test_id)
    if found is not None:
        problems.append(found)
    return problems


def confirm_problems(page: Page, touch: bool) -> list[str]:
    """With (1, 0) selected, `confirm-pencil` is the open Aide menu's first item."""
    cell = cell_at(page, 1, 0)
    if touch:
        cell.tap(timeout=WAIT_TIMEOUT_MS)
    else:
        cell.click(timeout=WAIT_TIMEOUT_MS)
    expect_selected_cell(page, 1, 0)
    open_aide(page)
    first = page.get_by_test_id("aide-menu").evaluate(
        "menu => menu.querySelector('button, a')?.getAttribute('data-testid')"
    )
    problems: list[str] = []
    if first != "confirm-pencil":
        problems.append(f"the Aide menu's first item is {first}")
    page.get_by_test_id("confirm-pencil").evaluate(
        "item => item.scrollIntoView({block: 'nearest'})"
    )
    problems.extend(reach_problems(page, "confirm-pencil"))
    return problems


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac7_the_pencil_controls_keep_the_grid_room_in_the_top_bar_and_the_aide_menu(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_top_bar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        layout = spec013_layout_problems(page, touch)
        place = top_bar_place_problems(page)
        toggle = reach_problems(page, "pencil-toggle")
        confirm = confirm_problems(page, touch)
    finally:
        close()

    assert layout == []
    assert place == []
    assert toggle == []
    assert confirm == []


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
    page.keyboard.press("Escape")
    walker.tab_to("aide-button")
    page.keyboard.press("Enter")
    expect(page.get_by_test_id("aide-menu")).to_be_visible()
    expect(confirm_button(page)).to_be_focused()
    walker.record("confirm-pencil")
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


def test_ac7_fr_json_holds_the_pencil_keys_of_spec_043() -> None:
    fr = load_fr()
    found: dict[str, str | None] = {}
    for key in NEW_KEYS:
        found[key] = fr.get(key)

    assert found == NEW_KEYS
    for key in REMOVED_KEYS:
        assert key not in fr, key


def test_ac7_scans_pass_with_pencil_letters_plain_selected_and_in_my_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: ChangeList = [
        (1, 0, pencil_letter("T", "p2")),
        (1, 2, pencil_letter("M", "p2")),
        (2, 2, pencil_letter("I", "p2")),
        (4, 4, {"letter": "T", "author": "p2"}),
    ]
    open_room(page, live_server, fx01_grid, changes=changes)
    tap(page, 1, 0)
    for row, column in [(1, 0), (1, 2), (2, 2)]:
        expect(cell_at(page, row, column)).to_have_attribute("data-pencil", "true")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-selected", "true")
    expect(cell_at(page, 1, 2)).to_have_attribute("data-in-word", "true")
    expect(cell_at(page, 2, 2)).to_have_attribute("data-in-word", "false")
    expect(cell_at(page, 2, 2)).to_have_attribute("data-tinted-by", "")
    open_aide(page)
    expect(confirm_button(page)).to_be_visible()

    offenders = contrast_problems(page)
    scanned = page.evaluate(LANGUAGE_SCAN_SCRIPT)
    toggle_text = pencil_toggle(page).inner_text(timeout=WAIT_TIMEOUT_MS).strip()
    confirm_text = confirm_button(page).inner_text(timeout=WAIT_TIMEOUT_MS).strip()
    confirm_label = confirm_button(page).get_attribute(
        "aria-label", timeout=WAIT_TIMEOUT_MS
    )
    # Outside a flash, the selected pencil letter and a selected normal letter.
    selected_pencil_colour = text_colour(cell_at(page, 1, 0))
    selected_normal = cell_at(page, 4, 4)
    tap(page, 4, 4)
    expect(selected_normal).to_have_attribute("data-selected", "true")
    expect(selected_normal).to_have_attribute("data-pencil", "false")
    selected_normal_colour = text_colour(selected_normal)

    assert offenders == []
    assert selected_pencil_colour != selected_normal_colour
    assert confirm_label is None
    button_texts = [toggle_text, confirm_text]
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


# The flash state of AC-7, read at once on the flashing `cell`: its `data-flash`,
# `data-pencil` and computed `font-style`; whether the flash colour (the
# `roster-colour` of the player who flashed it, as spec 016 AC-2 measures it) is
# the computed `background-color` of the one `cell-flash` element inside the cell,
# at the opacity 0.38 over a white cell (spec 041, AC-16: the flash is that colour
# at 38 % over white, under an ink letter, not an opaque swatch); and the contrast
# of the cell's computed `color` (its letter is the cell's own text) against that
# composite.
FLASH_READING_SCRIPT = "(cell, flashColour) => {\n" + COLOUR_CONTRAST_JS + r"""
  const style = getComputedStyle(cell);
  const overlays = cell.querySelectorAll('[data-testid="cell-flash"]');
  const overlay = overlays.length === 1 ? getComputedStyle(overlays[0]) : null;
  const flashShown = overlay !== null
    && overlay.backgroundColor === flashColour
    && overlay.opacity === '0.38'
    && style.backgroundColor === 'rgb(255, 255, 255)';
  const swatch = parseColour(flashColour);
  const composite = over([swatch[0], swatch[1], swatch[2], 0.38], WHITE);
  const text = over(parseColour(style.color), composite);
  return {
    flash: cell.getAttribute('data-flash'),
    pencil: cell.getAttribute('data-pencil'),
    fontStyle: style.fontStyle,
    flashShown: flashShown,
    ratio: contrast(text, composite),
  };
}
"""


@pytest.mark.parametrize("colour", COLOURS)
def test_ac7_pencil_letters_tinted_and_flashed_by_colour_keep_their_sign_and_contrast(
    page: Page, live_server: str, fx01_grid: Grid, colour: int
) -> None:
    # (3, 2) and (3, 3) are on W7, the word p2 selected: both tinted by p2.
    changes: ChangeList = [
        (3, 2, pencil_letter("M", "p2")),
        (3, 3, {"letter": "E", "author": "p2"}),
        (4, 3, {"letter": "S", "author": "p1"}),
    ]
    mock = open_room(
        page, live_server, fx01_grid, changes=changes, players=tinting_players(colour)
    )
    tinted_pencil = cell_at(page, 3, 2)
    tinted_normal = cell_at(page, 3, 3)
    for tinted in (tinted_pencil, tinted_normal):
        expect(tinted).to_have_attribute("data-tinted-by", "p2")
        expect(tinted).to_have_attribute("data-in-word", "false")
        expect(tinted).to_have_attribute("data-flash", "")
    expect(tinted_pencil).to_have_attribute("data-pencil", "true")
    expect(tinted_normal).to_have_attribute("data-pencil", "false")
    tinted_pencil_colour = text_colour(tinted_pencil)
    tinted_normal_colour = text_colour(tinted_normal)
    flash_colour = swatch_colour(page, "p2")

    mock.send(letter_changed_frame(6, 4, 3, "X", "p2", pencil=True))
    flashing = cell_at(page, 4, 3)
    expect(flashing).to_have_attribute("data-flash", str(colour))
    flash_reading = flashing.evaluate(FLASH_READING_SCRIPT, flash_colour)
    offenders = contrast_problems(page)
    flash_after_scan = flashing.get_attribute("data-flash")

    assert offenders == [], f"colour {colour}: {offenders}"
    # The reading and the scan ran within the 1-second flash (spec 016).
    assert flash_after_scan == str(colour)
    # Outside a flash, the grey differs from a normal letter in the same state.
    assert tinted_pencil_colour != tinted_normal_colour
    # In the flash, the italics alone mark the pencil letter (decision 12).
    assert flash_reading["flash"] == str(colour)
    assert flash_reading["pencil"] == "true"
    assert flash_reading["fontStyle"] == "italic"
    # Spec 041 AC-16: a white cell under one 38 % `cell-flash` overlay of the colour.
    assert flash_reading["flashShown"] is True, (flash_colour, flash_reading)
    assert flash_reading["ratio"] >= MIN_TEXT_CONTRAST, flash_reading


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


def test_ac7_once_solved_the_toggle_is_disabled_and_the_confirm_item_gone(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes = seventeen_right_letters()
    changes.append((1, 0, pencil_letter("T", "p2")))
    mock = open_room(page, live_server, fx01_grid, changes=changes)
    tap(page, 1, 0)
    expect(confirm_button(page)).to_have_count(1)
    expect(pencil_toggle(page)).to_be_enabled()

    for frame in solve_from_the_mock_frames():
        mock.send(frame)
    expect_seq(page, 7)

    expect(pencil_toggle(page)).to_be_disabled()
    expect(confirm_button(page)).to_have_count(0)


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
