"""Tests of spec 022, AC-17: while the vote banner shows, it is drawn above an open
chat panel, which stays open and usable under it and is fully visible again once
the banner has gone.

Browser with spec 025's mocked socket. The setup is AC-15's except that `p2` is
host: 8 players, 100 feed items, (3, 1) tapped, help mode `free`, and 100 lines
from `p2` in the snapshot's `chat`, with the panel open and the picker closed. One
page per window size of spec 006 AC-5 and per context (desktop, touch) runs the
two runs of the criterion one after the other, each ending with its vote's result:
"Typing" (`ok` typed in `chat-input`, which keeps the focus, then `Enter`) and
"List focus" (`Shift+Tab` from `chat-input`, so that `chat-list` has the focus).
The second run starts once the first banner has left the page.

"The five points" of an element are the centre of its bounding box and its four
corners, each moved 2 px inwards on both axes. On a rounded corner (the Salon's
sheet has 14 px corners, spec 043) the corner point is first moved onto the
rounded edge's diagonal, `r * (1 - 1 / sqrt 2)` px on each axis, then 2 px more,
so that it lies inside the shape the element draws.

Refined by spec 043 (the design's room layout): the open chat panel is the Salon
on its Discussion tab (the harness's `open_panel`), and the panel's box in the
checks is `salon`'s; in the column layout the banner and the Salon do not overlap,
and the checks hold as written.

Refined by spec 047 (the design's room overlays): the banner leaves within 300 ms
of the `vote_closed`, and the closed vote adds a `vote` line to the stream, which
moves a list that was at its end to its new end; so after the vote the test
checks the panel's points and box, the window's scroll and the focus, and no
longer the list's `scrollTop`, which the criterion does not read after the vote.

The shared setup is in `spec022_harness`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, NamedTuple

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import ChatMessage, CheckResult, GridTarget, PlayerView, VoteOutcome
from spec022_harness import (
    SETTLE_MS,
    expect_seq,
    frames_after,
    open_chat_room,
    open_panel,
)
from spec024_harness import cell_at, grid_from_text, open_context_page, player_view
from spec025_harness import GRID_CHECK, MockRoomSocket, closed, opened

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
CONTEXTS = ["desktop", "touch"]
EIGHT_NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve", "Fay", "Gus", "Hal"]
FEED_ITEMS = 100
CHAT_LINES = 100
FIRST_CHAT_SEQ = 6
SNAPSHOT_SEQ = FIRST_CHAT_SEQ + CHAT_LINES - 1  # the snapshot holds lines 6 to 105
LAST_FEED_SEQ = SNAPSHOT_SEQ + FEED_ITEMS
EIGHT_VOTERS = 8
BANNER_STAYS_MS = 1000  # "and again 1,000 ms later"
BANNER_GONE_MS = 5500  # an upper bound; spec 047: gone within 300 ms
TOLERANCE_PX = 1.0

# The measures of the page that the criterion compares before and during the vote.
STATE_SCRIPT = r"""
() => {
  const panel = document.querySelector('[data-testid="salon"]');
  const list = document.querySelector('[data-testid="chat-list"]');
  const active = document.activeElement;
  const box = panel === null ? null : panel.getBoundingClientRect();
  return {
    panelBox: box === null ? null : [box.left, box.top, box.width, box.height],
    scrollTop: list === null ? null : list.scrollTop,
    scrollX: window.scrollX,
    scrollY: window.scrollY,
    active: active === null
      ? null : (active.getAttribute('data-testid') || active.tagName),
  };
}
"""

# For each of the five points of an element: whether `elementFromPoint` returns
# the element or one of its descendants, and what it returns otherwise.
POINTS_SCRIPT = r"""
testId => {
  const element = document.querySelector(`[data-testid="${testId}"]`);
  if (element === null) {
    return [{point: 'none', inside: false, hit: 'no element'}];
  }
  const box = element.getBoundingClientRect();
  const style = getComputedStyle(element);
  // 2 px inwards from the corner of the shape: a rounded corner of radius r
  // takes r * (1 - 1 / sqrt 2) more on each axis.
  const inset = radius => 2 + (parseFloat(radius) || 0) * (1 - Math.SQRT1_2);
  const topLeft = inset(style.borderTopLeftRadius);
  const topRight = inset(style.borderTopRightRadius);
  const bottomLeft = inset(style.borderBottomLeftRadius);
  const bottomRight = inset(style.borderBottomRightRadius);
  const points = [
    ['centre', box.left + box.width / 2, box.top + box.height / 2],
    ['top left', box.left + topLeft, box.top + topLeft],
    ['top right', box.right - topRight, box.top + topRight],
    ['bottom left', box.left + bottomLeft, box.bottom - bottomLeft],
    ['bottom right', box.right - bottomRight, box.bottom - bottomRight],
  ];
  const found = [];
  for (const [name, x, y] of points) {
    const hit = document.elementFromPoint(x, y);
    found.push({
      point: name,
      inside: hit !== null && element.contains(hit),
      hit: hit === null ? null : (hit.getAttribute('data-testid') || hit.tagName),
    });
  }
  return found;
}
"""

LIST_SCROLLS_SCRIPT = r"""
() => {
  const list = document.querySelector('[data-testid="chat-list"]');
  const overflow = getComputedStyle(list).overflowY;
  return list.scrollHeight > list.clientHeight
    && (overflow === 'auto' || overflow === 'scroll');
}
"""


def size_ids() -> list[str]:
    return [f"{width}x{height}" for width, height in WINDOW_SIZES]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def eight_players_with_p2_host() -> list[PlayerView]:
    players: list[PlayerView] = []
    for number in range(1, 9):
        nickname = EIGHT_NICKNAMES[number - 1]
        is_host = number == 2
        players.append(player_view(f"p{number}", nickname, number - 1, is_host=is_host))
    return players


def check_frame(seq: int) -> str:
    event = CheckResult(
        seq=seq, player_id="p2", target=GridTarget(), correct=(), wrong=()
    )
    return event.model_dump_json()


def snapshot_chat() -> list[ChatMessage]:
    """The 100 lines from `p2` of the snapshot, seq 6 to 105."""
    lines: list[ChatMessage] = []
    for seq in range(FIRST_CHAT_SEQ, SNAPSHOT_SEQ + 1):
        lines.append(ChatMessage(seq=seq, player_id="p2", text=f"Ligne {seq}"))
    return lines


def open_scene(
    browser: Browser,
    browser_name: str,
    live_server: str,
    grid: Grid,
    width: int,
    height: int,
    touch: bool,
) -> tuple[Page, MockRoomSocket, Callable[[], None]]:
    """The setup of the criterion with the panel open; page, mock and closer."""
    page, close = open_context_page(browser, browser_name, width, height, touch)
    try:
        mock = open_chat_room(
            page,
            live_server,
            grid,
            seq=SNAPSHOT_SEQ,
            players=eight_players_with_p2_host(),
            chat=snapshot_chat(),
        )
        for seq in range(SNAPSHOT_SEQ + 1, LAST_FEED_SEQ + 1):
            mock.send(check_frame(seq))
        expect_seq(page, LAST_FEED_SEQ)
        cell = cell_at(page, 3, 1)
        if touch:
            cell.tap()
        else:
            cell.click()
        expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", "3,0,0")
        open_panel(page, touch)
        expect(page.get_by_test_id("chat-input")).to_be_focused()
        page.wait_for_timeout(SETTLE_MS)
        scrolls = page.evaluate(LIST_SCROLLS_SCRIPT)
        assert scrolls is True, "the chat list does not scroll"
    except BaseException:
        close()
        raise
    return page, mock, close


def point_problems(page: Page, test_id: str, label: str) -> list[str]:
    """The points of `test_id` where `elementFromPoint` returns something else."""
    problems: list[str] = []
    for found in page.evaluate(POINTS_SCRIPT, test_id):
        if found["inside"] is not True:
            problems.append(f"{label}: {test_id} {found['point']} hit {found['hit']}")
    return problems


class PageState(NamedTuple):
    """What the criterion compares before and during the vote."""

    panel_box: list[float] | None
    scroll_top: float | None
    scroll_x: float
    scroll_y: float
    active: str | None


def read_state(page: Page) -> PageState:
    """Read the panel's box, the list's `scrollTop`, the window scroll and focus."""
    raw = page.evaluate(STATE_SCRIPT)
    return PageState(
        panel_box=raw["panelBox"],
        scroll_top=raw["scrollTop"],
        scroll_x=raw["scrollX"],
        scroll_y=raw["scrollY"],
        active=raw["active"],
    )


def state_problems(
    page: Page,
    before: PageState,
    active: str,
    label: str,
    check_scroll_top: bool = True,
) -> list[str]:
    """How the panel, the list, the scroll and the focus differ from `before`.

    `check_scroll_top` is False after the vote: spec 047 adds the closed vote's
    line to the stream, which brings a list that was at its end to its new end
    (spec 022 AC-11), and the criterion reads no `scrollTop` after the vote.
    """
    now = read_state(page)
    if now.panel_box is None or before.panel_box is None:
        return [f"{label}: salon is not on the page"]
    problems: list[str] = []
    names = ["x", "y", "width", "height"]
    for index, name in enumerate(names):
        was = before.panel_box[index]
        is_now = now.panel_box[index]
        if abs(was - is_now) > TOLERANCE_PX:
            problems.append(f"{label}: panel {name} {was} -> {is_now}")
    if before.scroll_top is None or now.scroll_top is None:
        problems.append(f"{label}: chat-list is not on the page")
    elif check_scroll_top and abs(before.scroll_top - now.scroll_top) > TOLERANCE_PX:
        problems.append(f"{label}: scrollTop {before.scroll_top} -> {now.scroll_top}")
    if now.scroll_x != 0 or now.scroll_y != 0:
        problems.append(f"{label}: window scrolled {now.scroll_x}, {now.scroll_y}")
    if now.active != active:
        problems.append(f"{label}: focus on {now.active}, not {active}")
    return problems


def while_banner_shows(page: Page, before: PageState, active: str) -> list[str]:
    """The checks of the banner, once it shows and again 1,000 ms later."""
    expect(page.get_by_test_id("vote-banner")).to_be_visible()
    problems = point_problems(page, "vote-banner", "shown")
    problems += state_problems(page, before, active, "shown")
    page.wait_for_timeout(BANNER_STAYS_MS)
    problems += point_problems(page, "vote-banner", "1 s later")
    problems += state_problems(page, before, active, "1 s later")
    return problems


def after_the_vote(
    page: Page, mock: MockRoomSocket, seq: int, before: PageState, active: str
) -> list[str]:
    """Close the vote (rejected), wait for the banner to leave, check the panel."""
    mock.send(
        closed(seq, seq - 1, VoteOutcome.REJECTED, 1, EIGHT_VOTERS).model_dump_json()
    )
    expect(page.get_by_test_id("vote-banner")).to_have_count(0, timeout=BANNER_GONE_MS)
    problems = point_problems(page, "salon", "after the vote")
    problems += state_problems(
        page, before, active, "after the vote", check_scroll_top=False
    )
    return problems


def open_vote(mock: MockRoomSocket, seq: int) -> None:
    """The mock opens a vote for a grid check by `p2`; its id is the seq."""
    event = opened(seq, seq, "p2", GRID_CHECK, EIGHT_VOTERS)
    mock.send(event.model_dump_json())


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids())
def test_ac17_browser_the_banner_is_drawn_above_an_open_panel(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, mock, close = open_scene(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    problems: dict[str, list[str]] = {}
    sent: list[dict[str, Any]] = []
    try:
        # Typing: `ok` in `chat-input`, which keeps the focus.
        page.keyboard.type("ok")
        before = read_state(page)
        vote_seq = LAST_FEED_SEQ + 1
        open_vote(mock, vote_seq)
        typing = while_banner_shows(page, before, "chat-input")
        sent = frames_after(page, mock, lambda: page.keyboard.press("Enter"))
        problems["typing"] = typing
        problems["typing, after the vote"] = after_the_vote(
            page, mock, vote_seq + 1, before, "chat-input"
        )

        # List focus: `Shift+Tab` from `chat-input` puts the focus on `chat-list`.
        page.keyboard.press("Shift+Tab")
        expect(page.get_by_test_id("chat-list")).to_be_focused()
        before = read_state(page)
        vote_seq += 2
        open_vote(mock, vote_seq)
        problems["list focus"] = while_banner_shows(page, before, "chat-list")
        problems["list focus, after the vote"] = after_the_vote(
            page, mock, vote_seq + 1, before, "chat-list"
        )
    finally:
        close()

    assert problems == {
        "typing": [],
        "typing, after the vote": [],
        "list focus": [],
        "list focus, after the vote": [],
    }
    assert sent == [{"type": "chat", "text": "ok"}]
