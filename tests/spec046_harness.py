"""Shared setup of the tests of spec 046: catalogue and entry pages.

Pytest does not collect this module (its name does not start with `test_`). It
holds what more than one test file of spec 046 uses: the values of the spec, the
windows (desktop or touch, in Paris time), the mocked routes and the seeds of
"Test harness" (`BIG`, `ROOMS2`, `HIST2`, the account), the mocked room socket of
the entry pages, and the readers and checks of the frames, cards, rows, pills,
buttons and state lines. The tests are in these files, one per group of criteria:

- `test_spec_046_ac01_ac02_frames.py`: AC-1 and AC-2.
- `test_spec_046_ac03_account.py`: AC-3.
- `test_spec_046_ac04_ac06_filter_and_cards.py`: AC-4 to AC-6.
- `test_spec_046_ac07_ac08_marks_and_drawing.py`: AC-7 and AC-8.
- `test_spec_046_ac09_ac10_states.py`: AC-9 and AC-10.
- `test_spec_046_ac11_ac13_my_rooms_and_history.py`: AC-11 to AC-13.
- `test_spec_046_ac14_grid_page.py`: AC-14.
- `test_spec_046_ac15_ac17_entry_cards.py`: AC-15 to AC-17.
- `test_spec_046_ac18_ac19_not_found.py`: AC-18 and AC-19.
- `test_spec_046_ac20_ac21_opening.py`: AC-20 and AC-21.
- `test_spec_046_ac22_fit.py`: AC-22.
- `test_spec_046_ac23_scans_and_keys.py`: AC-23.

It reuses the harnesses of the specs it builds on: spec 043's readers of boxes,
labels, colours, borders, paddings and pictograms, its mocked room and its
snapshots; spec 032's summaries and identities; spec 029's history records;
spec 033's answers to a link request; spec 024's scans and outline check; spec
035's reference catalogue. Every helper that opens a page waits for the fonts
before it returns (spec 041's rule).

Tolerances ("Test harness"): 1 px for a position, 0.5 px for a size, 0.1 px for a
font size or a line height. Each comparison also allows 0.01 px more, so that a
sub-pixel rounding of the engine never fails a check that the spec's tolerance
meets.

The fixtures (`fx01_grid`, `catalogue`, `window`) are defined in each test file as
thin wrappers: a fixture imported from here would be an unused import for ruff.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator, Sequence
from datetime import date
from typing import Protocol

from playwright.sync_api import Browser, BrowserContext, Locator, Page, Route, expect

from fonts_ready import wait_for_fonts
from nock.catalogue import GridSummary
from nock.grid import Grid
from nock.protocol import ErrorCode
from nock.server import WEB_DIST_DIR
from spec013_harness import COARSE_POINTER_SCRIPT
from spec029_harness import (
    SOLVE_MS,
    XYZ_FINISHED_AT,
    device_record,
    history_value,
    old_record,
    xyz_record,
)
from spec032_harness import (
    ABC,
    ABC_TOKEN,
    XYZ,
    XYZ_TOKEN,
    abc_summary,
    identity_value,
    seed_storage,
    xyz_summary,
)
from spec033_harness import answer_link
from spec042_harness import Box, box_of, to_box
from spec043_harness import (
    CLUE_BG,
    LINE,
    MUTED,
    NAVY,
    READERS_JS,
    RED,
    WHITE,
    Reading,
    RoomMock,
    colour_matches,
    colour_of,
    error_frame,
    fr_format,
    fr_value,
    fx01_view,
    is_clear,
    padding_matches,
    padding_of,
    pictogram_of,
    players_up_to,
    px,
    set_timeouts,
    shown_test_ids,
    shows_pictogram,
    snapshot_frame,
    style_of,
)

Rgb = tuple[int, int, int]

# ---- Constants -------------------------------------------------------------------

PARIS = "Europe/Paris"
WAIT_TIMEOUT_MS = 10_000
FOLLOW_MS = 300  # "within 300 ms"
QUIET_MS = 300  # "sends no frame": nothing within this pause
POLL_MS = 50

WIDE = (1280, 720)
NARROW = (360, 740)
SIZES = [WIDE, NARROW]
WIDE_SIZES = [WIDE, (1024, 768)]
NARROW_SIZES = [NARROW, (768, 1024)]

ROOM_CODE = "ABC123"
UNKNOWN_CODE = "ZZZZZZ"
ROOM_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
EMAIL = "ana@example.org"
NOCK_MARK_POINTS = "0,0 10,0 10,14 5,10 0,14"
MIDDLE_DOT = "\N{MIDDLE DOT}"
SEP = MIDDLE_DOT  # how a `meta-sep` reads in a sequence (`sequence_of`)

# "Test harness": 1 px for a position, 0.5 px for a size, 0.1 px for a font size.
POSITION_TOLERANCE_PX = 1.0
SIZE_TOLERANCE_PX = 0.5
FONT_TOLERANCE_PX = 0.1
SUBPIXEL_PX = 0.01

PAGE_GREY: Rgb = (246, 247, 249)
THUMB: Rgb = (201, 210, 224)

# The window's top bar of the plain pages ("Page top bar").
WIDE_BAR_HEIGHT = 56.0
NARROW_BAR_HEIGHT = 54.0
WIDE_BAR_INSET = 16.0
NARROW_BAR_INSET = 14.0
# The entry frame's column ("Entry frame").
COLUMN_MAX_WIDTH = 420.0
WIDE_COLUMN_TOP = 48.0
NARROW_COLUMN_TOP = 20.0
NARROW_SIDE_PADDING = 16.0
CARD_GAP = 14.0

# The answers of the mocked routes ("Test harness").
GRIDS_ROUTE = "**/api/grids"
SUMMARIES_ROUTE = "**/api/rooms/summaries"
ACCOUNT_ROUTE = "**/api/account"
LINK_ROUTE = "**/api/account/link"
ACCOUNT_HISTORY_ROUTE = "**/api/account/history"
ACCOUNT_ROOMS_ROUTE = "**/api/account/rooms"
ROOMS_ROUTE = "**/api/rooms"
SOCKET_PATTERN = re.compile(r".*/api/rooms/ABC123/ws$")

SIGNED_OUT: dict[str, object] = {"signed_in": False, "email": None}
SIGNED_IN: dict[str, object] = {"signed_in": True, "email": EMAIL}

# The five refusals of AC-17: how the mock refuses the join, and the status.
REFUSALS = ["room_full", "room_locked", "removed", "close_4429", "close_4001"]
STATUS_OF_REFUSAL = {
    "room_full": "full",
    "room_locked": "locked",
    "removed": "removed",
    "close_4429": "throttled",
    "close_4001": "replaced",
}


def size_ids(sizes: Sequence[tuple[int, int]]) -> list[str]:
    return [f"{width}x{height}" for width, height in sizes]


def is_wide(width: int, height: int) -> bool:
    """A wide window of "Terms": landscape, at least 900 px wide, over 500 px high."""
    return width > height and width >= 900 and height > 500


# ---- Comparisons -------------------------------------------------------------------


def near(actual: float, expected: float, tolerance: float) -> bool:
    return abs(actual - expected) <= tolerance + SUBPIXEL_PX


def same_position(actual: float, expected: float) -> bool:
    return near(actual, expected, POSITION_TOLERANCE_PX)


def same_size(actual: float, expected: float) -> bool:
    return near(actual, expected, SIZE_TOLERANCE_PX)


def same_font(actual: float, expected: float) -> bool:
    return near(actual, expected, FONT_TOLERANCE_PX)


def inside(inner: Box, outer: Box) -> bool:
    """Tell whether `inner` lies inside `outer`, with 1 px of tolerance."""
    tolerance = POSITION_TOLERANCE_PX + SUBPIXEL_PX
    return (
        inner.left >= outer.left - tolerance
        and inner.top >= outer.top - tolerance
        and inner.right <= outer.right + tolerance
        and inner.bottom <= outer.bottom + tolerance
    )


def inside_horizontally(inner: Box, outer: Box) -> bool:
    tolerance = POSITION_TOLERANCE_PX + SUBPIXEL_PX
    return (
        inner.left >= outer.left - tolerance and inner.right <= outer.right + tolerance
    )


# ---- Windows -----------------------------------------------------------------------


class OpenWindow(Protocol):
    """The `window` fixtures: open a page of a size, desktop or touch."""

    def __call__(self, width: int, height: int, touch: bool = False) -> Page: ...


def new_context(
    browser: Browser, browser_name: str, width: int, height: int, touch: bool
) -> BrowserContext:
    """A desktop or touch context in Paris time (spec 019's touch context)."""
    viewport = {"width": width, "height": height}
    if not touch:
        return browser.new_context(viewport=viewport, timezone_id=PARIS)
    if browser_name == "firefox":
        context = browser.new_context(
            viewport=viewport, timezone_id=PARIS, has_touch=True, device_scale_factor=2
        )
    else:
        context = browser.new_context(
            viewport=viewport,
            timezone_id=PARIS,
            has_touch=True,
            is_mobile=True,
            device_scale_factor=2,
        )
    if browser_name != "chromium":
        context.add_init_script(COARSE_POINTER_SCRIPT)
    return context


def window_opener(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Yield `open_window(width, height, touch=False)`; close its contexts after."""
    contexts: list[BrowserContext] = []

    def open_window(width: int, height: int, touch: bool = False) -> Page:
        context = new_context(browser, browser_name, width, height, touch)
        contexts.append(context)
        page = context.new_page()
        set_timeouts(page)
        return page

    yield open_window
    for context in contexts:
        context.close()


def window_size(page: Page) -> tuple[float, float]:
    size = page.evaluate("() => [innerWidth, innerHeight]")
    assert isinstance(size, list), size
    return float(size[0]), float(size[1])


def settled[T](page: Page, read: Callable[[], T], accept: Callable[[T], bool]) -> T:
    """Read a value until `accept` takes it, up to 300 ms ("within 300 ms").

    Returns:
        The first reading that `accept` takes, else the last reading; the caller
        asserts on it.
    """
    value = read()
    waited_ms = 0
    while not accept(value) and waited_ms < FOLLOW_MS:
        page.wait_for_timeout(POLL_MS)
        waited_ms += POLL_MS
        value = read()
    return value


# ---- Mocked routes ---------------------------------------------------------------


def parsed_body(route: Route) -> object:
    data = route.request.post_data
    if data is None:
        return None
    return json.loads(data)


def fulfil_json(route: Route, status: int, body: object) -> None:
    route.fulfill(status=status, content_type="application/json", body=json.dumps(body))


def answer_json(page: Page, pattern: str, status: int, body: object) -> list[object]:
    """Answer every request of `pattern` with `body` as JSON.

    Returns:
        The list that collects each request's parsed body (None without one).
    """
    bodies: list[object] = []

    def handle(route: Route) -> None:
        bodies.append(parsed_body(route))
        fulfil_json(route, status, body)

    page.route(pattern, handle)
    return bodies


class HeldRoute:
    """A route whose requests wait until the test releases them ("delayed")."""

    def __init__(self, page: Page, pattern: str) -> None:
        self.routes: list[Route] = []
        page.route(pattern, self.keep)

    def keep(self, route: Route) -> None:
        """Keep a request without answering it (`page.route`'s handler)."""
        self.routes.append(route)

    def release(self, status: int, body: object) -> None:
        """Answer every request kept so far with `body`, as JSON."""
        for route in self.routes:
            fulfil_json(route, status, body)


def accounts_on(
    page: Page, status: dict[str, object], link_status: int = 202
) -> list[object]:
    """Answer the account routes: accounts on, signed out or signed in.

    `GET /api/account` answers `status` with 200; `POST /api/account/link` the
    status `link_status` with spec 033's body for it; `GET /api/account/history`
    and `GET /api/account/rooms` an empty list.

    Returns:
        The list that collects the parsed body of each link request.
    """
    link_bodies: list[object] = []

    def link(route: Route) -> None:
        link_bodies.append(parsed_body(route))
        answer_link(route, link_status)

    answer_json(page, ACCOUNT_ROUTE, 200, status)
    page.route(LINK_ROUTE, link)
    answer_json(page, ACCOUNT_HISTORY_ROUTE, 200, [])
    answer_json(page, ACCOUNT_ROOMS_ROUTE, 200, [])
    return link_bodies


def big_grids() -> list[object]:
    """`BIG`: grid 12 (13 by 17, force 3, 54 words) and grid 2 (5 by 5, force 2)."""
    big = GridSummary(
        number=12,
        published_on=date(2026, 10, 10),
        force=3,
        width=13,
        height=17,
        word_count=54,
    )
    small = GridSummary(
        number=2,
        published_on=date(2026, 10, 1),
        force=2,
        width=5,
        height=5,
        word_count=8,
    )
    return [big.model_dump(mode="json"), small.model_dump(mode="json")]


def answer_big(page: Page) -> None:
    answer_json(page, GRIDS_ROUTE, 200, big_grids())


def fail_play(page: Page) -> list[object]:
    """Answer `POST /api/rooms` with 500; return the bodies of its requests."""
    return answer_json(page, ROOMS_ROUTE, 500, {"detail": "Internal Server Error"})


def long_names(count: int) -> list[str]:
    """`count` different nicknames of 20 characters each."""
    names: list[str] = []
    for number in range(1, count + 1):
        prefix = f"Joueur{number}"
        names.append(prefix + "x" * (20 - len(prefix)))
    return names


def seed_rooms2(page: Page, players: list[str] | None = None) -> list[object]:
    """`ROOMS2`: the identities of both rooms seeded and their two summaries.

    Args:
        page: A fresh page.
        players: The players of `XYZ789` (`Ana` and `Bob` by default).

    Returns:
        The bodies of the summaries requests.
    """
    seed_rooms2_identities(page)
    body = [xyz_summary(players=players), abc_summary()]
    return answer_json(page, SUMMARIES_ROUTE, 200, body)


def seed_rooms2_identities(page: Page) -> None:
    """The identities of `XYZ789` and `ABC234`, seeded before the first load."""
    seed_storage(
        page,
        {
            f"nock.identity.{XYZ}": identity_value(XYZ_TOKEN),
            f"nock.identity.{ABC}": identity_value(ABC_TOKEN),
        },
    )


def seed_hist2(page: Page, teammates: list[str] | None = None) -> None:
    """`HIST2`: the records of `XYZ789` and `QQQQQQ` (spec 029 AC-2) seeded.

    Args:
        page: A fresh page.
        teammates: The team-mates of `XYZ789` (`Bob` and `Cy` by default).
    """
    first = xyz_record()
    if teammates is not None:
        first = device_record(XYZ, 2, XYZ_FINISHED_AT, SOLVE_MS, teammates)
    seed_storage(page, {"nock.history": history_value([first, old_record()])})


def seed_progress(page: Page) -> None:
    """`nock.progress` = `{"1": "started", "2": "finished"}`."""
    progress = json.dumps({"1": "started", "2": "finished"})
    seed_storage(page, {"nock.progress": progress})


# ---- Pages ---------------------------------------------------------------------


def open_catalogue(page: Page, base_url: str) -> None:
    """Open `/` and wait until `catalogue-page` is `ready` and its fonts load."""
    page.goto(f"{base_url}/")
    expect(page.get_by_test_id("catalogue-page")).to_have_attribute(
        "data-state", "ready", timeout=WAIT_TIMEOUT_MS
    )
    wait_for_fonts(page)


def open_catalogue_loading(page: Page, base_url: str) -> None:
    """Open `/` and wait until `catalogue-page` shows (any state)."""
    page.goto(f"{base_url}/")
    expect(page.get_by_test_id("catalogue-page")).to_be_visible(timeout=WAIT_TIMEOUT_MS)
    wait_for_fonts(page)


def item_of(page: Page, number: int) -> Locator:
    return page.locator(f'[data-testid="catalogue-item"][data-number="{number}"]')


def my_room_of(page: Page, code: str) -> Locator:
    return page.locator(f'[data-testid="my-room"][data-code="{code}"]')


def history_item_of(page: Page, code: str) -> Locator:
    return page.locator(f'[data-testid="history-item"][data-code="{code}"]')


def expect_my_rooms_ready(page: Page, count: int) -> None:
    expect(page.get_by_test_id("my-rooms")).to_have_attribute(
        "data-state", "ready", timeout=WAIT_TIMEOUT_MS
    )
    expect(page.get_by_test_id("my-room")).to_have_count(count)
    wait_for_fonts(page)


def expect_history_count(page: Page, count: int) -> None:
    expect(page.get_by_test_id("history-item")).to_have_count(
        count, timeout=WAIT_TIMEOUT_MS
    )
    wait_for_fonts(page)


def open_unknown_room(page: Page, base_url: str) -> None:
    """Open `/r/ZZZZZZ` on an empty registry and wait for `not_found`."""
    page.goto(f"{base_url}/r/{UNKNOWN_CODE}")
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-status", "not_found", timeout=WAIT_TIMEOUT_MS
    )
    wait_for_fonts(page)


def route_index(page: Page) -> None:
    """Answer `GET /nowhere` with the built `web/dist/index.html` (AC-19)."""
    index_html = (WEB_DIST_DIR / "index.html").read_text(encoding="utf-8")

    def answer(route: Route) -> None:
        route.fulfill(status=200, content_type="text/html", body=index_html)

    page.route("**/nowhere", answer)


def open_nowhere(page: Page, base_url: str) -> None:
    route_index(page)
    page.goto(f"{base_url}/nowhere")
    expect(page.get_by_test_id("not-found-page")).to_be_visible(timeout=WAIT_TIMEOUT_MS)
    wait_for_fonts(page)


# ---- The mocked room socket -----------------------------------------------------


def seed_identity(page: Page) -> None:
    """Spec 012's case a: `nock.identity.ABC123` stored."""
    seed_storage(
        page, {f"nock.identity.{ROOM_CODE}": identity_value(ROOM_TOKEN, nickname="ANA")}
    )


def seed_room_record(page: Page) -> None:
    """Spec 012's case b: `nock.room.ABC123` = `{"grid": 1, "selection": null}`."""
    record = json.dumps({"grid": 1, "selection": None})
    seed_storage(page, {f"nock.room.{ROOM_CODE}": record})


def open_mocked_room(page: Page, base_url: str) -> RoomMock:
    """Route the socket of `/r/ABC123` to a mock and open the page."""
    mock = RoomMock()
    page.route_web_socket(SOCKET_PATTERN, mock.handle)
    page.goto(f"{base_url}/r/{ROOM_CODE}")
    return mock


def expect_status(page: Page, status: str) -> None:
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-status", status, timeout=WAIT_TIMEOUT_MS
    )


def wait_for_join(page: Page, mock: RoomMock) -> None:
    waited_ms = 0
    while not mock.has_join_after(0):
        assert waited_ms < WAIT_TIMEOUT_MS, "the page sent no join"
        page.wait_for_timeout(POLL_MS)
        waited_ms += POLL_MS


def open_nickname_card(page: Page, base_url: str) -> RoomMock:
    """Spec 012's case c (nothing seeded): wait for `nickname` and the fonts."""
    mock = open_mocked_room(page, base_url)
    expect_status(page, "nickname")
    expect(page.get_by_test_id("nickname-form")).to_be_visible()
    wait_for_fonts(page)
    return mock


def show_nickname_error(page: Page) -> None:
    """Type `A` and submit: spec 012 refuses it with `nickname-error`.

    Fix after #40's CI (Firefox, 2026-10-23): `nickname-error` once never showed,
    most likely because the submit saw an empty field and the page joined with
    the default nickname. The field must now hold `A` before the click, and a
    page that leaves the `nickname` status instead of refusing fails with a
    message that says so, rather than a bare timeout.
    """
    field = page.get_by_test_id("nickname-input")
    field.fill("A")
    expect(field).to_have_value("A")
    page.get_by_test_id("nickname-submit").click()
    error = page.get_by_test_id("nickname-error")
    room = page.get_by_test_id("room-page")
    waited_ms = 0
    while not error.is_visible():
        status = room.get_attribute("data-status")
        if status != "nickname":
            held = field.input_value() if field.count() == 1 else "no field"
            raise AssertionError(
                f"the submit of `A` was not refused: data-status became {status!r}"
                f" (the field holds {held!r}); the page most likely joined with"
                " the default nickname"
            )
        if waited_ms >= WAIT_TIMEOUT_MS:
            raise AssertionError("nickname-error did not show after submitting `A`")
        page.wait_for_timeout(POLL_MS)
        waited_ms += POLL_MS
    wait_for_fonts(page)


def open_opening(page: Page, base_url: str) -> RoomMock:
    """Case a with a mock that never answers the join: wait for `joining`."""
    seed_identity(page)
    mock = open_mocked_room(page, base_url)
    expect_status(page, "joining")
    wait_for_join(page, mock)
    expect(page.get_by_test_id("room-topbar")).to_be_visible()
    wait_for_fonts(page)
    return mock


def refuse(mock: RoomMock, refusal: str) -> None:
    """Refuse the join as one of AC-17's five runs (`REFUSALS`)."""
    if refusal == "close_4429":
        mock.close(4429)
    elif refusal == "close_4001":
        mock.close(4001)
    else:
        mock.send(error_frame(ErrorCode(refusal)))


def open_status_card(page: Page, base_url: str, refusal: str) -> RoomMock:
    """Case a, the join refused as `refusal`: wait for its status card."""
    seed_identity(page)
    mock = open_mocked_room(page, base_url)
    wait_for_join(page, mock)
    refuse(mock, refusal)
    expect_status(page, STATUS_OF_REFUSAL[refusal])
    expect(page.get_by_test_id("entry-card")).to_be_visible()
    wait_for_fonts(page)
    return mock


def fx01_snapshot(grid: Grid) -> str:
    """A FX-01 snapshot for `p1` (`ANA`, host), seq 5."""
    return snapshot_frame(fx01_view(grid), players_up_to(1))


def frames_after(page: Page, mock: RoomMock, action: Callable[[], object]) -> list[str]:
    """Do `action`, wait QUIET_MS, and return the frames sent meanwhile (no pings)."""
    before = len(mock.frames_without_pings())
    action()
    page.wait_for_timeout(QUIET_MS)
    return mock.frames_without_pings()[before:]


# ---- Readers ---------------------------------------------------------------------

# The element children of an element that show (a box), in order. A visually
# hidden child (class `visually-hidden`, spec 043) does not show.
CHILDREN_SCRIPT = r"""
element => {
  const found = [];
  for (const child of element.children) {
    if (child.getClientRects().length === 0
        || child.classList.contains('visually-hidden')) {
      continue;
    }
    const rect = child.getBoundingClientRect();
    found.push({
      testId: child.getAttribute('data-testid'),
      tag: child.tagName,
      box: [rect.left, rect.top, rect.right, rect.bottom],
    });
  }
  return found;
}
"""

# An element's content box: its box less its borders and paddings.
CONTENT_BOX_SCRIPT = r"""
element => {
  const rect = element.getBoundingClientRect();
  const style = getComputedStyle(element);
  const left = parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft);
  const right = parseFloat(style.borderRightWidth) + parseFloat(style.paddingRight);
  const top = parseFloat(style.borderTopWidth) + parseFloat(style.paddingTop);
  const bottom = parseFloat(style.borderBottomWidth)
    + parseFloat(style.paddingBottom);
  return [rect.left + left, rect.top + top, rect.right - right,
    rect.bottom - bottom];
}
"""

# What an element holds, in order: each text (trimmed), `·` for a `meta-sep`, and
# `#<test id>` for another element with a test id; an element without a test id
# is read through.
SEQUENCE_SCRIPT = r"""
element => {
  const found = [];
  function read(node) {
    for (const child of node.childNodes) {
      if (child.nodeType === Node.TEXT_NODE) {
        const text = child.textContent.replace(/\s+/g, ' ').trim();
        if (text !== '') {
          found.push(text);
        }
        continue;
      }
      if (child.nodeType !== Node.ELEMENT_NODE) {
        continue;
      }
      const testId = child.getAttribute('data-testid');
      if (testId === 'meta-sep') {
        found.push('·');
      } else if (testId !== null) {
        found.push('#' + testId);
      } else {
        read(child);
      }
    }
  }
  read(element);
  return found;
}
"""

SHAPES_SCRIPT = "svg => {\n" + READERS_JS + "\nreturn svgOf(svg);\n}"


def children_of(locator: Locator) -> list[Reading]:
    """The element children of an element that show: test id, tag and box.

    A child with the class `visually-hidden` (spec 043) is left out: it shows
    nothing (`room-status` beside the nickname card).
    """
    found = locator.evaluate(CHILDREN_SCRIPT)
    assert isinstance(found, list), found
    return found


def child_ids(locator: Locator) -> list[str | None]:
    ids: list[str | None] = []
    for child in children_of(locator):
        test_id = child["testId"]
        ids.append(None if test_id is None else str(test_id))
    return ids


def child_tags(locator: Locator) -> list[str]:
    return [str(child["tag"]) for child in children_of(locator)]


def content_box(locator: Locator) -> Box:
    return to_box(locator.evaluate(CONTENT_BOX_SCRIPT))


def sequence_of(locator: Locator) -> list[str]:
    """What an element holds, in order (see `SEQUENCE_SCRIPT`)."""
    found = locator.evaluate(SEQUENCE_SCRIPT)
    assert isinstance(found, list), found
    return [str(item) for item in found]


def svg_of(locator: Locator) -> Reading:
    """An `svg`'s viewBox, box and shapes (spec 042's `svgOf`)."""
    found = locator.evaluate(SHAPES_SCRIPT)
    assert isinstance(found, dict), found
    return found


def font_size_of(locator: Locator) -> float:
    return px(style_of(locator, "fontSize"))


def classes_of(locator: Locator) -> list[str]:
    value = locator.get_attribute("class")
    return [] if value is None else value.split()


def is_visually_hidden(locator: Locator) -> bool:
    return "visually-hidden" in classes_of(locator)


def no_progress_or_animation(page: Page) -> list[str]:
    """How a page breaks "no spinner, no animation" (AC-9, AC-20)."""
    found = page.evaluate(
        "() => [document.querySelectorAll('[role=\"progressbar\"]').length,"
        " document.getAnimations().length]"
    )
    assert isinstance(found, list), found
    problems: list[str] = []
    if found[0] != 0:
        problems.append(f"{found[0]} elements with role=progressbar")
    if found[1] != 0:
        problems.append(f"{found[1]} animations")
    return problems


# ---- Checks of the looks ---------------------------------------------------------


def colour_problem(locator: Locator, name: str, prop: str, expected: Rgb) -> list[str]:
    colour = colour_of(locator, prop)
    if colour_matches(colour, expected):
        return []
    return [f"{name}: {prop} {colour}, not {expected}"]


def font_problems(
    locator: Locator,
    name: str,
    size: float,
    weight: str | None = None,
    colour: Rgb | None = None,
) -> list[str]:
    """How an element's font size, weight and colour differ from the spec's."""
    problems: list[str] = []
    actual = font_size_of(locator)
    if not same_font(actual, size):
        problems.append(f"{name}: font-size {actual}, not {size}")
    if weight is not None and style_of(locator, "fontWeight") != weight:
        problems.append(f"{name}: font-weight {style_of(locator, 'fontWeight')}")
    if colour is not None:
        problems.extend(colour_problem(locator, name, "color", colour))
    return problems


def border_side_problems(
    locator: Locator, name: str, side: str, colour: Rgb, width: str = "1px"
) -> list[str]:
    """How one border side (`Top`, `Right`, `Bottom`, `Left`) differs."""
    problems: list[str] = []
    if style_of(locator, f"border{side}Width") != width:
        problems.append(f"{name}: border-{side} width")
    if style_of(locator, f"border{side}Style") != "solid":
        problems.append(f"{name}: border-{side} style")
    problems.extend(colour_problem(locator, name, f"border{side}Color", colour))
    return problems


def border_problems(locator: Locator, name: str, colour: Rgb) -> list[str]:
    """How the four border sides differ from 1 px solid `colour`."""
    problems: list[str] = []
    for side in ("Top", "Right", "Bottom", "Left"):
        problems.extend(border_side_problems(locator, name, side, colour))
    return problems


def box_look_problems(
    locator: Locator, name: str, radius: str, padding: str
) -> list[str]:
    """White, 1 px solid `--nock-line`, `radius` and `padding` (card, row)."""
    problems = colour_problem(locator, name, "backgroundColor", WHITE)
    problems.extend(border_problems(locator, name, LINE))
    if style_of(locator, "borderTopLeftRadius") != radius:
        problems.append(f"{name}: radius {style_of(locator, 'borderTopLeftRadius')}")
    if not padding_matches(locator, padding):
        problems.append(f"{name}: padding {padding_of(locator)}")
    return problems


def card_problems(locator: Locator) -> list[str]:
    """The card of "Entry frame": radius 10 px, padding 18 px 16 px."""
    return box_look_problems(locator, "card", "10px", "18px 16px")


def row_problems(locator: Locator) -> list[str]:
    """A list row (`my-room`, `history-item`): radius 8 px, padding 12 px 14 px."""
    return box_look_problems(locator, "row", "8px", "12px 14px")


def card_title_problems(locator: Locator) -> list[str]:
    """The card's title: 700, 20 px (1.25rem), navy."""
    return font_problems(locator, "title", 20.0, "700", NAVY)


def section_heading_problems(locator: Locator) -> list[str]:
    """A catalogue section heading: 700, 18.4 px (1.15rem), navy."""
    return font_problems(locator, "section heading", 18.4, "700", NAVY)


def error_line_problems(locator: Locator) -> list[str]:
    """The error line of `_design.md` section 11: red, 500, 13.6 px."""
    return font_problems(locator, "error line", 13.6, "500", RED)


def muted_line_problems(locator: Locator) -> list[str]:
    """A state line, muted (400 1rem/1.5, `--nock-muted`)."""
    problems = font_problems(locator, "state line", 16.0, "400", MUTED)
    line_height = style_of(locator, "lineHeight")
    if not line_height.endswith("px") or not same_font(px(line_height), 24.0):
        problems.append(f"state line: line-height {line_height}")
    return problems


def pill_problems(locator: Locator, background: Rgb, colour: Rgb) -> list[str]:
    """A status pill: radius 12 px, padding 3 px 9px, 600 12 px, its colours."""
    problems = font_problems(locator, "pill", 12.0, "600", colour)
    problems.extend(colour_problem(locator, "pill", "backgroundColor", background))
    if style_of(locator, "borderTopLeftRadius") != "12px":
        problems.append(f"pill: radius {style_of(locator, 'borderTopLeftRadius')}")
    if not padding_matches(locator, "3px 9px"):
        problems.append(f"pill: padding {padding_of(locator)}")
    return problems


def button_colour_problems(locator: Locator, variant: str) -> list[str]:
    """The colours of spec 041 AC-10 (`primary`, `secondary`) or AC-11 (`disabled`).

    Primary: navy background, white text, a border with alpha 0. Secondary:
    white background, navy text and border. Disabled: clue blue-grey
    background, muted text, line-grey border.
    """
    expected: dict[str, tuple[Rgb, Rgb, Rgb | None]] = {
        "primary": (NAVY, WHITE, None),
        "secondary": (WHITE, NAVY, NAVY),
        "disabled": (CLUE_BG, MUTED, LINE),
    }
    background, text, border = expected[variant]
    problems = colour_problem(locator, variant, "backgroundColor", background)
    problems.extend(colour_problem(locator, variant, "color", text))
    if border is None:
        if not is_clear(colour_of(locator, "borderTopColor")):
            problems.append(f"{variant}: border {colour_of(locator, 'borderTopColor')}")
    else:
        problems.extend(colour_problem(locator, variant, "borderTopColor", border))
    return problems


def separator_problems(locator: Locator) -> list[str]:
    """How the `meta-sep` elements inside `locator` differ from the pictogram «·»."""
    separators = locator.get_by_test_id("meta-sep")
    problems: list[str] = []
    for index in range(separators.count()):
        reading = pictogram_of(separators.nth(index))
        if not shows_pictogram(reading, MIDDLE_DOT):
            problems.append(f"meta-sep {index}: {reading}")
        if reading["ariaHidden"] != "true" or reading["textNodes"] != 0:
            problems.append(f"meta-sep {index} is no empty aria-hidden element")
    return problems


# ---- Checks of the frames --------------------------------------------------------


def page_topbar_problems(page: Page, height: float, inset: float) -> list[str]:
    """`page-topbar`: a white `header` across the top, its brand `inset` px in."""
    width, _ = window_size(page)
    bar = page.get_by_test_id("page-topbar")
    problems: list[str] = []
    if bar.count() != 1:
        return [f"{bar.count()} page-topbar elements"]
    tag = bar.evaluate("element => element.tagName")
    if tag != "HEADER":
        problems.append(f"page-topbar is a {tag}")
    box = box_of(bar)
    if not (same_position(box.left, 0.0) and same_position(box.top, 0.0)):
        problems.append(f"page-topbar at {box}")
    if not same_size(box.width, width) or not same_size(box.height, height):
        problems.append(f"page-topbar {box.width} by {box.height}, not {height} high")
    problems.extend(colour_problem(bar, "page-topbar", "backgroundColor", WHITE))
    problems.extend(border_side_problems(bar, "page-topbar", "Bottom", LINE))
    brand = bar.get_by_test_id("topbar-brand")
    if brand.count() != 1:
        problems.append(f"{brand.count()} topbar-brand in page-topbar")
    elif not same_position(box_of(brand).left - box.left, inset):
        problems.append(f"topbar-brand {box_of(brand).left - box.left} px in")
    return problems


def entry_frame_problems(page: Page) -> list[str]:
    """The entry frame of AC-1 for this window: bar, grey body, centred column."""
    width, height = window_size(page)
    wide = is_wide(int(width), int(height))
    bar_height = WIDE_BAR_HEIGHT if wide else NARROW_BAR_HEIGHT
    inset = WIDE_BAR_INSET if wide else NARROW_BAR_INSET
    problems = page_topbar_problems(page, bar_height, inset)
    body = page.get_by_test_id("page-body")
    column = page.get_by_test_id("page-column")
    if body.count() != 1 or column.count() != 1:
        return [*problems, f"{body.count()} page-body, {column.count()} page-column"]
    bar_box = box_of(page.get_by_test_id("page-topbar"))
    body_box = box_of(body)
    problems.extend(colour_problem(body, "page-body", "backgroundColor", PAGE_GREY))
    if not same_position(body_box.top, bar_box.bottom):
        problems.append(f"page-body top {body_box.top}, bar bottom {bar_box.bottom}")
    if not same_position(body_box.bottom, height):
        problems.append(f"page-body bottom {body_box.bottom}, window {height}")
    column_box = box_of(column)
    expected_width = COLUMN_MAX_WIDTH
    if not wide:
        expected_width = min(COLUMN_MAX_WIDTH, width - 2 * NARROW_SIDE_PADDING)
    if not same_size(column_box.width, expected_width):
        problems.append(f"page-column {column_box.width} wide, not {expected_width}")
    if not same_position(column_box.centre_x, width / 2):
        problems.append(f"page-column centre {column_box.centre_x}, not {width / 2}")
    top_gap = WIDE_COLUMN_TOP if wide else NARROW_COLUMN_TOP
    if not same_position(column_box.top - bar_box.bottom, top_gap):
        problems.append(f"page-column {column_box.top - bar_box.bottom} px down")
    return problems


def code_line_problems(page: Page, code: str) -> list[str]:
    """The room code line: `page-column`'s first child is the room's `h1`."""
    column = page.get_by_test_id("page-column")
    children = children_of(column)
    if len(children) < 2 or children[0]["tag"] != "H1":
        return [f"page-column's children: {children}"]
    heading = column.locator(":scope > h1")
    problems: list[str] = []
    text = heading.inner_text().strip()
    expected = fr_format("room.heading", code=code)
    if text != expected:
        problems.append(f"code line {text!r}, not {expected!r}")
    problems.extend(font_problems(heading, "code line", 13.6, "600", MUTED))
    card_top = to_box(children[1]["box"]).top
    if not same_position(card_top - box_of(heading).bottom, CARD_GAP):
        problems.append(f"card {card_top - box_of(heading).bottom} px under h1")
    return problems


def entry_home_problems(page: Page, variant: str) -> list[str]:
    """`entry-home`: an `A` to `/` with `tabindex="0"`, « Voir les grilles »."""
    link = page.get_by_test_id("entry-home")
    if link.count() != 1:
        return [f"{link.count()} entry-home elements"]
    problems: list[str] = []
    if link.evaluate("element => element.tagName") != "A":
        problems.append("entry-home is not an A")
    if link.get_attribute("href") != "/":
        problems.append(f"entry-home href {link.get_attribute('href')}")
    if link.get_attribute("tabindex") != "0":
        problems.append(f"entry-home tabindex {link.get_attribute('tabindex')}")
    if link.inner_text().strip() != fr_value("share.home"):
        problems.append(f"entry-home reads {link.inner_text()!r}")
    problems.extend(button_colour_problems(link, variant))
    return problems


def status_card_problems(page: Page, status: str) -> list[str]:
    """AC-17's status card: `room-status` as its title, `entry-home` last."""
    card = page.get_by_test_id("entry-card")
    if card.count() != 1:
        return [f"{card.count()} entry-card elements"]
    problems = card_problems(card)
    ids = child_ids(card)
    if not ids or ids[0] != "room-status":
        problems.append(f"entry-card's children: {ids}")
    if not ids or ids[-1] != "entry-home":
        problems.append(f"entry-card's last child: {ids}")
    room_status = page.get_by_test_id("room-status")
    text = room_status.inner_text().strip()
    if text != fr_value(f"room.status.{status}"):
        problems.append(f"room-status reads {text!r}")
    problems.extend(card_title_problems(room_status))
    if is_visually_hidden(room_status):
        problems.append("room-status is visually hidden")
    return problems


def topbar_ids(page: Page, test_id: str = "room-topbar") -> list[str]:
    """The test-id'd elements of a top bar that show, outermost first."""
    return shown_test_ids(page.get_by_test_id(test_id))
