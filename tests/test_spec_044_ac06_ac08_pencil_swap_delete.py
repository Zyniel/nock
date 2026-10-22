"""Tests of spec 044, AC-6 to AC-8: the ✎, ⇄ and ⌫ keys.

AC-6: `key-pencil` turns pencil mode on and off, shows it navy with a white icon,
and the letter keys then show their letters in grey italics; on a touch tablet it
and « Crayon » show one state. AC-7: `key-swap` switches the selected cell
between its across and its down word, as a second tap on the cell does. AC-8: the
new keys stay out of the Tab order but in the accessibility tree, and a long press
on `key-delete` erases one letter.

Also tested, from "Edge cases and errors": with the keyboard hidden on a phone, no
pencil control shows, pencil mode keeps its state for a hardware keyboard, and ✎
shows it again once the keyboard is back.

Choices where the spec leaves room:

- "One edit frame" counts the frames that parse to `EditLetter`, `PencilEdit` or
  `Erase`; a `select_cell` the move of the selection sends is left aside. "No
  frame" and "exactly one frame" count every frame but the pings (spec 044's
  "Test harness").
- A letter key's `font-style` and `color` (AC-6) are the key element's computed
  values, as the criterion says.
- AC-7's second tap on `key-swap` sends `select_cell` too (spec 007 AC-5, the
  rule `key-swap` follows); the test checks that frame as well.
- AC-8's "a key of `keyboard`" is any element inside `keyboard`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import (
    Direction,
    EditLetter,
    Erase,
    PencilEdit,
    SelectCell,
    parse_client_message,
)
from spec019_harness import OpenWindow, window_opener
from spec042_harness import box_of, colour_of
from spec043_harness import (
    INK,
    NAVY,
    PHONE,
    WHITE,
    Reading,
    RoomMock,
    cell_at,
    colour_matches,
    expect_selected,
    expect_word,
    focused_test_id,
    fr_value,
    frames_sent_after,
    fx01_view,
    players_up_to,
    press_cell,
    reload_room,
    snapshot_frame,
    style_of,
)
from spec044_harness import (
    KEY_BG,
    LETTERS,
    PEN_FILL_ALPHA,
    PENCIL,
    TABLET,
    expect_keyboard_shows,
    expect_no_keyboard,
    fx01_frame,
    key_of,
    keyboard_of,
    keys_named,
    letter_keys,
    open_fx01,
    read_keyboard,
    tap_toggle,
)

MAX_TABS = 60
LONG_PRESS_MS = 1000
WORD_ACROSS = "0,0,0"  # W1, the across word of (1, 0) and (1, 1)
WORD_DOWN = "0,0,1"  # NAVAL, the down word of (1, 1)

# The element that has the focus: its test id, whether it is `body`, and whether
# it lies inside `keyboard`.
FOCUSED_SCRIPT = r"""
() => {
  const element = document.activeElement;
  if (element === null) {
    return {testId: null, isBody: false, inKeyboard: false};
  }
  return {
    testId: element.getAttribute('data-testid'),
    isBody: element === document.body,
    inKeyboard: element.closest('[data-testid="keyboard"]') !== null,
  };
}
"""

# The new keys or an ancestor that hides them from assistive technology.
HIDING_SCRIPT = r"""
() => {
  const offenders = [];
  for (const testId of ['key-pencil', 'key-swap']) {
    const key = document.querySelector(`[data-testid="${testId}"]`);
    if (key === null) {
      offenders.push([testId, 'missing']);
      continue;
    }
    for (let node = key; node !== null; node = node.parentElement) {
      const role = node.getAttribute('role');
      const hides = node.getAttribute('aria-hidden') === 'true'
        || node.hasAttribute('inert')
        || role === 'presentation' || role === 'none';
      if (hides) {
        offenders.push([testId, node.tagName]);
      }
    }
  }
  return offenders;
}
"""

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def open_touch(
    window: OpenWindow,
    base_url: str,
    frame: str,
    size: tuple[int, int] = PHONE,
) -> tuple[Page, RoomMock]:
    """A snapshot in the touch context, with the keyboard shown."""
    page, mock = open_fx01(window, base_url, frame, size)
    expect_keyboard_shows(page)
    return page, mock


def edit_messages(frames: list[str]) -> list[object]:
    """The frames that parse to `EditLetter`, `PencilEdit` or `Erase`, parsed."""
    edits: list[object] = []
    for frame in frames:
        message = parse_client_message(frame)
        if isinstance(message, EditLetter | PencilEdit | Erase):
            edits.append(message)
    return edits


def parsed(frames: list[str]) -> list[object]:
    return [parse_client_message(frame) for frame in frames]


def expect_grid_focused(page: Page) -> None:
    expect(page.get_by_test_id("grid")).to_be_focused()


def pencil_key(page: Page) -> Reading:
    """The reading of `key-pencil` (`KEYBOARD_SCRIPT`)."""
    keys = keys_named(read_keyboard(page), "key-pencil")
    assert len(keys) == 1, keys
    return keys[0]


def pencil_on_problems(key: Reading) -> list[str]:
    """How `key-pencil` differs from its pressed look: navy, white icon, pen fill."""
    problems: list[str] = []
    if not colour_matches(key["background"], NAVY):
        problems.append(f"background {key['background']}")
    svgs: list[Reading] = key["svgs"]
    if len(svgs) != 1:
        return [*problems, f"{len(svgs)} svg elements"]
    for shape in svgs[0]["shapes"]:
        stroke = shape["strokeColour"]
        fill = shape["fillColour"]
        if stroke is None or not colour_matches(stroke, WHITE):
            problems.append(f"{shape['tag']} stroke {shape['stroke']}")
        if fill is None or not colour_matches(fill, WHITE, PEN_FILL_ALPHA):
            problems.append(f"{shape['tag']} fill {shape['fill']}")
    return problems


def letter_key_problems(
    keys: list[Reading], style: str, colour: tuple[int, int, int]
) -> list[str]:
    """How the letter keys differ from `font-style` `style` and `color` `colour`."""
    problems: list[str] = []
    for key in keys:
        if key["fontStyle"] != style:
            problems.append(f"{key['dataKey']}: font-style {key['fontStyle']}")
        if not colour_matches(key["colour"], colour):
            problems.append(f"{key['dataKey']}: colour {key['colour']}")
    return problems


def turn_pencil_on(page: Page) -> None:
    """Tap `key-pencil` and wait until it is pressed."""
    page.get_by_test_id("key-pencil").tap()
    expect(page.get_by_test_id("key-pencil")).to_have_attribute("aria-pressed", "true")


# ---- AC-6: ✎ turns pencil mode on and off ----


def test_ac6_key_pencil_is_named_crayon_and_starts_off(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_touch(window, live_server, fx01_frame(fx01_grid))
    key = page.get_by_test_id("key-pencil")

    expect(key).to_have_attribute("aria-label", fr_value("pencil.toggle"))
    expect(key).to_have_attribute("aria-pressed", "false")


def test_ac6_a_tap_on_key_pencil_turns_pencil_mode_on_and_sends_nothing(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_touch(window, live_server, fx01_frame(fx01_grid))
    press_cell(page, 1, 0, touch=True)

    sent = frames_sent_after(page, mock, lambda: turn_pencil_on(page))

    assert sent == []
    assert focused_test_id(page) == "grid"


def test_ac6_in_pencil_mode_key_pencil_is_navy_with_a_white_filled_icon(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_touch(window, live_server, fx01_frame(fx01_grid))
    press_cell(page, 1, 0, touch=True)

    turn_pencil_on(page)

    assert pencil_on_problems(pencil_key(page)) == []


def test_ac6_in_pencil_mode_the_letter_keys_show_grey_italics_and_the_others_stay(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_touch(window, live_server, fx01_frame(fx01_grid))
    press_cell(page, 1, 0, touch=True)

    turn_pencil_on(page)
    keyboard = read_keyboard(page)
    letters = letter_keys(keyboard)

    assert len(letters) == len(LETTERS)
    assert letter_key_problems(letters, "italic", PENCIL) == []
    for test_id in ("key-swap", "key-delete"):
        keys = keys_named(keyboard, test_id)
        assert len(keys) == 1, test_id
        assert colour_matches(keys[0]["background"], KEY_BG), keys[0]


def test_ac6_in_pencil_mode_a_letter_key_sends_a_pencil_edit(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_touch(window, live_server, fx01_frame(fx01_grid))
    press_cell(page, 1, 0, touch=True)
    turn_pencil_on(page)

    sent = frames_sent_after(page, mock, lambda: key_of(page, "T").tap())

    assert edit_messages(sent) == [PencilEdit(row=1, column=0, letter="T")]
    expect(cell_at(page, 1, 0)).to_have_attribute("data-pencil", "true")


def test_ac6_a_second_tap_on_key_pencil_turns_pencil_mode_off(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_touch(window, live_server, fx01_frame(fx01_grid))
    press_cell(page, 1, 0, touch=True)
    turn_pencil_on(page)
    key_of(page, "T").tap()
    expect_selected(page, 1, 1)

    page.get_by_test_id("key-pencil").tap()
    expect(page.get_by_test_id("key-pencil")).to_have_attribute("aria-pressed", "false")
    keyboard = read_keyboard(page)
    sent = frames_sent_after(page, mock, lambda: key_of(page, "A").tap())

    key = keys_named(keyboard, "key-pencil")[0]
    assert colour_matches(key["background"], KEY_BG), key["background"]
    assert letter_key_problems(letter_keys(keyboard), "normal", INK) == []
    assert edit_messages(sent) == [EditLetter(row=1, column=1, letter="A")]


def test_ac6_after_a_reload_pencil_mode_is_off(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    frame = fx01_frame(fx01_grid)
    page, mock = open_touch(window, live_server, frame)
    turn_pencil_on(page)

    reload_room(page, mock, frame)

    expect_keyboard_shows(page)
    expect(page.get_by_test_id("key-pencil")).to_have_attribute("aria-pressed", "false")


def test_ac6_on_a_touch_tablet_crayon_and_key_pencil_show_one_state(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_touch(window, live_server, fx01_frame(fx01_grid), TABLET)
    toggle = page.get_by_test_id("pencil-toggle")
    key = page.get_by_test_id("key-pencil")

    toggle.click()
    expect(toggle).to_have_attribute("aria-pressed", "true")
    expect(key).to_have_attribute("aria-pressed", "true")

    key.tap()
    expect(key).to_have_attribute("aria-pressed", "false")
    expect(toggle).to_have_attribute("aria-pressed", "false")


def test_ac6_with_the_keyboard_hidden_pencil_mode_keeps_its_state(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    # Edge case "A touch screen with the phone top bar and the keyboard hidden".
    page, mock = open_touch(window, live_server, fx01_frame(fx01_grid))
    turn_pencil_on(page)
    tap_toggle(page)
    expect_no_keyboard(page)
    expect(page.get_by_test_id("key-pencil")).to_have_count(0)
    expect(page.get_by_test_id("pencil-toggle")).to_have_count(0)
    press_cell(page, 1, 0, touch=True)

    sent = frames_sent_after(page, mock, lambda: page.keyboard.press("t"))
    tap_toggle(page)

    assert edit_messages(sent) == [PencilEdit(row=1, column=0, letter="T")]
    expect_keyboard_shows(page)
    expect(page.get_by_test_id("key-pencil")).to_have_attribute("aria-pressed", "true")


# ---- AC-7: ⇄ switches the selected cell's word ----


def test_ac7_key_swap_is_named_changer_de_sens(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_touch(window, live_server, fx01_frame(fx01_grid))

    expect(page.get_by_test_id("key-swap")).to_have_attribute(
        "aria-label", fr_value("keyboard.swap")
    )


def test_ac7_with_nothing_selected_key_swap_selects_nothing_and_sends_nothing(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_touch(window, live_server, fx01_frame(fx01_grid))
    grid = page.get_by_test_id("grid")

    sent = frames_sent_after(page, mock, lambda: page.get_by_test_id("key-swap").tap())

    assert sent == []
    expect(grid).to_have_attribute("data-selected-row", "")
    expect(grid).to_have_attribute("data-selected-column", "")


def test_ac7_key_swap_turns_a_two_word_cell_to_its_down_word_and_sends_it(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_touch(window, live_server, fx01_frame(fx01_grid))
    press_cell(page, 1, 1, touch=True)
    expect_word(page, WORD_ACROSS)

    sent = frames_sent_after(page, mock, lambda: page.get_by_test_id("key-swap").tap())

    expect_selected(page, 1, 1)
    expect(page.get_by_test_id("grid")).to_have_attribute("data-direction", "down")
    expect_word(page, WORD_DOWN)
    assert parsed(sent) == [SelectCell(row=1, column=1, direction=Direction.DOWN)]
    expect_grid_focused(page)


def test_ac7_a_second_tap_on_key_swap_brings_back_the_across_word(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_touch(window, live_server, fx01_frame(fx01_grid))
    press_cell(page, 1, 1, touch=True)
    swap = page.get_by_test_id("key-swap")
    swap.tap()
    expect_word(page, WORD_DOWN)

    sent = frames_sent_after(page, mock, swap.tap)

    expect_selected(page, 1, 1)
    expect(page.get_by_test_id("grid")).to_have_attribute("data-direction", "across")
    expect_word(page, WORD_ACROSS)
    assert parsed(sent) == [SelectCell(row=1, column=1, direction=Direction.ACROSS)]
    expect_grid_focused(page)


def test_ac7_key_swap_on_a_one_word_cell_changes_nothing_and_sends_nothing(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_touch(window, live_server, fx01_frame(fx01_grid))
    press_cell(page, 1, 0, touch=True)
    expect_word(page, WORD_ACROSS)

    sent = frames_sent_after(page, mock, lambda: page.get_by_test_id("key-swap").tap())

    assert sent == []
    expect_selected(page, 1, 0)
    expect(page.get_by_test_id("grid")).to_have_attribute("data-direction", "across")
    expect_word(page, WORD_ACROSS)


# ---- AC-8: out of the Tab order, in the accessibility tree ----


@pytest.mark.parametrize("test_id", ["key-pencil", "key-swap"])
def test_ac8_the_new_keys_have_tabindex_minus_one(
    window: OpenWindow, live_server: str, fx01_grid: Grid, test_id: str
) -> None:
    page, _ = open_touch(window, live_server, fx01_frame(fx01_grid))
    key = page.get_by_test_id(test_id)

    expect(key).to_have_attribute("tabindex", "-1")
    assert key.evaluate("element => element.tabIndex") == -1


@pytest.mark.parametrize(
    ("test_id", "name_key"),
    [("key-pencil", "pencil.toggle"), ("key-swap", "keyboard.swap")],
)
def test_ac8_the_new_keys_are_found_by_role_and_name_in_the_keyboard(
    window: OpenWindow, live_server: str, fx01_grid: Grid, test_id: str, name_key: str
) -> None:
    page, _ = open_touch(window, live_server, fx01_frame(fx01_grid))

    found = keyboard_of(page).get_by_role("button", name=fr_value(name_key), exact=True)

    expect(found).to_have_count(1)
    expect(found).to_have_attribute("data-testid", test_id)


def test_ac8_nothing_hides_the_new_keys_from_assistive_technology(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_touch(window, live_server, fx01_frame(fx01_grid))

    assert page.evaluate(HIDING_SCRIPT) == []


@pytest.mark.parametrize("key", ["Tab", "Shift+Tab"])
def test_ac8_tab_and_shift_tab_from_the_grid_never_land_on_a_key(
    window: OpenWindow, live_server: str, fx01_grid: Grid, key: str
) -> None:
    page, _ = open_touch(window, live_server, fx01_frame(fx01_grid))
    press_cell(page, 1, 0, touch=True)
    expect_grid_focused(page)

    page.keyboard.press("Escape")
    landed: list[str | None] = []
    for _ in range(MAX_TABS + 1):
        page.keyboard.press(key)
        focused = page.evaluate(FOCUSED_SCRIPT)
        assert isinstance(focused, dict), focused
        if focused["inKeyboard"]:
            landed.append(focused["testId"])
        if focused["testId"] == "grid" or focused["isBody"]:
            break

    assert landed == []


def test_ac8_key_swap_focused_from_a_script_shows_the_navy_ring(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_touch(window, live_server, fx01_frame(fx01_grid))
    press_cell(page, 1, 0, touch=True)
    page.keyboard.press("ArrowRight")
    swap = page.get_by_test_id("key-swap")

    swap.evaluate("element => element.focus()")

    assert style_of(swap, "outlineStyle") == "solid"
    assert style_of(swap, "outlineWidth") == "2px"
    outline_colour = colour_of(swap, "outlineColor")
    assert colour_matches(outline_colour, NAVY), outline_colour


def test_ac8_a_long_press_on_key_delete_erases_one_letter(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    changes: list[tuple[int, int, dict[str, object]]] = [
        (1, 0, {"letter": "T", "author": "p1"}),
        (1, 1, {"letter": "A", "author": "p1"}),
    ]
    frame = snapshot_frame(fx01_view(fx01_grid, changes), players_up_to(3))
    page, mock = open_touch(window, live_server, frame)
    press_cell(page, 1, 1, touch=True)
    delete_box = box_of(page.get_by_test_id("key-delete"))

    def long_press() -> None:
        page.mouse.move(delete_box.centre_x, delete_box.centre_y)
        page.mouse.down()
        page.wait_for_timeout(LONG_PRESS_MS)
        page.mouse.up()

    sent = frames_sent_after(page, mock, long_press)

    assert parsed(sent) == [Erase(row=1, column=1)]
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
