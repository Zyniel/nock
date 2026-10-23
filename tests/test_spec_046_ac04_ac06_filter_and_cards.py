"""Tests of spec 046, AC-4 to AC-6: the force filter, the grid cards and the
progress pills.

Browser with live server, serving spec 004's reference catalogue `CAT` (grids 3,
2 and 1 shown, newest first). AC-4: the filter is a visible label and five chips,
the group labelled by `aria-labelledby`. AC-5: the cards sit two per row at 1280
by 720 and one per row at 360 by 740, each a white flex row with its number, its
publication line and « Jouer » on the right. AC-6: with `nock.progress` seeded,
the progress of a grid is a status pill on the line of its number.

Choices where the spec leaves room:

- "Chips 8 px apart": each chip's left less the right of the chip before it.
- The publication line is the element of the card whose text is
  `catalogue.item.published` filled with the card's date.
- "One column" at 360 by 740: the computed `grid-template-columns` is one length.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import pairwise

import pytest
from playwright.sync_api import Browser, Locator, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec035_harness import build_fx01_grid, build_reference_catalogue
from spec041_harness import text_contrast
from spec042_harness import box_of
from spec043_harness import (
    GREEN,
    GREEN_BG,
    INK,
    LINE,
    MUTED,
    NAVY,
    WHITE,
    WORD,
    fr_format,
    fr_value,
    px,
)
from spec046_harness import (
    SIZES,
    WIDE,
    OpenWindow,
    border_problems,
    button_colour_problems,
    child_ids,
    colour_problem,
    font_problems,
    item_of,
    near,
    open_catalogue,
    padding_matches,
    pill_problems,
    same_position,
    same_size,
    seed_progress,
    size_ids,
    style_of,
    window_opener,
)

FORCES = ["all", "1", "2", "3", "4"]
PUBLISHED = {1: "1 septembre 2026", 2: "1 octobre 2026", 3: "1 octobre 2026"}
MIN_TEXT_CONTRAST = 4.5


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return build_reference_catalogue(fx01_grid)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


def chip(filters: Locator, force: str) -> Locator:
    return filters.locator(f'[data-testid="force-filter"][data-force="{force}"]')


def chip_problems(button: Locator, pressed: bool) -> list[str]:
    """A filter chip's look: pressed on word blue with a navy border, else white."""
    name = f"chip {button.get_attribute('data-force')}"
    problems: list[str] = []
    if style_of(button, "borderTopLeftRadius") != "16px":
        problems.append(f"{name}: radius {style_of(button, 'borderTopLeftRadius')}")
    if not padding_matches(button, "7px 14px"):
        problems.append(f"{name}: padding")
    problems.extend(font_problems(button, name, 14.4, "600", NAVY))
    background = WORD if pressed else WHITE
    border = NAVY if pressed else LINE
    problems.extend(colour_problem(button, name, "backgroundColor", background))
    problems.extend(border_problems(button, name, border))
    return problems


# ---- AC-4: the force filter -------------------------------------------------------


def test_ac4_the_filter_group_is_labelled_by_its_visible_label(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    open_catalogue(page, live_server)
    filters = page.get_by_test_id("catalogue-filters")

    expect(filters).to_have_attribute("role", "group")
    expect(filters).to_have_attribute("aria-labelledby", "catalogue-filter-label")
    assert filters.get_attribute("aria-label") is None
    group = page.get_by_role("group", name="Force", exact=True)
    expect(group).to_have_attribute("data-testid", "catalogue-filters")


def test_ac4_the_label_comes_first_then_the_five_chips(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    open_catalogue(page, live_server)
    filters = page.get_by_test_id("catalogue-filters")

    ids = child_ids(filters)
    forces = filters.get_by_test_id("force-filter").evaluate_all(
        "buttons => buttons.map(button => button.getAttribute('data-force'))"
    )

    assert ids == ["catalogue-filter-label", *["force-filter"] * 5], ids
    assert forces == FORCES


def test_ac4_the_label_reads_force_in_muted_600_at_13_6_px(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    open_catalogue(page, live_server)
    label = page.get_by_test_id("catalogue-filter-label")

    expect(label).to_have_attribute("id", "catalogue-filter-label")
    expect(label).to_have_text(fr_value("catalogue.filter.label"))
    assert font_problems(label, "label", 13.6, "600", MUTED) == []


def test_ac4_toutes_is_pressed_and_the_four_others_are_white_chips(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    open_catalogue(page, live_server)
    filters = page.get_by_test_id("catalogue-filters")

    problems: list[str] = []
    for force in FORCES:
        problems.extend(chip_problems(chip(filters, force), force == "all"))

    assert problems == []


def test_ac4_the_chips_are_8_px_apart(window: OpenWindow, live_server: str) -> None:
    page = window(*WIDE)
    open_catalogue(page, live_server)
    filters = page.get_by_test_id("catalogue-filters")

    boxes = [box_of(chip(filters, force)) for force in FORCES]

    for before, after in pairwise(boxes):
        assert same_position(after.left - before.right, 8.0), (before, after)


def test_ac4_a_click_on_force_1_gives_it_the_pressed_look_and_toutes_the_other(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    open_catalogue(page, live_server)
    filters = page.get_by_test_id("catalogue-filters")

    chip(filters, "1").click()
    expect(chip(filters, "1")).to_have_attribute("aria-pressed", "true")

    assert chip_problems(chip(filters, "1"), True) == []
    assert chip_problems(chip(filters, "all"), False) == []


# ---- AC-5: the grid cards ---------------------------------------------------------


def column_widths(list_element: Locator) -> list[float]:
    """The computed `grid-template-columns` of `catalogue-list`, in px."""
    value = style_of(list_element, "gridTemplateColumns")
    return [px(part) for part in value.split()]


def test_ac5_on_a_computer_the_list_has_two_430_px_columns_12_px_apart(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    open_catalogue(page, live_server)
    list_element = page.get_by_test_id("catalogue-list")

    widths = column_widths(list_element)

    assert len(widths) == 2, widths
    for width in widths:
        assert near(width, 430.0, 1.0), widths
    assert style_of(list_element, "columnGap") == "12px"


def test_ac5_on_a_computer_two_cards_share_a_row_and_the_third_is_12_px_below(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    open_catalogue(page, live_server)

    card_3 = box_of(item_of(page, 3))
    card_2 = box_of(item_of(page, 2))
    card_1 = box_of(item_of(page, 1))

    assert same_position(card_3.top, card_2.top), (card_3, card_2)
    assert card_3.right < card_2.left, (card_3, card_2)
    assert same_position(card_1.top - card_3.bottom, 12.0), (card_3, card_1)
    for box in (card_3, card_2, card_1):
        assert same_size(box.width, 430.0), box


def test_ac5_on_a_phone_the_cards_are_one_per_row_328_px_wide_12_px_apart(
    window: OpenWindow, live_server: str
) -> None:
    page = window(360, 740)
    open_catalogue(page, live_server)

    widths = column_widths(page.get_by_test_id("catalogue-list"))
    boxes = [box_of(item_of(page, number)) for number in (3, 2, 1)]

    assert len(widths) == 1, widths
    for box in boxes:
        assert same_size(box.width, 328.0), box
    for before, after in pairwise(boxes):
        assert same_position(after.top - before.bottom, 12.0), (before, after)


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
@pytest.mark.parametrize("number", [1, 2, 3])
def test_ac5_each_card_is_a_white_flex_row_with_the_list_row_look(
    window: OpenWindow, live_server: str, width: int, height: int, number: int
) -> None:
    page = window(width, height)
    open_catalogue(page, live_server)
    card = item_of(page, number)

    problems = colour_problem(card, "card", "backgroundColor", WHITE)
    problems.extend(border_problems(card, "card", LINE))

    assert problems == []
    assert style_of(card, "borderTopLeftRadius") == "8px"
    assert padding_matches(card, "12px 14px")
    assert style_of(card, "display") == "flex"


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
@pytest.mark.parametrize("number", [1, 2, 3])
def test_ac5_each_card_has_its_number_in_ink_700_and_a_muted_publication_line(
    window: OpenWindow, live_server: str, width: int, height: int, number: int
) -> None:
    page = window(width, height)
    open_catalogue(page, live_server)
    card = item_of(page, number)
    heading = card.locator("h2")
    published = fr_format("catalogue.item.published", date=PUBLISHED[number])

    line = card.get_by_text(published, exact=True)

    expect(heading).to_have_text(f"Grille n\N{DEGREE SIGN} {number}")
    assert font_problems(heading, "h2", 16.8, "700", INK) == []
    expect(line).to_have_count(1)
    assert font_problems(line, "publication line", 13.6, colour=MUTED) == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac5_jouer_is_the_last_child_a_primary_button_on_the_right(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_catalogue(page, live_server)
    card = item_of(page, 2)
    play = card.get_by_test_id("catalogue-play")

    ids = child_ids(card)
    card_box = box_of(card)
    play_box = box_of(play)

    assert ids[-1] == "catalogue-play", ids
    assert button_colour_problems(play, "primary") == []
    assert padding_matches(play, "9px 16px")
    assert same_position(card_box.right - play_box.right, 14.0), (card_box, play_box)
    assert same_position(play_box.centre_y, card_box.centre_y), (card_box, play_box)


# ---- AC-6: the progress pills ----------------------------------------------------


def test_ac6_a_started_grid_has_its_pill_on_the_line_of_its_number(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    seed_progress(page)
    open_catalogue(page, live_server)
    card = item_of(page, 1)
    pill = card.get_by_test_id("catalogue-progress")

    expect(pill).to_have_text(fr_value("catalogue.progress.started"))
    heading_box = box_of(card.locator("h2"))
    pill_box = box_of(pill)

    assert same_position(pill_box.left - heading_box.right, 8.0), (heading_box, pill)
    assert near(pill_box.centre_y, heading_box.centre_y, 2.0), (heading_box, pill)


def test_ac6_the_started_pill_is_navy_on_word_blue(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    seed_progress(page)
    open_catalogue(page, live_server)
    pill = item_of(page, 1).get_by_test_id("catalogue-progress")

    expect(pill).to_have_text(fr_value("catalogue.progress.started"))

    assert pill_problems(pill, WORD, NAVY) == []
    assert text_contrast(pill) >= MIN_TEXT_CONTRAST


def test_ac6_the_finished_pill_is_green_on_green_background(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    seed_progress(page)
    open_catalogue(page, live_server)
    pill = item_of(page, 2).get_by_test_id("catalogue-progress")

    expect(pill).to_have_text(fr_value("catalogue.progress.finished"))

    assert pill_problems(pill, GREEN_BG, GREEN) == []
    assert text_contrast(pill) >= MIN_TEXT_CONTRAST


def test_ac6_a_grid_without_progress_has_no_pill(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    seed_progress(page)
    open_catalogue(page, live_server)

    expect(item_of(page, 3).get_by_test_id("catalogue-progress")).to_have_count(0)
