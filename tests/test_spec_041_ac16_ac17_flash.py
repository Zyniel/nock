"""Tests of spec 041, AC-16 and AC-17: the flash of spec 016 is the replacer's
colour at 38 % over white, drawn by a `cell-flash` overlay under an ink letter.

On the mocked room of spec 035's harness with a FX-01 snapshot. A flash lasts
1,000 ms (spec 016), so every reading taken during a flash is one
`page.evaluate`, which also returns the cell's `data-flash` at that moment: the
test then checks that the reading was taken while the cell flashed. The shared
setup is in `tests/spec041_harness.py`.

Choices where the spec leaves room:

- AC-16, "within 300 ms": the wait for `data-flash="1"` starts once the mock has
  sent `letter_changed`, with a 300 ms timeout. The other checks of AC-16 wait
  with the default timeout, so that a slow engine fails only the 300 ms check.
- AC-16, "a bounding box within 1 px of the cell's padding box": the padding box
  is the cell's border box less its computed border widths, each edge within
  1 px.
- AC-17, the player of colour N: `p2`, and `p1` has colour 0, or 1 when N is 0
  (two players of one room never share a colour). The composite is the page's
  `--player-colour-N` (read through a probe) at 38 % over white, and the contrast
  uses spec 035's formula (`tests/colour_contrast.js`).
"""

from __future__ import annotations

from typing import NamedTuple

import pytest
from playwright.sync_api import Locator, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec035_harness import (
    COLOUR_CONTRAST_JS,
    MIN_TEXT_CONTRAST,
    ChangeList,
    MockRoomSocket,
    build_fx01_grid,
    build_reference_catalogue,
    open_room,
    player_view,
)
from spec041_harness import (
    INK,
    STYLE_READERS_JS,
    WHITE,
    Colour,
    assert_colour,
    cell_at,
    colour_of,
    letter_changed_frame,
    to_colour,
    token_colour,
)

# ---- Fixtures: thin wrappers around the harnesses ---------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of spec 004 (served by live_server for `/`)."""
    return build_reference_catalogue(fx01_grid)


# ---- Reading a cell during its flash ----------------------------------------------

FLASH_OPACITY = 0.38
START_WITHIN_MS = 300
FLASH_END_TIMEOUT_MS = 3000
BOX_TOLERANCE = 1.0

READ_FLASH_SCRIPT = "([row, column]) => {\n" + STYLE_READERS_JS + r"""
const selector =
  `[data-testid="cell"][data-row="${row}"][data-column="${column}"]`;
const cell = document.querySelector(selector);
const style = getComputedStyle(cell);
const overlays = cell.querySelectorAll('[data-testid="cell-flash"]');
const reading = {
  flash: cell.getAttribute('data-flash'),
  letter: cell.getAttribute('data-letter'),
  background: readColour(cell, 'backgroundColor'),
  colour: readColour(cell, 'color'),
  fontStyle: style.fontStyle,
  isolation: style.isolation,
  overlayCount: overlays.length,
  overlay: null,
};
if (overlays.length === 1) {
  const overlay = overlays[0];
  const overlayStyle = getComputedStyle(overlay);
  const box = overlay.getBoundingClientRect();
  const cellBox = cell.getBoundingClientRect();
  reading.overlay = {
    ariaHidden: overlay.getAttribute('aria-hidden'),
    position: overlayStyle.position,
    zIndex: overlayStyle.zIndex,
    pointerEvents: overlayStyle.pointerEvents,
    opacity: overlayStyle.opacity,
    background: readColour(overlay, 'backgroundColor'),
    box: [box.left, box.top, box.right, box.bottom],
    paddingBox: [
      cellBox.left + parseFloat(style.borderLeftWidth),
      cellBox.top + parseFloat(style.borderTopWidth),
      cellBox.right - parseFloat(style.borderRightWidth),
      cellBox.bottom - parseFloat(style.borderBottomWidth),
    ],
  };
}
return reading;
}"""


class OverlayReading(NamedTuple):
    """The `cell-flash` element of a cell, as read during the flash."""

    aria_hidden: str | None
    position: str
    z_index: str
    pointer_events: str
    opacity: str
    background: Colour
    box: list[float]
    padding_box: list[float]


class FlashReading(NamedTuple):
    """A letter cell read in one go, with its `data-flash` at that moment."""

    flash: str
    letter: str
    background: Colour
    colour: Colour
    font_style: str
    isolation: str
    overlay_count: int
    overlay: OverlayReading | None


def read_overlay(found: object) -> OverlayReading | None:
    """Turn the overlay data read in the page into an `OverlayReading`."""
    if found is None:
        return None
    assert isinstance(found, dict)
    return OverlayReading(
        aria_hidden=found["ariaHidden"],
        position=str(found["position"]),
        z_index=str(found["zIndex"]),
        pointer_events=str(found["pointerEvents"]),
        opacity=str(found["opacity"]),
        background=to_colour(found["background"]),
        box=[float(edge) for edge in found["box"]],
        padding_box=[float(edge) for edge in found["paddingBox"]],
    )


def read_flash(page: Page, row: int, column: int) -> FlashReading:
    """Read a letter cell and its `cell-flash` element in one `page.evaluate`."""
    found = page.evaluate(READ_FLASH_SCRIPT, [row, column])
    assert isinstance(found, dict)
    return FlashReading(
        flash=str(found["flash"]),
        letter=str(found["letter"]),
        background=to_colour(found["background"]),
        colour=to_colour(found["colour"]),
        font_style=str(found["fontStyle"]),
        isolation=str(found["isolation"]),
        overlay_count=int(found["overlayCount"]),
        overlay=read_overlay(found["overlay"]),
    )


def read_during_flash(page: Page, row: int, column: int, flash: str) -> FlashReading:
    """Read a cell that must flash in colour `flash`; fail if the flash is over."""
    reading = read_flash(page, row, column)
    assert reading.flash == flash, f"read after the flash: {reading}"
    return reading


def overlay_of(reading: FlashReading) -> OverlayReading:
    """Return the single flash overlay of `reading`, after checking there is one."""
    assert reading.overlay_count == 1, f"{reading.overlay_count} cell-flash elements"
    assert reading.overlay is not None
    return reading.overlay


# ---- The rooms of AC-16 and AC-17 ---------------------------------------------


def open_flash_room(
    page: Page, base_url: str, grid: Grid, my_colour: int, their_colour: int
) -> MockRoomSocket:
    """Open the room of AC-16 with `T` at (1, 0), a pencil `A` at (1, 1); tap (1, 0)."""
    players = [
        player_view("p1", "Ana", my_colour, is_host=True),
        player_view("p2", "Bob", their_colour),
    ]
    changes: ChangeList = [
        (1, 0, {"letter": "T", "author": "p1"}),
        (1, 1, {"letter": "A", "author": "p1", "pencil": True}),
    ]
    mock = open_room(page, base_url, grid, changes=changes, players=players)
    cell_at(page, 1, 0).click()
    expect(page.get_by_test_id("grid")).to_have_attribute("data-selected-row", "1")
    expect(page.get_by_test_id("grid")).to_have_attribute("data-selected-column", "0")
    return mock


def replace_t_with_b(mock: MockRoomSocket) -> None:
    """The mock sends `letter_changed` by `p2` setting (1, 0) to `B`."""
    mock.send(letter_changed_frame(6, 1, 0, "B", "p2", pencil=False))


def start_ac16_flash(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    """The room of AC-16 with (1, 0) flashing in `p2`'s colour 1."""
    mock = open_flash_room(page, base_url, grid, my_colour=0, their_colour=1)
    replace_t_with_b(mock)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-flash", "1")
    return mock


def roster_swatch(page: Page, player_id: str) -> Locator:
    row = page.locator(f'[data-testid="roster-player"][data-player-id="{player_id}"]')
    return row.get_by_test_id("roster-colour")


# ---- AC-16: the flash overlay -------------------------------------------------


def test_ac16_no_cell_has_a_cell_flash_before_any_flash(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_flash_room(page, live_server, fx01_grid, my_colour=0, their_colour=1)

    expect(page.get_by_test_id("cell-flash")).to_have_count(0)


def test_ac16_the_flash_starts_within_300_ms(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_flash_room(page, live_server, fx01_grid, my_colour=0, their_colour=1)

    replace_t_with_b(mock)

    expect(cell_at(page, 1, 0)).to_have_attribute(
        "data-flash", "1", timeout=START_WITHIN_MS
    )


def test_ac16_the_flashing_cell_background_is_white(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    start_ac16_flash(page, live_server, fx01_grid)

    reading = read_during_flash(page, 1, 0, "1")

    assert_colour(reading.background, WHITE)


def test_ac16_the_flashing_letter_is_ink(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    start_ac16_flash(page, live_server, fx01_grid)

    reading = read_during_flash(page, 1, 0, "1")

    assert reading.letter == "B"
    assert_colour(reading.colour, INK)


def test_ac16_the_flashing_cell_holds_one_hidden_cell_flash(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    start_ac16_flash(page, live_server, fx01_grid)

    reading = read_during_flash(page, 1, 0, "1")

    assert overlay_of(reading).aria_hidden == "true"


def test_ac16_cell_flash_is_absolute_below_the_letter_and_lets_pointers_through(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    start_ac16_flash(page, live_server, fx01_grid)

    overlay = overlay_of(read_during_flash(page, 1, 0, "1"))

    assert overlay.position == "absolute"
    assert overlay.z_index == "-1"
    assert overlay.pointer_events == "none"


def test_ac16_cell_flash_opacity_is_0_38(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    start_ac16_flash(page, live_server, fx01_grid)

    overlay = overlay_of(read_during_flash(page, 1, 0, "1"))

    assert float(overlay.opacity) == pytest.approx(FLASH_OPACITY, abs=0.001)


def test_ac16_cell_flash_has_the_replacers_roster_colour(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    start_ac16_flash(page, live_server, fx01_grid)

    overlay = overlay_of(read_during_flash(page, 1, 0, "1"))
    swatch = colour_of(roster_swatch(page, "p2"), "backgroundColor")

    assert overlay.background == swatch
    assert_colour(overlay.background, (96, 136, 56))


def test_ac16_cell_flash_covers_the_cell_padding_box(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    start_ac16_flash(page, live_server, fx01_grid)

    overlay = overlay_of(read_during_flash(page, 1, 0, "1"))

    for edge, padding_edge in zip(overlay.box, overlay.padding_box, strict=True):
        assert abs(edge - padding_edge) <= BOX_TOLERANCE, overlay


def test_ac16_the_flashing_cell_is_its_own_stacking_context(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    start_ac16_flash(page, live_server, fx01_grid)

    reading = read_during_flash(page, 1, 0, "1")

    assert reading.isolation == "isolate"


def test_ac16_a_flashing_pencil_letter_is_ink_and_italic(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = start_ac16_flash(page, live_server, fx01_grid)

    mock.send(letter_changed_frame(7, 1, 1, "C", "p2", pencil=True))
    pencil_cell = cell_at(page, 1, 1)
    expect(pencil_cell).to_have_attribute("data-letter", "C")
    expect(pencil_cell).to_have_attribute("data-flash", "1")
    reading = read_during_flash(page, 1, 1, "1")

    assert reading.font_style == "italic"
    assert_colour(reading.colour, INK)


def test_ac16_the_cell_flash_goes_once_the_flash_ends(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    start_ac16_flash(page, live_server, fx01_grid)
    cell = cell_at(page, 1, 0)
    expect(cell.get_by_test_id("cell-flash")).to_have_count(1)

    expect(cell).to_have_attribute("data-flash", "", timeout=FLASH_END_TIMEOUT_MS)

    expect(cell.get_by_test_id("cell-flash")).to_have_count(0)


# ---- AC-17: the flash keeps the letter readable for every player colour -------

FLASH_CONTRAST_SCRIPT = "([letter, player, opacity]) => {\n" + COLOUR_CONTRAST_JS + r"""
const composite = over([player[0], player[1], player[2], opacity], WHITE);
const shown = over(letter, composite);
return contrast(shown, composite);
}"""

SCAN_DURING_FLASH_SCRIPT = "([row, column]) => {\n" + COLOUR_CONTRAST_JS + r"""
const selector =
  `[data-testid="cell"][data-row="${row}"][data-column="${column}"]`;
const flash = document.querySelector(selector).getAttribute('data-flash');
return {flash: flash, measurements: scanTextContrast()};
}"""


def start_flash_in_colour(page: Page, base_url: str, grid: Grid, colour: int) -> None:
    """The room of AC-16 where `p2` has colour N and replaces `p1`'s `T`."""
    my_colour = 1 if colour == 0 else 0
    mock = open_flash_room(
        page, base_url, grid, my_colour=my_colour, their_colour=colour
    )
    replace_t_with_b(mock)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-flash", str(colour))


def flash_contrast(page: Page, letter: Colour, player: Colour) -> float:
    """Return the contrast between `letter` and the flash over `player`."""
    ratio = page.evaluate(
        FLASH_CONTRAST_SCRIPT, [list(letter), list(player), FLASH_OPACITY]
    )
    assert isinstance(ratio, (int, float))
    return float(ratio)


@pytest.mark.parametrize("colour", range(8))
def test_ac17_the_letter_reaches_4_5_to_1_on_the_flash_composite(
    page: Page, live_server: str, fx01_grid: Grid, colour: int
) -> None:
    start_flash_in_colour(page, live_server, fx01_grid, colour)
    reading = read_during_flash(page, 1, 0, str(colour))
    player = token_colour(page, f"--player-colour-{colour}")

    ratio = flash_contrast(page, reading.colour, player)

    assert ratio >= MIN_TEXT_CONTRAST, f"{ratio:.2f}:1 for colour {colour}"


@pytest.mark.parametrize("colour", range(8))
def test_ac17_the_contrast_scan_during_the_flash_finds_no_offender(
    page: Page, live_server: str, fx01_grid: Grid, colour: int
) -> None:
    start_flash_in_colour(page, live_server, fx01_grid, colour)

    found = page.evaluate(SCAN_DURING_FLASH_SCRIPT, [1, 0])

    assert isinstance(found, dict)
    assert found["flash"] == str(colour), "the scan ran after the flash"
    offenders = []
    for measurement in found["measurements"]:
        if measurement["ratio"] < MIN_TEXT_CONTRAST:
            offenders.append(measurement)
    assert offenders == []
