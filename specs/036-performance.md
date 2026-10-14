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
- `main()` reads `NOCK_HOST` and `NOCK_PORT` from `os.environ` each time it is
  called. A variable that is unset or empty takes its default (`127.0.0.1`,
  `8000`), so an empty host never makes uvicorn listen on every interface.
  `NOCK_HOST` is passed on as given. `NOCK_PORT` must be ASCII digits only, with a
  value from 1 to 65535. Any other value makes `main()` raise `SystemExit` whose
  `code` is a `str` naming `NOCK_PORT` and the value as given, before it builds a
  server, so `python -m nock` prints that message on stderr and exits with
  status 1. (Note from the lead, 2026-10-14: added with AC-10 and AC-11. The spec
  gave the defaults but no rule for empty or invalid values.)
- `main()` then runs
  `uvicorn.Server(server_config(nock.server.app, host=host, port=port)).run()`
  and returns when the server stops (log level `info`, `server_config`'s
  default). `src/nock/__main__.py` calls `main()` only under
  `if __name__ == "__main__":`, so importing `nock.__main__` starts nothing.
  (Note from the lead, 2026-10-14: added so that AC-10 and AC-11 can call
  `main()` in the test process with `uvicorn.Server.run` replaced.)
- The production command becomes `uv run python -m nock` (with `NOCK_DATABASE`,
  spec 018); the implementer updates `README.md` and documents `NOCK_HOST` and
  `NOCK_PORT` there. (Note from the lead, 2026-10-14: "and documents `NOCK_HOST`
  and `NOCK_PORT` there" added.)
- The shared `live_server` fixture of `tests/conftest.py` builds its server with
  `server_config(app, log_level="warning")` once the implementation provides
  `server_config`. The test-writer switches it in a commit after the
  implementer's, before this spec is `done`. Switching it earlier would make
  every browser test of every spec fail on the missing name. From then on, every
  browser test runs with the production limits (none of today's browser tests
  sends a frame over 8,192 bytes). Until then, AC-7's live part starts its own
  server with `server_config` (see "Test harness"). (Note from the lead,
  2026-10-14: this used to say that the fixture builds its server with
  `server_config` and that this spec's test-writer changes it. That change has to
  wait for `server_config`, so the tests at 81a4260 leave conftest as it is.)

### Test harness

- Rooms on FX-02 are registered with
  `room_registry.register_room(Grid.model_validate_json(fx02_text))`.
- Automatic join without the nickname form: before `page.goto`, an init script
  sets `nock.room.<code>` to `{"grid": 1, "selection": null}` and `nock.nickname`
  to `Ana` (spec 010's creator path), or to `Bob` for AC-4's second page, so the
  page joins as soon as its socket opens. (Note from the lead, 2026-10-14: "or to
  `Bob` for AC-4's second page" added, since AC-4 joins that page as `Bob`.)
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
- Live server built with `server_config` (AC-7): until the shared `live_server`
  is switched (see "Frame size at the socket"), the test starts its own server
  the way that fixture does (the same `room_registry` and `catalogue`, the built
  client, failing when it is missing, a free port of 127.0.0.1), but with
  `uvicorn.Server(server_config(app, log_level="warning"))`. After the switch,
  either server will do. (Note from the lead, 2026-10-14: added; the tests at
  81a4260 do this in `production_live_server`.)
- Production entry point (AC-8 to AC-11). Subprocess (AC-8, AC-9): a SQLite file
  in `tmp_path` holds a FX-01 room registered by
  `RoomRegistry(store=RoomStore(path))`, after which the registry, then the
  store, are closed. The test runs `[sys.executable, "-m", "nock"]` (the
  interpreter that `uv run` gives the tests) with its own environment plus
  `NOCK_DATABASE` (the file) and `NOCK_PORT` (a free port, bound on 127.0.0.1
  with port 0, then released), and without `NOCK_HOST`. It polls
  `GET http://127.0.0.1:<port>/` for up to 10 seconds, opens the sockets from a
  Playwright page on that origin as AC-7 does, and stops the process at the end
  (terminate, then kill). In the test process (AC-10, AC-11): the test imports
  `nock.__main__`, sets or deletes the two variables with `monkeypatch`, and
  replaces `uvicorn.Server.run` (`monkeypatch.setattr`) with a recorder that
  keeps `self.config` and returns None. (Note from the lead, 2026-10-14: added
  with AC-8 to AC-11.)

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-10.2.1) (browser with live server, phone profile, Chromium only) FX-02 is interactive within 2.5 seconds on a mid-range phone over 4G. For a room registered on FX-02 and the automatic join of the harness, three cold loads of `/r/<code>` (a new context each) each record a `nock:interactive` mark; the median of their `startTime` values is at most 2500 ms. At the mark the room page has `data-status="joined"` and `data-grid="13x17"` and holds 221 `cell` elements; after the third load, tapping a letter cell and pressing `A` shows `A` in it.
- **AC-2** (AC-10.2.2) (browser with live server, phone profile, Chromium only) A typed letter shows locally within 50 ms. On a FX-02 room joined as in AC-1, the player taps a letter cell starting an across word and types 40 letters with `page.keyboard.press`, 250 ms apart, re-tapping the start of another word when the selection reaches the end of one; for each key, the time from its `keydown` to the first change of the typed cell's `data-letter` to that letter is measured in the page; the p95 of the 40 times is at most 50 ms.
- **AC-3** (AC-10.2.3) (WebSocket, simulated clients) With 8 players each typing 2 letters a second, the server keeps its share of spec 015 AC-1's budget. Eight simulated clients join one FX-02 room (`RoomConfig()` defaults, so spec 037's limit of 20 a second applies); each sends one `edit_letter` every 500 ms on a random letter cell (`random.Random(36)`) for 10 seconds, the eight starting 62.5 ms apart, while reading its socket. For each of the 160 edits and each of the 7 other clients, the relay time is from the sender's send to that client's receipt of the `letter_changed` with the edit's seq (known from the sender's own answer), with `time.monotonic()`. Every edit is answered with its `letter_changed` (no `error`), every client receives all 160, and the p95 of the 1,120 relay times is at most 100 ms (spec 015 decision 1).
- **AC-4** (AC-10.2.3) (browser with live server and simulated clients, CPU throttling, Chromium only) Under the same load, a letter typed in one page appears in another within 300 ms. Two pages with spec 006's phone options and `Emulation.setCPUThrottlingRate` 4 (no network emulation: the network share is accounted by spec 015 decision 1) join a FX-02 room as `Ana` and `Bob`. Ana's words are FX-02's two longest across words, the first by row-major order of its first cell among words of equal length: `OREILLE` from (1, 2) to (1, 8) and `TRAIT` from (4, 6) to (4, 10), 12 cells. Six simulated clients then join; each sends one `edit_letter` every 500 ms on a random letter cell outside Ana's words (`random.Random(36)`), the six starting 62.5 ms apart, while reading its socket. All six are typing before Ana's first key (she starts 1 second after the load) and go on until Bob's page shows her last letters, so seven of the eight players type 2 letters a second while Bob watches. Ana types 20 keys with `page.keyboard.press`, 500 ms apart, tapping the first cell of a word before its first key: the answers of her two words (12 keys), then the same cells again from the start of `OREILLE`, each with the letter after its answer letter in the alphabet (Z gives A), so that every key changes its cell: `PSFJMMF`, then `U` at (4, 6) (8 keys). For each key, the time from Ana's `keydown` to the first change after it of the same cell's `data-letter` to that key's letter in Bob's page is measured (in-page timing). All 20 letters arrive in Bob's page, the p95 of the 20 times is at most 300 ms, and every edit of the simulated clients is answered with its `letter_changed` (no `error`). (Note from the lead, 2026-10-14: reworded to state the load that the tests at 81a4260 run. It used to say that Ana "types 20 letters 500 ms apart on two across words" while six clients type "as in AC-3", but FX-02's two longest across words hold 12 cells. Ana now types their answers, then retypes the same cells with other letters; the load runs while she types instead of for AC-3's 10 seconds; the answers to the load are checked. The intent is unchanged: 2 letters a second, sustained, and 300 ms from Ana's key to Bob's page.)
- **AC-5** (new, from spec 037's review) (hub test) A client that never reads its socket is disconnected instead of growing a queue. With `RoomRegistry(config=RoomConfig(max_outbound_messages=20, max_edits_per_second=1000))` and a FX-01 room: connection A joins with a stuck `send_text`; connection B joins with a recording `send_text`; B sends 30 `edit_letter` messages. Then within 1 s A's `close` is called exactly once, with `STALLED_CLOSE_CODE` (4507), and A's `run_writer` returns; B receives its 30 `letter_changed` events and a `player_state_changed` with A's player id and state `disconnected`; A's `send_text` was called once only (the snapshot that never completed), also after B sends 10 more edits.
- **AC-6** (new, from spec 037's review) (hub test) A client that sends faster than its room applies is closed, and the room keeps working. With `RoomConfig(max_inbound_pending=5, max_edits_per_second=1000)`, the blocking store, and a FX-01 room where A joined (recording writer): the store starts blocking; A submits `EditLetter(row=1, column=0, letter="T")` (its step waits in `append`), then 7 `Ping` messages; then, while the store is still blocked, A's `close` is called once with `FLOOD_CLOSE_CODE` (1008). After the store is released, the room's state has `T` at (1, 0), and a new connection C can join the room and receives a `Snapshot` holding `T` at (1, 0).
- **AC-7** (new, from spec 037's review) (Python; WebSocket with live server) Oversized frames are refused at the socket. Python: `server_config(app).ws_max_size == WS_MAX_SIZE_BYTES == 8192`. Live server built with `server_config` (see "Test harness"), from a Playwright page with `page.evaluate` opening a `WebSocket` to a FX-01 room: a text frame of 9,000 bytes makes the server close the socket with code 1009; on a second socket, after a join, a text frame of 8,000 bytes is answered with an `error` whose `code` is `invalid_message` and the socket stays open (a following `ping` gets a `pong`). This criterion runs in every engine. (Note from the lead, 2026-10-14: "the fixture built with `server_config`" became "built with `server_config` (see "Test harness")": until the shared fixture is switched, the test starts its own server.)
- **AC-8** (new, from the review of this spec's tests) (subprocess; WebSocket from a Playwright page, every engine) `python -m nock` serves the app on the port of `NOCK_PORT`. Given a SQLite file holding a FX-01 room (see "Test harness"), when the test runs `python -m nock` with `NOCK_DATABASE` set to that file, `NOCK_PORT` set to a free port and `NOCK_HOST` unset, then within 10 seconds `GET http://127.0.0.1:<port>/` answers 200 with the built client, and a socket to the room's `/api/rooms/<code>/ws` that sends a `join` receives a `snapshot` as its first message (the room is loaded from the file as after spec 018 AC-1's restart; an unknown code would be closed with 4404). (Note from the lead, 2026-10-14: added; see decision 10.)
- **AC-9** (new, from the review of this spec's tests) (subprocess; WebSocket from a Playwright page, every engine) `python -m nock` refuses oversized frames at the socket, which shows that it runs `server_config`. On a server started as in AC-8, a socket to the room that sends a text frame of 9,000 bytes is closed with code 1009 and receives no message; with uvicorn's default `ws_max_size` the frame would reach the app and get spec 037's `invalid_message`. (Note from the lead, 2026-10-14: added; see decision 10.)
- **AC-10** (new, from the review of this spec's tests) (Python, `uvicorn.Server.run` replaced) `main()` hands uvicorn the address of `NOCK_HOST` and `NOCK_PORT`, 127.0.0.1 and 8000 by default. With the recorder of the "Test harness", `main()` returns after one call of `run`, whose server's `config` has `app` `nock.server.app` (the same object), `ws_max_size` 8192, and: `host` `"127.0.0.1"` and `port` 8000 with neither variable set; the same with both set to `""`; `host` `"0.0.0.0"` and `port` 9123 with `NOCK_HOST="0.0.0.0"` and `NOCK_PORT="9123"`. (Note from the lead, 2026-10-14: added; see decision 10.)
- **AC-11** (new, from the review of this spec's tests) (Python, `uvicorn.Server.run` replaced) An invalid `NOCK_PORT` stops `main()` before any server runs. With the recorder of the "Test harness" and `NOCK_HOST` unset, for each `NOCK_PORT` of `"abc"`, `"0"`, `"65536"`, `"-1"`, `"8000.0"` and `" 8000"`, `main()` raises `SystemExit` whose `code` is a `str` containing `NOCK_PORT` and the value as given, and `run` is never called. (Note from the lead, 2026-10-14: added; see decision 10.)

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
- Ana's cells (AC-4): the simulated clients never write Ana's 12 cells, so on
  Bob's page every change of those cells comes from one of her keys, and the
  second pass always gives a cell a letter it does not hold yet. (Note from the
  lead, 2026-10-14: added with the new wording of AC-4.)
- Empty and invalid variables (AC-10, AC-11): an empty `NOCK_HOST` or `NOCK_PORT`
  counts as unset. `NOCK_PORT` `"0"` is refused (uvicorn would pick a random
  port); leading zeros (`"08000"`) are accepted; signs, spaces, decimal points
  and digits outside ASCII are refused. (Note from the lead, 2026-10-14: added
  with AC-10 and AC-11.)
- An address that cannot be bound (AC-8): a port in use, or a `NOCK_HOST` that is
  not an address of the machine, is uvicorn's error: it logs the error and ends
  the process with a non-zero status. `main()` adds nothing. (Note from the lead,
  2026-10-14: added.)

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
- Other settings of `python -m nock` (command-line arguments, log level, workers,
  TLS, reload): it reads only `NOCK_HOST`, `NOCK_PORT` and spec 018's
  `NOCK_DATABASE`. (Note from the lead, 2026-10-14: added with AC-8 to AC-11.)

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
   tests; AC-7's live part runs in every engine. AC-8 and AC-9 use a page only as
   a WebSocket client and run in every engine too; AC-10 and AC-11 are not
   browser tests. (Note from the lead, 2026-10-14: the last sentence was added
   with AC-8 to AC-11.)
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

Decided by the lead on 2026-10-14, from the test-writer's review of the tests at
81a4260, under the same delegation. Each one is already part of the spec above.

8. AC-4 states the load its test runs. FX-02's across words hold at most 7
   letters, so Ana's two words hold 12 cells, not 20. She types their answers,
   then the same cells again with the next letter of the alphabet, so each of her
   20 keys changes a cell on Bob's page. The intent is kept: Ana types 2 letters
   a second for 10 seconds while six simulated players do the same, Bob watches,
   and the p95 from her key to Bob's page is at most 300 ms. Typing the 12 cells
   only was rejected: it would cut the sustained load to 6 seconds.
9. The shared `live_server` fixture moves to `server_config` once the
   implementation provides it, in a test-writer commit after the implementer's.
   Until then AC-7 starts its own server with `server_config`.
10. The production entry point gets four criteria (AC-8 to AC-11): the spec
    defined `main()`, but no criterion tested it. An empty variable counts as
    unset, because an empty host would make uvicorn listen on every interface. An
    invalid `NOCK_PORT` stops the start with a message and status 1. Falling back
    to 8000 was rejected, because a typo would then serve on a port nobody
    expects. `main()` does not check `NOCK_HOST`, since uvicorn reports an
    address it cannot bind.

## Open questions

None.
