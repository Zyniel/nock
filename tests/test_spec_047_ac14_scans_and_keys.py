"""Tests of spec 047, AC-14: the overlays pass spec 035's scans, and `fr.json`
holds this spec's keys.

The contrast scan (spec 035 AC-8) and the language scan (spec 035 AC-9) run at
1280 by 720 and at 360 by 740, in the desktop context, in each state of the
criterion; and at 320 by 568 on `SOLVED` with the band. The static part reads
`web/src/i18n/fr.json`.

The states:

- `vote`: `VOTE_ROOM` with `VOTE` shown (the buttons and the countdown);
- `voted`: the same after a click on `vote-yes`;
- `snapshot-vote`: a first snapshot holding `VOTE` (no countdown);
- `vote-note`: a `room-note` showing `fr.json["vote.result.timed_out"]`;
- `vote-line`: the stream holding a `vote` line;
- `solved`: `SOLVED` with the band;
- `recap`: `recap` loaded with `RECAP`;
- `recap-loading`: `recap` with the route held;
- `recap-error`: `recap` with the route answering 404;
- `muted`: the Discussion tab while I am muted.

Readings where the spec leaves room:

- The language scan's data are the nicknames as the page shows them and their
  two first letters, the room code and its link, FX-01's clue texts (spec 024's
  `language_data`), and the share URL.
- `vote-note` closes the Salon first where it shows (the column layout, where it
  is open at load), then the mock sends `VOTE` and `CLOSED("timed_out")`. After
  each scan the test checks that the note is still on the page, so that a scan
  that outlasts the note's 3 seconds fails rather than checking a page without
  it.
- `vote-line`: `VOTE`, `CLOSED("passed")`, then `show_tab(page, "discussion")`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import PlayerMuted, VoteOutcome
from room_panels import show_tab
from spec019_harness import OpenWindow, window_opener
from spec024_harness import contrast_problems, language_data, language_problems
from spec043_harness import (
    DISPLAY_NICKNAMES,
    expect_closed,
    is_open,
    load_fr,
    send_and_wait,
)
from spec044_harness import solved_frame
from spec047_harness import (
    COMPUTER,
    NARROW,
    PHONE,
    SHARE_PATH,
    VOTE,
    click_recap_open,
    closed,
    open_loaded_recap,
    open_solved,
    open_solved_held,
    open_vote_room,
    result_text,
    show_vote,
    vote_lines,
)

SIZES = [COMPUTER, PHONE]
STATES = [
    "vote",
    "voted",
    "snapshot-vote",
    "vote-note",
    "vote-line",
    "solved",
    "recap",
    "recap-loading",
    "recap-error",
    "muted",
]
SCAN_CASES = [(size, state) for size in SIZES for state in STATES]
SCAN_CASES.append((NARROW, "solved"))
SCAN_IDS = [f"{width}x{height}-{state}" for (width, height), state in SCAN_CASES]

NEW_KEYS = {"vote.seconds_left": "{count} s"}
CHANGED_KEYS = {
    "vote.cast": "Vote enregistré. En attente des autres joueurs…",
}
KEPT_KEYS = {
    "vote.waiting": "En attente des autres joueurs…",
    "vote.result.passed": "Vote accepté.",
    "vote.result.rejected": "Vote refusé.",
    "vote.result.timed_out": "Temps écoulé, vote annulé.",
}

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- The states of the scans --------------------------------------------------------


def open_vote_state(page: Page, base_url: str, grid: Grid, state: str) -> None:
    """The states of the vote: `vote`, `voted`, `vote-note`, `vote-line`."""
    mock = open_vote_room(page, base_url, grid)
    if state == "vote-note":
        salon = page.get_by_test_id("salon")
        if is_open(salon):
            page.get_by_test_id("chat-toggle").click()
        expect_closed(salon)
    show_vote(page, mock)
    if state == "voted":
        page.get_by_test_id("vote-yes").click()
        expect(page.get_by_test_id("vote-status")).to_be_visible()
    elif state == "vote-note":
        send_and_wait(page, mock, closed(VoteOutcome.TIMED_OUT).model_dump_json())
        note = page.get_by_test_id("room-note")
        expect(note).to_have_count(1)
        expect(note).to_have_text(result_text(VoteOutcome.TIMED_OUT))
    elif state == "vote-line":
        send_and_wait(page, mock, closed(VoteOutcome.PASSED).model_dump_json())
        show_tab(page, "discussion")
        expect(vote_lines(page)).to_have_count(1)


def open_recap_state(page: Page, base_url: str, grid: Grid, state: str) -> None:
    """The states of the solved page: `solved`, `recap`, `recap-*`."""
    frame = solved_frame(grid)
    if state == "recap-loading":
        open_solved_held(page, base_url, frame)
        click_recap_open(page)
        expect(page.get_by_test_id("recap-loading")).to_be_visible()
    elif state == "recap-error":
        open_solved(page, base_url, frame, body={"detail": "Not Found"}, status=404)
        click_recap_open(page)
        expect(page.get_by_test_id("recap-error")).to_be_visible()
    else:
        open_solved(page, base_url, frame)
        expect(page.get_by_test_id("grid-status")).to_have_attribute(
            "data-state", "solved"
        )
        if state == "recap":
            open_loaded_recap(page)


def open_scan_state(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int], state: str
) -> Page:
    """Open the page of AC-14 at `size` (desktop) in `state`."""
    page = window(size[0], size[1], False)
    if state in ("vote", "voted", "vote-note", "vote-line"):
        open_vote_state(page, base_url, grid, state)
    elif state == "snapshot-vote":
        open_vote_room(page, base_url, grid, open_vote=VOTE)
        expect(page.get_by_test_id("vote-banner")).to_be_visible()
    elif state == "muted":
        mock = open_vote_room(page, base_url, grid)
        show_tab(page, "discussion")
        muted = PlayerMuted(seq=6, player_id="p1", muted=True)
        send_and_wait(page, mock, muted.model_dump_json())
        expect(page.get_by_test_id("chat-muted")).to_be_visible()
    else:
        open_recap_state(page, base_url, grid, state)
    return page


def expect_note_outlasted_the_scan(page: Page, state: str) -> None:
    """In the `vote-note` state, fail unless `room-note` is still on the page."""
    if state == "vote-note":
        count = page.get_by_test_id("room-note").count()
        assert count == 1, "the room-note left before the scan ended"


# ---- The scans ----------------------------------------------------------------------


@pytest.mark.parametrize(("size", "state"), SCAN_CASES, ids=SCAN_IDS)
def test_ac14_the_contrast_scan_finds_no_offender(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    size: tuple[int, int],
    state: str,
) -> None:
    page = open_scan_state(window, live_server, fx01_grid, size, state)

    problems = contrast_problems(page)

    expect_note_outlasted_the_scan(page, state)
    assert problems == []


@pytest.mark.parametrize(("size", "state"), SCAN_CASES, ids=SCAN_IDS)
def test_ac14_the_language_scan_finds_no_offender(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    size: tuple[int, int],
    state: str,
) -> None:
    page = open_scan_state(window, live_server, fx01_grid, size, state)
    expect(page.locator("html")).to_have_attribute("lang", "fr")

    data = language_data(live_server, DISPLAY_NICKNAMES)
    data.add(f"{live_server}{SHARE_PATH}")
    problems = language_problems(page, data)

    expect_note_outlasted_the_scan(page, state)
    assert problems == []


# ---- The keys of fr.json --------------------------------------------------------


@pytest.mark.parametrize(("key", "value"), list(NEW_KEYS.items()))
def test_ac14_fr_json_holds_the_new_key(key: str, value: str) -> None:
    assert load_fr().get(key) == value


@pytest.mark.parametrize(("key", "value"), list(CHANGED_KEYS.items()))
def test_ac14_fr_json_holds_the_changed_value(key: str, value: str) -> None:
    assert load_fr().get(key) == value


@pytest.mark.parametrize(("key", "value"), list(KEPT_KEYS.items()))
def test_ac14_fr_json_still_holds_spec_025s_vote_keys(key: str, value: str) -> None:
    assert load_fr().get(key) == value
