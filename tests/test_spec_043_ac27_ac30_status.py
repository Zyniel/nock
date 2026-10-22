"""Tests of spec 043, AC-27 and AC-30: the completion status, and the players'
icons in the Accessibilité mode.

AC-30: with `access-switch` on, each player dot, `roster-colour` in the Joueurs
rows (work package WP-1, spec 042's rule) and `chat-dot` in the stream (WP-2),
holds its player's 12 px icon on no background and no ring; with it off again,
the dots have their colours back. (AC-26, the notes, is in
`test_spec_043_ac26_notes.py` and `test_spec_043_ac26_note_lifetime.py`.)

AC-27: the completion status is a band under the clue bar, holding « Voir le
bilan » once solved, and sits in the clue bar's row only in the sheet layout of a
low window while the in-app keyboard shows. AC-27's case "at 568 by 320 in the
touch context, the solved page has no `keyboard` and `data-layout="column"`" is
not tested here: it is spec 044's (the keyboard goes away once solved, "in step 4"
says the note of "Completion status"), and this step keeps the keyboard on a
solved page (spec 026 AC-5).

Choices where the spec leaves room:

- The band's text is its text outside `recap-open`; its colour and font are those
  of the element holding it.
- "The band's content right edge" is its box less its right padding (12 px).
- AC-30: a `roster-colour`'s colour index is its row's `data-colour`, a
  `chat-dot`'s its own `data-colour`; "no ring" (spec 043's "Discussion") is a
  computed `box-shadow` of `none`, checked on the `chat-dot` elements.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import GridFullWrong
from room_panels import open_menu, show_tab
from spec019_harness import OpenWindow, window_opener
from spec042_harness import (
    PLAYER_COLOURS,
    READERS_JS,
    box_of,
    icon_shape_problems,
)
from spec043_harness import (
    CLUE_BG,
    GREEN,
    GREEN_BG,
    NAVY,
    WHITE,
    Reading,
    RoomMock,
    chat_line,
    colour_matches,
    expect_closed,
    expect_colour,
    expect_layout,
    fr_value,
    full_wrong_view,
    fx01_view,
    is_clear,
    open_room,
    padding_matches,
    player,
    players_up_to,
    same_font_size,
    same_position,
    send_and_wait,
    snapshot_frame,
    solved_view,
    style_of,
    to_box,
)

SIZES = [(1280, 720), (360, 740)]
SIZE_IDS = ["1280x720", "360x740"]

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- AC-27: the completion status ----------------------------------------------------

STATUS_TEXT_SCRIPT = "status => {\n" + READERS_JS + r"""
const nodes = [];
const walker = document.createTreeWalker(status, NodeFilter.SHOW_TEXT);
for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
  const inButton = node.parentElement.closest('[data-testid="recap-open"]') !== null;
  if (!inButton && node.textContent.trim() !== '') {
    nodes.push(node);
  }
}
if (nodes.length === 0) {
  return null;
}
const holder = nodes[0].parentElement;
const style = getComputedStyle(holder);
const range = document.createRange();
range.setStartBefore(nodes[0]);
range.setEndAfter(nodes[nodes.length - 1]);
let text = '';
for (const node of nodes) {
  text += node.textContent;
}
return {text: text.trim(), colour: parseColour(style.color),
  fontWeight: style.fontWeight, fontSize: style.fontSize, box: boxOf(range)};
}"""


# Where the status's check mark is drawn against its text, in reading order: for
# each element of `grid-status` (outside `recap-open`) whose `::before` or `::after`
# draws `glyph`, whether that pictogram comes before the first text node. A
# `::before` comes before the text when its element holds the text or precedes it;
# an `::after` only when its element precedes the text without holding it.
PICTOGRAM_PLACE_SCRIPT = r"""
(status, glyph) => {
  const walker = document.createTreeWalker(status, NodeFilter.SHOW_TEXT);
  let first = null;
  for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
    const inButton = node.parentElement.closest('[data-testid="recap-open"]');
    if (inButton === null && node.textContent.trim() !== '') {
      first = node;
      break;
    }
  }
  if (first === null) {
    return [];
  }
  const drawn = `"${glyph}"`;
  const precedes = element => (element.compareDocumentPosition(first)
    & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
  const places = [];
  for (const element of [status, ...status.querySelectorAll('*')]) {
    if (element.closest('[data-testid="recap-open"]') !== null) {
      continue;
    }
    const holds = element.contains(first);
    if (getComputedStyle(element, '::before').content === drawn) {
      places.push(holds || precedes(element) ? 'before' : 'after');
    }
    if (getComputedStyle(element, '::after').content === drawn) {
      places.push(!holds && precedes(element) ? 'before' : 'after');
    }
  }
  return places;
}
"""


def pictogram_places(page: Page, glyph: str) -> list[str]:
    """Where each `glyph` pictogram of `grid-status` is, `before` or `after` text."""
    status = page.get_by_test_id("grid-status")
    found = status.evaluate(PICTOGRAM_PLACE_SCRIPT, glyph)
    assert isinstance(found, list), found
    return [str(place) for place in found]


def status_text(page: Page) -> Reading:
    found = page.get_by_test_id("grid-status").evaluate(STATUS_TEXT_SCRIPT)
    assert isinstance(found, dict), "grid-status holds no text"
    return found


def open_solved(page: Page, base_url: str, grid: Grid) -> RoomMock:
    frame = snapshot_frame(solved_view(grid), players_up_to(3), solved=True)
    mock = open_room(page, base_url, frame)
    expect(page.get_by_test_id("grid-status")).to_have_attribute("data-state", "solved")
    return mock


def open_full_wrong(page: Page, base_url: str, grid: Grid) -> RoomMock:
    frame = snapshot_frame(full_wrong_view(grid), players_up_to(3))
    mock = open_room(page, base_url, frame)
    send_and_wait(page, mock, GridFullWrong(seq=6).model_dump_json())
    expect(page.get_by_test_id("grid-status")).to_have_attribute(
        "data-state", "full_wrong"
    )
    return mock


@pytest.mark.parametrize(("width", "height"), SIZES, ids=SIZE_IDS)
def test_ac27_the_solved_status_is_a_green_band_under_the_clue_bar(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = window(width, height, False)
    open_solved(page, live_server, fx01_grid)
    status = page.get_by_test_id("grid-status")

    box = box_of(status)
    bar_box = box_of(page.get_by_test_id("clue-bar"))

    assert same_position(box.top, bar_box.bottom), (box, bar_box)
    assert same_position(box.left, bar_box.left), (box, bar_box)
    assert same_position(box.right, bar_box.right), (box, bar_box)
    expect_colour(status, "backgroundColor", GREEN_BG)
    assert padding_matches(status, "8px 12px")


@pytest.mark.parametrize(("width", "height"), SIZES, ids=SIZE_IDS)
def test_ac27_the_solved_text_is_green_after_its_check_pictogram(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = window(width, height, False)
    open_solved(page, live_server, fx01_grid)

    text = status_text(page)

    assert text["text"] == fr_value("completion.solved")
    assert colour_matches(text["colour"], GREEN), text
    assert text["fontWeight"] == "600"
    assert same_font_size(float(str(text["fontSize"]).removesuffix("px")), 15.2)
    assert pictogram_places(page, "\N{CHECK MARK}") == ["before"]


@pytest.mark.parametrize(("width", "height"), SIZES, ids=SIZE_IDS)
def test_ac27_voir_le_bilan_is_the_primary_button_at_the_bands_right(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = window(width, height, False)
    open_solved(page, live_server, fx01_grid)
    status = page.get_by_test_id("grid-status")
    button = status.get_by_test_id("recap-open")
    expect(button).to_have_count(1)

    box = box_of(button)
    band_box = box_of(status)
    text_box = to_box(status_text(page)["box"])

    assert box.left >= text_box.right - 1.0, (box, text_box)
    assert same_position(box.right, band_box.right - 12.0), (box, band_box)
    expect_colour(button, "backgroundColor", NAVY)
    expect_colour(button, "color", WHITE)
    assert padding_matches(button, "7px 12px")
    assert same_font_size(float(style_of(button, "fontSize").removesuffix("px")), 13.6)


def test_ac27_a_click_on_voir_le_bilan_opens_the_recap(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_solved(page, live_server, fx01_grid)

    page.get_by_test_id("recap-open").click()

    expect(page.get_by_test_id("recap")).to_be_visible()


@pytest.mark.parametrize(("width", "height"), SIZES, ids=SIZE_IDS)
def test_ac27_the_full_but_wrong_status_is_a_navy_on_blue_grey_band(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = window(width, height, False)
    open_full_wrong(page, live_server, fx01_grid)
    status = page.get_by_test_id("grid-status")

    text = status_text(page)

    expect_colour(status, "backgroundColor", CLUE_BG)
    assert colour_matches(text["colour"], NAVY), text
    expect(page.get_by_test_id("recap-open")).to_have_count(0)


def test_ac27_on_a_low_touch_window_full_but_wrong_sits_in_the_clue_bars_row(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(568, 320, True)
    open_full_wrong(page, live_server, fx01_grid)
    expect_layout(page, "sheet")
    expect(page.get_by_test_id("keyboard")).to_be_visible()

    box = box_of(page.get_by_test_id("grid-status"))
    bar_box = box_of(page.get_by_test_id("clue-bar"))
    text_box = box_of(page.get_by_test_id("clue-bar-text"))
    react_box = box_of(page.get_by_test_id("react-button"))
    text = status_text(page)

    assert box.left >= bar_box.left - 1.0, (box, bar_box)
    assert box.right <= bar_box.right + 1.0, (box, bar_box)
    assert box.top >= bar_box.top - 1.0, (box, bar_box)
    assert box.bottom <= bar_box.bottom + 1.0, (box, bar_box)
    assert box.left >= text_box.right - 1.0, (box, text_box)
    assert box.right <= react_box.left + 1.0, (box, react_box)
    assert colour_matches(text["colour"], WHITE), text
    expect(page.get_by_test_id("recap-open")).to_have_count(0)


LOW_TOUCH_SIZES = [(568, 320), (740, 360)]


@pytest.mark.parametrize(
    ("width", "height"), LOW_TOUCH_SIZES, ids=["568x320", "740x360"]
)
def test_ac27_until_spec_044_a_solved_low_touch_window_sits_in_the_clue_bars_row(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    # Decision of 2026-10-22: until spec 044 hides the keyboard on a solved page,
    # the solved status sits in the clue bar's row like the full-and-wrong one,
    # with `recap-open` in the secondary button's colours.
    page = window(width, height, True)
    open_solved(page, live_server, fx01_grid)
    expect_layout(page, "sheet")
    expect(page.get_by_test_id("keyboard")).to_be_visible()
    button = page.get_by_test_id("grid-status").get_by_test_id("recap-open")
    expect(button).to_have_count(1)

    box = box_of(page.get_by_test_id("grid-status"))
    bar_box = box_of(page.get_by_test_id("clue-bar"))
    text_box = box_of(page.get_by_test_id("clue-bar-text"))
    react_box = box_of(page.get_by_test_id("react-button"))
    text = status_text(page)

    assert box.left >= bar_box.left - 1.0, (box, bar_box)
    assert box.right <= bar_box.right + 1.0, (box, bar_box)
    assert box.top >= bar_box.top - 1.0, (box, bar_box)
    assert box.bottom <= bar_box.bottom + 1.0, (box, bar_box)
    assert box.left >= text_box.right - 1.0, (box, text_box)
    assert box.right <= react_box.left + 1.0, (box, react_box)
    assert colour_matches(text["colour"], WHITE), text
    expect_colour(button, "backgroundColor", WHITE)
    expect_colour(button, "color", NAVY)
    expect_colour(button, "borderTopColor", NAVY)


@pytest.mark.parametrize("state", ["solved", "full_wrong"])
def test_ac27_on_a_low_desktop_window_the_status_is_under_the_bar(
    window: OpenWindow, live_server: str, fx01_grid: Grid, state: str
) -> None:
    page = window(568, 320, False)
    if state == "solved":
        open_solved(page, live_server, fx01_grid)
    else:
        open_full_wrong(page, live_server, fx01_grid)
    expect_layout(page, "column")

    box = box_of(page.get_by_test_id("grid-status"))
    bar_box = box_of(page.get_by_test_id("clue-bar"))

    assert box.top >= bar_box.bottom - 1.0, (box, bar_box)
    assert box.bottom <= 320.0 + 1.0, box


# ---- AC-30: the player dots show the players' icons ---------------------------------

# Each player dot of one kind: its colour index, background, ring and icons.
# `roster`: each `roster-colour`, its index on its `roster-player` row; `chat`: each
# `chat-dot`, its index on itself.
SWATCHES_SCRIPT = "kind => {\n" + READERS_JS + r"""
const dots = [];
if (kind === 'roster') {
  for (const row of document.querySelectorAll('[data-testid="roster-player"]')) {
    dots.push([row.querySelector('[data-testid="roster-colour"]'),
      row.getAttribute('data-colour')]);
  }
} else {
  for (const dot of document.querySelectorAll('[data-testid="chat-dot"]')) {
    dots.push([dot, dot.getAttribute('data-colour')]);
  }
}
const found = [];
for (const [dot, colour] of dots) {
  const icons = [];
  for (const svg of dot.querySelectorAll('[data-testid="player-icon"]')) {
    icons.push(svgOf(svg));
  }
  const style = getComputedStyle(dot);
  found.push({colour: colour, background: parseColour(style.backgroundColor),
    ring: style.boxShadow, icons: icons});
}
return found;
}"""


def swatches(page: Page, kind: str) -> list[Reading]:
    """The player dots of `kind`: `"roster"` (`roster-colour`) or `"chat"`."""
    found = page.evaluate(SWATCHES_SCRIPT, kind)
    assert isinstance(found, list), found
    return found


def icon_swatch_problems(swatch: Reading) -> list[str]:
    """How a dot differs from its player's 12 px icon on no background."""
    colour = str(swatch["colour"])
    problems: list[str] = []
    if not is_clear(swatch["background"]):
        problems.append(f"colour {colour}: background {swatch['background']}")
    if len(swatch["icons"]) != 1:
        problems.append(f"colour {colour}: {len(swatch['icons'])} icons")
        return problems
    icon = swatch["icons"][0]
    box = to_box(icon["box"])
    if abs(box.width - 12.0) > 0.5 or abs(box.height - 12.0) > 0.5:
        problems.append(f"colour {colour}: icon {box.width} by {box.height}")
    if icon["dataIcon"] != colour:
        problems.append(f"colour {colour}: data-icon {icon['dataIcon']}")
    problems.extend(icon_shape_problems(icon, int(colour)))
    return problems


def colour_swatch_problems(swatch: Reading) -> list[str]:
    """How a dot differs from its player's colour, with no icon."""
    index = int(str(swatch["colour"]))
    problems: list[str] = []
    if swatch["icons"] != []:
        problems.append(f"colour {index}: still {len(swatch['icons'])} icons")
    if not colour_matches(swatch["background"], PLAYER_COLOURS[index]):
        problems.append(f"colour {index}: background {swatch['background']}")
    return problems


def flip_access(page: Page, pressed: str) -> None:
    """Flip `access-switch` in the Menu, then close the Menu with `Escape`.

    The Menu stays open after a switch (AC-11) and would cover the Salon's tabs.
    """
    open_menu(page)
    switch = page.get_by_test_id("access-switch")
    switch.click()
    expect(switch).to_have_attribute("aria-pressed", pressed)
    page.keyboard.press("Escape")
    expect_closed(page.get_by_test_id("room-menu"))


def ac30_frame(grid: Grid) -> str:
    chat = [chat_line(3, "p2", "Salut"), chat_line(4, "p3", "IDES ?")]
    players = [player("p1", host=True), player("p2"), player("p3")]
    return snapshot_frame(fx01_view(grid), players, chat=chat)


def test_ac30_with_access_on_each_players_dot_holds_their_12_px_icon(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, ac30_frame(fx01_grid))

    flip_access(page, "true")
    show_tab(page, "players")

    problems: list[str] = []
    for swatch in swatches(page, "roster"):
        problems.extend(icon_swatch_problems(swatch))
    assert len(swatches(page, "roster")) == 3
    assert problems == []


def test_ac30_with_access_on_each_chat_dot_holds_its_players_icon_and_no_ring(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, ac30_frame(fx01_grid))

    flip_access(page, "true")
    show_tab(page, "discussion")

    found = swatches(page, "chat")
    problems: list[str] = []
    for swatch in found:
        problems.extend(icon_swatch_problems(swatch))
        if swatch["ring"] != "none":
            problems.append(f"colour {swatch['colour']}: ring {swatch['ring']}")
    assert [swatch["colour"] for swatch in found] == ["1", "2"]
    assert problems == []


def test_ac30_with_access_off_again_the_dots_have_their_colours_back(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, ac30_frame(fx01_grid))
    flip_access(page, "true")

    flip_access(page, "false")

    problems: list[str] = []
    for swatch in swatches(page, "roster"):
        problems.extend(colour_swatch_problems(swatch))
    assert problems == []


def test_ac30_with_access_off_again_the_chat_dots_have_their_colours_back(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, ac30_frame(fx01_grid))
    flip_access(page, "true")

    flip_access(page, "false")

    found = swatches(page, "chat")
    problems: list[str] = []
    for swatch in found:
        problems.extend(colour_swatch_problems(swatch))
    assert [swatch["colour"] for swatch in found] == ["1", "2"]
    assert problems == []
