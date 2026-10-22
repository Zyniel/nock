"""Tests of spec 042, AC-12 to AC-14: clue cells, the separator, the active clue
and the flag.

On the mocked room of `tests/spec042_harness.py`, 1280 by 720, desktop context.
Sizes and positions are read after `document.fonts.ready` (the harness waits for
it); `s` is the clue cell's side.

Choices where the spec leaves room:

- AC-12, "clue 0 above the separator and clue 1 below it": the bottom of clue 0
  is at most the separator's top and the top of clue 1 at least the separator's
  bottom (1 px tolerance).
- AC-12, `hyphens` is read as `hyphens`, or `webkitHyphens` where the engine
  only has the prefixed property.
- AC-13, "as large as its content box": left `L + 3`, top `T + 2`, width
  `s - 7` and height `s - 5`, as AC-12's lone clue.
- AC-14, the flag's svg is "centred in the flag's box": the two centres within
  1 px; the hit test uses the style of "Hit tests" after `scrollIntoView` of the
  clue cell. The clue text's box without the flag is read on the same page
  before `flag_changed` arrives.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import ClueRef, FlagView, PlayerView
from spec021_harness import flag_changed_frame
from spec042_harness import (
    CELL_SELECTOR,
    CLUE_BG,
    CLUE_FONT_STACK,
    CLUE_INK,
    FLAG_PATHS,
    IDES,
    MIN_MARK_CONTRAST,
    NAVAL,
    READERS_JS,
    RED,
    SELECTED,
    Reading,
    box_problems,
    clue_font_size,
    colour_problems,
    contrast_ratio,
    end_hit_test,
    expect_seq,
    flag_side,
    font_families,
    fx01_view,
    hit_chain,
    hit_owner,
    is_transparent,
    make_catalogue,
    me,
    open_room,
    player,
    start_hit_test,
    tap,
    to_box,
    to_colour,
)

# ---- Fixtures: thin wrappers around the harness ---------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


# ---- Reading a clue cell -----------------------------------------------------------

CLUE_CELL_SCRIPT = "cell => {\n" + READERS_JS + r"""
const style = getComputedStyle(cell);
const reading = {
  box: boxOf(cell),
  background: parseColour(style.backgroundColor),
  padding: [style.paddingTop, style.paddingRight, style.paddingBottom,
    style.paddingLeft],
  clues: [],
  separator: null,
};
for (const clue of cell.querySelectorAll('[data-testid="clue"]')) {
  const clueStyle = getComputedStyle(clue);
  const text = clue.querySelector('[data-testid="clue-text"]');
  const textStyle = text === null ? null : getComputedStyle(text);
  const flags = clue.querySelectorAll('[data-testid="clue-flag"]');
  const item = {
    index: clue.getAttribute('data-clue-index'),
    active: clue.getAttribute('data-active'),
    box: boxOf(clue),
    background: parseColour(clueStyle.backgroundColor),
    radii: [clueStyle.borderTopLeftRadius, clueStyle.borderTopRightRadius,
      clueStyle.borderBottomRightRadius, clueStyle.borderBottomLeftRadius],
    text: null,
    flags: [],
  };
  if (text !== null) {
    item.text = {
      box: boxOf(text),
      content: text.textContent,
      family: textStyle.fontFamily,
      weight: textStyle.fontWeight,
      size: textStyle.fontSize,
      lineHeight: textStyle.lineHeight,
      letterSpacing: textStyle.letterSpacing,
      transform: textStyle.textTransform,
      align: textStyle.textAlign,
      wrap: textStyle.overflowWrap,
      hyphens: textStyle.hyphens || textStyle.webkitHyphens,
      colour: parseColour(textStyle.color),
    };
  }
  for (const flag of flags) {
    const flagStyle = getComputedStyle(flag);
    const flagReading = markOf(flag);
    flagReading.background = parseColour(flagStyle.backgroundColor);
    flagReading.radii = [flagStyle.borderTopLeftRadius,
      flagStyle.borderTopRightRadius, flagStyle.borderBottomRightRadius,
      flagStyle.borderBottomLeftRadius];
    flagReading.svgs = svgsIn(flag);
    item.flags.push(flagReading);
  }
  reading.clues.push(item);
}
const separator = cell.querySelector('[data-testid="clue-separator"]');
if (separator !== null) {
  const separatorStyle = getComputedStyle(separator);
  reading.separator = {
    box: boxOf(separator),
    background: parseColour(separatorStyle.backgroundColor),
    opacity: separatorStyle.opacity,
    marginLeft: separatorStyle.marginLeft,
    marginRight: separatorStyle.marginRight,
  };
}
return reading;
}"""


def read_clue_cell(page: Page, row: int, column: int) -> Reading:
    selector = CELL_SELECTOR.format(row=row, column=column)
    found = page.locator(selector).evaluate(CLUE_CELL_SCRIPT)
    assert isinstance(found, dict)
    return found


def px_value(text: str) -> float:
    """Read a computed length such as `0.13px` as a number of px."""
    if not text.endswith("px"):
        pytest.fail(f"{text!r} is not a length in px")
    return float(text.removesuffix("px"))


def line_height_of(text: str, size: float) -> float:
    if text.endswith("px"):
        return float(text.removesuffix("px"))
    return float(text) * size


# ---- AC-12: clue cells and clue text ------------------------------------------

CLUE_CASES = [
    (0, 0, 0, "Passoire fine"),
    (0, 0, 1, "De la marine"),
    (0, 2, 0, "Artiste muet"),
]


@pytest.mark.parametrize(("row", "column"), [(0, 0), (0, 2)], ids=["0-0", "0-2"])
def test_ac12_a_clue_cell_is_clue_blue_grey_with_2_and_3_px_of_padding(
    page: Page, live_server: str, fx01_grid: Grid, row: int, column: int
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])

    reading = read_clue_cell(page, row, column)

    assert colour_problems("clue cell", reading["background"], CLUE_BG) == []
    assert reading["padding"] == ["2px", "3px", "2px", "3px"]


def clue_text_problems(cell: Reading, index: int, written: str) -> list[str]:
    """How a `clue-text` breaks the type of "Clue cells"."""
    side = to_box(cell["box"]).width
    text = cell["clues"][index]["text"]
    if text is None:
        return [f"clue {index} has no clue-text"]
    problems: list[str] = []
    size = px_value(text["size"])
    expected_size = clue_font_size(side)
    if abs(size - expected_size) > 0.1:
        problems.append(f"font size {size}, expected {expected_size:.2f}")
    if font_families(text["family"]) != CLUE_FONT_STACK:
        problems.append(f"font family {text['family']}")
    if int(float(text["weight"])) != 600:
        problems.append(f"font weight {text['weight']}")
    line_height = line_height_of(text["lineHeight"], size)
    if abs(line_height - 1.12 * size) > 0.1:
        problems.append(f"line height {line_height}, expected {1.12 * size:.2f}")
    spacing = px_value(text["letterSpacing"])
    if abs(spacing - 0.01 * size) > 0.05:
        problems.append(f"letter spacing {spacing}, expected {0.01 * size:.3f}")
    styles = (text["transform"], text["align"], text["wrap"], text["hyphens"])
    if styles != ("uppercase", "center", "break-word", "manual"):
        problems.append(f"transform, align, wrap and hyphens {styles}")
    problems.extend(colour_problems("clue text", text["colour"], CLUE_INK))
    if text["content"] != written:
        problems.append(f"text {text['content']!r}, expected {written!r}")
    return problems


@pytest.mark.parametrize(
    ("row", "column", "index", "written"),
    CLUE_CASES,
    ids=["0-0-clue0", "0-0-clue1", "0-2-clue0"],
)
def test_ac12_clue_text_is_ibm_plex_sans_condensed_600_in_css_capitals(
    page: Page,
    live_server: str,
    fx01_grid: Grid,
    row: int,
    column: int,
    index: int,
    written: str,
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])

    reading = read_clue_cell(page, row, column)

    assert clue_text_problems(reading, index, written) == []


def test_ac12_one_clue_size_serves_one_clue_and_two_clue_cells(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])

    sizes: list[str] = []
    for row, column in ((0, 0), (0, 2)):
        for clue in read_clue_cell(page, row, column)["clues"]:
            sizes.append(clue["text"]["size"])

    assert len(sizes) == 3
    assert len(set(sizes)) == 1, sizes


def test_ac12_a_lone_clue_fills_the_content_box(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])

    reading = read_clue_cell(page, 0, 2)

    cell = to_box(reading["box"])
    assert len(reading["clues"]) == 1
    problems = box_problems(
        "clue",
        to_box(reading["clues"][0]["box"]),
        left=cell.left + 3,
        top=cell.top + 2,
        width=cell.width - 7,
        height=cell.height - 5,
    )
    assert problems == []


def test_ac12_two_clues_share_the_content_box_in_equal_halves_around_the_line(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])

    reading = read_clue_cell(page, 0, 0)

    cell = to_box(reading["box"])
    assert len(reading["clues"]) == 2
    assert reading["separator"] is not None
    first = to_box(reading["clues"][0]["box"])
    second = to_box(reading["clues"][1]["box"])
    separator = to_box(reading["separator"]["box"])
    assert reading["clues"][0]["index"] == "0"
    assert abs(first.height - second.height) <= 0.5, (first, second)
    assert abs(first.width - (cell.width - 7)) <= 0.5, (first, cell)
    assert abs(second.width - (cell.width - 7)) <= 0.5, (second, cell)
    assert first.bottom <= separator.top + 1, (first, separator)
    assert second.top >= separator.bottom - 1, (second, separator)
    assert abs(first.top - (cell.top + 2)) <= 1, (first, cell)
    assert abs(second.bottom - (cell.bottom - 3)) <= 1, (second, cell)


@pytest.mark.parametrize(
    ("row", "column", "index"),
    [(0, 0, 0), (0, 0, 1), (0, 2, 0)],
    ids=["0-0-clue0", "0-0-clue1", "0-2-clue0"],
)
def test_ac12_each_clue_text_is_centred_vertically_in_its_clue(
    page: Page, live_server: str, fx01_grid: Grid, row: int, column: int, index: int
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])

    clue = read_clue_cell(page, row, column)["clues"][index]

    text_box = to_box(clue["text"]["box"])
    clue_box = to_box(clue["box"])
    assert abs(text_box.centre_y - clue_box.centre_y) <= 1, (text_box, clue_box)


# ---- AC-13: the separator and the active clue ---------------------------------------


def test_ac13_the_separator_is_a_55_percent_clue_ink_line_inset_14_percent(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])

    reading = read_clue_cell(page, 0, 0)

    separator = reading["separator"]
    assert separator is not None
    content_width = to_box(reading["box"]).width - 7
    assert abs(to_box(separator["box"]).height - 1) <= 0.5
    assert colour_problems("separator", separator["background"], CLUE_INK) == []
    assert abs(float(separator["opacity"]) - 0.55) <= 0.001
    for margin in (separator["marginLeft"], separator["marginRight"]):
        assert abs(px_value(margin) - 0.14 * content_width) <= 0.5, separator


def test_ac13_the_active_clue_is_its_own_half_in_selected_blue(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])

    tap(page, 1, 0)
    expect(page.get_by_test_id("grid")).to_have_attribute("data-word", "0,0,0")

    clues = read_clue_cell(page, 0, 0)["clues"]
    assert clues[0]["active"] == "true"
    assert colour_problems("clue 0", clues[0]["background"], SELECTED) == []
    assert clues[0]["radii"] == ["2px", "2px", "2px", "2px"]
    assert is_transparent(clues[1]["background"]), clues[1]["background"]


def test_ac13_a_lone_active_clue_fills_its_content_box_and_the_other_clears(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])
    tap(page, 1, 0)

    tap(page, 2, 1)
    expect(page.get_by_test_id("grid")).to_have_attribute("data-word", "2,0,0")

    reading = read_clue_cell(page, 2, 0)
    clue = reading["clues"][0]
    cell = to_box(reading["box"])
    assert colour_problems("clue of (2, 0)", clue["background"], SELECTED) == []
    problems = box_problems(
        "clue of (2, 0)",
        to_box(clue["box"]),
        left=cell.left + 3,
        top=cell.top + 2,
        width=cell.width - 7,
        height=cell.height - 5,
    )
    assert problems == []
    first = read_clue_cell(page, 0, 0)["clues"][0]
    assert is_transparent(first["background"]), first["background"]


# ---- AC-14: the flag ----------------------------------------------------------

AC14_FLAGS = [FlagView(player_id="p2", clue=IDES), FlagView(player_id="p3", clue=NAVAL)]


def ac14_players() -> list[PlayerView]:
    return [me(), player("p2", 1), player("p3", 2)]


def flag_reading(page: Page, clue: ClueRef) -> tuple[Reading, Reading]:
    """The clue cell's reading and its flagged clue's reading."""
    cell = read_clue_cell(page, clue.row, clue.column)
    return cell, cell["clues"][clue.clue_index]


def flag_box_problems(cell: Reading, clue: Reading, clue_ref: ClueRef) -> list[str]:
    """The flag's square: side `f`, left 1 px right of the cell, top on its clue."""
    flags: list[Reading] = clue["flags"]
    if len(flags) != 1:
        return [f"{len(flags)} clue-flag elements"]
    cell_box = to_box(cell["box"])
    side = flag_side(cell_box.width)
    top = to_box(clue["box"]).top
    if clue_ref.clue_index == 1:
        assert cell["separator"] is not None
        top = to_box(cell["separator"]["box"]).bottom
    return box_problems(
        "clue-flag",
        to_box(flags[0]["box"]),
        width=side,
        height=side,
        left=cell_box.left + 1,
        top=top,
    )


@pytest.mark.parametrize("clue", [IDES, NAVAL], ids=["IDES", "NAVAL"])
def test_ac14_a_flag_is_a_clue_blue_grey_square_over_the_text_with_no_text(
    page: Page, live_server: str, fx01_grid: Grid, clue: ClueRef
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), ac14_players(), flags=AC14_FLAGS)

    _, flagged = flag_reading(page, clue)

    flags: list[Reading] = flagged["flags"]
    assert len(flags) == 1
    flag = flags[0]
    assert flag["position"] == "absolute"
    assert flag["zIndex"] == "2"
    assert colour_problems("flag", flag["background"], CLUE_BG) == []
    assert flag["radii"] == ["0px", "0px", "3px", "0px"]
    assert flag["text"].strip() == ""


@pytest.mark.parametrize("clue", [IDES, NAVAL], ids=["IDES", "NAVAL"])
def test_ac14_the_flag_sits_at_the_top_left_of_its_own_clue(
    page: Page, live_server: str, fx01_grid: Grid, clue: ClueRef
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), ac14_players(), flags=AC14_FLAGS)

    cell, flagged = flag_reading(page, clue)

    assert flag_box_problems(cell, flagged, clue) == []


def flag_icon_problems(flag: Reading) -> list[str]:
    """The flag's `svg`: 86 % of the square, centred, the two red paths."""
    svgs: list[Reading] = flag["svgs"]
    if len(svgs) != 1:
        return [f"{len(svgs)} svg elements"]
    svg = svgs[0]
    problems: list[str] = []
    if svg["ariaHidden"] != "true" or svg["viewBox"] != "0 0 24 24":
        problems.append(f"svg aria-hidden {svg['ariaHidden']!r} {svg['viewBox']!r}")
    square = to_box(flag["box"])
    problems.extend(
        box_problems(
            "flag svg",
            to_box(svg["box"]),
            width=0.86 * square.width,
            height=0.86 * square.height,
            centre_x=square.centre_x,
            centre_y=square.centre_y,
        )
    )
    shapes: list[Reading] = svg["shapes"]
    paths = [shape["attributes"].get("d") for shape in shapes]
    if [shape["tag"] for shape in shapes] != ["path", "path"] or paths != FLAG_PATHS:
        return [*problems, f"shapes {[shape['tag'] for shape in shapes]} {paths}"]
    for shape in shapes:
        name = f"path {shape['attributes'].get('d')}"
        if shape["fillColour"] is None or shape["strokeColour"] is None:
            problems.append(f"{name}: fill {shape['fill']} stroke {shape['stroke']}")
            continue
        problems.extend(colour_problems(f"{name} fill", shape["fillColour"], RED))
        problems.extend(colour_problems(f"{name} stroke", shape["strokeColour"], RED))
        if shape["strokeWidth"] != "2px":
            problems.append(f"{name}: stroke-width {shape['strokeWidth']}")
        if shape["linecap"] != "round" or shape["linejoin"] != "round":
            problems.append(f"{name}: caps {shape['linecap']} {shape['linejoin']}")
    return problems


@pytest.mark.parametrize("clue", [IDES, NAVAL], ids=["IDES", "NAVAL"])
def test_ac14_the_flag_holds_the_red_flag_icon(
    page: Page, live_server: str, fx01_grid: Grid, clue: ClueRef
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), ac14_players(), flags=AC14_FLAGS)

    _, flagged = flag_reading(page, clue)

    assert len(flagged["flags"]) == 1
    flag = flagged["flags"][0]
    assert flag_icon_problems(flag) == []
    ratio = contrast_ratio(RED, to_colour(flag["background"]))
    assert ratio >= MIN_MARK_CONTRAST


@pytest.mark.parametrize("clue", [IDES, NAVAL], ids=["IDES", "NAVAL"])
def test_ac14_the_flag_is_drawn_over_the_clue_text(
    page: Page, live_server: str, fx01_grid: Grid, clue: ClueRef
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), ac14_players(), flags=AC14_FLAGS)
    flag = page.locator(
        f"{CELL_SELECTOR.format(row=clue.row, column=clue.column)} "
        f'[data-testid="clue"][data-clue-index="{clue.clue_index}"] '
        '[data-testid="clue-flag"]'
    )
    expect(flag).to_have_count(1)

    start_hit_test(page, clue.row, clue.column)
    try:
        _, flagged = flag_reading(page, clue)
        square = to_box(flagged["flags"][0]["box"])
        chain = hit_chain(page, square.centre_x, square.centre_y)
    finally:
        end_hit_test(page)

    assert hit_owner(chain) == "clue-flag", chain


def test_ac14_the_flag_never_moves_the_clue_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_view(fx01_grid), ac14_players())
    before = to_box(flag_reading(page, IDES)[1]["text"]["box"])

    mock.send(flag_changed_frame(6, "p2", IDES))
    expect_seq(page, 6)

    _, flagged = flag_reading(page, IDES)
    assert len(flagged["flags"]) == 1
    after = to_box(flagged["text"]["box"])
    for edge in range(4):
        assert abs(after[edge] - before[edge]) <= 1, (before, after)
