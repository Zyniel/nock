"""Tests of spec 043, AC-19 and AC-20: the Joueurs tab.

AC-19: each `roster-player` row is two lines, the player's dot, name and tags on
the first, their state and the clue of their selected word on the second, with
the host's « Couper » and « Retirer » on the other players' rows. AC-20: the
invitation link sits under the players, with « Copier le lien » and its
confirmation line.

Choices where the spec leaves room:

- "Line 1 above line 2": the lowest bottom of `roster-colour`, `roster-nickname`,
  `roster-you` and `roster-host` is at or above the highest top of
  `roster-state`, `roster-sep` and `roster-clue` (1 px).
- "Inside the row and the Salon" and "right of `roster-host` and
  `roster-nickname`" have the position tolerance of 1 px.
- AC-20's "as wide as `share-panel`'s content" is the panel's content box: its
  box less its padding and borders.
- The live clipboard check runs on spec 011's room, registered on FX-01 and
  entered with `enter_room`, in a context granted the clipboard permissions.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from hud_harness import live_role_problems
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import Direction, PlayerState
from room_panels import show_tab
from spec011_harness import EnterRoom, open_fx01_room
from spec019_harness import OpenWindow, window_opener
from spec041_harness import shadow_of
from spec042_harness import box_of, colour_of
from spec043_harness import (
    CLUE_BG,
    GREEN,
    INK,
    MUTED,
    NAVY,
    RULE,
    WHITE,
    Box,
    border_problems,
    colour_matches,
    expect_colour,
    fr_format,
    fr_value,
    fx01_view,
    open_room,
    padding_matches,
    pictogram_of,
    player,
    players_up_to,
    same_font_size,
    same_position,
    select_mime,
    selecting,
    selection_frame,
    shows_pictogram,
    snapshot_frame,
    style_of,
)

SIZES = [(360, 740), (1280, 720)]
SIZE_IDS = ["360x740", "1280x720"]
ROW = '[data-testid="roster-player"][data-player-id="{player_id}"]'
LINE_ONE = ["roster-colour", "roster-nickname", "roster-you", "roster-host"]
LINE_TWO = ["roster-state", "roster-sep", "roster-clue"]
OTHER_ROWS = {"p2": "Jean-Luc", "p3": "Cy", "p4": "Dee"}

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def ac19_frame(grid: Grid, *, host: str = "p1") -> str:
    """`p1` (host), `p2` (`JEAN-LUC`, idle, on (1, 0) across), `p3` (`CY`,
    disconnected) and `p4` (`DEE`), the last two with no selection."""
    players = [
        player("p1", host=host == "p1"),
        player(
            "p2",
            nickname="JEAN-LUC",
            host=host == "p2",
            state=PlayerState.IDLE,
            selection=selecting(1, 0, Direction.ACROSS),
        ),
        player("p3", state=PlayerState.DISCONNECTED),
        player("p4"),
    ]
    return snapshot_frame(fx01_view(grid), players)


def open_ac19(
    window: OpenWindow,
    base_url: str,
    grid: Grid,
    size: tuple[int, int],
    host: str = "p1",
) -> Page:
    """AC-19's room at `size`, MIME selected, the Joueurs tab shown."""
    page = window(size[0], size[1], False)
    open_room(page, base_url, ac19_frame(grid, host=host))
    select_mime(page)
    show_tab(page, "players")
    return page


def row_of(page: Page, player_id: str) -> Locator:
    return page.locator(ROW.format(player_id=player_id))


def part_boxes(page: Page, player_id: str, names: list[str]) -> dict[str, Box]:
    """The boxes of the parts of a row that are on the page."""
    boxes: dict[str, Box] = {}
    row = row_of(page, player_id)
    for name in names:
        part = row.get_by_test_id(name)
        if part.count() == 1:
            boxes[name] = box_of(part)
    return boxes


# ---- AC-19: the Joueurs rows ---------------------------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac19_the_rows_come_in_snapshot_order_each_on_two_lines(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_ac19(window, live_server, fx01_grid, size)

    order = page.get_by_test_id("roster-player").evaluate_all(
        "rows => rows.map(row => row.getAttribute('data-player-id'))"
    )
    problems: list[str] = []
    for player_id in ("p1", "p2", "p3", "p4"):
        line_one = part_boxes(page, player_id, LINE_ONE)
        line_two = part_boxes(page, player_id, LINE_TWO)
        if "roster-nickname" not in line_one or "roster-state" not in line_two:
            problems.append(f"{player_id}: no roster-nickname or roster-state")
            continue
        lowest = max(box.bottom for box in line_one.values())
        highest = min(box.top for box in line_two.values())
        if lowest > highest + 1.0:
            problems.append(
                f"{player_id}: line 1 ends at {lowest}, line 2 at {highest}"
            )
        nickname_left = line_one["roster-nickname"].left
        if not same_position(line_two["roster-state"].left, nickname_left):
            problems.append(f"{player_id}: line 2 is not on the nickname's left edge")

    assert order == ["p1", "p2", "p3", "p4"]
    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac19_my_row_is_bold_with_the_you_and_host_tags_and_my_clue(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_ac19(window, live_server, fx01_grid, size)
    row = row_of(page, "p1")
    host_tag = row.get_by_test_id("roster-host")

    assert style_of(row.get_by_test_id("roster-nickname"), "fontWeight") == "700"
    expect(row.get_by_test_id("roster-you")).to_have_text(fr_value("roster.you"))
    expect(host_tag).to_have_text(fr_value("roster.host"))
    expect_colour(host_tag, "backgroundColor", CLUE_BG)
    expect_colour(host_tag, "color", NAVY)
    assert style_of(host_tag, "fontWeight") == "600"
    assert same_font_size(
        float(style_of(host_tag, "fontSize").removesuffix("px")), 11.52
    )
    assert style_of(host_tag, "borderTopLeftRadius") == "10px"
    expect(row.get_by_test_id("roster-clue")).to_have_text("Artiste muet")


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac19_another_players_row_shows_their_state_and_clue_in_muted_text(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_ac19(window, live_server, fx01_grid, size)
    row = row_of(page, "p2")
    state = row.get_by_test_id("roster-state")
    clue = row.get_by_test_id("roster-clue")
    separator = row.get_by_test_id("roster-sep")

    assert style_of(row.get_by_test_id("roster-nickname"), "fontWeight") == "400"
    expect(state).to_have_text(fr_value("presence.idle"))
    expect(clue).to_have_text("Passoire fine")
    for part in (state, clue):
        assert same_font_size(
            float(style_of(part, "fontSize").removesuffix("px")), 13.6
        )
        expect_colour(part, "color", MUTED)
    reading = pictogram_of(separator)
    assert reading["ariaHidden"] == "true"
    assert reading["textNodes"] == 0
    assert shows_pictogram(reading, "\N{MIDDLE DOT}"), reading


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac19_a_player_with_no_selection_has_no_clue_and_no_separator(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_ac19(window, live_server, fx01_grid, size)

    for player_id in ("p3", "p4"):
        row = row_of(page, player_id)
        expect(row.get_by_test_id("roster-clue")).to_have_count(0)
        expect(row.get_by_test_id("roster-sep")).to_have_count(0)


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac19_each_dot_is_10_px_with_its_ring(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_ac19(window, live_server, fx01_grid, size)

    problems: list[str] = []
    for player_id in ("p1", "p2", "p3", "p4"):
        dot = row_of(page, player_id).get_by_test_id("roster-colour")
        box = box_of(dot)
        shadow = shadow_of(dot)
        if abs(box.width - 10.0) > 0.5 or abs(box.height - 10.0) > 0.5:
            problems.append(f"{player_id}: dot {box.width} by {box.height}")
        if shadow.spread != 1 or shadow.blur != 0 or (shadow.x, shadow.y) != (0, 0):
            problems.append(f"{player_id}: ring {shadow.text}")
        if shadow.colour is None or not colour_matches(shadow.colour, INK, 0.55):
            problems.append(f"{player_id}: ring colour {shadow.colour}")
    assert problems == []


def small_button_problems(page: Page, player_id: str, test_id: str) -> list[str]:
    """How a row's `mute-player` or `remove-player` differs from AC-19's button."""
    button = row_of(page, player_id).get_by_test_id(test_id)
    problems: list[str] = []
    classes = str(button.get_attribute("class")).split()
    if "nock-button" not in classes:
        problems.append(f"{player_id} {test_id}: classes {classes}")
    if not colour_matches(colour_of(button, "backgroundColor"), WHITE):
        problems.append(f"{player_id} {test_id}: background")
    if not colour_matches(colour_of(button, "color"), NAVY):
        problems.append(f"{player_id} {test_id}: colour")
    if not colour_matches(colour_of(button, "borderTopColor"), NAVY):
        problems.append(f"{player_id} {test_id}: border colour")
    size = float(style_of(button, "fontSize").removesuffix("px"))
    if not same_font_size(size, 12.8):
        problems.append(f"{player_id} {test_id}: font size {size}")
    if not padding_matches(button, "6px 10px"):
        problems.append(f"{player_id} {test_id}: padding")
    box = box_of(button)
    if box.width < 24.0 - 0.5 or box.height < 24.0 - 0.5:
        problems.append(f"{player_id} {test_id}: {box.width} by {box.height}")
    return problems


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac19_the_host_has_mute_then_remove_on_each_other_row(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_ac19(window, live_server, fx01_grid, size)

    problems: list[str] = []
    expect(row_of(page, "p1").get_by_test_id("mute-player")).to_have_count(0)
    expect(row_of(page, "p1").get_by_test_id("remove-player")).to_have_count(0)
    for player_id, name in OTHER_ROWS.items():
        row = row_of(page, player_id)
        mute = row.get_by_test_id("mute-player")
        remove = row.get_by_test_id("remove-player")
        expect(mute).to_have_count(1)
        expect(remove).to_have_count(1)
        follows = mute.evaluate(
            "(mute, remove) => (mute.compareDocumentPosition(remove)"
            " & Node.DOCUMENT_POSITION_FOLLOWING) !== 0",
            remove.element_handle(),
        )
        if follows is not True:
            problems.append(f"{player_id}: remove-player does not follow mute-player")
        expect(remove).to_have_text(fr_value("host.remove"))
        expect(remove).to_have_attribute(
            "aria-label", fr_format("host.remove_label", name=name)
        )
        expect(mute).to_have_text(fr_value("chat.mute"))
        expect(mute).to_have_attribute(
            "aria-label", fr_format("chat.mute_label", name=name)
        )
        problems.extend(small_button_problems(page, player_id, "mute-player"))
        problems.extend(small_button_problems(page, player_id, "remove-player"))
    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac19_the_buttons_lie_inside_their_row_and_right_of_the_name(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_ac19(window, live_server, fx01_grid, size)
    salon_box = box_of(page.get_by_test_id("salon"))

    problems: list[str] = []
    for player_id in OTHER_ROWS:
        row = row_of(page, player_id)
        row_box = box_of(row)
        name_box = box_of(row.get_by_test_id("roster-nickname"))
        for test_id in ("mute-player", "remove-player"):
            box = box_of(row.get_by_test_id(test_id))
            for outer_name, outer in (("row", row_box), ("salon", salon_box)):
                inside = (
                    box.left >= outer.left - 1.0
                    and box.right <= outer.right + 1.0
                    and box.top >= outer.top - 1.0
                    and box.bottom <= outer.bottom + 1.0
                )
                if not inside:
                    problems.append(f"{player_id} {test_id}: outside the {outer_name}")
            if box.left < name_box.right - 1.0:
                problems.append(f"{player_id} {test_id}: not right of the name")
    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac19_a_players_clue_follows_their_selection_within_300_ms(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = window(size[0], size[1], False)
    mock = open_room(page, live_server, ac19_frame(fx01_grid))
    show_tab(page, "players")
    row = row_of(page, "p2")

    mock.send(selection_frame("p2", selecting(2, 1, Direction.ACROSS)))
    expect(row.get_by_test_id("roster-clue")).to_have_text("Sans contenu", timeout=300)
    mock.send(selection_frame("p2", None))

    expect(row.get_by_test_id("roster-clue")).to_have_count(0, timeout=300)
    expect(row.get_by_test_id("roster-sep")).to_have_count(0)


def test_ac19_a_guest_sees_no_host_buttons(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_ac19(window, live_server, fx01_grid, (1280, 720), host="p2")

    expect(page.get_by_test_id("roster-player")).to_have_count(4)
    expect(page.get_by_test_id("mute-player")).to_have_count(0)
    expect(page.get_by_test_id("remove-player")).to_have_count(0)


# ---- AC-20: the invitation under the players -----------------------------------------


def open_players(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int]
) -> Page:
    page = window(size[0], size[1], False)
    open_room(page, base_url, snapshot_frame(fx01_view(grid), players_up_to(3)))
    show_tab(page, "players")
    return page


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac20_the_share_panel_comes_after_the_players_list(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_players(window, live_server, fx01_grid, size)
    roster = page.get_by_test_id("roster")

    found = roster.evaluate(
        "roster => { const list = roster.querySelector('ul');"
        " const panel = roster.querySelector('[data-testid=\"share-panel\"]');"
        " return list !== null && panel !== null"
        " && (list.compareDocumentPosition(panel)"
        " & Node.DOCUMENT_POSITION_FOLLOWING) !== 0"
        " && !list.contains(panel); }"
    )

    assert found is True


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac20_the_share_label_is_a_muted_uppercase_section_heading(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_players(window, live_server, fx01_grid, size)
    label = page.get_by_test_id("share-label")

    expect(label).to_have_text(fr_value("room.share.label"))
    assert style_of(label, "textTransform") == "uppercase"
    assert style_of(label, "fontWeight") == "600"
    assert same_font_size(float(style_of(label, "fontSize").removesuffix("px")), 12.48)
    expect_colour(label, "color", MUTED)


CONTENT_BOX_SCRIPT = r"""
element => {
  const style = getComputedStyle(element);
  const rect = element.getBoundingClientRect();
  return rect.width - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)
    - parseFloat(style.borderLeftWidth) - parseFloat(style.borderRightWidth);
}
"""


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac20_the_share_link_is_a_one_line_url_box_as_wide_as_the_panel(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_players(window, live_server, fx01_grid, size)
    link = page.get_by_test_id("share-link")
    expected = f"{live_server}/r/ABC123"

    tag = link.evaluate("element => element.tagName")
    content_width = page.get_by_test_id("share-panel").evaluate(CONTENT_BOX_SCRIPT)

    assert tag == "A"
    expect(link).to_have_attribute("href", expected)
    expect(link).to_have_text(expected)
    assert same_position(box_of(link).width, float(content_width))
    assert border_problems(link, "Top", "1px", "solid", RULE) == []
    assert style_of(link, "borderTopLeftRadius") == "6px"
    assert padding_matches(link, "8px 10px")
    assert same_font_size(float(style_of(link, "fontSize").removesuffix("px")), 13.6)
    assert style_of(link, "whiteSpace") == "nowrap"
    assert style_of(link, "overflowX") == "hidden"
    assert style_of(link, "textOverflow") == "ellipsis"


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac20_copy_link_is_the_primary_button(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_players(window, live_server, fx01_grid, size)
    button = page.get_by_test_id("copy-link")

    expect(button).to_have_text(fr_value("room.share.copy"))
    expect_colour(button, "backgroundColor", NAVY)
    expect_colour(button, "color", WHITE)


@pytest.fixture
def clipboard_page(browser: Browser) -> Iterator[Page]:
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    try:
        yield context.new_page()
    finally:
        context.close()


@pytest.mark.only_browser("chromium")
def test_ac20_a_copy_puts_the_link_in_the_clipboard_and_shows_the_green_line(
    clipboard_page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    page = clipboard_page
    link = open_fx01_room(enter_room, page, live_server, room_registry, fx01_grid)
    show_tab(page, "players")
    button = page.get_by_test_id("copy-link")

    button.click()

    copied = page.get_by_test_id("share-copied")
    expect(copied).to_have_text(fr_value("room.share.copied"))
    assert live_role_problems(copied) == []
    expect_colour(copied, "color", GREEN)
    assert style_of(copied, "fontWeight") == "500"
    assert same_font_size(float(style_of(copied, "fontSize").removesuffix("px")), 13.6)
    expect(button).to_have_text(fr_value("room.share.copy"))
    assert page.evaluate("navigator.clipboard.readText()") == link
    page.wait_for_timeout(2500)
    expect(copied).to_have_count(0)
