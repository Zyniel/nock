---
id: "036"
title: Performance
status: approved
---

# 036 - Performance

Epic E10 Quality bar (US-10.2) · Release: MVP · Epic depends on: All
FX-02 is `tests/fixtures/fx02.json` (13 by 17, spec 006), read by the `fx02_text`
fixture. The rooms engine and hub are those of specs 011 and 018, edits spec
015, the frame limit spec 037, the phone context spec 006, the live server and
the room page spec 040.

## Goal

As a player on a mid-range phone, I want a responsive grid, so that typing never lags.

These criteria apply to every story above and belong in each agent's definition of done.

## Public interface

### Reference phone profile (test harness and every criterion that names it)

"Phone profile" is a Chromium browser context with spec 006's phone options
(`viewport` 360 by 740, `has_touch=True`, `is_mobile=True`,
`device_scale_factor=2`), a new context per measurement (cold cache), and a CDP
session (`context.new_cdp_session(page)`) that sends, before the first
`page.goto`:

- `Emulation.setCPUThrottlingRate` with `{"rate": 4}`;
- `Network.enable`, then `Network.emulateNetworkConditions` with
  `{"offline": false, "latency": 170, "downloadThroughput": 1125000, "uploadThroughput": 187500}`
  (9 Mbit/s down, 1.5 Mbit/s up, 170 ms latency).

CPU throttling and network emulation exist only through Chromium's CDP, so every
test that uses the phone profile is marked `@pytest.mark.only_browser("chromium")`.
These tests run inside the normal gate (`uv run python scripts/gate.py`), locally
and in CI.

### Client: interactive mark

`web/src/lib/RoomPage.svelte` calls `performance.mark("nock:interactive")` once
per page load, right after the DOM shows the grid of the page's first snapshot
(after Svelte's `tick()`), so `performance.getEntriesByName("nock:interactive")[0].startTime`
is the time in milliseconds from navigation start to a grid that takes taps and
keys. A later snapshot (reconnection) adds no mark.

### Hub bounds (`src/nock/hub.py`, `src/nock/room.py`)

```python
# src/nock/room.py: RoomConfig gains two fields (defaults below)
class RoomConfig(RoomModel):
    # ... fields of specs 011 to 037
    max_outbound_messages: int = Field(default=1000, ge=1)  # per connection
    max_inbound_pending: int = Field(default=100, ge=1)     # per connection


# src/nock/hub.py
STALLED_CLOSE_CODE: int = 4507  # the client did not read its messages
FLOOD_CLOSE_CODE: int = 1008    # the client sent faster than the room applies


class RoomConnection:
    def __init__(
        self,
        owner_loop: asyncio.AbstractEventLoop,
        post: Callable[[_Input], None],
        max_outbound: int = 1000,
        max_inbound: int = 100,
    ) -> None: ...
```

`RoomRegistry.connect` passes `config.max_outbound_messages` and
`config.max_inbound_pending`. Both names are added to `nock.hub.__all__`.

Outbound bound (a client that never reads):

- A connection's outbound queue counts the items queued and not yet handed to
  `send_text`. When the room task delivers a message while that count is already
  `max_outbound`, the connection is **stalled**: its queued items are dropped,
  every later delivery to it is dropped, `run_writer` stops waiting for the
  current `send_text` (even one that never completes), calls
  `close(STALLED_CLOSE_CODE)` once and returns, and the room applies a
  disconnection of that connection (spec 017: `player_state_changed`
  `disconnected` to the others when it was the player's last connection).
- The room task never waits for a stalled socket; the other connections get
  their messages as before.

Inbound bound (a client that floods):

- A connection counts the inputs it posted to the room (messages and invalid
  frames, joined or not) that the room task has not finished applying. When a
  frame arrives while that count is already `max_inbound`, the frame is dropped,
  every later frame of the connection is dropped, and the connection is closed
  with `FLOOD_CLOSE_CODE` through its own outbound queue, without waiting for the
  room task. The inputs posted before stay queued and are applied in order. The
  socket's close then detaches the connection as usual (`leave()` is not counted).

### Frame size at the socket (`src/nock/server.py`, `src/nock/__main__.py`)

```python
# src/nock/server.py
import uvicorn

WS_MAX_SIZE_BYTES: int = 8192  # uvicorn refuses larger frames (close 1009)


def server_config(
    app: FastAPI, host: str = "127.0.0.1", port: int = 8000, log_level: str = "info"
) -> uvicorn.Config:
    """Return the uvicorn configuration of the server: `ws_max_size` is
    WS_MAX_SIZE_BYTES; every other option is uvicorn's default."""


# src/nock/__main__.py
def main() -> None:
    """Run `nock.server.app` with `server_config`, host from NOCK_HOST (default
    127.0.0.1) and port from NOCK_PORT (default 8000)."""
```

- Frames of 4,097 to 8,192 bytes still reach the app and get spec 037's
  `invalid_message`; frames over 8,192 bytes are refused by uvicorn before they
  are buffered whole, and the socket is closed with code 1009.
- The production command becomes `uv run python -m nock` (with `NOCK_DATABASE`,
  spec 018); the implementer updates `README.md`. The `live_server` fixture of
  `tests/conftest.py` builds its server with `server_config(app, log_level="warning")`
  (this spec's test-writer changes it), so browser tests run with the production
  limits.

### Test harness

- Rooms on FX-02 are registered with
  `room_registry.register_room(Grid.model_validate_json(fx02_text))`.
- Automatic join without the nickname form: before `page.goto`, an init script
  sets `nock.room.<code>` to `{"grid": 1, "selection": null}` and `nock.nickname`
  to `Ana` (spec 010's creator path), so the page joins as soon as its socket
  opens.
- Simulated players are spec 015's Python clients: threads, each with one
  `TestClient` socket. When a browser page also plays, the simulated clients use
  `TestClient(create_app(rooms=room_registry))` on the same `room_registry` as the
  live server, so they are in the same room.
- In-page timing: an init script registered before `page.goto` adds a capturing
  `keydown` listener on `window` that records `performance.now()` for each key, and
  a `MutationObserver` on the document that records `performance.now()` for each
  change of a `cell` element's `data-letter`. Times of two pages are compared as
  `performance.timeOrigin + performance.now()`.
- Percentiles: the p95 of `n` samples is the `ceil(0.95 * n)`-th smallest.
- Hub tests run their own event loop (`asyncio.run`) and use `RoomRegistry.connect`
  and `RoomConnection.run_writer` with test `send_text` and `close` coroutines;
  a "stuck" `send_text` awaits an `asyncio.Event` that is never set.
- A blocking store for AC-6 is a `RoomStore(":memory:")` subclass whose `append`
  waits on a `threading.Event` while a flag is set.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-10.2.1) (browser with live server, phone profile, Chromium only) FX-02 is interactive within 2.5 seconds on a mid-range phone over 4G. For a room registered on FX-02 and the automatic join of the harness, three cold loads of `/r/<code>` (a new context each) each record a `nock:interactive` mark; the median of their `startTime` values is at most 2500 ms. At the mark the room page has `data-status="joined"` and `data-grid="13x17"` and holds 221 `cell` elements; after the third load, tapping a letter cell and pressing `A` shows `A` in it.
- **AC-2** (AC-10.2.2) (browser with live server, phone profile, Chromium only) A typed letter shows locally within 50 ms. On a FX-02 room joined as in AC-1, the player taps a letter cell starting an across word and types 40 letters with `page.keyboard.press`, 250 ms apart, re-tapping the start of another word when the selection reaches the end of one; for each key, the time from its `keydown` to the first change of the typed cell's `data-letter` to that letter is measured in the page; the p95 of the 40 times is at most 50 ms.
- **AC-3** (AC-10.2.3) (WebSocket, simulated clients) With 8 players each typing 2 letters a second, the server keeps its share of spec 015 AC-1's budget. Eight simulated clients join one FX-02 room (`RoomConfig()` defaults, so spec 037's limit of 20 a second applies); each sends one `edit_letter` every 500 ms on a random letter cell (`random.Random(36)`) for 10 seconds, the eight starting 62.5 ms apart, while reading its socket. For each of the 160 edits and each of the 7 other clients, the relay time is from the sender's send to that client's receipt of the `letter_changed` with the edit's seq (known from the sender's own answer), with `time.monotonic()`. Every edit is answered with its `letter_changed` (no `error`), every client receives all 160, and the p95 of the 1,120 relay times is at most 100 ms (spec 015 decision 1).
- **AC-4** (AC-10.2.3) (browser with live server and simulated clients, CPU throttling, Chromium only) Under the same load, a letter typed in one page appears in another within 300 ms. Two pages with spec 006's phone options and `Emulation.setCPUThrottlingRate` 4 (no network emulation: the network share is accounted by spec 015 decision 1) join a FX-02 room as `Ana` and `Bob`, with six simulated clients typing as in AC-3 on cells outside Ana's words; Ana types 20 letters 500 ms apart on two across words; for each letter, the time from Ana's `keydown` to the change of the same cell's `data-letter` in Bob's page is measured (in-page timing); the p95 of the 20 times is at most 300 ms and every letter arrived.
- **AC-5** (new, from spec 037's review) (hub test) A client that never reads its socket is disconnected instead of growing a queue. With `RoomRegistry(config=RoomConfig(max_outbound_messages=20, max_edits_per_second=1000))` and a FX-01 room: connection A joins with a stuck `send_text`; connection B joins with a recording `send_text`; B sends 30 `edit_letter` messages. Then within 1 s A's `close` is called exactly once, with `STALLED_CLOSE_CODE` (4507), and A's `run_writer` returns; B receives its 30 `letter_changed` events and a `player_state_changed` with A's player id and state `disconnected`; A's `send_text` was called once only (the snapshot that never completed), also after B sends 10 more edits.
- **AC-6** (new, from spec 037's review) (hub test) A client that sends faster than its room applies is closed, and the room keeps working. With `RoomConfig(max_inbound_pending=5, max_edits_per_second=1000)`, the blocking store, and a FX-01 room where A joined (recording writer): the store starts blocking; A submits `EditLetter(row=1, column=0, letter="T")` (its step waits in `append`), then 7 `Ping` messages; then, while the store is still blocked, A's `close` is called once with `FLOOD_CLOSE_CODE` (1008). After the store is released, the room's state has `T` at (1, 0), and a new connection C can join the room and receives a `Snapshot` holding `T` at (1, 0).
- **AC-7** (new, from spec 037's review) (Python; WebSocket with live server) Oversized frames are refused at the socket. Python: `server_config(app).ws_max_size == WS_MAX_SIZE_BYTES == 8192`. Live server (the fixture built with `server_config`), from a Playwright page with `page.evaluate` opening a `WebSocket` to a FX-01 room: a text frame of 9,000 bytes makes the server close the socket with code 1009; on a second socket, after a join, a text frame of 8,000 bytes is answered with an `error` whose `code` is `invalid_message` and the socket stays open (a following `ping` gets a `pong`). This criterion runs in every engine.

## Edge cases and errors

Note from the lead (2026-10-11, from the spec 037 review), settled here: the hub's
per-room inbox and per-connection outbound queues were unbounded, and uvicorn's
default `ws_max_size` (16 MiB) received an oversized frame whole before spec 037
refused it. Settled by AC-5 (bounded outbound queue that disconnects a stalled
client), AC-6 (per-connection inbound cap) and AC-7 (`ws_max_size` 8,192 bytes).

- AC-3 depends on behaviour owned by spec 015; this spec tests only its own side:
  the server's relay under the 8-player load (AC-3) and the receiving page under
  load and CPU throttling (AC-4). The 4G network share (two one-way trips of
  about 85 ms under the 170 ms profile) is spec 015 decision 1's budget split:
  100 ms server + 170 ms network + the page's own time stay within 300 ms.
- Rate limit (AC-3): 2 edits a second is far below spec 037's 20; no edit may be
  refused.
- Collisions (AC-3): two simulated clients may write the same cell; each edit
  still gets its own `letter_changed` (spec 015), so every seq is measured.
- Stalled close and reconnection (AC-5): 4507 is not a final close code for the
  page (spec 040 lists 4404, 4429 and 4001), so a tab that was only frozen
  reconnects and gets a fresh snapshot (spec 017).
- Flood close (AC-6): 1008 is not final either; an honest page never reaches 100
  unapplied inputs (edits are limited to 20 a second and pings come every 2 s).
- Unjoined sockets (AC-6): the inbound cap applies to them too; how many sockets
  one address may open is spec 038's concern.
- Frame between 4,097 and 8,192 bytes (AC-7): spec 037's rule applies unchanged.
  Binary frames follow the same limits.
- Mark timing (AC-1): the mark is set after the first snapshot's grid is in the
  DOM, not after fonts or later events; a page that never gets a snapshot (room
  not found) sets no mark.
- Measurement noise (AC-1, AC-2, AC-4): medians and p95 are used rather than
  maxima, so one garbage-collection pause does not fail the gate; thresholds are
  not relaxed.

## Out of scope

- Nothing stated in the backlog (epic E10).
- Accessibility: spec 035.
- Integrity: spec 037.
- Privacy and operations: spec 038 (connection counts per address, deployment).
- Tests on real phones or real 4G networks; Firefox and WebKit timings (no CPU
  throttling there).
- Load beyond 8 players per room or many rooms at once; server capacity planning.
- Bundle size budgets, service workers and offline caching, as long as AC-1 holds.
- Throttling messages other than edits (spec 037 out of scope); the inbound cap
  bounds memory, not rate.

## Work packages

None.

## Decisions

Decided by the lead on 2026-10-11, under the owner's delegation of technical
decisions and the owner's answers of the same day. Each one is already part of
the spec above.

1. FX-02 is `tests/fixtures/fx02.json` (owner's answer).
2. "Mid-range phone over 4G" is a Playwright Chromium run with 4x CPU throttling
   and the 4G profile 9 Mbit/s down, 1.5 Mbit/s up, 170 ms latency, inside the
   normal gate (owner's answer). AC-1 and AC-2 use it; AC-4 uses the CPU part only.
   AC-1, AC-2 and AC-4 are Chromium-only (CDP); AC-3, AC-5 and AC-6 are not browser
   tests; AC-7's live part runs in every engine.
3. Thresholds: the backlog's 2.5 s, 50 ms and spec 015's 300 ms are kept (owner's
   answer). Measured as a median of three cold loads (AC-1) and as p95 (AC-2,
   AC-4), to keep the gate stable without relaxing the values.
4. "Interactive" is an explicit `performance.mark` set when the first snapshot's
   grid is in the DOM, then confirmed by a tap and a letter.
5. Outbound bound: 1,000 messages per connection (a full FX-02 game is about 300
   events), then close 4507 and disconnect the player; the room never waits for a
   socket.
6. Inbound bound: 100 unapplied inputs per connection, then close 1008 (WebSocket
   "policy violation"); dropping frames silently was rejected because every edit
   needs exactly one answer (spec 015).
7. `ws_max_size` 8,192 bytes: twice spec 037's 4,096, so spec 037's
   `invalid_message` answer still holds for frames just over its limit, while a
   frame can no longer be megabytes. It needs a run command that sets it, hence
   `server_config` and `python -m nock`.

## Open questions

None.
