"""Tests of spec 017, AC-5: offline edits survive a long absence.

The page is tested with spec 040's mocked socket and the page clock, frozen before
the page loads and moved by hand with `advance_page`. The shared setup is in
`spec017_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import EditLetter
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
    grid_from_text,
    joined_room,
    room_page,
    settle,
    snapshot_frame,
    wait_until,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-5: offline edits survive a long absence (browser) --------------------

OFFLINE_EDIT_COUNT = 30
RESEND_PER_WINDOW = 10
RESEND_WINDOW_MS = 1000
SAMPLE_STEP_MS = 100
SAMPLE_SETTLE_MS = 60
RESEND_SPAN_LIMIT_MS = 4000
# Two page-side stand-ins for what Playwright's mocked socket cannot do (its
# `on_close` handler raises a KeyError when the page closes without a code, and
# a mocked socket always opens at once). Both are off unless a test switches
# them on, and other sockets are the real (mocked) ones.
# - `window.__hangNext`: the next socket stays CONNECTING for ever.
# - `window.__deafClose`: `close()` is recorded in `window.__pageCloses` and
#   goes no further: the server side never sees it and the page never gets a
#   `close` event, while messages still arrive (as on a dead network).
SOCKET_STAND_INS_SCRIPT = """
(() => {
  const RealWebSocket = window.WebSocket;
  window.__hangNext = false;
  window.__deafClose = false;
  window.__hung = 0;
  window.__pageCloses = [];
  class HangingSocket extends EventTarget {
    constructor(url) {
      super();
      this.url = String(url);
      this.readyState = 0;
      this.protocol = '';
      this.extensions = '';
      this.bufferedAmount = 0;
      this.binaryType = 'blob';
      this.onopen = null;
      this.onmessage = null;
      this.onerror = null;
      this.onclose = null;
    }
    send() { throw new DOMException('not open', 'InvalidStateError'); }
    close() { this.readyState = 2; }
  }
  class DeafCloseSocket extends EventTarget {
    constructor(url, protocols) {
      super();
      this._ws = protocols === undefined
        ? new RealWebSocket(url) : new RealWebSocket(url, protocols);
      this._closedByPage = false;
      this.onopen = null;
      this.onmessage = null;
      this.onerror = null;
      this.onclose = null;
      for (const type of ['open', 'message', 'error', 'close']) {
        this._ws.addEventListener(type, (event) => this._forward(type, event));
      }
    }
    _forward(type, event) {
      if (type === 'close' && this._closedByPage) { return; }
      let copy = new Event(type);
      if (type === 'message') {
        copy = new MessageEvent('message', { data: event.data });
      }
      if (type === 'close') {
        copy = new CloseEvent('close', { code: event.code, reason: event.reason });
      }
      this.dispatchEvent(copy);
      const handler = this['on' + type];
      if (typeof handler === 'function') { handler.call(this, copy); }
    }
    get url() { return this._ws.url; }
    get protocol() { return this._ws.protocol; }
    get extensions() { return this._ws.extensions; }
    get bufferedAmount() { return this._ws.bufferedAmount; }
    get binaryType() { return this._ws.binaryType; }
    set binaryType(value) { this._ws.binaryType = value; }
    get readyState() { return this._closedByPage ? 2 : this._ws.readyState; }
    send(data) { this._ws.send(data); }
    close(code) {
      this._closedByPage = true;
      window.__pageCloses.push(code === undefined ? null : code);
    }
  }
  function PatchedWebSocket(url, protocols) {
    if (window.__hangNext) {
      window.__hung += 1;
      return new HangingSocket(url);
    }
    if (window.__deafClose) { return new DeafCloseSocket(url, protocols); }
    if (protocols === undefined) { return new RealWebSocket(url); }
    return new RealWebSocket(url, protocols);
  }
  PatchedWebSocket.prototype = RealWebSocket.prototype;
  PatchedWebSocket.CONNECTING = 0;
  PatchedWebSocket.OPEN = 1;
  PatchedWebSocket.CLOSING = 2;
  PatchedWebSocket.CLOSED = 3;
  window.WebSocket = PatchedWebSocket;
})();
"""
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

    advance_page(page, 1000)

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
