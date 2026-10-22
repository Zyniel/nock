"""Tests of spec 043, AC-23 to AC-25: the clue bar, its chevrons, and the picker.

AC-23: `clue-bar` is a 34 px navy bar holding `clue-prev`, the clue on one line
with its direction pictogram, « Réagir », « Je bloque » and `clue-next`, with
its widths in each layout. AC-24: the chevrons move to the previous and the
next unfinished word as `Shift+Tab` and `Tab` do, and a pointer press keeps the
focus on the grid. AC-25: `reaction-picker` floats over the bottom of
`grid-viewport` (work package WP-1), and a shown reaction is a white pill centred
on its `clue` element, drawn over its neighbours (WP-2).

Also tested, from "Edge cases and errors": with no unfinished word the chevrons
change nothing and send nothing (AC-24).

Choices where the spec leaves room:

- "The play area's content box" at 568 by 320 (AC-23): the play area runs from the
  window's left edge to the Salon column's left edge, with 12 px of padding each
  side ("Play area and fit"), so its content is the Salon's left less 24 px wide.
- A focus ring is read on `document.activeElement` after spec 035's `tab_to`.
- AC-25's pill: its look is read on `clue-reaction` itself, with the shadow of
  "Reactions" (`0 4px 10px -4px` in the soft shadow token); "the lower `clue`
  element of (0, 0)" is the one of its two `clue` elements whose top is lower.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import pairwise

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.grid import Grid
from nock.protocol import (
    ClueRef,
    Direction,
    Reaction,
    SelectCell,
    grid_view,
    parse_client_message,
)
from spec019_harness import OpenWindow, window_opener
from spec021_harness import clue_at
from spec035_harness import Walker
from spec041_harness import shadow_of
from spec042_harness import box_of, colour_of, contrast_ratio
from spec043_harness import (
    CLUE_BAR_BUTTONS,
    ICON_OF_CLUE_BAR_BUTTON,
    IDES,
    INK,
    LABEL_KEY_OF_CLUE_BAR_BUTTON,
    LINE,
    MIME,
    NAVAL,
    NAVY,
    RULE,
    SHADOW_SOFT_ALPHA,
    WHITE,
    WORD,
    Reading,
    RoomMock,
    border_problems,
    cell_at,
    colour_matches,
    expect_colour,
    expect_selected,
    expect_word,
    flag_frame,
    focused_test_id,
    font_size_of,
    fr_value,
    frames_sent_after,
    full_wrong_view,
    fx01_view,
    hit_problem,
    icon_problems,
    is_clear,
    letters_of,
    open_room,
    padding_matches,
    padding_of,
    parts_of,
    pictogram_of,
    players_up_to,
    press_cell,
    px,
    reaction_frame,
    reading_box,
    same_font_size,
    same_position,
    same_size,
    select_mime,
    send_and_wait,
    shown_test_ids,
    shows_pictogram,
    snapshot_frame,
    stroke_width_problems,
    style_of,
    to_box,
)

SIZES = [(360, 740), (1280, 720)]
SIZE_IDS = ["360x740", "1280x720"]
BUTTON_WIDTHS = {
    "clue-prev": 36.0,
    "react-button": 40.0,
    "flag-button": 40.0,
    "clue-next": 36.0,
}
TAMIS = [(1, 0), (1, 1), (1, 2), (1, 3), (1, 4)]

# ---- Fixtures --------------------------------------------------------------------


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


def open_fx01(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int]
) -> Page:
    page = window(size[0], size[1], False)
    open_room(page, base_url, snapshot_frame(fx01_view(grid), players_up_to(3)))
    return page


def shapes_of(page: Page, test_id: str) -> list[Reading]:
    svgs = parts_of(page.get_by_test_id(test_id))["svgs"]
    assert len(svgs) == 1, f"{test_id}: {len(svgs)} svg elements"
    shapes: list[Reading] = svgs[0]["shapes"]
    return shapes


# ---- AC-23: the clue bar -------------------------------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac23_the_clue_bar_is_a_34_px_navy_bar(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_fx01(window, live_server, fx01_grid, size)
    select_mime(page)
    bar = page.get_by_test_id("clue-bar")

    classes = str(bar.get_attribute("class")).split()

    assert "nock-on-navy" in classes
    expect_colour(bar, "backgroundColor", NAVY)
    assert same_size(box_of(bar).height, 34.0), box_of(bar)


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac23_its_five_parts_come_left_to_right_on_its_middle_line(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_fx01(window, live_server, fx01_grid, size)
    select_mime(page)
    bar = page.get_by_test_id("clue-bar")
    order = ["clue-prev", "clue-bar-text", "react-button", "flag-button", "clue-next"]

    shown = shown_test_ids(bar)
    bar_box = box_of(bar)
    boxes = [box_of(page.get_by_test_id(test_id)) for test_id in order]

    assert shown == order
    for previous, following in pairwise(boxes):
        assert following.left >= previous.right - 1.0, boxes
    for test_id, box in zip(order, boxes, strict=True):
        assert same_position(box.centre_y, bar_box.centre_y), (test_id, box, bar_box)


@pytest.mark.parametrize("test_id", CLUE_BAR_BUTTONS)
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac23_each_button_is_an_icon_with_its_label_and_width(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    size: tuple[int, int],
    test_id: str,
) -> None:
    page = open_fx01(window, live_server, fx01_grid, size)
    select_mime(page)

    parts = parts_of(page.get_by_test_id(test_id))

    assert parts["tag"] == "BUTTON"
    assert parts["text"] == ""
    assert parts["ariaLabel"] == fr_value(LABEL_KEY_OF_CLUE_BAR_BUTTON[test_id])
    assert same_size(reading_box(parts).width, BUTTON_WIDTHS[test_id]), parts["box"]
    if test_id in ("react-button", "flag-button"):
        assert parts["radius"] == "6px"
    assert len(parts["svgs"]) == 1, parts["svgs"]
    svg = parts["svgs"][0]
    svg_box = reading_box(svg)
    assert same_size(svg_box.width, 20.0), svg_box
    assert same_size(svg_box.height, 20.0), svg_box
    assert svg["ariaHidden"] == "true"
    assert icon_problems(svg, ICON_OF_CLUE_BAR_BUTTON[test_id]) == []
    assert stroke_width_problems(svg, 2.0) == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac23_the_clue_is_one_white_line_ending_with_an_ellipsis(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_fx01(window, live_server, fx01_grid, size)
    select_mime(page)
    text = page.get_by_test_id("clue-bar-text")

    content = text.evaluate("element => element.textContent.trim()")

    assert content == "Artiste muet"
    expect_colour(text, "color", WHITE)
    assert same_font_size(float(style_of(text, "fontSize").removesuffix("px")), 15.2)
    assert style_of(text, "fontWeight") == "500"
    assert style_of(text, "whiteSpace") == "nowrap"
    assert style_of(text, "overflowX") == "hidden"
    assert style_of(text, "textOverflow") == "ellipsis"


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac23_the_direction_pictogram_follows_the_clue_and_the_word(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_fx01(window, live_server, fx01_grid, size)
    select_mime(page)
    direction = page.get_by_test_id("clue-bar-text").get_by_test_id(
        "clue-bar-direction"
    )

    down = pictogram_of(direction)
    press_cell(page, 2, 2)
    expect_word(page, "2,0,0")
    across = pictogram_of(direction)

    assert down["ariaHidden"] == "true"
    assert down["textNodes"] == 0
    assert shows_pictogram(down, "\N{DOWNWARDS ARROW}"), down
    assert style_of(direction, "opacity") == "0.8"
    assert style_of(direction, "marginLeft") == "6px"
    assert shows_pictogram(across, "\N{RIGHTWARDS ARROW}"), across


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac23_the_flag_button_is_a_white_outline_until_pressed(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_fx01(window, live_server, fx01_grid, size)
    select_mime(page)
    button = page.get_by_test_id("flag-button")

    shapes = shapes_of(page, "flag-button")

    assert is_clear(colour_of(button, "backgroundColor"))
    for shape in shapes:
        assert shape["strokeColour"] is not None, shape
        assert colour_matches(shape["strokeColour"], WHITE), shape
        assert shape["fillColour"] is None or is_clear(shape["fillColour"]), shape


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac23_pressed_the_flag_button_is_white_with_a_navy_flag(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = window(size[0], size[1], False)
    mock = open_room(
        page, live_server, snapshot_frame(fx01_view(fx01_grid), players_up_to(3))
    )
    select_mime(page)
    button = page.get_by_test_id("flag-button")

    send_and_wait(page, mock, flag_frame(6, "p1", MIME))

    expect(button).to_have_attribute("aria-pressed", "true")
    expect_colour(button, "backgroundColor", WHITE)
    flag_shape = shapes_of(page, "flag-button")[1]
    assert flag_shape["fillColour"] is not None, flag_shape
    assert colour_matches(flag_shape["fillColour"], NAVY), flag_shape


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac23_with_nothing_selected_react_and_flag_are_disabled_in_rule_grey(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_fx01(window, live_server, fx01_grid, size)

    for test_id in ("react-button", "flag-button"):
        expect(page.get_by_test_id(test_id)).to_be_disabled()
        for shape in shapes_of(page, test_id):
            assert shape["strokeColour"] is not None, (test_id, shape)
            assert colour_matches(shape["strokeColour"], RULE), (test_id, shape)
    assert contrast_ratio(RULE, NAVY) >= 4.5


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac23_the_focus_ring_in_the_bar_is_white_and_inset(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_fx01(window, live_server, fx01_grid, size)
    select_mime(page)

    Walker(page).tab_to("flag-button")
    button = page.get_by_test_id("flag-button")

    assert style_of(button, "outlineStyle") == "solid"
    assert style_of(button, "outlineWidth") == "2px"
    expect_colour(button, "outlineColor", WHITE)
    assert style_of(button, "outlineOffset") == "-4px"


def test_ac23_on_a_phone_the_bar_is_as_wide_as_the_window(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_fx01(window, live_server, fx01_grid, (360, 740))

    box = box_of(page.get_by_test_id("clue-bar"))

    assert same_size(box.width, 360.0), box


def test_ac23_on_a_computer_the_bar_is_as_wide_as_the_grid_and_under_it(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_fx01(window, live_server, fx01_grid, (1280, 720))

    box = box_of(page.get_by_test_id("clue-bar"))
    grid_box = box_of(page.get_by_test_id("grid"))

    assert same_position(box.width, grid_box.width), (box, grid_box)
    assert same_position(box.left, grid_box.left), (box, grid_box)


def test_ac23_on_a_narrow_column_the_bar_fills_the_play_area(
    window: OpenWindow, live_server: str, fx02_grid: Grid
) -> None:
    page = window(568, 320, False)
    open_room(page, live_server, snapshot_frame(grid_view(fx02_grid), players_up_to(3)))
    expect(page.get_by_test_id("salon")).to_be_visible()

    box = box_of(page.get_by_test_id("clue-bar"))
    salon_box = box_of(page.get_by_test_id("salon"))
    content_width = salon_box.left - 24.0

    assert same_position(box.width, content_width), (box, salon_box)
    assert box.width < 320.0, box


# ---- AC-24: the chevrons -------------------------------------------------------------


def open_tamis(page: Page, base_url: str, grid: Grid) -> RoomMock:
    """FX-01 with TAMIS full and every other letter cell empty."""
    view = fx01_view(grid, letters_of(TAMIS))
    return open_room(page, base_url, snapshot_frame(view, players_up_to(3)))


def selections_sent(frames: list[str]) -> list[object]:
    """The `select_cell` messages among the frames, parsed."""
    found: list[object] = []
    for frame in frames:
        message = parse_client_message(frame)
        if isinstance(message, SelectCell):
            found.append(message)
    return found


def test_ac24_next_from_nothing_selects_the_first_unfinished_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_tamis(page, live_server, fx01_grid)

    frames = frames_sent_after(page, mock, page.get_by_test_id("clue-next").click)

    expect_word(page, "0,0,1")
    expect_selected(page, 0, 1)
    assert selections_sent(frames) == [
        SelectCell(row=0, column=1, direction=Direction.DOWN)
    ]


def test_ac24_next_and_previous_walk_the_unfinished_words(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_tamis(page, live_server, fx01_grid)
    next_button = page.get_by_test_id("clue-next")

    next_button.click()
    expect_word(page, "0,0,1")
    next_button.click()
    expect_word(page, "0,2,0")
    page.get_by_test_id("clue-prev").click()

    expect_word(page, "0,0,1")


def test_ac24_a_pointer_press_on_next_keeps_the_focus_on_the_grid(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_tamis(page, live_server, fx01_grid)
    cell_at(page, 2, 0).click()
    expect_word(page, "2,0,0")
    expect(page.get_by_test_id("grid")).to_be_focused()
    box = box_of(page.get_by_test_id("clue-next"))

    page.mouse.click(box.centre_x, box.centre_y)
    expect_word(page, "3,0,0")
    expect_selected(page, 3, 1)
    expect(page.get_by_test_id("grid")).to_be_focused()
    page.keyboard.press("I")

    expect(cell_at(page, 3, 1).get_by_test_id("cell-letter")).to_have_text("I")


def test_ac24_from_the_keyboard_next_moves_and_keeps_its_focus(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_tamis(page, live_server, fx01_grid)

    Walker(page).tab_to("clue-next")
    page.keyboard.press("Enter")

    expect_word(page, "0,0,1")
    assert focused_test_id(page) == "clue-next"


def test_ac24_with_no_unfinished_word_the_chevrons_change_and_send_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        snapshot_frame(full_wrong_view(fx01_grid), players_up_to(3)),
    )
    select_mime(page)

    for test_id in ("clue-next", "clue-prev"):
        frames = frames_sent_after(page, mock, page.get_by_test_id(test_id).click)
        assert frames == [], test_id
        expect_word(page, "0,2,0")
        expect_selected(page, 2, 2)


# ---- AC-25: the reaction picker over the grid ----------------------------------------


def open_picker(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int]
) -> Page:
    """The FX-01 room at `size`, the clue (0, 3) tapped and the picker open."""
    page = open_fx01(window, base_url, grid, size)
    cell_at(page, 0, 3).click()
    expect_word(page, "0,3,0")
    page.get_by_test_id("react-button").click()
    expect(page.get_by_test_id("reaction-picker")).to_be_visible()
    return page


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac25_the_picker_floats_centred_8_px_above_the_grids_bottom(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_picker(window, live_server, fx01_grid, size)
    picker = page.get_by_test_id("reaction-picker")

    box = box_of(picker)
    viewport_box = box_of(page.get_by_test_id("grid-viewport"))

    assert same_position(box.centre_x, viewport_box.centre_x), (box, viewport_box)
    assert same_position(box.bottom, viewport_box.bottom - 8.0), (box, viewport_box)
    assert style_of(picker, "zIndex") == "9"
    expect_colour(picker, "backgroundColor", WHITE)
    assert border_problems(picker, "Top", "1px", "solid", LINE) == []
    assert style_of(picker, "borderTopLeftRadius") == "24px"
    assert padding_matches(picker, "5px")


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac25_each_option_is_a_40_px_round_button_word_blue_on_hover(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_picker(window, live_server, fx01_grid, size)
    options = page.get_by_test_id("reaction-option")

    problems: list[str] = []
    for index in range(options.count()):
        option = options.nth(index)
        box = box_of(option)
        if not (same_size(box.width, 40.0) and same_size(box.height, 40.0)):
            problems.append(f"option {index}: {box.width} by {box.height}")
        if style_of(option, "borderTopLeftRadius") != "20px":
            problems.append(f"option {index}: radius")
        if not is_clear(colour_of(option, "backgroundColor")):
            problems.append(f"option {index}: background")
        size_px = float(style_of(option, "fontSize").removesuffix("px"))
        if not same_font_size(size_px, 22.0):
            problems.append(f"option {index}: font size {size_px}")
    options.first.hover()

    assert options.count() == 5
    assert problems == []
    expect_colour(options.first, "backgroundColor", WORD)


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac25_react_button_shows_the_open_picker_and_a_second_click_closes_it(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_picker(window, live_server, fx01_grid, size)
    button = page.get_by_test_id("react-button")
    page.mouse.move(1, 1)

    expect(button).to_have_attribute("aria-expanded", "true")
    expect_colour(button, "backgroundColor", WHITE)
    button.click()

    expect(page.get_by_test_id("reaction-picker")).not_to_be_visible()


# ---- AC-25: a shown reaction is a pill over its clue (WP-2) -------------------------


def show_reaction(
    window: OpenWindow,
    base_url: str,
    grid: Grid,
    size: tuple[int, int],
    clue: ClueRef,
) -> Page:
    """The FX-01 room at `size`, once `p2`'s `clap` on `clue` shows."""
    page = window(size[0], size[1], False)
    mock = open_room(page, base_url, snapshot_frame(fx01_view(grid), players_up_to(3)))
    mock.send(reaction_frame("p2", clue, Reaction.CLAP))
    expect(page.get_by_test_id("clue-reaction")).to_have_count(1)
    return page


def pill_look_problems(pill: Locator) -> list[str]:
    """How a `clue-reaction` differs from the white pill of "Reactions"."""
    problems: list[str] = []
    background = colour_of(pill, "backgroundColor")
    if not colour_matches(background, WHITE):
        problems.append(f"background {background}")
    problems.extend(border_problems(pill, "Top", "1px", "solid", LINE))
    problems.extend(border_problems(pill, "Bottom", "1px", "solid", LINE))
    if style_of(pill, "borderTopLeftRadius") != "12px":
        problems.append(f"radius {style_of(pill, 'borderTopLeftRadius')}")
    if not padding_matches(pill, "2px 6px"):
        problems.append(f"padding {padding_of(pill)}")
    if not same_font_size(font_size_of(pill), 16.0):
        problems.append(f"font-size {font_size_of(pill)}")
    line_height = style_of(pill, "lineHeight")
    if not line_height.endswith("px") or not same_font_size(px(line_height), 19.2):
        problems.append(f"line-height {line_height}")
    if style_of(pill, "zIndex") != "8":
        problems.append(f"z-index {style_of(pill, 'zIndex')}")
    shadow = shadow_of(pill)
    if (shadow.x, shadow.y, shadow.blur, shadow.spread) != (0, 4, 10, -4):
        problems.append(f"box-shadow {shadow.text}")
    if shadow.colour is None or not colour_matches(
        shadow.colour, INK, SHADOW_SOFT_ALPHA
    ):
        problems.append(f"box-shadow colour {shadow.colour}")
    return problems


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac25_a_shown_reaction_is_a_white_pill_with_a_line_grey_border(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = show_reaction(window, live_server, fx01_grid, size, IDES)

    assert pill_look_problems(page.get_by_test_id("clue-reaction")) == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac25_the_pill_is_centred_on_its_clue_and_drawn_on_top(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = show_reaction(window, live_server, fx01_grid, size, IDES)

    box = box_of(page.get_by_test_id("clue-reaction"))
    clue_box = box_of(clue_at(page, IDES))

    assert same_position(box.centre_x, clue_box.centre_x), (box, clue_box)
    assert same_position(box.centre_y, clue_box.centre_y), (box, clue_box)
    assert hit_problem(page, "clue-reaction") is None


# The boxes of the two `clue` elements of a clue cell, in document order.
CLUE_BOXES_SCRIPT = r"""
cell => {
  const found = [];
  for (const clue of cell.querySelectorAll('[data-testid="clue"]')) {
    const rect = clue.getBoundingClientRect();
    found.push([rect.left, rect.top, rect.right, rect.bottom]);
  }
  return found;
}
"""


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac25_on_a_two_clue_cell_the_pill_is_centred_on_its_lower_clue(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = show_reaction(window, live_server, fx01_grid, size, NAVAL)

    found = cell_at(page, 0, 0).evaluate(CLUE_BOXES_SCRIPT)
    assert isinstance(found, list), found
    assert len(found) == 2, found
    first_clue = to_box(found[0])
    second_clue = to_box(found[1])
    lower = second_clue if second_clue.top > first_clue.top else first_clue
    box = box_of(page.get_by_test_id("clue-reaction"))

    assert same_position(box.centre_x, lower.centre_x), (box, lower)
    assert same_position(box.centre_y, lower.centre_y), (box, lower)
