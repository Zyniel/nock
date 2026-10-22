"""Tests of spec 042, AC-9 to AC-11: the other players on a cell.

On the mocked room of `tests/spec042_harness.py`, 1280 by 720, desktop context,
`localStorage` empty unless a test seeds it. AC-9 checks the corner triangles,
AC-10 the arrival rules of the corners, AC-11 the « Accessibilité » switch, its
icons on the grid and in the roster.

Choices where the spec leaves room:

- "Within 300 ms": the first check of each step waits 300 ms at most, from the
  moment the mock has sent the step's frames; the other checks of the step are
  read at once after it (spec 041's way for its 300 ms check).
- AC-9, "filling the box": the `svg`'s box equals the triangle's (0.5 px).
- AC-9, the edge case "A player who leaves the room and a new player who joins
  with the same colour" is tested here: `p2` (colour 1) leaves, `p4` joins with
  colour 1 and selects the cell: `p4` takes the free corner with `data-colour`
  1.
- AC-10, the edge case "A reconnection snapshot" is tested here: a second
  snapshot keeps the corners of the players still on the cell (not roster order)
  and brings a new one into the first free corner.
- AC-10, "`p2` moves to (2, 2) `down`" is known to be applied when (1, 2), in
  MIME, gets `p2` in its `data-tinted-by`.
- AC-11, "exactly the shapes of `PLAYER_ICONS[N]`": the same number of shapes,
  the same tags, and each attribute the design gives equal (numbers compared as
  numbers). The edge case "A `localStorage` that throws" is tested here too, and
  one test checks the roster icon of every colour index 0 to 7.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Locator, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import Direction, PlayerState, PlayerView
from spec013_harness import state_frame
from spec019_harness import MockRoomSocket, player_joined_frame, player_left_frame
from spec042_harness import (
    ACCESS_STORAGE_KEY,
    ACCESS_SWITCH,
    CORNERS,
    FOLLOW_MS,
    PLAYER_COLOURS,
    QUIET_MS,
    TRIANGLE_POINTS,
    Box,
    Reading,
    box_problems,
    cell_at,
    click_switch,
    colour_problems,
    corners_on,
    fx01_view,
    icon_inset,
    icon_shape_problems,
    icon_side,
    inner_box,
    is_transparent,
    make_catalogue,
    make_storage_throw,
    me,
    open_room,
    player,
    read_cursors,
    read_swatches,
    reload_room,
    seed_value,
    selecting,
    selection_frame,
    shape_colour_problems,
    snapshot_frame,
    stored_value,
    tap,
    to_box,
    to_colour,
    triangle_side,
)

# ---- Fixtures: thin wrappers around the harness ---------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


# ---- Geometry of a cursor ----------------------------------------------------------


def corner_box_problems(
    name: str, box: Box, corner: object, inner: Box, side: float, inset: float
) -> list[str]:
    """A square of `side` placed `inset` px inside `corner` of the inner box."""
    if not isinstance(corner, str) or corner not in CORNERS:
        return [f"{name}: data-corner {corner!r}"]
    expected: dict[str, float] = {"width": side, "height": side}
    if corner.endswith("left"):
        expected["left"] = inner.left + inset
    else:
        expected["right"] = inner.right - inset
    if corner.startswith("top"):
        expected["top"] = inner.top + inset
    else:
        expected["bottom"] = inner.bottom - inset
    return box_problems(name, box, **expected)


def swatch_colours(page: Page) -> dict[str, tuple[float, float, float, float]]:
    """Each roster player's swatch background, by player id."""
    colours: dict[str, tuple[float, float, float, float]] = {}
    for swatch in read_swatches(page):
        colours[str(swatch["playerId"])] = to_colour(swatch["background"])
    return colours


def rgb_of(colour: tuple[float, float, float, float]) -> tuple[int, int, int]:
    return (round(colour[0]), round(colour[1]), round(colour[2]))


def triangle_problems(
    cursor: Reading, cell: Box, swatch: tuple[int, int, int]
) -> list[str]:
    """How a `remote-selection` breaks the triangle of "Other players on a cell"."""
    name = f"{cursor['playerId']}"
    problems: list[str] = []
    if cursor["shape"] != "triangle":
        problems.append(f"{name}: data-shape {cursor['shape']!r}")
    inner = inner_box(cell)
    t = triangle_side(cell.width)
    problems.extend(
        corner_box_problems(name, to_box(cursor["box"]), cursor["corner"], inner, t, 0)
    )
    svgs: list[Reading] = cursor["svgs"]
    if len(svgs) != 1:
        return [*problems, f"{name}: {len(svgs)} svg elements"]
    svg = svgs[0]
    if svg["viewBox"] != "0 0 10 10" or svg["aspect"] != "none":
        problems.append(f"{name}: viewBox {svg['viewBox']!r} {svg['aspect']!r}")
    svg_box = to_box(svg["box"])
    own_box = to_box(cursor["box"])
    problems.extend(
        box_problems(
            f"{name} svg",
            svg_box,
            width=own_box.width,
            height=own_box.height,
            left=own_box.left,
            top=own_box.top,
        )
    )
    shapes: list[Reading] = svg["shapes"]
    if len(shapes) != 1 or shapes[0]["tag"] != "polygon":
        tags = [shape["tag"] for shape in shapes]
        return [*problems, f"{name}: shapes {tags}"]
    points = " ".join(str(shapes[0]["attributes"].get("points", "")).split())
    if points != TRIANGLE_POINTS.get(str(cursor["corner"]), "?"):
        problems.append(f"{name}: points {points!r} at {cursor['corner']}")
    problems.extend(shape_colour_problems(name, shapes[0], swatch))
    return problems


def icon_problems(
    cursor: Reading, cell: Box, swatch: tuple[int, int, int]
) -> list[str]:
    """How a `remote-selection` breaks the icon of "Other players on a cell"."""
    name = f"{cursor['playerId']}"
    problems: list[str] = []
    if cursor["shape"] != "icon":
        problems.append(f"{name}: data-shape {cursor['shape']!r}")
    inner = inner_box(cell)
    side = icon_side(cell.width)
    inset = icon_inset(cell.width)
    problems.extend(
        corner_box_problems(
            name, to_box(cursor["box"]), cursor["corner"], inner, side, inset
        )
    )
    svgs: list[Reading] = cursor["svgs"]
    if len(svgs) != 1:
        return [*problems, f"{name}: {len(svgs)} svg elements"]
    svg = svgs[0]
    if svg["testId"] != "player-icon" or svg["viewBox"] != "0 0 10 10":
        problems.append(f"{name}: svg {svg['testId']!r} {svg['viewBox']!r}")
    if svg["dataIcon"] != cursor["colour"]:
        problems.append(f"{name}: data-icon {svg['dataIcon']!r}")
    problems.extend(icon_shape_problems(svg, int(cursor["colour"])))
    for shape in svg["shapes"]:
        problems.extend(shape_colour_problems(name, shape, swatch))
    return problems


# ---- AC-9: a plain triangle in the player's colour ---------------------------------


def ac9_players() -> list[PlayerView]:
    """`p1`, `p2` (colour 1) and `p3` (colour 2), no selection."""
    return [me(), player("p2", 1), player("p3", 2)]


def open_ac9(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    """The snapshot of AC-9, then `p2` on (2, 2) across and `p3` on it down."""
    mock = open_room(page, base_url, fx01_view(grid), ac9_players())
    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    mock.send(selection_frame("p3", 2, 2, Direction.DOWN))
    return mock


def test_ac9_two_players_on_a_cell_take_top_left_then_top_right_within_300_ms(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac9(page, live_server, fx01_grid)
    cursors = cell_at(page, 2, 2).get_by_test_id("remote-selection")

    expect(cursors).to_have_count(2, timeout=FOLLOW_MS)

    assert corners_on(page, 2, 2) == {"p2": "top-left", "p3": "top-right"}


def test_ac9_each_triangle_is_a_mark_with_no_text_under_the_notch(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac9(page, live_server, fx01_grid)
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(2)

    _, cursors = read_cursors(page, 2, 2)

    for cursor in cursors:
        assert cursor["shape"] == "triangle", cursor
        assert cursor["ariaHidden"] == "true", cursor
        assert cursor["text"] == "", cursor
        assert cursor["pointerEvents"] == "none", cursor
        assert cursor["position"] == "absolute", cursor
        assert cursor["zIndex"] == "2", cursor


def test_ac9_each_triangle_is_a_polygon_in_its_corner_in_the_roster_colour(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac9(page, live_server, fx01_grid)
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(2)
    swatches = swatch_colours(page)

    cell, cursors = read_cursors(page, 2, 2)

    problems: list[str] = []
    for cursor in cursors:
        swatch = rgb_of(swatches[str(cursor["playerId"])])
        problems.extend(triangle_problems(cursor, cell, swatch))
    assert problems == []


def test_ac9_my_own_selection_is_never_drawn_as_a_triangle(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac9(page, live_server, fx01_grid)
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(2)

    tap(page, 2, 2)

    mine = page.locator('[data-testid="remote-selection"][data-player-id="p1"]')
    expect(mine).to_have_count(0)
    assert corners_on(page, 2, 2) == {"p2": "top-left", "p3": "top-right"}


def test_ac9_a_new_player_with_a_departed_players_colour_takes_a_free_corner(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac9(page, live_server, fx01_grid)
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(2)

    mock.send(player_left_frame(6, "p2"))
    mock.send(player_joined_frame(7, player("p4", 1)))
    mock.send(selection_frame("p4", 2, 2, Direction.ACROSS))

    p4 = cell_at(page, 2, 2).locator(
        '[data-testid="remote-selection"][data-player-id="p4"]'
    )
    expect(p4).to_have_count(1)
    expect(p4).to_have_attribute("data-colour", "1")
    assert corners_on(page, 2, 2) == {"p4": "top-left", "p3": "top-right"}


# ---- AC-10: corners by order of arrival --------------------------------------------


def ac10_players() -> list[PlayerView]:
    """`p1`, and `p2` to `p6` with colours 1 to 5, no selection."""
    players = [me()]
    for number in range(2, 7):
        players.append(player(f"p{number}", number - 1))
    return players


FOUR_ON_2_2 = {
    "p2": "top-left",
    "p3": "top-right",
    "p4": "bottom-right",
    "p5": "bottom-left",
}
AFTER_P3_LEFT = {
    "p2": "top-left",
    "p6": "top-right",
    "p4": "bottom-right",
    "p5": "bottom-left",
}


def remote_of(page: Page, row: int, column: int, player_id: str) -> Locator:
    selector = f'[data-testid="remote-selection"][data-player-id="{player_id}"]'
    return cell_at(page, row, column).locator(selector)


def open_ac10(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    """The snapshot of AC-10, then `p2` to `p6` arrive on (2, 2) in that order."""
    mock = open_room(page, base_url, fx01_view(grid), ac10_players())
    for number in range(2, 7):
        mock.send(selection_frame(f"p{number}", 2, 2, Direction.ACROSS))
    expect(remote_of(page, 2, 2, "p5")).to_have_count(1)
    expect(cell_at(page, 2, 2)).to_have_attribute("data-tinted-by", "p2 p3 p4 p5 p6")
    return mock


def p3_moves_away(page: Page, mock: MockRoomSocket) -> None:
    mock.send(selection_frame("p3", 3, 1, Direction.ACROSS))
    expect(remote_of(page, 3, 1, "p3")).to_have_count(1, timeout=FOLLOW_MS)


def p2_turns(page: Page, mock: MockRoomSocket) -> None:
    mock.send(selection_frame("p2", 2, 2, Direction.DOWN))
    expect(cell_at(page, 1, 2)).to_have_attribute(
        "data-tinted-by", "p2", timeout=FOLLOW_MS
    )


def p3_comes_back(page: Page, mock: MockRoomSocket) -> None:
    mock.send(selection_frame("p3", 2, 2, Direction.ACROSS))
    expect(cell_at(page, 3, 1).get_by_test_id("remote-selection")).to_have_count(
        0, timeout=FOLLOW_MS
    )


def test_ac10_four_arrivals_fill_the_corners_in_order_and_the_fifth_waits(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac10(page, live_server, fx01_grid)

    assert corners_on(page, 2, 2) == FOUR_ON_2_2
    expect(
        page.locator('[data-testid="remote-selection"][data-player-id="p6"]')
    ).to_have_count(0)


def test_ac10_a_player_who_leaves_frees_the_corner_for_the_one_who_waited(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac10(page, live_server, fx01_grid)

    p3_moves_away(page, mock)

    assert corners_on(page, 2, 2) == AFTER_P3_LEFT
    assert corners_on(page, 3, 1) == {"p3": "top-left"}


def test_ac10_a_new_direction_on_the_same_cell_keeps_the_corner(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac10(page, live_server, fx01_grid)
    p3_moves_away(page, mock)

    p2_turns(page, mock)

    assert corners_on(page, 2, 2) == AFTER_P3_LEFT


def test_ac10_a_player_coming_back_to_a_full_cell_waits_and_moves_nobody(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac10(page, live_server, fx01_grid)
    p3_moves_away(page, mock)
    p2_turns(page, mock)

    p3_comes_back(page, mock)

    assert corners_on(page, 2, 2) == AFTER_P3_LEFT


def test_ac10_a_disconnected_player_frees_the_corner_for_the_one_who_waited(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac10(page, live_server, fx01_grid)
    p3_moves_away(page, mock)
    p2_turns(page, mock)
    p3_comes_back(page, mock)

    mock.send(state_frame(6, "p4", PlayerState.DISCONNECTED))
    expect(remote_of(page, 2, 2, "p3")).to_have_count(1, timeout=FOLLOW_MS)

    assert corners_on(page, 2, 2) == {
        "p2": "top-left",
        "p6": "top-right",
        "p3": "bottom-right",
        "p5": "bottom-left",
    }


def test_ac10_a_first_snapshot_brings_its_players_in_roster_order(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    on_2_2 = selecting(2, 2, Direction.ACROSS)
    players = [
        me(),
        player("p2", 1, selection=on_2_2),
        player("p3", 2, selection=on_2_2),
        player("p4", 3, selection=on_2_2),
    ]

    open_room(page, live_server, fx01_view(fx01_grid), players)

    assert corners_on(page, 2, 2) == {
        "p2": "top-left",
        "p3": "top-right",
        "p4": "bottom-right",
    }


def test_ac10_a_later_snapshot_keeps_the_corners_of_the_players_who_stayed(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    players = [me(), player("p2", 1), player("p3", 2), player("p4", 3)]
    mock = open_room(page, live_server, fx01_view(fx01_grid), players)
    mock.send(selection_frame("p3", 2, 2, Direction.ACROSS))
    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    expect(remote_of(page, 2, 2, "p2")).to_have_count(1)
    assert corners_on(page, 2, 2) == {"p3": "top-left", "p2": "top-right"}
    on_2_2 = selecting(2, 2, Direction.ACROSS)
    again = [
        me(),
        player("p2", 1, selection=on_2_2),
        player("p3", 2, selection=on_2_2),
        player("p4", 3, selection=on_2_2),
    ]

    mock.send(snapshot_frame(fx01_view(fx01_grid), again, seq=8))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "8")
    expect(remote_of(page, 2, 2, "p4")).to_have_count(1)

    assert corners_on(page, 2, 2) == {
        "p3": "top-left",
        "p2": "top-right",
        "p4": "bottom-right",
    }


# ---- AC-11: the « Accessibilité » switch ---------------------------------------


def ac11_players() -> list[PlayerView]:
    """`p2` (1) and `p3` (2) on (2, 2), `p4` (6) on (1, 0)."""
    return [
        me(),
        player("p2", 1, selection=selecting(2, 2, Direction.ACROSS)),
        player("p3", 2, selection=selecting(2, 2, Direction.DOWN)),
        player("p4", 6, selection=selecting(1, 0, Direction.ACROSS)),
    ]


AC11_CORNERS = {
    (2, 2): {"p2": "top-left", "p3": "top-right"},
    (1, 0): {"p4": "top-left"},
}


def open_ac11(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    mock = open_room(page, base_url, fx01_view(grid), ac11_players())
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(2)
    expect(cell_at(page, 1, 0).get_by_test_id("remote-selection")).to_have_count(1)
    return mock


def shapes_of_all_cursors(page: Page) -> dict[str, str | None]:
    shapes: dict[str, str | None] = {}
    for row, column in AC11_CORNERS:
        _, cursors = read_cursors(page, row, column)
        for cursor in cursors:
            shapes[str(cursor["playerId"])] = cursor["shape"]
    return shapes


def icons_problems(page: Page, swatches: dict[str, tuple[int, int, int]]) -> list[str]:
    """Every cursor of AC-11 checked as an icon, against the colours given."""
    problems: list[str] = []
    for (row, column), corners in AC11_CORNERS.items():
        cell, cursors = read_cursors(page, row, column)
        found_corners: dict[str, str | None] = {}
        for cursor in cursors:
            found_corners[str(cursor["playerId"])] = cursor["corner"]
            problems.extend(
                icon_problems(cursor, cell, swatches[str(cursor["playerId"])])
            )
        if found_corners != corners:
            problems.append(f"({row}, {column}): corners {found_corners}")
    return problems


def roster_swatch_rgb(page: Page) -> dict[str, tuple[int, int, int]]:
    found: dict[str, tuple[int, int, int]] = {}
    for player_id, colour in swatch_colours(page).items():
        found[player_id] = rgb_of(colour)
    return found


def test_ac11_the_switch_is_off_by_default_and_the_cursors_are_triangles(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac11(page, live_server, fx01_grid)

    expect(page.get_by_test_id(ACCESS_SWITCH)).to_have_attribute(
        "aria-pressed", "false"
    )
    assert shapes_of_all_cursors(page) == {
        "p2": "triangle",
        "p3": "triangle",
        "p4": "triangle",
    }


def test_ac11_a_click_turns_the_mode_on_stores_it_and_sends_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac11(page, live_server, fx01_grid)
    before = len(mock.frames_without_pings())

    click_switch(page, ACCESS_SWITCH, "true")
    page.wait_for_timeout(QUIET_MS)

    assert mock.frames_without_pings()[before:] == []
    assert stored_value(page, ACCESS_STORAGE_KEY) == "true"


def test_ac11_with_the_mode_on_each_cursor_is_its_players_icon_in_its_corner(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac11(page, live_server, fx01_grid)
    swatches = roster_swatch_rgb(page)

    click_switch(page, ACCESS_SWITCH, "true")

    assert icons_problems(page, swatches) == []


def test_ac11_the_icons_of_p2_p3_and_p4_are_the_square_the_triangle_and_the_heart(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac11(page, live_server, fx01_grid)
    click_switch(page, ACCESS_SWITCH, "true")

    found: dict[str, list[tuple[str, dict[str, str]]]] = {}
    for row, column in AC11_CORNERS:
        _, cursors = read_cursors(page, row, column)
        for cursor in cursors:
            shapes: list[tuple[str, dict[str, str]]] = []
            for svg in cursor["svgs"]:
                for shape in svg["shapes"]:
                    shapes.append((shape["tag"], shape["attributes"]))
            found[str(cursor["playerId"])] = shapes

    assert [tag for tag, _ in found["p2"]] == ["rect"]
    assert {
        key: found["p2"][0][1].get(key) for key in ("x", "y", "width", "height")
    } == {
        "x": "0.9",
        "y": "0.9",
        "width": "8.2",
        "height": "8.2",
    }
    assert [tag for tag, _ in found["p3"]] == ["polygon"]
    assert found["p3"][0][1].get("points") == "5,0.4 9.7,9.3 0.3,9.3"
    assert [tag for tag, _ in found["p4"]] == ["path"]
    assert found["p4"][0][1].get("d") == (
        "M5 9.4L1.1 5.5A2.45 2.45 0 0 1 5 2.3A2.45 2.45 0 0 1 8.9 5.5Z"
    )


def swatch_icon_problems(page: Page) -> list[str]:
    """Each roster swatch: transparent, holding one 12 px icon of its colour."""
    problems: list[str] = []
    for swatch in read_swatches(page):
        name = f"swatch of {swatch['playerId']}"
        if not is_transparent(swatch["background"]):
            problems.append(f"{name}: background {swatch['background']}")
        svgs: list[Reading] = swatch["svgs"]
        if len(svgs) != 1:
            problems.append(f"{name}: {len(svgs)} svg elements")
            continue
        svg = svgs[0]
        if svg["testId"] != "player-icon" or svg["dataIcon"] != swatch["colour"]:
            problems.append(f"{name}: svg {svg['testId']!r} {svg['dataIcon']!r}")
        problems.extend(box_problems(name, to_box(svg["box"]), width=12.0, height=12.0))
        colour_index = int(swatch["colour"])
        problems.extend(icon_shape_problems(svg, colour_index))
        for shape in svg["shapes"]:
            problems.extend(
                shape_colour_problems(name, shape, PLAYER_COLOURS[colour_index])
            )
    return problems


def test_ac11_with_the_mode_on_each_roster_swatch_shows_its_icon(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac11(page, live_server, fx01_grid)

    click_switch(page, ACCESS_SWITCH, "true")

    assert swatch_icon_problems(page) == []


def test_ac11_every_colour_index_has_its_own_icon_in_the_roster(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    players = [me()]
    for number in range(2, 9):
        players.append(player(f"p{number}", number - 1))
    open_room(page, live_server, fx01_view(fx01_grid), players)

    click_switch(page, ACCESS_SWITCH, "true")

    assert len(read_swatches(page)) == 8
    assert swatch_icon_problems(page) == []


def test_ac11_the_choice_is_kept_after_a_reload(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac11(page, live_server, fx01_grid)
    swatches = roster_swatch_rgb(page)
    click_switch(page, ACCESS_SWITCH, "true")

    reload_room(page, mock, fx01_view(fx01_grid), ac11_players())

    expect(page.get_by_test_id(ACCESS_SWITCH)).to_have_attribute("aria-pressed", "true")
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(2)
    assert icons_problems(page, swatches) == []


def test_ac11_a_second_click_brings_back_triangles_and_coloured_swatches(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac11(page, live_server, fx01_grid)
    click_switch(page, ACCESS_SWITCH, "true")

    click_switch(page, ACCESS_SWITCH, "false")

    assert stored_value(page, ACCESS_STORAGE_KEY) == "false"
    assert shapes_of_all_cursors(page) == {
        "p2": "triangle",
        "p3": "triangle",
        "p4": "triangle",
    }
    problems: list[str] = []
    for swatch in read_swatches(page):
        colour_index = int(swatch["colour"])
        name = f"swatch of {swatch['playerId']}"
        problems.extend(
            colour_problems(name, swatch["background"], PLAYER_COLOURS[colour_index])
        )
        if swatch["svgs"] != []:
            problems.append(f"{name}: holds {len(swatch['svgs'])} svg elements")
    assert problems == []


@pytest.mark.parametrize(
    ("stored", "pressed"),
    [("true", "true"), ("false", "false"), ("yes", "false"), ("", "false")],
    ids=["true", "false", "other-value", "empty-text"],
)
def test_ac11_the_switch_starts_from_the_stored_value(
    page: Page, live_server: str, fx01_grid: Grid, stored: str, pressed: str
) -> None:
    seed_value(page, ACCESS_STORAGE_KEY, stored)

    open_ac11(page, live_server, fx01_grid)

    expect(page.get_by_test_id(ACCESS_SWITCH)).to_have_attribute(
        "aria-pressed", pressed
    )
    shape = "icon" if pressed == "true" else "triangle"
    assert shapes_of_all_cursors(page) == {"p2": shape, "p3": shape, "p4": shape}


def test_ac11_with_a_storage_that_throws_the_mode_starts_off_and_still_flips(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    make_storage_throw(page)
    open_ac11(page, live_server, fx01_grid)
    expect(page.get_by_test_id(ACCESS_SWITCH)).to_have_attribute(
        "aria-pressed", "false"
    )

    click_switch(page, ACCESS_SWITCH, "true")

    assert shapes_of_all_cursors(page) == {"p2": "icon", "p3": "icon", "p4": "icon"}
