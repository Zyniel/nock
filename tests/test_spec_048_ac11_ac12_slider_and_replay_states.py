"""Tests of spec 048, AC-11 and AC-12: the replay's step slider, drawn over the
native range input, and the replay's waiting, not-found and failed lines.

The server is spec 038's live server with `operator_token=OPS_TOKEN`; the token
is seeded, the dashboard answered with AC-5's 7-day figures, and
`page.route("**/api/ops/rooms/*/edits", ...)` answers `REPLAY`, 404 or 500, or
holds the request, after a submit of `k7qm2x` (AC-11) or `K7QM2X` (AC-12).
Keyboard: spec 035's `Walker` (`tab_to`). Windows: desktop contexts in Paris
time.

Readings of the spec's wording:

- "Its centre at ..." and "runs from the track's left edge to the knob's centre":
  the knob's box centre, and the fill's left and right edges, within 1 px.
- "The fill is 0 to 1 px wide": its box is at most 1 px wide (plus the
  sub-pixel margin of the harness).
- "Holds, after its form, `ops-replay-state-line`": the line's top is not above
  the form's bottom (1 px), and the card shows nothing else but its `h2`, its
  form and the line.
- "The dashboard card stays above with its figures": `ops-dashboard` is visible,
  its bottom not under the replay card's top (1 px), its six texts spec 038's.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec035_harness import Walker
from spec038_harness import SEVEN_DAY_TEXTS, OpsServer, ops_live_server, texts_of
from spec042_harness import Box, box_of
from spec043_harness import NAVY, WORD, fr_value, hit_problem, style_of
from spec046_harness import (
    SUBPIXEL_PX,
    OpenWindow,
    colour_problem,
    same_position,
    same_size,
    window_opener,
)
from spec048_harness import (
    NOT_FOUND,
    ROOM_CODE,
    SIZE_IDS,
    SIZES,
    error_line_problems,
    others_in,
    ring_problems,
    role_problems,
    text_problems,
    waiting_line_problems,
)
from spec048_ops_harness import (
    REPLAY_COUNT,
    ReplayRoute,
    open_replay,
    replay,
    replay_answer,
    set_position,
    step_text,
)

KNOB = 18.0
TRACK = 6.0
DRAWN_PARTS = ["ops-replay-track", "ops-replay-fill", "ops-replay-knob"]
# The answers of AC-12: the replay request held, answered 404, answered 500.
STATES = [
    pytest.param(None, "loading", "ops.loading", "status", id="loading"),
    pytest.param(404, "not_found", "ops.replay_not_found", "alert", id="not_found"),
    pytest.param(500, "error", "ops.error", "alert", id="error"),
]


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


@pytest.fixture
def server(tmp_path: Path, catalogue: Catalogue) -> Iterator[OpsServer]:
    with ops_live_server(tmp_path, catalogue) as running:
        yield running


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


def slider_page(window: OpenWindow, server: OpsServer, grid: Grid) -> Page:
    """`REPLAY` at 1280 by 720, at its maximum position 7."""
    page = window(1280, 720)
    open_replay(page, server.base_url, replay_answer(replay(grid)), "ready")
    expect(page.get_by_test_id("ops-replay-position")).to_have_value("7")
    return page


def input_box(page: Page) -> Box:
    return box_of(page.get_by_test_id("ops-replay-position"))


def knob_centre_problems(page: Page, position: int) -> list[str]:
    """The knob's centre at `left + 9 + (width - 18) * k / 7`, on the input's
    vertical centre (1 px)."""
    field = input_box(page)
    knob = box_of(page.get_by_test_id("ops-replay-knob"))
    expected_x = field.left + 9.0 + (field.width - KNOB) * position / REPLAY_COUNT
    problems: list[str] = []
    if not same_position(knob.centre_x, expected_x):
        problems.append(f"the knob's centre at {knob.centre_x}, not {expected_x}")
    if not same_position(knob.centre_y, field.centre_y):
        problems.append(f"the knob's middle at {knob.centre_y}, not {field.centre_y}")
    return problems


# ---- AC-11: the slider -------------------------------------------------------------


def test_ac11_the_position_is_a_transparent_native_range_as_wide_as_its_field(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = slider_page(window, server, fx01_grid)
    position = page.get_by_test_id("ops-replay-position")
    field = box_of(page.get_by_test_id("ops-replay-position-field"))
    box = input_box(page)

    assert position.evaluate("element => element.tagName") == "INPUT"
    assert position.get_attribute("type") == "range"
    assert same_size(box.height, KNOB), box
    assert same_position(box.width, field.width), (box, field)
    assert style_of(position, "opacity") == "0"
    # At 1280 by 720 the slider lies below the window's bottom: scrolled into view
    # first, so that `elementFromPoint` reaches it (the coordinator's fix of
    # 2026-10-23, after the code).
    position.scroll_into_view_if_needed()
    assert hit_problem(page, "ops-replay-position") is None


def test_ac11_the_track_is_a_6_px_word_blue_bar_centred_on_the_input(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = slider_page(window, server, fx01_grid)
    track = page.get_by_test_id("ops-replay-track")
    box = box_of(track)
    field = input_box(page)

    problems = colour_problem(track, "track", "backgroundColor", WORD)
    if style_of(track, "borderTopLeftRadius") != "3px":
        problems.append(f"track radius {style_of(track, 'borderTopLeftRadius')}")

    assert problems == []
    assert same_size(box.height, TRACK), box
    assert same_position(box.width, field.width), (box, field)
    assert same_position(box.centre_y, field.centre_y), (box, field)


def test_ac11_at_the_maximum_the_knob_is_at_the_right_end_and_the_fill_reaches_it(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = slider_page(window, server, fx01_grid)
    knob = page.get_by_test_id("ops-replay-knob")
    fill = page.get_by_test_id("ops-replay-fill")
    knob_box = box_of(knob)
    fill_box = box_of(fill)
    track_box = box_of(page.get_by_test_id("ops-replay-track"))
    field = input_box(page)

    problems = colour_problem(knob, "knob", "backgroundColor", NAVY)
    problems.extend(colour_problem(fill, "fill", "backgroundColor", NAVY))
    if style_of(knob, "borderTopLeftRadius") != "50%":
        problems.append(f"knob radius {style_of(knob, 'borderTopLeftRadius')}")
    if not (same_size(knob_box.width, KNOB) and same_size(knob_box.height, KNOB)):
        problems.append(f"the knob is {knob_box.width} by {knob_box.height}")
    if not same_position(knob_box.centre_x, field.right - 9.0):
        problems.append(f"the knob's centre at {knob_box.centre_x}")
    problems.extend(knob_centre_problems(page, REPLAY_COUNT))
    if not same_position(fill_box.left, track_box.left):
        problems.append(
            f"the fill starts at {fill_box.left}, the track {track_box.left}"
        )
    if not same_position(fill_box.right, knob_box.centre_x):
        problems.append(f"the fill ends at {fill_box.right}")
    if not same_size(fill_box.height, track_box.height):
        problems.append(f"the fill is {fill_box.height} px high")

    assert problems == []


def test_ac11_at_the_position_0_the_knob_is_9_px_in_and_the_fill_is_empty(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = slider_page(window, server, fx01_grid)

    set_position(page, 0)

    knob = box_of(page.get_by_test_id("ops-replay-knob"))
    fill = box_of(page.get_by_test_id("ops-replay-fill"))
    assert same_position(knob.centre_x, input_box(page).left + 9.0), knob
    assert fill.width <= 1.0 + SUBPIXEL_PX, fill


def test_ac11_at_the_position_4_the_knob_is_four_sevenths_along(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = slider_page(window, server, fx01_grid)

    set_position(page, 4)

    assert knob_centre_problems(page, 4) == []


def test_ac11_the_three_drawn_parts_are_hidden_from_assistive_technology(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = slider_page(window, server, fx01_grid)

    hidden: list[str | None] = []
    for test_id in DRAWN_PARTS:
        hidden.append(page.get_by_test_id(test_id).get_attribute("aria-hidden"))

    assert hidden == ["true", "true", "true"]


def test_ac11_the_slider_named_by_its_label_is_the_native_input(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = slider_page(window, server, fx01_grid)

    slider = page.get_by_role("slider", name=fr_value("ops.replay_position_label"))

    expect(slider).to_have_count(1)
    expect(slider).to_have_attribute("data-testid", "ops-replay-position")


def test_ac11_keyboard_focus_rings_the_knob_and_arrow_left_steps_back(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = slider_page(window, server, fx01_grid)
    walker = Walker(page)

    walker.tab_to("ops-replay-position")
    ring = ring_problems(page.get_by_test_id("ops-replay-knob"), "knob")
    page.keyboard.press("ArrowLeft")

    expect(page.get_by_test_id("ops-replay-position")).to_have_value("6")
    expect(page.get_by_test_id("ops-replay-step")).to_have_text(step_text(6))
    assert ring == []


# ---- AC-12: the replay's state lines -----------------------------------------------


@pytest.mark.parametrize(("status", "state", "key", "role"), STATES)
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac12_each_replay_state_is_one_line_under_the_form(
    window: OpenWindow,
    server: OpsServer,
    size: tuple[int, int],
    status: int | None,
    state: str,
    key: str,
    role: str,
) -> None:
    page = window(*size)
    route = ReplayRoute(status, None if status is None else NOT_FOUND)
    open_replay(page, server.base_url, route, state, ROOM_CODE)
    card = page.get_by_test_id("ops-replay")
    line = card.get_by_test_id("ops-replay-state-line")
    expect(line).to_have_count(1)

    problems = text_problems(line, "line", fr_value(key))
    problems.extend(role_problems(line, "line", role))
    if status is None:
        problems.extend(waiting_line_problems(line, "line"))
    else:
        problems.extend(error_line_problems(line, "line"))
    form = box_of(card.get_by_test_id("ops-replay-form"))
    if box_of(line).top < form.bottom - 1.0:
        problems.append("the line is not under the form")
    selectors = ["h2", '[data-testid="ops-replay-form"]']
    selectors.append('[data-testid="ops-replay-state-line"]')
    problems.extend(others_in(card, selectors))

    assert problems == []


@pytest.mark.parametrize(("status", "state", "key", "role"), STATES)
def test_ac12_the_dashboard_stays_above_with_its_figures(
    window: OpenWindow,
    server: OpsServer,
    status: int | None,
    state: str,
    key: str,
    role: str,
) -> None:
    page = window(1280, 720)
    route = ReplayRoute(status, None if status is None else NOT_FOUND)
    open_replay(page, server.base_url, route, state, ROOM_CODE)
    dashboard = page.get_by_test_id("ops-dashboard")
    expect(dashboard).to_be_visible()
    line = page.get_by_test_id("ops-replay-state-line")
    expect(line).to_have_text(fr_value(key))
    expect(line).to_have_attribute("role", role)

    replay_top = box_of(page.get_by_test_id("ops-replay")).top

    assert box_of(dashboard).bottom <= replay_top + 1.0
    assert texts_of(page.get_by_test_id("ops-metric")) == SEVEN_DAY_TEXTS
    assert route.urls != []
