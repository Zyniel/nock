"""Tests of spec 045, AC-6 to AC-8: the legend under the grid.

AC-6: while the mode is on, `authors-legend` follows `grid-viewport` in
`grid-area`, is hidden from screen readers, and names every player of the kept
snapshot in their ink, in join order, following `player_left` and
`player_joined` within 300 ms. AC-7: the legend has the design's look and sits
8 px under the grid. AC-8: the grid gives the legend its room (38 px, or `h + 8`
when it wraps), and nothing else moves. The shared setup is in `spec045_harness`.

Also tested, from "Edge cases and errors" and "The legend": the Accessibilité
mode (the names keep their inks, with no dot and no icon), a nickname inserted as
text (spec 037), and a legend that wraps is never wider than `grid-area`'s
content box.

Choices where the spec leaves room:

- AC-7's "short nicknames" are spec 043's `ANA`, `BOB`, `CY` and `DEE`.
- AC-8 turns the mode on in the Menu of the same page, after reading the boxes
  with the mode off, and reads them again once the layout has settled
  (`settle_layout`). "The same box" is each edge within 1 px; at 1280 by 720
  `clue-bar`'s left and right edges are within 1 px and its top and bottom within
  5 px.
- "The legend wraps onto more than one line" (AC-8): its items do not all have
  the same top (1 px).
- AC-8's eight long nicknames have 20 characters each (`LONG_NICKNAMES`).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import LeaveReason, PlayerState, PlayerView
from room_panels import expect_open
from spec019_harness import OpenWindow, window_opener
from spec042_harness import Box, to_box
from spec043_harness import (
    COMPUTER,
    FONT_TOLERANCE_PX,
    PHONE,
    POSITION_TOLERANCE_PX,
    SIZE_TOLERANCE_PX,
    RoomMock,
    border_problems,
    box_inside,
    colour_matches,
    expect_seq,
    fr_value,
    fx01_view,
    joined_frame,
    left_frame,
    padding_matches,
    player,
    players_up_to,
    snapshot_frame,
    style_of,
)
from spec045_harness import (
    INKS,
    LEGEND_BG,
    LEGEND_BG_ALPHA,
    LEGEND_GAP_PX,
    LINE,
    MUTED,
    ONE_LINE_ROOM_PX,
    boxes_of,
    eight_frame,
    legend_names,
    legend_of,
    legend_place_problems,
    legend_reading,
    name_ids,
    name_texts,
    names_within,
    open_page,
    overlap_area,
    required_box,
    set_mode,
    settle_layout,
)

LABEL_FONT_PX = 12.8  # 0.8rem
LABEL_LINE_HEIGHT_PX = 15.36  # 1.2
ONE_LINE_MAX_HEIGHT_PX = 26.0
CLUE_BAR_SHIFT_PX = 5.0  # AC-8 at 1280 by 720
GRID_LESS_MIN_PX = 35.0
GRID_LESS_MAX_PX = 40.0
SIZES = [PHONE, COMPUTER]
SIZE_IDS = ["360x740", "1280x720"]

AC6_SHOWN = ["Ana", "Jean-Luc", "Cy", "Dee", "Eve", "Fay", "Gus", "Hal"]
EIGHT_IDS = [f"p{number}" for number in range(1, 9)]

# Eight nicknames of 20 characters (AC-8), as the server stores them.
LONG_NICKNAMES = [
    "BARTHOLOMEW LEFEBVRE",
    "GENEVIEVE MONTAIGNES",
    "ALEXANDRINE DUVERNAY",
    "CHRISTOPHE BEAUCHAMP",
    "MARIE-CLAIRE FONTANE",
    "JEAN-BAPTISTE ROUSSY",
    "PHILIPPINE ROCHEFORT",
    "EMMANUELLE GRANDPRES",
]

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- AC-6: the names, in their inks, in join order ----


def ac6_players() -> list[PlayerView]:
    """`p1` to `p8`, `p2` named `JEAN-LUC` and `p3` disconnected."""
    players = players_up_to(8)
    players[1] = player("p2", nickname="JEAN-LUC")
    players[2] = player("p3", state=PlayerState.DISCONNECTED)
    return players


def open_ac6(window: OpenWindow, base_url: str, grid: Grid) -> tuple[Page, RoomMock]:
    page, mock = open_page(
        window, base_url, eight_frame(grid, players=ac6_players()), mode_on=True
    )
    return page, mock


def test_ac6_the_legend_follows_grid_viewport_in_grid_area_hidden_from_readers(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_ac6(window, live_server, fx01_grid)

    reading = legend_reading(page)

    assert reading["inGridArea"] is True
    assert reading["previousTestId"] == "grid-viewport"
    assert reading["ariaHidden"] == "true"


def test_ac6_the_label_comes_first_then_one_name_per_player_in_join_order(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_ac6(window, live_server, fx01_grid)

    reading = legend_reading(page)

    first = reading["items"][0]
    assert first["testId"] == "authors-legend-label"
    assert first["text"].strip() == fr_value("authors.legend")
    assert len(reading["items"]) == 9
    assert name_ids(reading) == EIGHT_IDS
    assert [text.strip() for text in name_texts(reading)] == AC6_SHOWN


def test_ac6_each_name_has_its_colour_index_weight_700_and_its_players_ink(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_ac6(window, live_server, fx01_grid)

    reading = legend_reading(page)

    problems: list[str] = []
    for index, name in enumerate(legend_names(reading)):
        if name["colourIndex"] != str(index):
            problems.append(f"{name['playerId']}: data-colour {name['colourIndex']}")
        if name["fontWeight"] != "700":
            problems.append(f"{name['playerId']}: font-weight {name['fontWeight']}")
        if not colour_matches(name["colour"], INKS[index]):
            problems.append(f"{name['playerId']}: color {name['colour']}")
    assert len(legend_names(reading)) == 8
    assert problems == []


def test_ac6_a_player_who_leaves_is_dropped_within_300_ms(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_page(
        window,
        live_server,
        eight_frame(fx01_grid, players=ac6_players()),
        mode_on=True,
    )
    legend_reading(page)

    mock.send(left_frame(6, "p4", LeaveReason.LEFT))
    expect_seq(page, 6)

    expected = ["p1", "p2", "p3", "p5", "p6", "p7", "p8"]
    reading = names_within(page, lambda found: name_ids(found) == expected)
    assert name_ids(reading) == expected


def test_ac6_a_player_who_joins_is_the_last_name_in_their_ink_within_300_ms(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_page(
        window,
        live_server,
        eight_frame(fx01_grid, players=ac6_players()),
        mode_on=True,
    )
    legend_reading(page)
    mock.send(left_frame(6, "p4", LeaveReason.LEFT))
    expect_seq(page, 6)

    mock.send(joined_frame(7, player("p9", colour=3, nickname="ZOÉ")))
    expect_seq(page, 7)

    reading = names_within(page, lambda found: name_ids(found)[-1:] == ["p9"])
    last = legend_names(reading)[-1]
    assert last["playerId"] == "p9"
    assert last["text"].strip() == "Zoé"
    assert last["colourIndex"] == "3"
    assert colour_matches(last["colour"], INKS[3])
    assert len(legend_names(reading)) == 8


def test_ac6_with_the_mode_off_there_is_no_legend(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_page(window, live_server, eight_frame(fx01_grid))

    expect(legend_of(page)).to_have_count(0)


def test_ac6_switching_the_mode_off_removes_the_legend(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_ac6(window, live_server, fx01_grid)
    legend_reading(page)

    set_mode(page, False)

    expect(legend_of(page)).to_have_count(0)


def test_ac6_in_accessibilite_mode_the_names_keep_their_inks_with_no_icon(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_page(
        window,
        live_server,
        eight_frame(fx01_grid, players=ac6_players()),
        mode_on=True,
        accessibility=True,
    )

    reading = legend_reading(page)

    assert reading["playerIcons"] == 0
    problems: list[str] = []
    for index, name in enumerate(legend_names(reading)):
        if name["svgs"] != 0 or name["childElements"] != 0:
            problems.append(f"{name['playerId']} holds an element")
        if not colour_matches(name["colour"], INKS[index]):
            problems.append(f"{name['playerId']}: color {name['colour']}")
    assert problems == []


def test_ac6_a_nickname_is_inserted_as_text(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    players = players_up_to(3)
    players[1] = player("p2", nickname="<B>BOB</B>")
    frame = snapshot_frame(fx01_view(fx01_grid), players)
    page, _ = open_page(window, live_server, frame, mode_on=True)

    reading = legend_reading(page)

    name = legend_names(reading)[1]
    assert name["childElements"] == 0
    assert "<" in name["text"]
    expect(legend_of(page).locator("b")).to_have_count(0)


# ---- AC-7: the look and the place ----


def ac7_frame(grid: Grid) -> str:
    """A FX-01 snapshot with `p1` to `p4` (short nicknames)."""
    return snapshot_frame(fx01_view(grid), players_up_to(4))


def open_ac7(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int]
) -> Page:
    page, _ = open_page(window, base_url, ac7_frame(grid), size, mode_on=True)
    legend_reading(page)
    settle_layout(page)
    return page


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac7_the_legend_has_its_background_border_radius_and_padding(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_ac7(window, live_server, fx01_grid, size)
    legend = legend_of(page)

    reading = legend_reading(page)

    problems: list[str] = []
    if not colour_matches(reading["background"], LEGEND_BG, LEGEND_BG_ALPHA):
        problems.append(f"background {reading['background']}")
    for side in ("Top", "Right", "Bottom", "Left"):
        problems.extend(border_problems(legend, side, "1px", "solid", LINE))
    for corner in ("TopLeft", "TopRight", "BottomRight", "BottomLeft"):
        radius = style_of(legend, f"border{corner}Radius")
        if radius != "14px":
            problems.append(f"border-{corner} radius {radius}")
    if not padding_matches(legend, "4px 12px"):
        problems.append("padding is not 4px 12px")
    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac7_the_legend_is_a_flex_row_with_a_gap_of_8_px(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_ac7(window, live_server, fx01_grid, size)

    reading = legend_reading(page)

    assert reading["display"] == "flex"
    assert reading["columnGap"] == "8px"


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac7_the_label_is_in_500_0_8rem_1_2_ui_font_muted(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_ac7(window, live_server, fx01_grid, size)

    label = legend_reading(page)["items"][0]

    assert label["testId"] == "authors-legend-label"
    assert abs(label["fontSize"] - LABEL_FONT_PX) <= FONT_TOLERANCE_PX
    assert label["fontWeight"] == "500"
    line_height = float(str(label["lineHeight"]).removesuffix("px"))
    assert abs(line_height - LABEL_LINE_HEIGHT_PX) <= FONT_TOLERANCE_PX
    assert colour_matches(label["colour"], MUTED), label["colour"]
    first_family = str(label["fontFamily"]).split(",")[0].strip().strip("\"'")
    assert first_family == "Source Sans 3"


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac7_each_name_has_the_labels_size(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_ac7(window, live_server, fx01_grid, size)

    names = legend_names(legend_reading(page))

    assert len(names) == 4
    sizes = [name["fontSize"] for name in names]
    for font_size in sizes:
        assert abs(font_size - LABEL_FONT_PX) <= FONT_TOLERANCE_PX, sizes


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac7_the_legend_is_one_line(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_ac7(window, live_server, fx01_grid, size)

    box = to_box(legend_reading(page)["box"])

    assert box.height <= ONE_LINE_MAX_HEIGHT_PX, box


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac7_the_legend_is_centred_on_the_grid_8_px_under_it(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_ac7(window, live_server, fx01_grid, size)

    assert legend_place_problems(page) == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac7_the_legend_lies_inside_grid_area(
    window: OpenWindow, live_server: str, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = open_ac7(window, live_server, fx01_grid, size)

    reading = legend_reading(page)

    assert reading["areaBox"] is not None, "no grid-area"
    legend_box = to_box(reading["box"])
    area_box = to_box(reading["areaBox"])
    assert box_inside(legend_box, area_box), (legend_box, area_box)


# ---- AC-8: the grid's room ----

PHONE_IDS = ["room-topbar", "clue-bar", "keyboard", "grid-viewport", "grid"]
COMPUTER_IDS = ["room-topbar", "clue-bar", "salon", "grid-viewport", "grid"]


def same_box(first: Box, second: Box) -> bool:
    return (
        abs(first.left - second.left) <= POSITION_TOLERANCE_PX
        and abs(first.top - second.top) <= POSITION_TOLERANCE_PX
        and abs(first.right - second.right) <= POSITION_TOLERANCE_PX
        and abs(first.bottom - second.bottom) <= POSITION_TOLERANCE_PX
    )


def boxes_off_then_on(
    page: Page, test_ids: list[str], touch: bool
) -> tuple[dict[str, Box], dict[str, Box]]:
    """The boxes with the mode off, then with the mode on (both settled)."""
    settle_layout(page)
    found_off = boxes_of(page, test_ids)
    set_mode(page, True, touch)
    expect(legend_of(page)).to_be_visible()
    settle_layout(page)
    found_on = boxes_of(page, test_ids)
    off: dict[str, Box] = {}
    on: dict[str, Box] = {}
    for test_id in test_ids:
        off[test_id] = required_box(found_off, test_id)
        on[test_id] = required_box(found_on, test_id)
    return off, on


def open_phone_touch(window: OpenWindow, base_url: str, frame: str) -> Page:
    """The page at 360 by 740 in the touch context (sheet layout, keyboard shown)."""
    page, _ = open_page(window, base_url, frame, PHONE, touch=True)
    expect(page.get_by_test_id("keyboard")).to_be_visible()
    return page


def test_ac8_on_a_phone_grid_viewport_is_38_px_less_high_and_keeps_width_and_top(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_phone_touch(window, live_server, ac7_frame(fx01_grid))

    off, on = boxes_off_then_on(page, PHONE_IDS, touch=True)

    viewport_off = off["grid-viewport"]
    viewport_on = on["grid-viewport"]
    less = viewport_off.height - viewport_on.height
    assert abs(less - ONE_LINE_ROOM_PX) <= POSITION_TOLERANCE_PX, (off, on)
    assert abs(viewport_on.width - viewport_off.width) <= SIZE_TOLERANCE_PX
    assert abs(viewport_on.top - viewport_off.top) <= POSITION_TOLERANCE_PX


def test_ac8_on_a_phone_the_top_bar_clue_bar_and_keyboard_do_not_move(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_phone_touch(window, live_server, ac7_frame(fx01_grid))

    off, on = boxes_off_then_on(page, PHONE_IDS, touch=True)

    moved: list[str] = []
    for test_id in ("room-topbar", "clue-bar", "keyboard"):
        if not same_box(off[test_id], on[test_id]):
            moved.append(f"{test_id}: {off[test_id]} -> {on[test_id]}")
    assert moved == []


def open_computer(window: OpenWindow, base_url: str, grid: Grid) -> Page:
    """The page at 1280 by 720 in the desktop context, the Salon column open."""
    page, _ = open_page(window, base_url, ac7_frame(grid), COMPUTER)
    expect_open(page.get_by_test_id("salon"))
    return page


def test_ac8_on_a_computer_the_grid_is_35_to_40_px_less_high(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_computer(window, live_server, fx01_grid)

    off, on = boxes_off_then_on(page, COMPUTER_IDS, touch=False)

    less = off["grid"].height - on["grid"].height
    assert GRID_LESS_MIN_PX <= less <= GRID_LESS_MAX_PX, (off["grid"], on["grid"])


def test_ac8_on_a_computer_the_top_bar_and_salon_keep_their_boxes(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_computer(window, live_server, fx01_grid)

    off, on = boxes_off_then_on(page, COMPUTER_IDS, touch=False)

    moved: list[str] = []
    for test_id in ("room-topbar", "salon"):
        if not same_box(off[test_id], on[test_id]):
            moved.append(f"{test_id}: {off[test_id]} -> {on[test_id]}")
    assert moved == []


def test_ac8_on_a_computer_the_clue_bar_moves_by_5_px_at_most_vertically(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_computer(window, live_server, fx01_grid)

    off, on = boxes_off_then_on(page, COMPUTER_IDS, touch=False)

    bar_off = off["clue-bar"]
    bar_on = on["clue-bar"]
    assert abs(bar_on.left - bar_off.left) <= POSITION_TOLERANCE_PX, (bar_off, bar_on)
    assert abs(bar_on.right - bar_off.right) <= POSITION_TOLERANCE_PX
    assert abs(bar_on.top - bar_off.top) <= CLUE_BAR_SHIFT_PX, (bar_off, bar_on)
    assert abs(bar_on.bottom - bar_off.bottom) <= CLUE_BAR_SHIFT_PX


def long_names_frame(grid: Grid) -> str:
    """FX-01 with 8 players whose nicknames have 20 characters each."""
    players: list[PlayerView] = []
    for number, nickname in enumerate(LONG_NICKNAMES, start=1):
        assert len(nickname) == 20, nickname
        players.append(player(f"p{number}", nickname=nickname, host=number == 1))
    return snapshot_frame(fx01_view(grid), players)


def item_tops(page: Page) -> list[float]:
    tops: list[float] = []
    for item in legend_reading(page)["items"]:
        tops.append(to_box(item["box"]).top)
    return tops


def test_ac8_a_long_legend_wraps_and_the_viewport_gives_it_h_plus_8_px(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_phone_touch(window, live_server, long_names_frame(fx01_grid))

    off, on = boxes_off_then_on(page, PHONE_IDS, touch=True)

    tops = item_tops(page)
    assert max(tops) - min(tops) > POSITION_TOLERANCE_PX, f"one line: {tops}"
    legend = required_box(boxes_of(page, ["authors-legend"]), "authors-legend")
    room = legend.height + LEGEND_GAP_PX
    less = off["grid-viewport"].height - on["grid-viewport"].height
    assert room > ONE_LINE_ROOM_PX, legend
    assert abs(less - room) <= POSITION_TOLERANCE_PX, (less, room)


def test_ac8_a_long_legend_lies_in_grid_area_above_the_clue_bar_off_the_grid(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_phone_touch(window, live_server, long_names_frame(fx01_grid))
    set_mode(page, True, touch=True)
    settle_layout(page)

    reading = legend_reading(page)

    legend = to_box(reading["box"])
    assert reading["areaBox"] is not None, "no grid-area"
    area = to_box(reading["areaBox"])
    boxes = boxes_of(page, ["grid", "clue-bar"])
    grid = required_box(boxes, "grid")
    bar = required_box(boxes, "clue-bar")
    problems: list[str] = []
    if not box_inside(legend, area):
        problems.append(f"legend {legend} is not inside grid-area {area}")
    if legend.bottom > bar.top + POSITION_TOLERANCE_PX:
        problems.append(f"legend {legend} goes below clue-bar's top {bar.top}")
    if overlap_area(legend, grid) > 0:
        problems.append(f"legend {legend} overlaps the grid {grid}")
    assert problems == []


def test_ac8_a_long_legend_is_never_wider_than_grid_areas_content_box(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_phone_touch(window, live_server, long_names_frame(fx01_grid))
    set_mode(page, True, touch=True)
    settle_layout(page)

    reading = legend_reading(page)

    legend = to_box(reading["box"])
    assert reading["areaContent"] is not None, "no grid-area"
    content = to_box(reading["areaContent"])
    assert legend.width <= content.width + SIZE_TOLERANCE_PX, (legend, content)
    assert legend.left >= content.left - POSITION_TOLERANCE_PX, (legend, content)
    assert legend.right <= content.right + POSITION_TOLERANCE_PX, (legend, content)
