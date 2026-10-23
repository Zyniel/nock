"""Tests of spec 025, AC-8: the banner never takes the grid's room, and it can be
reached from the keyboard.

Setup: spec 013 AC-6's (FX-01, `you` host among 8 players, 100 feed items), in
vote mode, then the mock's `vote_opened` by `p2` (a grid check). The layout is
read at the eight window sizes of spec 006 AC-5 in desktop and touch contexts;
the keyboard, contrast and language checks use spec 035's harness. After a ballot
the focus is on `vote-status`, and on the `grid` once the vote closes or the
banner leaves (decision 19), while a focus outside the banner stays where it is;
the contrast and language scans run in the state before the ballot. The shared
setup is in `spec025_harness`.

Refined by spec 043 (the design's room layout): "the room header" reads
`room-topbar` (it was the `header` element that holds `share-panel`); the focus
outside the banner is put on `copy-link` once the Salon's Joueurs tab shows
(spec 043's `show_tab`), since `copy-link` is in that tab.

Refined by spec 047 (the design's room overlays): after the `vote_closed` the
banner is gone within 300 ms and there is no `vote-result`; the focus that was on
`vote-status` is on the `grid`, and a focus outside the banner stays where it
is. The boxes compared are those of `room-topbar` (already read so since spec
043), `grid-viewport`, `clue-bar` and `keyboard`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, FloatRect, Locator, Page, expect

from nock.grid import Grid
from nock.protocol import GridSolved, Vote, VoteOutcome
from room_panels import show_tab
from spec025_harness import (
    EIGHT_NICKNAMES,
    GRID_CHECK,
    MOCK_CODE,
    MockRoomSocket,
    box_of,
    cell_at,
    closed,
    eight_players,
    fr_text,
    grid_check_line_frame,
    grid_from_text,
    make_page,
    open_room,
    opened,
    settle,
    wait_until,
)
from spec035_harness import (
    FX01_CLUES,
    LANGUAGE_SCAN_SCRIPT,
    MIN_FOCUS_CONTRAST,
    MIN_OUTLINE_PX,
    Walker,
    contrast_offenders,
    unknown_texts,
)

TAP_TIMEOUT_MS = 3000
BANNER_GONE_MS = 300  # spec 047: "within 300 ms" of the `vote_closed`
EPSILON = 1.0
MIN_GRID_VIEWPORT_PX = 100.0
MIN_TARGET_PX = 24.0
FEED_ITEMS = 100
FIRST_FEED_SEQ = 6
VOTE_SEQ = FIRST_FEED_SEQ + FEED_ITEMS
WINDOW_SIZES = [
    (320, 568),
    (568, 320),
    (360, 740),
    (740, 360),
    (768, 1024),
    (1024, 768),
    (1280, 800),
    (1920, 1080),
]
KEYBOARD_SIZES = [(1280, 720), (568, 320)]
SCAN_SIZES = [(1280, 720), (360, 740)]
NEXT_SEQ = VOTE_SEQ + 1  # the seq of the event after the `vote_opened`
EIGHT_ELIGIBLE = 8
FIVE_YES = 5  # the majority of 8 eligible voters


# Whether `document.elementFromPoint` at the centre of the element returns it.
ELEMENT_AT_CENTRE_SCRIPT = (
    "el => { const r = el.getBoundingClientRect();"
    " return document.elementFromPoint(r.left + r.width / 2,"
    " r.top + r.height / 2) === el; }"
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def open_spec_013_room(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    """The FX-01 snapshot with 8 players in vote mode, then 100 feed lines."""
    mock = open_room(page, base_url, grid, players=eight_players())
    last_seq = VOTE_SEQ - 1
    for seq in range(FIRST_FEED_SEQ, last_seq + 1):
        mock.send(grid_check_line_frame(seq))
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-seq", str(last_seq)
    )
    return mock


def send_grid_check_vote(page: Page, mock: MockRoomSocket) -> None:
    """The mock's `vote_opened`: vote 1, by `p2`, a grid check, 8 eligible."""
    mock.send(opened(VOTE_SEQ, 1, "p2", GRID_CHECK, 8).model_dump_json())
    expect(page.get_by_test_id("vote-banner")).to_be_visible()
    expect(page.get_by_test_id("vote-no")).to_be_visible()


def vote_yes_from_the_keyboard(page: Page, mock: MockRoomSocket) -> None:
    """From the `grid`: `Escape`, `Shift+Tab` twice to `vote-yes`, then `Enter`.

    Returns once the page sent its ballot, `Vote(vote_id=1, yes=True)`.
    """
    walker = Walker(page)
    walker.tab_to("grid")
    page.keyboard.press("Escape")
    page.keyboard.press("Shift+Tab")
    expect(page.get_by_test_id("vote-no")).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(page.get_by_test_id("vote-yes")).to_be_focused()
    page.keyboard.press("Enter")
    wait_until(page, lambda: len(mock.votes()) >= 1)
    assert mock.votes() == [Vote(vote_id=1, yes=True)]


def active_test_id(page: Page) -> str | None:
    """The `data-testid` of `document.activeElement`, None if it has none."""
    test_id = page.evaluate("document.activeElement?.getAttribute('data-testid')")
    assert test_id is None or isinstance(test_id, str), test_id
    return test_id


def room_header(page: Page) -> Locator:
    return page.get_by_test_id("room-topbar")


def layout_boxes(page: Page, touch: bool) -> dict[str, FloatRect]:
    """The boxes that showing the banner must not move."""
    header = room_header(page)
    expect(header).to_have_count(1)
    boxes = {
        "room header": box_of(header),
        "grid-viewport": box_of(page.get_by_test_id("grid-viewport")),
        "clue-bar": box_of(page.get_by_test_id("clue-bar")),
    }
    if touch:
        boxes["keyboard"] = box_of(page.get_by_test_id("keyboard"))
    return boxes


def same_box(first: FloatRect, second: FloatRect) -> bool:
    for key in ("x", "y", "width", "height"):
        if abs(first[key] - second[key]) > EPSILON:
            return False
    return True


def is_inside(inner: FloatRect, outer: FloatRect) -> bool:
    return (
        inner["x"] >= outer["x"] - EPSILON
        and inner["y"] >= outer["y"] - EPSILON
        and inner["x"] + inner["width"] <= outer["x"] + outer["width"] + EPSILON
        and inner["y"] + inner["height"] <= outer["y"] + outer["height"] + EPSILON
    )


def check_spec_013_ac6(page: Page, touch: bool) -> None:
    """Spec 013 AC-6's checks: the grid keeps its room, no page scroll."""
    viewport = page.get_by_test_id("grid-viewport")
    viewport_box = box_of(viewport)
    bar_box = box_of(page.get_by_test_id("clue-bar"))
    sizes = page.evaluate(
        "() => [document.documentElement.scrollWidth, window.innerWidth,"
        " document.documentElement.scrollHeight, window.innerHeight]"
    )
    scroll_width, window_width, scroll_height, window_height = sizes

    assert viewport_box["height"] >= MIN_GRID_VIEWPORT_PX, viewport_box
    assert scroll_width <= window_width
    assert scroll_height <= window_height
    expect(viewport).to_have_attribute("data-zoom", "1")
    assert is_inside(box_of(page.get_by_test_id("grid")), viewport_box)
    assert bar_box["x"] >= -EPSILON
    assert bar_box["x"] + bar_box["width"] <= window_width + EPSILON
    assert bar_box["y"] >= -EPSILON
    bar_bottom = bar_box["y"] + bar_box["height"]
    assert bar_bottom <= window_height + EPSILON
    if touch:
        keyboard_box = box_of(page.get_by_test_id("keyboard"))
        assert bar_bottom <= keyboard_box["y"] + EPSILON
        assert keyboard_box["y"] + keyboard_box["height"] <= window_height + EPSILON


# ---- AC-8: layout at every window size ----


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac8_the_banner_changes_no_layout_and_its_buttons_can_be_tapped(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = make_page(browser, browser_name, width, height, touch)
    try:
        mock = open_spec_013_room(page, live_server, fx01_grid)
        cell = cell_at(page, 3, 1)
        if touch:
            cell.tap(timeout=TAP_TIMEOUT_MS)
        else:
            cell.click(timeout=TAP_TIMEOUT_MS)
        expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", "3,0,0")
        settle(page)
        before = layout_boxes(page, touch)

        send_grid_check_vote(page, mock)
        settle(page)

        after = layout_boxes(page, touch)
        for name, box in before.items():
            assert same_box(box, after[name]), f"{name}: {box} then {after[name]}"
        check_spec_013_ac6(page, touch)
        viewport_box = box_of(page.get_by_test_id("grid-viewport"))
        banner_box = box_of(page.get_by_test_id("vote-banner"))
        assert is_inside(banner_box, viewport_box), (banner_box, viewport_box)
        for test_id in ("vote-yes", "vote-no"):
            button = page.get_by_test_id(test_id)
            button_box = box_of(button)
            assert button_box["width"] >= MIN_TARGET_PX, (test_id, button_box)
            assert button_box["height"] >= MIN_TARGET_PX, (test_id, button_box)
            assert button.evaluate(ELEMENT_AT_CENTRE_SCRIPT) is True, test_id
    finally:
        close()


# ---- AC-8: keyboard only ----


@pytest.mark.parametrize(
    ("width", "height"), KEYBOARD_SIZES, ids=[f"{w}x{h}" for w, h in KEYBOARD_SIZES]
)
def test_ac8_keyboard_shift_tab_from_the_grid_reaches_no_then_yes_and_enter_votes(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = make_page(browser, browser_name, width, height, touch=False)
    try:
        mock = open_spec_013_room(page, live_server, fx01_grid)
        send_grid_check_vote(page, mock)
        walker = Walker(page)

        walker.tab_to("grid")
        page.keyboard.press("Escape")
        page.keyboard.press("Shift+Tab")

        expect(page.get_by_test_id("vote-no")).to_be_focused()
        walker.record("vote-no")
        page.keyboard.press("Shift+Tab")
        expect(page.get_by_test_id("vote-yes")).to_be_focused()
        walker.record("vote-yes")
        for reached in walker.reached[-2:]:
            assert reached.outline_style not in ("none", "auto"), reached
            assert reached.outline_width >= MIN_OUTLINE_PX, reached
            assert reached.outline_contrast >= MIN_FOCUS_CONTRAST, reached

        page.keyboard.press("Enter")

        wait_until(page, lambda: len(mock.votes()) >= 1)
        settle(page)
        assert mock.votes() == [Vote(vote_id=1, yes=True)]
    finally:
        close()


# ---- AC-8: where the focus goes after a ballot (decision 19) ----


@pytest.mark.parametrize(
    ("width", "height"), KEYBOARD_SIZES, ids=[f"{w}x{h}" for w, h in KEYBOARD_SIZES]
)
def test_ac8_keyboard_after_enter_on_yes_the_focus_is_on_vote_status(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = make_page(browser, browser_name, width, height, touch=False)
    try:
        mock = open_spec_013_room(page, live_server, fx01_grid)
        send_grid_check_vote(page, mock)

        vote_yes_from_the_keyboard(page, mock)

        status = page.get_by_test_id("vote-status")
        expect(status).to_be_visible()
        expect(status).to_have_attribute("tabindex", "-1")
        expect(status).to_be_focused()
        assert page.evaluate("document.activeElement !== document.body") is True
    finally:
        close()


@pytest.mark.parametrize(
    ("width", "height"), KEYBOARD_SIZES, ids=[f"{w}x{h}" for w, h in KEYBOARD_SIZES]
)
def test_ac8_keyboard_a_grid_solved_moves_the_focus_from_vote_status_to_the_grid(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = make_page(browser, browser_name, width, height, touch=False)
    try:
        mock = open_spec_013_room(page, live_server, fx01_grid)
        send_grid_check_vote(page, mock)
        vote_yes_from_the_keyboard(page, mock)
        expect(page.get_by_test_id("vote-status")).to_be_focused()

        mock.send(GridSolved(seq=NEXT_SEQ, elapsed_ms=60_000).model_dump_json())

        room = page.get_by_test_id("room-page")
        expect(room).to_have_attribute("data-solved", "true")
        expect(page.get_by_test_id("vote-banner")).to_be_hidden()
        expect(page.get_by_test_id("grid")).to_be_focused()
    finally:
        close()


def test_ac8_a_click_on_no_sends_false_and_leaves_the_focus_on_vote_status(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
) -> None:
    page, close = make_page(browser, browser_name, 1280, 720, touch=False)
    try:
        mock = open_spec_013_room(page, live_server, fx01_grid)
        send_grid_check_vote(page, mock)

        page.get_by_test_id("vote-no").click()

        wait_until(page, lambda: len(mock.votes()) >= 1)
        settle(page)
        assert mock.votes() == [Vote(vote_id=1, yes=False)]
        status = page.get_by_test_id("vote-status")
        expect(status).to_have_text(fr_text("vote.cast"))
        expect(status).to_be_focused()
    finally:
        close()


@pytest.mark.parametrize(
    ("width", "height"), KEYBOARD_SIZES, ids=[f"{w}x{h}" for w, h in KEYBOARD_SIZES]
)
def test_ac8_keyboard_a_vote_closed_moves_the_focus_from_vote_status_to_the_grid(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = make_page(browser, browser_name, width, height, touch=False)
    try:
        mock = open_spec_013_room(page, live_server, fx01_grid)
        send_grid_check_vote(page, mock)
        vote_yes_from_the_keyboard(page, mock)
        expect(page.get_by_test_id("vote-status")).to_be_focused()

        passed = closed(NEXT_SEQ, 1, VoteOutcome.PASSED, FIVE_YES, EIGHT_ELIGIBLE)
        mock.send(passed.model_dump_json())

        # Spec 047: the banner is gone within 300 ms, with no `vote-result`.
        banner = page.get_by_test_id("vote-banner")
        expect(banner).to_have_count(0, timeout=BANNER_GONE_MS)
        expect(page.get_by_test_id("vote-result")).to_have_count(0)
        expect(page.get_by_test_id("grid")).to_be_focused()
    finally:
        close()


def test_ac8_a_focus_outside_the_banner_stays_where_it_is(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
) -> None:
    page, close = make_page(browser, browser_name, 1280, 720, touch=False)
    try:
        mock = open_spec_013_room(page, live_server, fx01_grid)
        send_grid_check_vote(page, mock)
        show_tab(page, "players")
        page.get_by_test_id("copy-link").focus()
        assert active_test_id(page) == "copy-link"

        passed = closed(NEXT_SEQ, 1, VoteOutcome.PASSED, FIVE_YES, EIGHT_ELIGIBLE)
        mock.send(passed.model_dump_json())

        # Spec 047: the banner leaves at the `vote_closed`, with no result.
        banner = page.get_by_test_id("vote-banner")
        expect(banner).to_have_count(0, timeout=BANNER_GONE_MS)
        expect(page.get_by_test_id("vote-announcement")).to_have_text(
            fr_text("vote.result.passed")
        )
        assert active_test_id(page) == "copy-link"
    finally:
        close()


# ---- AC-8: contrast and language in the state before the ballot ----


@pytest.mark.parametrize(
    ("width", "height"), SCAN_SIZES, ids=[f"{w}x{h}" for w, h in SCAN_SIZES]
)
def test_ac8_the_contrast_scan_finds_no_offender_with_the_banner_shown(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = make_page(browser, browser_name, width, height, touch=False)
    try:
        mock = open_spec_013_room(page, live_server, fx01_grid)
        send_grid_check_vote(page, mock)

        offenders = contrast_offenders(page)

        assert offenders == [], f"{width}x{height}: {offenders}"
    finally:
        close()


@pytest.mark.parametrize(
    ("width", "height"), SCAN_SIZES, ids=[f"{w}x{h}" for w, h in SCAN_SIZES]
)
def test_ac8_the_language_scan_finds_only_french_with_the_banner_shown(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = make_page(browser, browser_name, width, height, touch=False)
    try:
        mock = open_spec_013_room(page, live_server, fx01_grid)
        send_grid_check_vote(page, mock)

        assert page.evaluate("document.documentElement.lang") == "fr"
        texts = page.evaluate(LANGUAGE_SCAN_SCRIPT)
        assert isinstance(texts, list)
        data = {
            *EIGHT_NICKNAMES,
            *FX01_CLUES,
            MOCK_CODE,
            f"{live_server}/r/{MOCK_CODE}",
        }
        unknown = unknown_texts(texts, data)
        assert unknown == [], f"{width}x{height}: {unknown}"
    finally:
        close()
