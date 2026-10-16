---
id: "036"
title: Performance
status: done
---

# 036 - Performance

Epic E10 Quality bar (US-10.2) · Release: MVP · Epic depends on: All
FX-02 is `tests/fixtures/fx02.json` (13 by 17, spec 006), read by the `fx02_text`
fixture. The rooms engine and hub are those of specs 011 and 018, edits spec
015, the frame limit spec 037, the phone context spec 006, the live server and
the room page spec 040.

(Note from the lead, 2026-10-16: refined under the human's rule of the same day,
"Technical variables should not contain special characters". `main()` now checks
`NOCK_HOST` and `NOCK_DATABASE` too, and the message of a refused value shows it
escaped. Changed: "Frame size at the socket", "Test harness", AC-10, AC-11, the
new AC-12, "Edge cases and errors", "Out of scope", decisions 2 and 10, the new
decisions 11 to 13 and "Open questions". The tests of AC-10 to AC-12 are updated
before the implementer runs.)

(Note from the lead, 2026-10-16, after the spec-writer's report: open question 1
is answered with option (b), decision 14: `NOCK_DATABASE` also refuses the
format characters other than U+200C and U+200D and the line and paragraph
separators. An empty `NOCK_DATABASE` counts as unset, decision 15, which refines
spec 018. Decision 12 is confirmed. "Open questions" is empty again.)

(Note from the lead, 2026-10-16: refined after the review of the refinement above.
`main()` also refuses a `NOCK_HOST` name with an empty label other than the last,
or with a label of 64 characters or more, on which uvicorn crashed instead of
reporting its error (decision 16). AC-12 gains three accepted `NOCK_DATABASE`
values, of categories Co, Cn and Cs. In the note above, "the invisible format
characters" became "the format characters other than U+200C and U+200D", as in
decision 11, since those two are invisible too and stay allowed. Changed: the
`NOCK_HOST` and README bullets of "Frame size at the socket", the values bullet of
"Test harness", AC-10 to AC-12, the "Special characters" and "An address that
cannot be bound" edge cases, decision 11 and the new decision 16. The tests of
AC-10 to AC-12 are updated before the implementer runs (review of spec 036's
refinement).)

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
    127.0.0.1) and port from NOCK_PORT (default 8000), once NOCK_HOST, NOCK_PORT
    and NOCK_DATABASE have passed the checks below."""
```

- Frames of 4,097 to 8,192 bytes still reach the app and get spec 037's
  `invalid_message`; frames over 8,192 bytes are refused by uvicorn before they
  are buffered whole, and the socket is closed with code 1009.
- `main()` reads `NOCK_HOST`, `NOCK_PORT` and `NOCK_DATABASE` from `os.environ`
  each time it is called, and checks each one that is set and not empty before it
  builds a server. An unset or empty `NOCK_HOST` or `NOCK_PORT` takes its default
  (`127.0.0.1`, `8000`), so an empty host never makes uvicorn listen on every
  interface; an unset or empty `NOCK_DATABASE` is not checked, and the app then
  keeps its rooms in memory (spec 018). The values each variable takes:
  - `NOCK_HOST`: a host name or an IP address. Each character is an ASCII letter
    (`A` to `Z`, `a` to `z`), an ASCII digit (`0` to `9`), `.`, `-` or `:`, and a
    value that holds `:` is an IPv6 address that `ipaddress.IPv6Address` accepts,
    so it is written without brackets (`::1`, not `[::1]`). A value that holds no
    `:` is cut at each `.` into labels: each label holds 1 to 63 characters, and
    only the last label may be empty, so that a fully qualified name ending with
    `.` passes (`example.org.`), while `a..b`, `.example` and a label of 64
    characters are refused. `main()` passes it on to uvicorn as given. (Note from
    the lead, 2026-10-16, after the test-writer's question: "an ASCII letter, a
    digit" became "an ASCII letter (`A` to `Z`, `a` to `z`), an ASCII digit (`0`
    to `9`)". The rule did not say whether the digits are ASCII; a check written
    with `str.isdigit()` would accept a superscript two (U+00B2) or Arabic-Indic
    digits, which no host name holds.) (Note from the lead, 2026-10-16: the
    sentence on labels added with decision 16; the bullet used to check only the
    characters and the form of an IPv6 address, so that `a..b` reached uvicorn,
    which crashed on it (review of spec 036's refinement).)
  - `NOCK_PORT`: ASCII digits only, with a value from 1 to 65535.
  - `NOCK_DATABASE`: a file path without a refused character. A character is
    refused when its Unicode general category, as `unicodedata.category` gives
    it, is Cc (control characters: U+0000 to U+001F and U+007F to U+009F), Cf
    (format characters, such as U+200B ZERO WIDTH SPACE, U+FEFF and U+202E
    RIGHT-TO-LEFT OVERRIDE), Zl (U+2028 LINE SEPARATOR) or Zp (U+2029 PARAGRAPH
    SEPARATOR), except U+200C ZERO WIDTH NON-JOINER and U+200D ZERO WIDTH JOINER,
    which some scripts need inside words. Every other character is allowed:
    spaces, accents, the separators `/` and `\` and the `:` of a Windows drive,
    so `C:\Users\François\nock.sqlite3` and `/srv/jeu de mots/données/nock.sqlite3`
    are valid. `main()` does not change the variable; the app reads it when it
    starts (spec 018).

  `NOCK_HOST` and `NOCK_PORT` already refuse every character that `NOCK_DATABASE`
  refuses, since they take only ASCII letters, ASCII digits, `.`, `-` and `:`.
  Any other value makes `main()` raise `SystemExit` whose `code` is a `str`
  naming the variable and showing the value escaped (next bullet), before it
  builds a server, so `python -m nock` prints that message on stderr and exits
  with status 1. (Note from the lead, 2026-10-14: added with AC-10 and AC-11. The
  spec gave the defaults but no rule for empty or invalid values.) (Note from the
  lead, 2026-10-16: the rules of `NOCK_HOST` and `NOCK_DATABASE` added under the
  human's rule of 2026-10-16, "Technical variables should not contain special
  characters"; see decisions 11 and 13. This bullet used to say that `main()`
  reads `NOCK_HOST` and `NOCK_PORT`, that `NOCK_HOST` "is passed on as given"
  whatever it holds, and that the message names `NOCK_PORT` and "the value as
  given". The docstring of `main()` above gained its last clause. `NOCK_PORT`'s
  rule is unchanged.) (Note from the lead, 2026-10-16, after the spec-writer's
  report: `NOCK_DATABASE` used to refuse control characters only; it now also
  refuses the characters of categories Cf, Zl and Zp other than U+200C and U+200D
  (decision 14), and the sentence on `NOCK_HOST` and `NOCK_PORT` was added. "The
  app treats it as spec 018 says" became "the app then keeps its rooms in memory"
  (decision 15).) (Note from the lead, 2026-10-16, after the test-writer's
  question: in the sentence on `NOCK_HOST` and `NOCK_PORT`, "ASCII letters,
  digits" became "ASCII letters, ASCII digits", as in the `NOCK_HOST` bullet.)
- The message shows the refused value as Python's `repr()` writes it
  (`repr(value)`): between quotes, each control character as an escape (`\n`,
  `\t`, `\r`, `\x1b`, `\x85` ...), each backslash doubled, the other characters
  that `str.isprintable()` rejects escaped too (`\u2028`, `\u200b`), and accents
  as they are. So the message holds no character of categories Cc, Cf, Zl or Zp,
  `str.splitlines()` finds one line in it, and `\n` in it always stands for a
  newline, never for the two characters of a Windows path such as `C:\nock`. The
  rest of the wording is free. (Note from the lead, 2026-10-16: added; see
  decision 12.) (Note from the lead, 2026-10-16, after the spec-writer's report:
  "no control character of the value reaches the message" became "the message
  holds no character of categories Cc, Cf, Zl or Zp", with decision 14.)
- `main()` then runs
  `uvicorn.Server(server_config(nock.server.app, host=host, port=port)).run()`
  and returns when the server stops (log level `info`, `server_config`'s
  default). `src/nock/__main__.py` calls `main()` only under
  `if __name__ == "__main__":`, so importing `nock.__main__` starts nothing.
  (Note from the lead, 2026-10-14: added so that AC-10 and AC-11 can call
  `main()` in the test process with `uvicorn.Server.run` replaced.)
- The production command becomes `uv run python -m nock` (with `NOCK_DATABASE`,
  spec 018); the implementer updates `README.md` and documents `NOCK_HOST` and
  `NOCK_PORT` there, with the characters that `NOCK_HOST` and `NOCK_DATABASE`
  take, the labels of a `NOCK_HOST` name, and the fact that an empty
  `NOCK_DATABASE` keeps the rooms in memory.
  (Note from the lead, 2026-10-14: "and documents `NOCK_HOST` and `NOCK_PORT`
  there" added.) (Note from the lead, 2026-10-16: "with the characters that
  `NOCK_HOST` and `NOCK_DATABASE` take" added with decision 11, and "the fact that
  an empty `NOCK_DATABASE` keeps the rooms in memory" with decision 15.) (Note
  from the lead, 2026-10-16: "the labels of a `NOCK_HOST` name" added with
  decision 16 (review of spec 036's refinement).)
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
  waits on a `threading.Event` while a flag is set. AC-6's second case does not use
  it: its registry has the normal in-memory store, and its test sends one message
  at a time, waiting after each until A's recording `send_text` holds the answer
  to it, for at most 1 s (a missing answer fails the test). (Note from the lead,
  2026-10-15: added with the second case of AC-6.)
- Live server built with `server_config` (AC-7): until the shared `live_server`
  is switched (see "Frame size at the socket"), the test starts its own server
  the way that fixture does (the same `room_registry` and `catalogue`, the built
  client, failing when it is missing, a free port of 127.0.0.1), but with
  `uvicorn.Server(server_config(app, log_level="warning"))`. After the switch,
  either server will do. (Note from the lead, 2026-10-14: added; the tests at
  81a4260 do this in `production_live_server`.)
- Production entry point (AC-8 to AC-12). Subprocess (AC-8, AC-9): a SQLite file
  in `tmp_path` holds a FX-01 room registered by
  `RoomRegistry(store=RoomStore(path))`, after which the registry, then the
  store, are closed. The test runs `[sys.executable, "-m", "nock"]` (the
  interpreter that `uv run` gives the tests) with its own environment plus
  `NOCK_DATABASE` (the file) and `NOCK_PORT` (a free port, bound on 127.0.0.1
  with port 0, then released), and without `NOCK_HOST`. It polls
  `GET http://127.0.0.1:<port>/` for up to 10 seconds, opens the sockets from a
  Playwright page on that origin as AC-7 does, and stops the process at the end
  (terminate, then kill). In the test process (AC-10 to AC-12): the test imports
  `nock.__main__`, sets or deletes the three variables `NOCK_HOST`, `NOCK_PORT`
  and `NOCK_DATABASE` with `monkeypatch` (each one a case does not set is
  deleted), and replaces `uvicorn.Server.run` (`monkeypatch.setattr`) with a
  recorder that keeps `self.config` and returns None. (Note from the lead,
  2026-10-14: added with AC-8 to AC-11.) (Note from the lead, 2026-10-16: AC-12
  and `NOCK_DATABASE` added, so that a variable left in the environment that runs
  the tests cannot change a case.)
- Values in AC-10 to AC-12 are Python string literals, or expressions that join
  or repeat them (`"0" * 5000 + "8000"`, and `"a" * 64 + ".example"`, which is 64
  `a` followed by `.example`): `"8000\n"` ends with a newline (U+000A), `"\x1b"`
  is U+001B ESCAPE and `"\x85"` is U+0085; a raw literal such as
  `r"C:\Users\François\nock.sqlite3"` holds backslashes, not escapes.
  `repr(value)` is what Python's `repr()` returns for the value. No case sets
  U+0000, which `os.environ` refuses (`ValueError: embedded null byte`).
  `monkeypatch.setenv` accepts the three values of AC-12 written with `\ue000`,
  `\u0378` and `\udce9`: it sets `os.environ`, which on Linux and macOS stores
  U+DCE9 as the byte 0xE9 (`surrogateescape`) and gives U+DCE9 back when the
  variable is read. The recorder never starts the app, so no case opens or
  creates the file named by `NOCK_DATABASE`. (Note from the lead, 2026-10-16:
  added with decisions 11 to 13.) (Note from the lead, 2026-10-16: "or
  expressions that join or repeat them", with its two examples, and the sentence
  on `monkeypatch.setenv` added, with decision 16 and the new values of AC-12;
  the bullet used to call every value a string literal (review of spec 036's
  refinement).)
- The app's store (AC-12, second part): the test replaces `nock.server.RoomStore`
  (`monkeypatch.setattr`) with a `RoomStore` subclass whose `__init__` appends
  `str(path)` to a list, then calls `RoomStore.__init__`. The app of
  `create_app(dist_dir=tmp_path)` builds its store with that name when it starts
  (spec 018), so `with TestClient(app):` makes the subclass record the path, and
  the store is closed when the block ends. (Note from the lead, 2026-10-16, after
  the spec-writer's report: added with decision 15.)

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-10.2.1) (browser with live server, phone profile, Chromium only) FX-02 is interactive within 2.5 seconds on a mid-range phone over 4G. For a room registered on FX-02 and the automatic join of the harness, three cold loads of `/r/<code>` (a new context each) each record a `nock:interactive` mark; the median of their `startTime` values is at most 2500 ms. At the mark the room page has `data-status="joined"` and `data-grid="13x17"` and holds 221 `cell` elements; after the third load, tapping a letter cell and pressing `A` shows `A` in it.
- **AC-2** (AC-10.2.2) (browser with live server, phone profile, Chromium only) A typed letter shows locally within 50 ms. On a FX-02 room joined as in AC-1, the player taps a letter cell starting an across word and types 40 letters with `page.keyboard.press`, 250 ms apart, re-tapping the start of another word when the selection reaches the end of one; for each key, the time from its `keydown` to the first change of the typed cell's `data-letter` to that letter is measured in the page; the p95 of the 40 times is at most 50 ms.
- **AC-3** (AC-10.2.3) (WebSocket, simulated clients) With 8 players each typing 2 letters a second, the server keeps its share of spec 015 AC-1's budget. Eight simulated clients join one FX-02 room (`RoomConfig()` defaults, so spec 037's limit of 20 a second applies); each sends one `edit_letter` every 500 ms on a random letter cell (`random.Random(36)`) for 10 seconds, the eight starting 62.5 ms apart, while reading its socket. For each of the 160 edits and each of the 7 other clients, the relay time is from the sender's send to that client's receipt of the `letter_changed` with the edit's seq (known from the sender's own answer), with `time.monotonic()`. Every edit is answered with its `letter_changed` (no `error`), every client receives all 160, and the p95 of the 1,120 relay times is at most 100 ms (spec 015 decision 1).
- **AC-4** (AC-10.2.3) (browser with live server and simulated clients, CPU throttling, Chromium only) Under the same load, a letter typed in one page appears in another within 300 ms. Two pages with spec 006's phone options and `Emulation.setCPUThrottlingRate` 4 (no network emulation: the network share is accounted by spec 015 decision 1) join a FX-02 room as `Ana` and `Bob`. Ana's words are FX-02's two longest across words, the first by row-major order of its first cell among words of equal length: `OREILLE` from (1, 2) to (1, 8) and `TRAIT` from (4, 6) to (4, 10), 12 cells. Six simulated clients then join; each sends one `edit_letter` every 500 ms on a random letter cell outside Ana's words (`random.Random(36)`), the six starting 62.5 ms apart, while reading its socket. All six are typing before Ana's first key (she starts 1 second after the load) and go on until Bob's page shows her last letters, so seven of the eight players type 2 letters a second while Bob watches. Ana types 20 keys with `page.keyboard.press`, 500 ms apart, tapping the first cell of a word before its first key: the answers of her two words (12 keys), then the same cells again from the start of `OREILLE`, each with the letter after its answer letter in the alphabet (Z gives A), so that every key changes its cell: `PSFJMMF`, then `U` at (4, 6) (8 keys). For each key, the time from Ana's `keydown` to the first change after it of the same cell's `data-letter` to that key's letter in Bob's page is measured (in-page timing). All 20 letters arrive in Bob's page, the p95 of the 20 times is at most 300 ms, and every edit of the simulated clients is answered with its `letter_changed` (no `error`). (Note from the lead, 2026-10-14: reworded to state the load that the tests at 81a4260 run. It used to say that Ana "types 20 letters 500 ms apart on two across words" while six clients type "as in AC-3", but FX-02's two longest across words hold 12 cells. Ana now types their answers, then retypes the same cells with other letters; the load runs while she types instead of for AC-3's 10 seconds; the answers to the load are checked. The intent is unchanged: 2 letters a second, sustained, and 300 ms from Ana's key to Bob's page.)
- **AC-5** (new, from spec 037's review) (hub test) A client that never reads its socket is disconnected instead of growing a queue. With `RoomRegistry(config=RoomConfig(max_outbound_messages=20, max_edits_per_second=1000))` and a FX-01 room: connection A joins with a stuck `send_text`; connection B joins with a recording `send_text`; B sends 30 `edit_letter` messages in three groups of 10, sending the next group only after its `send_text` has recorded the 10 `letter_changed` events of the previous one. A stalls during the second group (see "Edge cases and errors"). Then, within 1 s of B sending the last edit of the second group, A's `close` is called exactly once, with `STALLED_CLOSE_CODE` (4507), and A's `run_writer` returns; B receives its 30 `letter_changed` events and a `player_state_changed` with A's player id and state `disconnected`; A's `send_text` was called once only (the snapshot that never completed), also after B sends 10 more edits. (Note from the lead, 2026-10-14: B's 30 edits used to go out in one burst, which the criterion never required. `max_outbound_messages=20` applies to B too: the burst queued 30 `letter_changed` for B within milliseconds, and when B's `run_writer` was not scheduled in that window, B was itself closed as stalled (4507), so the test failed intermittently. In groups of 10, B never has more than 11 messages waiting (10 `letter_changed` plus A's `player_state_changed`), whatever the scheduling. A still stalls during the second group, and the 1 s now starts after that group.)
- **AC-6** (new, from spec 037's review) (hub test) A client that sends faster than its room applies is closed, and the room keeps working; a client whose inputs the room applies as they come is not. An input counts toward `max_inbound_pending` from the moment its connection posts it until the room task has finished applying it, and it stops counting then, however many inputs the connection sent before. (Note from the lead, 2026-10-15: this sentence added; the second case below tests it.) First case, a blocked room: with `RoomConfig(max_inbound_pending=5, max_edits_per_second=1000)`, the blocking store, and a FX-01 room where A joined (recording writer): the store starts blocking; A submits `EditLetter(row=1, column=0, letter="T")` (its step waits in `append`), then 7 `Ping` messages; then, while the store is still blocked, A's `close` is called once with `FLOOD_CLOSE_CODE` (1008). After the store is released, the room's state has `T` at (1, 0), and a new connection C can join the room and receives a `Snapshot` holding `T` at (1, 0). Second case, inputs applied as they come: with `RoomConfig(max_inbound_pending=5, max_edits_per_second=1000)`, the registry's normal in-memory store (not the blocking one), and a FX-01 room where A joined (recording writer): A sends 20 messages one at a time, the n-th being `EditLetter(row=1, column=0, letter=L)` with `L` the n-th letter of the alphabet (`A` to `T`), each sent only after the answer to the previous one (the first, after A's `Snapshot`) has reached A's writer, and every answer reaching A's writer within 1 s of its message. Then A's recording holds, after its `Snapshot`, a `LetterChanged` for each of the 20 messages, in order, with the letter sent, at (1, 0), with the player id that the `Snapshot` gives as `you`, and no `ErrorMessage`; A's `close` has never been called; and the room's state has `T` at (1, 0). (Note from the lead, 2026-10-15: second case added. The first case alone does not show that an input stops counting: a connection that counted every input it ever sent, and never subtracted one, would pass it, and would close every honest player after `max_inbound_pending` messages. `EditLetter` is the message used because spec 015 gives every edit exactly one answer to its sender, a `letter_changed` even when the cell does not change, and the room task applies it through the store like any step.)
- **AC-7** (new, from spec 037's review) (Python; WebSocket with live server) Oversized frames are refused at the socket. Python: `server_config(app).ws_max_size == WS_MAX_SIZE_BYTES == 8192`. Live server built with `server_config` (see "Test harness"), from a Playwright page with `page.evaluate` opening a `WebSocket` to a FX-01 room: a text frame of 9,000 bytes makes the server close the socket with code 1009; on a second socket, after a join, a text frame of 8,000 bytes is answered with an `error` whose `code` is `invalid_message` and the socket stays open (a following `ping` gets a `pong`). This criterion runs in every engine. (Note from the lead, 2026-10-14: "the fixture built with `server_config`" became "built with `server_config` (see "Test harness")": until the shared fixture is switched, the test starts its own server.)
- **AC-8** (new, from the review of this spec's tests) (subprocess; WebSocket from a Playwright page, every engine) `python -m nock` serves the app on the port of `NOCK_PORT`. Given a SQLite file holding a FX-01 room (see "Test harness"), when the test runs `python -m nock` with `NOCK_DATABASE` set to that file, `NOCK_PORT` set to a free port and `NOCK_HOST` unset, then within 10 seconds `GET http://127.0.0.1:<port>/` answers 200 with the built client, and a socket to the room's `/api/rooms/<code>/ws` that sends a `join` receives a `snapshot` as its first message (the room is loaded from the file as after spec 018 AC-1's restart; an unknown code would be closed with 4404). (Note from the lead, 2026-10-14: added; see decision 10.)
- **AC-9** (new, from the review of this spec's tests) (subprocess; WebSocket from a Playwright page, every engine) `python -m nock` refuses oversized frames at the socket, which shows that it runs `server_config`. On a server started as in AC-8, a socket to the room that sends a text frame of 9,000 bytes is closed with code 1009 and receives no message; with uvicorn's default `ws_max_size` the frame would reach the app and get spec 037's `invalid_message`. (Note from the lead, 2026-10-14: added; see decision 10.)
- **AC-10** (new, from the review of this spec's tests) (Python, `uvicorn.Server.run` replaced) `main()` hands uvicorn the address of `NOCK_HOST` and `NOCK_PORT`, 127.0.0.1 and 8000 by default. With the recorder of the "Test harness", `main()` returns after one call of `run`, whose server's `config` has `app` `nock.server.app` (the same object), `ws_max_size` 8192, and: `host` `"127.0.0.1"` and `port` 8000 with neither variable set; the same with both set to `""`; `host` `"0.0.0.0"` and `port` 9123 with `NOCK_HOST="0.0.0.0"` and `NOCK_PORT="9123"`; `host` `"127.0.0.1"` and `port` 8000 with `NOCK_HOST` unset and `NOCK_PORT` set to 5,000 `"0"` characters followed by `"8000"` (`"0" * 5000 + "8000"`, 5,004 characters). (Note from the lead, 2026-10-14: added; see decision 10.) (Note from the lead, 2026-10-15: the last case added. The final review found `main()` raising an uncaught `ValueError` for such a value; see "Edge cases and errors", empty and invalid variables.) With `NOCK_PORT` unset, the `config` has `port` 8000 and `host` equal to `NOCK_HOST` as given for each `NOCK_HOST` of `"localhost"`, `"Nock-1.example.org"`, `"example.org."`, `"a" * 63 + ".example"`, `"::"`, `"::1"`, `"fe80::1"`, `"2001:DB8::1"` and `"::ffff:192.0.2.1"` (ASCII letters of both cases, ASCII digits, `.`, `-`, a name ending with `.`, a label of 63 characters, and `:` in IPv6 addresses written without brackets). (Note from the lead, 2026-10-16: this sentence added with decisions 11 and 13, so that the new checks of AC-11 refuse none of the values `NOCK_HOST` takes.) (Note from the lead, 2026-10-16, after the test-writer's question: "digits" became "ASCII digits" in the brackets. The values are unchanged: all of them are ASCII.) (Note from the lead, 2026-10-16: `"example.org."` and `"a" * 63 + ".example"` added with decision 16, and "a name ending with `.`, a label of 63 characters" in the brackets: a check of the labels that refused the empty last label of a fully qualified name, or a label of 63 characters, now fails AC-10 (review of spec 036's refinement).)
- **AC-11** (new, from the review of this spec's tests) (Python, `uvicorn.Server.run` replaced) An invalid `NOCK_PORT`, `NOCK_HOST` or `NOCK_DATABASE` stops `main()` before any server runs, with a one-line message that names the variable and shows the value escaped. With the recorder of the "Test harness" and the two other variables unset, for each value below, `main()` raises `SystemExit` whose `code` is a `str` containing the variable's name and `repr(value)`, with no character of Unicode general category Cc, Cf, Zl or Zp and one item in its `splitlines()`, and `run` is never called. `NOCK_PORT`: `"abc"`, `"0"`, `"65536"`, `"-1"`, `"8000.0"`, `" 8000"`, `"8000\n"`, `"\t8000"`, `"80\x1b[2J00"`, `"8000\x7f"`, `"8000\x85"` and `"8000\x9b"`. `NOCK_HOST`: `"localhost\n"`, `"\t127.0.0.1"`, `"local\x1b[2Jhost"`, `"127.0.0.1\x7f"`, `"::1\x85"`, `"localhost\u2028"`, `" "`, `"local host"`, `"[::1]"`, `"localhost:8000"`, `"127.0.0.1:8000"`, `"fe80::1%eth0"`, `"my_host"`, `"bücher.example"`, `"\u0661\u0662\u0667.0.0.1"`, `"\uff11\uff12\uff17.0.0.1"`, `"localhost\u00b2"`, `"0.0.0.0/0"`, `"a..b"`, `"."`, `".example"`, `"example.."` and `"a" * 64 + ".example"`. `NOCK_DATABASE`: `"\n"`, `"data/nock.sqlite3\n"`, `"\tdata/nock.sqlite3"`, `r"C:\Users\François\nock.sqlite3" + "\r\n"`, `"nock\x01.sqlite3"`, `"nock\x1b[2J.sqlite3"`, `"nock\x1f.sqlite3"`, `"nock\x7f.sqlite3"`, `"nock\x85.sqlite3"`, `"nock\x9f.sqlite3"`, `"nock\u200b.sqlite3"`, `"\ufeffdata/nock.sqlite3"`, `"nock\u202e.sqlite3"`, `"nock\u2028.sqlite3"`, `"nock\u2029.sqlite3"`, `"nock\xad.sqlite3"` and `"nock\U000e0001.sqlite3"`. (Note from the lead, 2026-10-14: added; see decision 10.) (Note from the lead, 2026-10-16: `NOCK_HOST`, `NOCK_DATABASE` and the `NOCK_PORT` values from `"8000\n"` on added with decisions 11 to 13. The message used to contain `NOCK_PORT` and "the value as given"; it now contains `repr(value)` (decision 12), which for the first six `NOCK_PORT` values holds the value as given, between quotes.) (Note from the lead, 2026-10-16, after the spec-writer's report: the `NOCK_DATABASE` values from `"nock\u200b.sqlite3"` on added with decision 14; U+00AD SOFT HYPHEN and U+E0001 LANGUAGE TAG are format characters too, the second outside the first 65,536 code points, so the rule is the category, not a list. "No character of Unicode category Cc" in the message became "of Unicode general category Cc, Cf, Zl or Zp", which `repr()` never leaves raw.) (Note from the lead, 2026-10-16, after the test-writer's question: the three `NOCK_HOST` values after `"bücher.example"` added, since the digits of `NOCK_HOST` are ASCII digits (decision 11): `127` written with ARABIC-INDIC DIGIT ONE, TWO and SEVEN (U+0661, U+0662, U+0667), `127` written with FULLWIDTH DIGIT ONE, TWO and SEVEN (U+FF11, U+FF12, U+FF17), each followed by `.0.0.1`, and `localhost` followed by SUPERSCRIPT TWO (U+00B2). `str.isdigit()` is true of all of these characters, so a check written with it would let them through. The list used to go from `"bücher.example"` straight to `"0.0.0.0/0"`.) (Note from the lead, 2026-10-16: the five `NOCK_HOST` values after `"0.0.0.0/0"` added with decision 16: an empty label other than the last (`"a..b"`, `"."`, `".example"`, `"example.."`), and a label of 64 characters, `"a" * 64` followed by `.example`. Python's `idna` codec refuses each of them, and uvicorn crashed on them instead of reporting its error. The `NOCK_HOST` list used to end with `"0.0.0.0/0"` (review of spec 036's refinement).)
- **AC-12** (new, from the human's rule of 2026-10-16) (Python, `uvicorn.Server.run` replaced; app started with `TestClient`) A `NOCK_DATABASE` without a refused character never stops `main()`, whatever spaces, accents, joiners and path separators it holds, and an empty one keeps the rooms in memory. With the recorder of the "Test harness" and `NOCK_HOST` and `NOCK_PORT` unset, for `NOCK_DATABASE` unset and for each of `""`, `"data/nock.sqlite3"`, `"~/nock.sqlite3"`, `"/srv/jeu de mots/données/nock.sqlite3"`, `"/srv/nock\u00a0data/nock.sqlite3"`, `"/srv/nock\u200cdata/nock.sqlite3"`, `"/srv/nock\u200ddata/nock.sqlite3"`, `"/srv/nock\ue000data/nock.sqlite3"`, `"/srv/nock\u0378data/nock.sqlite3"`, `"/srv/donn\udce9es/nock.sqlite3"`, `r"C:\Users\François\nock.sqlite3"`, `r"C:\temp\nock.sqlite3"` and `":memory:"`, `main()` returns after one call of `run`, whose server's `config` has `host` `"127.0.0.1"` and `port` 8000, and `NOCK_DATABASE` in `os.environ` is afterwards what it was before the call (still unset when it was unset). App: with `NOCK_DATABASE` unset, and with it set to `""`, the app of `create_app(dist_dir=tmp_path)`, started and stopped by `with TestClient(app):` while `nock.server.RoomStore` is the recording subclass of the "Test harness", builds at least one store, every one with the path `":memory:"` and none with `""` (spec 018). (Note from the lead, 2026-10-16: added with decision 11. The two Windows paths hold a backslash followed by `n` or `t`, two characters each, not a newline or a tab; U+00A0 NO-BREAK SPACE, just above the control characters, is a space.) (Note from the lead, 2026-10-16, after the spec-writer's report: the U+200C and U+200D cases added with decision 14, and the app part with decision 15; the first sentence used to say "without a control character" and said nothing of an empty value. Today the app hands `""` to `RoomStore`, so the app part fails until the implementer changes it.) (Note from the lead, 2026-10-16: the three values after `"/srv/nock\u200ddata/nock.sqlite3"` added, so that a check that refuses every general category starting with C fails AC-12; such a check passed every earlier value. `"\ue000"` is U+E000, a private use character (Co). `"\u0378"` is U+0378, a code point that Unicode leaves unassigned (Cn). `"\udce9"` is U+DCE9, a lone surrogate (Cs): this is how Python's `os.environ` shows, on Linux and macOS, a path whose bytes are not UTF-8, a Latin-1 `é` (the byte 0xE9) arriving as U+DCE9 (`surrogateescape`); the app then opens the file with the original bytes. The list used to go from `"/srv/nock\u200ddata/nock.sqlite3"` straight to `r"C:\Users\François\nock.sqlite3"` (review of spec 036's refinement).)

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
- Pacing (AC-5): before B's first edit, A's queue holds B's `player_joined`
  (spec 012), and its snapshot too unless the stuck `send_text` has already taken
  it; each edit of B then adds one `letter_changed`. The delivery made while 20
  messages wait is therefore the `letter_changed` of B's 20th edit (snapshot
  taken) or 19th (snapshot still queued): the second group either way. B's queue
  never holds more than one group's 10 `letter_changed` plus A's
  `player_state_changed`: 11, below the bound of 20. (Note from the lead,
  2026-10-14: added with the paced wording of AC-5.)
- Flood close (AC-6): 1008 is not final either; an honest page never reaches 100
  unapplied inputs (edits are limited to 20 a second and pings come every 2 s).
- Pacing (AC-6, second case): the room task queues the answer to a message before
  it counts that message as applied, so when A's writer has recorded the answer to
  message `n`, message `n` may still count for a moment. Message `n + 1` is applied
  only after that, so at most 2 inputs of A count at any time, below the bound of 5,
  whatever the scheduling. A connection that never stops counting its inputs finds
  5 counted at A's 5th edit (the join counts too) and is closed: the answer to
  that edit never comes, and the test fails on the wait. (Note from the lead,
  2026-10-15: added with the second case of AC-6.)
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
  port); leading zeros are accepted, however many (`"08000"`, and 5,000 zeros
  followed by `"8000"`, which is 8000); signs, spaces, decimal points and digits
  outside ASCII are refused. (Note from the lead, 2026-10-14: added with AC-10
  and AC-11.) (Note from the lead, 2026-10-15: "however many" added. Python's
  `int()` refuses a string of more than 4,300 digits with `ValueError` (its default
  limit), so the check must not hand such a string to `int()` as written, and it
  must not refuse it either: the value of 5,000 zeros followed by `"8000"` is
  8000 (AC-10). The range rule applies to the number the digits make, whatever
  the zeros before them: 5,000 zeros followed by `"70000"` is refused, as
  `"70000"` is. The final review found `main()` raising an uncaught `ValueError`
  for a `NOCK_PORT` of that length.)
- Special characters (AC-10 to AC-12). (Note from the lead, 2026-10-16: added
  with decisions 11 to 13.)
  - Only an unset or empty variable escapes the checks. Any other value is
    checked: `" "` is refused for `NOCK_HOST` and `NOCK_PORT`, and `"\n"` for all
    three.
  - U+0000 cannot reach `os.environ` (Python refuses it with `ValueError:
    embedded null byte`, and an environment cannot carry it), so no test sets
    it; the rules refuse it all the same.
  - `NOCK_HOST`: `%` is refused, so an IPv6 zone (`fe80::1%eth0`) cannot be
    given; `_` is refused, as host names (RFC 1123) do not use it; a name with
    letters outside ASCII is given in its ASCII form (`xn--bcher-kva.example`
    for `bücher.example`). Digits outside ASCII are refused, as letters outside
    ASCII are: a superscript two (U+00B2) or an Arabic-Indic digit is not a
    digit of a host name. (Note from the lead, 2026-10-16, after the
    test-writer's question: this sentence added, with the ASCII digits of the
    `NOCK_HOST` bullet of "Frame size at the socket".) In a value without `:`,
    an empty label other than the last is refused (`a..b`, `.`, `.example`,
    `example..`), as is a label of 64 characters or more
    (`"a" * 64 + ".example"`), while a name ending with `.` (`example.org.`) and
    a label of 63 characters pass (decision 16). Nothing else is checked in a
    name: a label may start or end with `-` (`-`, `a-.b`), and the whole name
    has no length limit of its own (a name of 320 characters in labels of 63
    passes); such a name ends at uvicorn's error when it does not resolve ("An
    address that cannot be bound"). (Note from the lead, 2026-10-16: the last
    two sentences added with decision 16 (review of spec 036's refinement).)
  - `NOCK_DATABASE`: every character outside the refused set passes `main()`'s
    check: U+200C and U+200D, the other spaces (category Zs, such as U+00A0
    NO-BREAK SPACE), the characters of the other categories that start with C
    (private use, Co, such as U+E000; unassigned, Cn, such as U+0378; lone
    surrogates, Cs, such as U+DCE9, which is how `os.environ` gives a byte of a
    path that is not UTF-8, AC-12), and the characters that Windows refuses in a
    file name (`*`, `?`, `|`); opening the file stays the app's job (spec 018).
    (Note from the lead, 2026-10-16, after the spec-writer's report: this used to
    say that every character that is not a control character passes, the
    invisible ones of open question 1 included; decision 14.) (Note from the
    lead, 2026-10-16: the characters of categories Co, Cn and Cs added, with the
    new values of AC-12 (review of spec 036's refinement).)
  - Several invalid variables: `main()` stops with the message of one of them.
    Which one is not specified; each case of AC-11 sets a single variable.
- An address that cannot be bound (AC-8): a port in use, or a `NOCK_HOST` that is
  not an address of the machine, is uvicorn's error: it logs the error and ends
  the process with a non-zero status. `main()` adds nothing. (Note from the lead,
  2026-10-14: added.) `main()` checks only the characters of `NOCK_HOST`, the
  form of an IPv6 address and the labels of a name (AC-11), so a name whose
  labels are fine but which does not resolve, or does not name an address of the
  machine, such as `-`, `a-.b` or `1.2.3`, also ends here. (Note from the lead,
  2026-10-16: last sentence added with decision 11.) A name with an empty label
  other than the last, or with a label of 64 characters or more, no longer
  reaches uvicorn: there, `getaddrinfo` encodes the host with Python's `idna`
  codec, which raises `UnicodeError` on such a label, and uvicorn, which catches
  only `OSError` at that point, ended with two tracebacks and status 1 instead of
  its error (decision 16). (Note from the lead, 2026-10-16: in the sentence
  before, "the characters of `NOCK_HOST` and the form of an IPv6 address" became
  "the characters of `NOCK_HOST`, the form of an IPv6 address and the labels of a
  name", and "a name that does not resolve, such as `a..b` or `-`" became the
  names whose labels are fine; the last sentence added with decision 16 (review
  of spec 036's refinement).)

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
- Checks of `NOCK_DATABASE` other than its characters (that its folder exists,
  that the file can be opened): the app's start, spec 018. The variables of specs
  033 and 038 follow the rules of those specs. (Note from the lead, 2026-10-16:
  added with decision 11.) (Note from the lead, 2026-10-16, after the
  spec-writer's report: "other than control characters" became "other than its
  characters", with decision 14.)

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
   a WebSocket client and run in every engine too; AC-10 to AC-12 are not
   browser tests. (Note from the lead, 2026-10-14: the last sentence was added
   with AC-8 to AC-11.) (Note from the lead, 2026-10-16: "AC-10 and AC-11"
   became "AC-10 to AC-12".)
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
    expects. `main()` does not check whether `NOCK_HOST` can be bound, since
    uvicorn reports an address it cannot bind. (Note from the lead, 2026-10-16:
    the last sentence used to say that `main()` does not check `NOCK_HOST`;
    since decision 11 it checks its characters.)

Decided by the lead on 2026-10-16, under the human's rule of the same day,
"Technical variables should not contain special characters", and the human's
confirmation that `NOCK_HOST` and `NOCK_DATABASE` must refuse control characters
too, not only `NOCK_PORT`. Each one is already part of the spec above.

11. No special characters in the variables of `python -m nock` (AC-10 to AC-12).
    `main()` checks the three variables it reads before it builds a server; an
    unset or empty one is not checked and takes its default (decision 15 for
    `NOCK_DATABASE`). `NOCK_PORT` keeps its rule. `NOCK_HOST` takes ASCII
    letters, ASCII digits, `.`, `-` and, in an IPv6 address, `:`, and nothing
    else, and the labels of a name hold 1 to 63 characters, the last one
    possibly empty (decision 16); whether a name resolves stays uvicorn's report
    (decision 10).
    `NOCK_DATABASE` is a path, and a path may hold almost any character: spaces,
    accents and the separators of both systems are allowed
    (`C:\Users\François\nock.sqlite3` is valid), and a control character
    (Unicode category Cc) anywhere in it is refused, as are the format
    characters other than U+200C and U+200D and the line and paragraph
    separators (decision 14). A refused value stops the start with status 1 and
    a one-line message naming the variable, as `NOCK_PORT` already did. (Note
    from the lead, 2026-10-16, after the spec-writer's report: "keeps today's
    meaning" became "takes its default (decision 15 for `NOCK_DATABASE`)", and
    "only a control character (Unicode category Cc) anywhere in it is refused"
    became "a control character ... is refused, as are the invisible characters
    of decision 14".) (Note from the lead, 2026-10-16, after the test-writer's
    question: "ASCII letters, digits" became "ASCII letters, ASCII digits", as
    in the `NOCK_HOST` bullet of "Frame size at the socket".) (Note from the
    lead, 2026-10-16: ", and the labels of a name hold 1 to 63 characters, the
    last one possibly empty (decision 16)" added; "as are the invisible
    characters of decision 14" became "as are the format characters other than
    U+200C and U+200D and the line and paragraph separators (decision 14)",
    since U+200C and U+200D are invisible too and stay allowed, and some format
    characters, such as U+0600 ARABIC NUMBER SIGN, are visible and refused all
    the same (review of spec 036's refinement).)
12. Refused values show escaped (AC-11). This answers the question that the
    tests of AC-11 left open in their case of a port ending with a newline:
    should the message show a control character raw or escaped? (It was listed
    in `docs/handoff.md`, not in this spec.) Pick: the message holds
    `repr(value)`, for the three variables. A raw newline would split the
    message, and a raw ESC (U+001B) or CSI (U+009B) could drive the operator's
    terminal or forge a log line. `repr()` is used whole, rather than an escape
    of control characters alone, because it also doubles backslashes, so that
    `\n` in a message always means a newline and never the two characters of a
    Windows path such as `C:\nock`, and because it escapes the line separators
    U+2028 and U+2029 too. Leaving the value out was rejected: the operator has
    to see what is wrong, and unlike spec 038's operator token these values are
    not secrets.
13. IPv6 addresses without brackets (AC-10, AC-11). uvicorn takes the bare form:
    it hands the host to asyncio's `loop.create_server`, which resolves it with
    `getaddrinfo`, and `getaddrinfo` does not read `[::1]`; uvicorn adds the
    brackets itself when it prints the URL of a host that holds `:`. A bracketed
    value therefore makes uvicorn fail at start, and no spec or test accepted
    one, so `[` and `]` are refused with the other characters. `:` is allowed
    only in a value that `ipaddress.IPv6Address` accepts, so that a port written
    into the host (`localhost:8000`) gets `main()`'s message instead of uvicorn's
    error at start.

Decided by the lead on 2026-10-16, after the spec-writer's report, under the same
rule. Decision 12 is confirmed as written. Each one is already part of the spec
above.

14. Invisible characters in `NOCK_DATABASE` (former open question 1; AC-11,
    AC-12). Control characters alone left out the characters that nobody sees
    and that make the path name another file than the one meant, so that the
    server may start on a new, empty database. Options: (a) refuse control
    characters (Cc) only; (b) also refuse the line and paragraph separators and
    the format characters. Pick: (b), the reading closest to "no special
    characters". The rule is exact: a character is refused when
    `unicodedata.category` gives Cc, Cf, Zl or Zp, except U+200C ZERO WIDTH
    NON-JOINER and U+200D ZERO WIDTH JOINER, which some scripts need inside
    words (Persian, for example) and emoji sequences use. `NOCK_HOST` and
    `NOCK_PORT` refuse all of these already, since they take only ASCII letters,
    ASCII digits, `.`, `-` and `:`. (Note from the lead, 2026-10-16, after the
    test-writer's question: "ASCII letters, digits" became "ASCII letters, ASCII
    digits", as in decision 11.)
15. An empty `NOCK_DATABASE` counts as unset (AC-12), like the other technical
    variables: the app keeps its rooms in memory (`":memory:"`). The app used to
    hand `""` to `RoomStore`, which SQLite opens as a private temporary file,
    against the rule that an empty variable counts as unset (README, specs 033
    and 036). This refines spec 018 (its "`nock.server`" bullet and decision 7,
    with a dated note there). The test is in AC-12 of this spec, since no
    criterion of spec 018 covers the database location.

Decided by the lead on 2026-10-16, after the review of spec 036's refinement,
under the same rule. It is already part of the spec above.

16. Labels of `NOCK_HOST` (AC-10, AC-11). The review of this spec's refinement
    found that a name such as `a..b` did not end at uvicorn's error, as "An
    address that cannot be bound" said. uvicorn hands the host to asyncio's
    `loop.create_server` (decision 13), whose `getaddrinfo` first encodes it with
    Python's `idna` codec. On a name in ASCII, that codec raises `UnicodeError`
    when a label other than the last is empty, or when a label holds 64
    characters or more; uvicorn catches only `OSError` there, so it ended with
    two tracebacks and status 1 instead of its one-line error. The lead checked
    the codec: it refuses `a..b`, `.`, `.example`, `..`, `example..` and a label
    of 64 characters, and accepts `example.`, `localhost.`, a label of 63
    characters, `-`, `a-.b`, `1.2.3` and a name of 320 characters made of
    63-character labels. Options: (a) leave these names to uvicorn; (b) refuse in
    `main()` exactly the labels that the codec refuses; (c) a full host name
    syntax (RFC 1123: no label that starts or ends with `-`, at most 253
    characters in all). Pick: (b), with the usual message (decision 12). A value
    that holds no `:` is cut at each `.` into labels; each label holds 1 to 63
    characters, and only the last label may be empty, so that a fully qualified
    name ending with `.` (`example.org.`) passes. A value that holds `:` keeps
    the IPv6 rule (decision 13): an address that passes it (its characters, then
    `ipaddress.IPv6Address`) never holds an empty label or one of 64 characters.
    (a) leaves a crash where this spec promises uvicorn's report (decision 10);
    (c) would refuse names such as `-` and `a-.b`, which uvicorn already reports
    as names that do not resolve, and no crash calls for it. The whole name has
    no length limit of its own, since the codec sets none.

## Open questions

None. (Note from the lead, 2026-10-16, after the spec-writer's report: open
question 1, on the invisible characters of `NOCK_DATABASE`, was answered with
option (b); it is decision 14.)
