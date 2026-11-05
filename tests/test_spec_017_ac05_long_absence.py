"""Tests of spec 017, AC-5: offline edits survive a long absence.

The page is tested with spec 040's mocked socket and the page clock, frozen before
the page loads and moved by hand with `advance_page`. The shared setup is in
`spec017_harness`.

Refined by `platform/reconnection.md` rule 6 (B-047): the first retry comes 0.8 to
1.2 seconds after a loss, so a test that waits for it moves the page clock by
1.2 seconds.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import EditLetter
from reconnection_harness import SOCKET_STAND_INS_SCRIPT
from spec017_harness import (
    SETTLE_MS,
    STORED_JOIN,
    Edit,
    advance_page,
    banner,
    cell_at,
    expect_cell,
    expect_new_connection_after,
    expect_offline,
    expect_status,
    first_join,
    joined_room,
    room_page,
    settle,
    snapshot_frame,
    wait_until,
)

# ---- AC-5: offline edits survive a long absence (browser) --------------------

OFFLINE_EDIT_COUNT = 30
RESEND_PER_WINDOW = 10
RESEND_WINDOW_MS = 1000
SAMPLE_STEP_MS = 100
SAMPLE_SETTLE_MS = 60
RESEND_SPAN_LIMIT_MS = 4000
FIRST_DELAY_LATEST_MS = 1200  # the first retry delay, 1 s drawn within 20 %
# The page-side stand-ins for what Playwright's mocked socket cannot do (its
# `on_close` handler raises a KeyError when the page closes without a code, and
# a mocked socket always opens at once) are `reconnection_harness`'s:
# `window.__hangNext` keeps the next sockets CONNECTING for ever, and
# `window.__deafClose` records `close()` in `window.__pageCloses` and sends it no
# further, while messages still arrive (as on a dead network).
DEAF_CLOSE_SCRIPT = SOCKET_STAND_INS_SCRIPT + "window.__deafClose = true;"


def offline_letter(index: int) -> str:
    """Return the letter of the `index`-th offline edit (never twice in a row)."""
    return chr(ord("A") + index % 26)


def edit_summaries(edits: list[Edit]) -> list[tuple[str, int, int, str | None]]:
    """Return (kind, row, column, letter) of each edit, without the base_seq."""
    summaries: list[tuple[str, int, int, str | None]] = []
    for edit in edits:
        if isinstance(edit, EditLetter):
            summaries.append(("edit_letter", edit.row, edit.column, edit.letter))
        else:
            summaries.append(("erase", edit.row, edit.column, None))
    return summaries


def test_ac5_a_silence_loss_does_not_wait_for_the_close_event(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(
        page,
        live_server,
        fx01_grid,
        frozen=True,
        answer_pings=False,
        init_script=DEAF_CLOSE_SCRIPT,
    )

    advance_page(page, 4000)

    expect_offline(page)
    assert page.evaluate("window.__pageCloses.length") == 1
    assert len(room.connections) == 1
    expect_new_connection_after(page, room, 1000)
    assert first_join(page, room.connections[1]) == STORED_JOIN


def test_ac5_the_silent_socket_is_detached_and_late_frames_change_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(
        page,
        live_server,
        fx01_grid,
        frozen=True,
        answer_pings=False,
        init_script=DEAF_CLOSE_SCRIPT,
    )
    advance_page(page, 4000)
    expect_offline(page)

    room.connections[0].send(snapshot_frame(fx01_grid, 8))
    page.wait_for_timeout(SETTLE_MS)

    expect_status(page, "reconnecting")
    expect(banner(page)).to_be_visible()
    expect(room_page(page)).to_have_attribute("data-seq", "5")


def test_ac5_the_online_event_forces_a_try_while_a_new_socket_is_connecting(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(
        page, live_server, fx01_grid, frozen=True, init_script=SOCKET_STAND_INS_SCRIPT
    )
    room.connections[0].close(1011)
    expect_offline(page)
    page.evaluate("window.__hangNext = true")

    advance_page(page, FIRST_DELAY_LATEST_MS)

    wait_until(page, lambda: page.evaluate("window.__hung") == 1)
    assert len(room.connections) == 1
    page.evaluate("window.__hangNext = false")
    page.evaluate("window.dispatchEvent(new Event('online'))")

    room.wait_for_connections(2)
    assert first_join(page, room.connections[1]) == STORED_JOIN
    assert page.evaluate("window.__hung") == 1


def type_offline_edits(page: Page) -> list[Edit]:
    """Type the offline edits on (1, 0) and return the edits expected on the wire."""
    expected: list[Edit] = []
    for index in range(OFFLINE_EDIT_COUNT):
        letter = offline_letter(index)
        cell_at(page, 1, 0).click()
        page.keyboard.press(letter.lower())
        expected.append(EditLetter(row=1, column=0, letter=letter, base_seq=5))
    return expected


def test_ac5_thirty_offline_edits_are_resent_in_order_at_most_10_per_second(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, seq=5, frozen=True)
    room.connections[0].close(1011)
    expect_offline(page)
    expected = type_offline_edits(page)
    expect_new_connection_after(page, room, 1000)
    second = room.connections[1]
    assert second.edits() == []
    # Time 0 is just before the snapshot; the first sample follows it by 1 ms.
    samples: list[tuple[int, int]] = [(0, 0)]
    second.send(snapshot_frame(fx01_grid, 9))
    expect(room_page(page)).to_have_attribute("data-seq", "9")
    page.wait_for_timeout(SETTLE_MS)
    elapsed_ms = 1
    samples.append((elapsed_ms, len(second.edits())))
    while len(second.edits()) < OFFLINE_EDIT_COUNT:
        assert elapsed_ms < RESEND_SPAN_LIMIT_MS, "the 30 edits did not all arrive"
        page.clock.run_for(SAMPLE_STEP_MS)
        page.wait_for_timeout(SAMPLE_SETTLE_MS)
        elapsed_ms += SAMPLE_STEP_MS
        samples.append((elapsed_ms, len(second.edits())))
    advance_page(page, 1000)

    assert second.edits() == expected
    for start_ms, start_count in samples:
        for end_ms, end_count in samples:
            if 0 < end_ms - start_ms <= RESEND_WINDOW_MS:
                sent_in_window = end_count - start_count
                assert sent_in_window <= RESEND_PER_WINDOW, (
                    f"{sent_in_window} edits between {start_ms} and {end_ms} ms "
                    "after the snapshot"
                )
    assert elapsed_ms >= 2500, "the 30 edits were not spread over about 3 seconds"


def test_ac5_the_resend_waits_for_the_snapshot_and_keeps_pending_edits_shown(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, seq=5, frozen=True)
    room.connections[0].close(1011)
    expect_offline(page)
    type_offline_edits(page)
    expect_new_connection_after(page, room, 1000)
    second = room.connections[1]

    advance_page(page, 3000)

    assert second.edits() == []
    expect_cell(page, 1, 0, offline_letter(OFFLINE_EDIT_COUNT - 1), unconfirmed=True)


def test_ac5_no_edit_is_sent_between_the_new_socket_and_the_snapshot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, seq=5)
    room.connections[0].close(1011)
    expect_offline(page)
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    room.wait_for_connections(2)
    second = room.connections[1]
    assert first_join(page, second) == STORED_JOIN

    page.keyboard.press("a")

    expect_cell(page, 1, 1, "A", unconfirmed=True)
    settle(page)
    assert second.edits() == []
    second.send(snapshot_frame(fx01_grid, 9))
    wait_until(page, lambda: len(second.edits()) >= 2)
    settle(page)
    sent = second.edits()
    assert edit_summaries(sent) == [
        ("edit_letter", 1, 0, "T"),
        ("edit_letter", 1, 1, "A"),
    ]
    assert sent[0] == EditLetter(row=1, column=0, letter="T", base_seq=5)
