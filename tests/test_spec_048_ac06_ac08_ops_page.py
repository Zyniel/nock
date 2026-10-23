"""Tests of spec 048, AC-6 to AC-8: the operator page in the catalogue's frame,
its token card, its state lines, and the dashboard's chips and tiles.

The server is spec 038's live server with `operator_token=OPS_TOKEN`
(`ops_live_server`), which serves `/ops`; the dashboard is answered by
`page.route("**/api/ops/dashboard*", ...)` with spec 038 AC-5's 7-day figures,
or held, or refused, as each criterion says. Where a criterion opens the page
`ready` or `loading`, `sessionStorage["nock.ops_token"]` is seeded with
`OPS_TOKEN` by an init script. Windows: desktop contexts in Paris time.

Readings of the spec's wording:

- "Its column holds the `h1` then `ops-state-line` only": everything `ops-page`
  shows outside its `header` is the `h1`, the line, inside them, or a wrapper.
- "The label lies 6 px above `ops-token-input`": from the label's bottom to the
  input's top, 6 px (1 px); the label is the element of the card that reads
  `fr.json["ops.token_label"]`.
- "Between the input and `ops-token-submit`": the error line's top is not above
  the input's bottom and its bottom not under the button's top (1 px). Since
  the lead's second-review note, its top is also 6 px under the input's bottom
  (1 px), as the screens sheet draws it.
- "The periods' group names [the label] in its `aria-labelledby`": the label's
  `id` is one of the ids of that attribute, on the element of role `group` that
  holds the three `ops-period` buttons.
- "Each about 272.7 px wide (1 px)": 272.7 px within 1 px; "10 px apart": from
  one tile's right edge to the next one's left edge (1 px).
- "A border rgb(27, 47, 85)": the four sides have that colour.
- `aria-describedby` (added by the lead after review round 1): after the 401,
  `ops-token-error`'s `id` is one of `ops-token-input`'s whitespace-separated
  ids, at 1280 by 720 and at 360 by 740.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Locator, Page, Route, expect

from nock.catalogue import Catalogue
from spec038_harness import (
    DASHBOARD_ROUTE,
    SEVEN_DAY_TEXTS,
    OpsServer,
    ops_live_server,
    texts_of,
)
from spec042_harness import box_of
from spec043_harness import INK, LINE, NAVY, RED, WHITE, WORD, fr_value
from spec046_harness import (
    HeldRoute,
    OpenWindow,
    button_colour_problems,
    card_problems,
    colour_problem,
    content_box,
    font_problems,
    fulfil_json,
    same_position,
    window_opener,
)
from spec048_harness import (
    SIZE_IDS,
    SIZES,
    all_borders_problems,
    border_colour_problems,
    box_inside,
    card_title_problems,
    described_by_problems,
    error_line_problems,
    field_label_problems,
    header_box,
    header_problems,
    no_horizontal_scroll,
    others_in,
    page_colour_problems,
    radius_padding_problems,
    role_problems,
    text_input_problems,
    text_problems,
    waiting_line_problems,
)
from spec048_ops_harness import (
    expect_ops_state,
    open_ops,
    open_ready_ops,
    seed_ops_token,
)
from sure_click import click_until_pressed

COLUMN_CARD_WIDTH = 872.0  # the 920 px column less its 24 px paddings
WIDE_COLUMN_LEFT = 204.0  # (1280 - 920) / 2 + 24
NARROW_COLUMN_LEFT = 16.0
TILE_WIDTH = 272.7
STATE_LINE = '[data-testid="ops-state-line"]'


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


@pytest.fixture
def server(tmp_path: Path, catalogue: Catalogue) -> Iterator[OpsServer]:
    with ops_live_server(tmp_path, catalogue) as running:
        yield running


def heading_of(page: Page) -> Locator:
    heading = page.get_by_test_id("ops-page").locator("h1")
    expect(heading).to_have_count(1)
    return heading


def locked_page(window: OpenWindow, server: OpsServer, size: tuple[int, int]) -> Page:
    page = window(*size)
    open_ops(page, server.base_url)
    expect_ops_state(page, "locked")
    return page


def refuse_token(page: Page) -> None:
    """Submit `wrong`, the dashboard answering 401; wait for `ops-token-error`."""

    def refuse(route: Route) -> None:
        fulfil_json(route, 401, {"detail": "Not authorized"})

    page.route(DASHBOARD_ROUTE, refuse)
    field = page.get_by_test_id("ops-token-input")
    field.fill("wrong")
    expect(field).to_have_value("wrong")
    # 2026-10-23: Firefox under load lost the press; main's run after #43.
    click_until_pressed(page.get_by_test_id("ops-token-submit"))
    expect(page.get_by_test_id("ops-token-error")).to_be_visible()


def held_page(window: OpenWindow, server: OpsServer, size: tuple[int, int]) -> Page:
    """The token seeded and the dashboard request held: the page `loading`."""
    page = window(*size)
    HeldRoute(page, DASHBOARD_ROUTE)
    seed_ops_token(page)
    open_ops(page, server.base_url)
    expect_ops_state(page, "loading")
    return page


def ready_page(window: OpenWindow, server: OpsServer, size: tuple[int, int]) -> Page:
    page = window(*size)
    open_ready_ops(page, server.base_url)
    return page


# ---- AC-6: the frame and the token card --------------------------------------------


def test_ac6_the_header_is_the_catalogue_bar_with_the_brand_only(
    window: OpenWindow, server: OpsServer
) -> None:
    page = locked_page(window, server, (1280, 720))

    problems = header_problems(page, 56.0, links_allowed=False)
    if not problems:
        problems.extend(page_colour_problems(page))

    assert problems == []


def test_ac6_the_heading_is_in_the_catalogue_heading_style_in_the_column(
    window: OpenWindow, server: OpsServer
) -> None:
    page = locked_page(window, server, (1280, 720))
    heading = heading_of(page)
    box = box_of(heading)

    problems = text_problems(heading, "h1", fr_value("ops.heading"))
    problems.extend(font_problems(heading, "h1", 27.2, "700", NAVY))
    if not same_position(box.left, WIDE_COLUMN_LEFT):
        problems.append(f"the h1's left edge at {box.left}")
    if not same_position(box.top - header_box(page).bottom, 24.0):
        problems.append(f"the h1 {box.top - header_box(page).bottom} px down")

    assert problems == []


def test_ac6_the_token_form_is_a_card_16_px_under_the_heading(
    window: OpenWindow, server: OpsServer
) -> None:
    page = locked_page(window, server, (1280, 720))
    heading = box_of(heading_of(page))
    form = page.get_by_test_id("ops-token-form")
    box = box_of(form)

    problems = card_problems(form)
    if not same_position(box.left, heading.left):
        problems.append(f"the card's left edge at {box.left}, the h1's {heading.left}")
    if not same_position(box.width, COLUMN_CARD_WIDTH):
        problems.append(f"the card is {box.width} px wide")
    if not same_position(box.top - heading.bottom, 16.0):
        problems.append(f"the card is {box.top - heading.bottom} px under the h1")

    assert problems == []


def test_ac6_the_card_holds_the_token_field_then_the_primary_submit(
    window: OpenWindow, server: OpsServer
) -> None:
    page = locked_page(window, server, (1280, 720))
    form = page.get_by_test_id("ops-token-form")
    label = form.get_by_text(fr_value("ops.token_label"), exact=True)
    expect(label).to_have_count(1)
    field = form.get_by_test_id("ops-token-input")
    submit = form.get_by_test_id("ops-token-submit")

    problems = field_label_problems(label, "label")
    gap = box_of(field).top - box_of(label).bottom
    if not same_position(gap, 6.0):
        problems.append(f"the label is {gap} px above the input")
    if field.get_attribute("type") != "password":
        problems.append(f"ops-token-input type {field.get_attribute('type')}")
    problems.extend(text_input_problems(field, form, "ops-token-input"))
    problems.extend(button_colour_problems(submit, "primary"))
    if box_of(submit).top < box_of(field).bottom - 1.0:
        problems.append("ops-token-submit is not under the input")

    assert problems == []


def test_ac6_on_a_phone_the_bar_is_56_px_and_the_heading_16_px_in(
    window: OpenWindow, server: OpsServer
) -> None:
    page = locked_page(window, server, (360, 740))

    left = box_of(heading_of(page)).left

    assert header_problems(page, 56.0, links_allowed=False) == []
    assert same_position(left, NARROW_COLUMN_LEFT), left


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac6_a_refused_token_turns_the_input_red_with_an_error_line_under_it(
    window: OpenWindow, server: OpsServer, size: tuple[int, int]
) -> None:
    page = locked_page(window, server, size)
    field = page.get_by_test_id("ops-token-input")

    refuse_token(page)

    error = page.get_by_test_id("ops-token-error")
    expect(field).to_have_attribute("aria-invalid", "true")
    problems = border_colour_problems(field, "ops-token-input", RED)
    problems.extend(
        text_problems(error, "ops-token-error", fr_value("ops.token_refused"))
    )
    problems.extend(role_problems(error, "ops-token-error", "alert"))
    problems.extend(error_line_problems(error, "ops-token-error"))
    line = box_of(error)
    submit = box_of(page.get_by_test_id("ops-token-submit"))
    if line.top < box_of(field).bottom - 1.0 or line.bottom > submit.top + 1.0:
        problems.append("ops-token-error is not between the input and the button")
    # Spec 048 AC-6 after its second review: 6 px under the input, as drawn.
    gap = line.top - box_of(field).bottom
    if not same_position(gap, 6.0):
        problems.append(f"ops-token-error is {gap} px under the input, not 6")

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac6_the_refusal_describes_the_token_input(
    window: OpenWindow, server: OpsServer, size: tuple[int, int]
) -> None:
    page = locked_page(window, server, size)

    refuse_token(page)

    field = page.get_by_test_id("ops-token-input")
    error = page.get_by_test_id("ops-token-error")
    assert described_by_problems(field, error, "ops-token-error") == []


# ---- AC-7: the page's waiting and failed lines -------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac7_while_the_dashboard_loads_one_muted_line_is_under_the_heading(
    window: OpenWindow, server: OpsServer, size: tuple[int, int]
) -> None:
    page = held_page(window, server, size)
    line = page.get_by_test_id("ops-state-line")
    expect(line).to_have_count(1)

    problems = text_problems(line, "ops-state-line", fr_value("ops.loading"))
    problems.extend(role_problems(line, "ops-state-line", "status"))
    problems.extend(waiting_line_problems(line, "ops-state-line"))
    gap = box_of(line).top - box_of(heading_of(page)).bottom
    if not same_position(gap, 16.0):
        problems.append(f"the line is {gap} px under the h1")
    problems.extend(others_in(page.get_by_test_id("ops-page"), ["h1", STATE_LINE]))

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac7_a_failed_dashboard_is_one_error_line(
    window: OpenWindow, server: OpsServer, size: tuple[int, int]
) -> None:
    page = window(*size)

    def fail(route: Route) -> None:
        fulfil_json(route, 500, {"detail": "Internal Server Error"})

    page.route(DASHBOARD_ROUTE, fail)
    seed_ops_token(page)
    open_ops(page, server.base_url)
    expect_ops_state(page, "error")
    line = page.get_by_test_id("ops-state-line")
    expect(line).to_have_count(1)

    problems = text_problems(line, "ops-state-line", fr_value("ops.error"))
    problems.extend(role_problems(line, "ops-state-line", "alert"))
    problems.extend(error_line_problems(line, "ops-state-line"))

    assert problems == []


# ---- AC-8: the dashboard's chips and tiles -----------------------------------------


def test_ac8_the_dashboard_is_a_card_872_px_wide_with_its_heading(
    window: OpenWindow, server: OpsServer
) -> None:
    page = ready_page(window, server, (1280, 720))
    dashboard = page.get_by_test_id("ops-dashboard")
    heading = dashboard.locator("h2")
    expect(heading).to_have_count(1)
    field = dashboard.get_by_test_id("ops-period-field")
    expect(field).to_have_count(1)

    problems = card_problems(dashboard)
    if not same_position(box_of(dashboard).width, COLUMN_CARD_WIDTH):
        problems.append(f"ops-dashboard is {box_of(dashboard).width} px wide")
    problems.extend(text_problems(heading, "h2", fr_value("ops.dashboard_heading")))
    problems.extend(card_title_problems(heading, "h2"))
    if box_of(field).top < box_of(heading).bottom - 1.0:
        problems.append("ops-period-field is not under the h2")

    assert problems == []


def test_ac8_the_period_label_is_a_field_label_naming_the_group(
    window: OpenWindow, server: OpsServer
) -> None:
    page = ready_page(window, server, (1280, 720))
    period_label = fr_value("ops.period_label")
    field = page.get_by_test_id("ops-period-field")
    label = field.get_by_text(period_label, exact=True)
    expect(label).to_have_count(1)
    group = page.get_by_role("group", name=period_label)
    expect(group).to_have_count(1)
    expect(group.get_by_test_id("ops-period")).to_have_count(3)

    label_id = label.get_attribute("id")
    named = (group.get_attribute("aria-labelledby") or "").split()

    assert field_label_problems(label, "label") == []
    assert label_id is not None
    assert label_id in named
    assert box_of(label).bottom <= box_of(group).top + 1.0


def chip_problems(chip: Locator, name: str) -> list[str]:
    """A filter chip: radius 16 px, padding 7 px 14 px, 600 14.4 px navy."""
    problems = radius_padding_problems(chip, name, "16px", "7px 14px")
    problems.extend(font_problems(chip, name, 14.4, "600", NAVY))
    return problems


def test_ac8_the_periods_are_chips_on_one_line_8_px_apart(
    window: OpenWindow, server: OpsServer
) -> None:
    page = ready_page(window, server, (1280, 720))
    chips = page.get_by_test_id("ops-period")
    expect(chips).to_have_count(3)

    problems: list[str] = []
    boxes = [box_of(chips.nth(index)) for index in range(3)]
    for index in range(3):
        chip = chips.nth(index)
        name = f"ops-period {chip.get_attribute('data-days')}"
        problems.extend(chip_problems(chip, name))
        if chip.get_attribute("aria-pressed") == "true":
            problems.extend(colour_problem(chip, name, "backgroundColor", WORD))
            problems.extend(border_colour_problems(chip, name, NAVY))
        else:
            problems.extend(colour_problem(chip, name, "backgroundColor", WHITE))
            problems.extend(border_colour_problems(chip, name, LINE))
    for index in range(2):
        if not same_position(boxes[index + 1].top, boxes[index].top):
            problems.append(f"chips {index} and {index + 1} are not on one line")
        gap = boxes[index + 1].left - boxes[index].right
        if not same_position(gap, 8.0):
            problems.append(f"chips {index} and {index + 1} are {gap} px apart")

    assert chips.nth(1).get_attribute("data-days") == "7"
    assert chips.nth(1).get_attribute("aria-pressed") == "true"
    assert problems == []


def test_ac8_the_six_figures_are_tiles_three_per_row(
    window: OpenWindow, server: OpsServer
) -> None:
    page = ready_page(window, server, (1280, 720))
    tiles = page.get_by_test_id("ops-metric")

    problems: list[str] = []
    boxes = [box_of(tiles.nth(index)) for index in range(6)]
    for index in range(6):
        tile = tiles.nth(index)
        name = f"ops-metric {index + 1}"
        problems.extend(colour_problem(tile, name, "backgroundColor", WHITE))
        problems.extend(all_borders_problems(tile, name, LINE))
        problems.extend(radius_padding_problems(tile, name, "8px", "12px 14px"))
        problems.extend(font_problems(tile, name, 15.2, colour=INK))
    for index in range(3):
        if not same_position(boxes[index].width, TILE_WIDTH):
            problems.append(f"tile {index + 1} is {boxes[index].width} px wide")
        if not same_position(boxes[index].top, boxes[0].top):
            problems.append(f"tile {index + 1} is not on the first row")
    for index in range(2):
        gap = boxes[index + 1].left - boxes[index].right
        if not same_position(gap, 10.0):
            problems.append(f"tiles {index + 1} and {index + 2} are {gap} px apart")

    assert texts_of(tiles) == SEVEN_DAY_TEXTS
    assert problems == []


def test_ac8_on_a_phone_the_tiles_are_one_per_row_and_the_chips_fit_the_card(
    window: OpenWindow, server: OpsServer
) -> None:
    page = ready_page(window, server, (360, 740))
    dashboard = page.get_by_test_id("ops-dashboard")
    inner = content_box(dashboard)
    tiles = page.get_by_test_id("ops-metric")
    chips = page.get_by_test_id("ops-period")

    problems: list[str] = []
    previous_bottom = -1.0
    for index in range(6):
        box = box_of(tiles.nth(index))
        if not same_position(box.width, 294.0):
            problems.append(f"tile {index + 1} is {box.width} px wide")
        if box.top < previous_bottom - 1.0:
            problems.append(f"tile {index + 1} shares a row")
        previous_bottom = box.bottom
    if not same_position(inner.width, 294.0):
        problems.append(f"the card's content is {inner.width} px wide")
    for index in range(3):
        if not box_inside(box_of(chips.nth(index)), box_of(dashboard)):
            problems.append(f"chip {index + 1} is not inside the card")

    assert problems == []
    assert no_horizontal_scroll(page)
