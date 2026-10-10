---
id: "040"
title: Web client shell
status: draft
---

# 040 - Web client shell

Build plan phase 3 (client toolchain and shell) · Release: MVP · No backlog story:
this is the client and server frame that specs 004 and 006 onwards fill in.
The FX-01 reference grid is in `specs/_reference.md`. The stack, the modeling rules
and the toolchain are in `specs/_architecture.md`. The messages are those of spec
039 (`nock.protocol`).

## Goal

Players reach Nock through a browser. This spec puts the frame in place: FastAPI
serves the built Svelte app and the room WebSocket, the app has a catalogue page
and a room page, and the room page joins the room, keeps the latest snapshot and
applies later events in `seq` order. Every word the user reads comes from one
French file, so that later specs add text in one place.

## Public interface

### Python: `src/nock/server.py`

```python
# src/nock/server.py
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from nock.grid import Grid

WEB_DIST_DIR: Path                      # <repository root>/web/dist
ROOM_CODE_PATTERN: str = r"^[A-Z0-9]{6}$"
ROOM_NOT_FOUND_CLOSE_CODE: int = 4404   # WebSocket close code, unknown room


class RoomRegistry:
    """In-memory rooms of this process, by room code.

    A seam for tests until spec 011 (room creation) replaces or extends it.
    A plain class, not a Pydantic model: it is a mutable service, not data.
    """

    def __init__(self) -> None: ...

    def register_room(self, grid: Grid) -> str:
        """Register a new room on `grid` and return its fresh room code.

        The code matches ROOM_CODE_PATTERN and differs from every code already
        registered in this registry.
        """

    def find_room(self, code: str) -> Grid | None:
        """Return the grid of the room `code`, or None when it is not registered."""


def create_app(
    rooms: RoomRegistry | None = None, dist_dir: Path | None = None
) -> FastAPI:
    """Build the app.

    Args:
        rooms: The rooms the WebSocket serves. None: a new empty registry.
        dist_dir: The built client. None: WEB_DIST_DIR.

    Never raises because `dist_dir` is missing or empty (see AC-6).
    """


app: FastAPI  # create_app(); run with: uv run uvicorn nock.server:app
```

`WEB_DIST_DIR` is computed from the module file
(`Path(__file__).resolve().parents[2] / "web" / "dist"`), never from the current
directory.

### HTTP routes

| Method and path | Answer |
| --- | --- |
| `GET /` | `<dist_dir>/index.html`, status 200, `text/html` |
| `GET /r/{code}`, `code` matching `ROOM_CODE_PATTERN` | the same `index.html`, whether or not the room exists |
| `GET /assets/{file}` | that file from `<dist_dir>/assets/`, 404 when absent |
| `GET /{file}` naming a regular file directly inside `<dist_dir>` (for example `/favicon.svg`) | that file |
| WebSocket `/api/rooms/{code}/ws` | the room socket below |
| any other path under `/api`, and `/api` itself | 404, FastAPI's JSON body `{"detail": "Not Found"}` |
| any other path | 404, never `index.html` |

Every server route lives under `/api/`; no path under `/api/` ever returns the app.

### Room WebSocket `/api/rooms/{code}/ws`

The server keeps this to what the shell needs. In order:

1. The server accepts the connection.
2. If `rooms.find_room(code)` is None (unregistered or malformed code), the server
   closes the socket with code `ROOM_NOT_FOUND_CLOSE_CODE` (4404) and sends no
   message.
3. Otherwise it waits for client messages (text or binary frames), each read with
   `parse_client_message`, until one is a `Join`:
   - a message that fails to parse gets one
     `ErrorMessage(code=ErrorCode.INVALID_MESSAGE, message=<English text>)`;
   - a valid message that is not a `Join` gets one
     `ErrorMessage(code=ErrorCode.NOT_JOINED, message=<English text>)`;
   - the socket stays open in both cases.
4. On the first `Join`, it sends exactly one `Snapshot` (as `model_dump_json()`):

   | Field | Value |
   | --- | --- |
   | `seq` | `0` |
   | `you` | a new player id for this connection, matching the `PlayerId` pattern |
   | `resume_token` | a new random token for this connection, matching the `ResumeToken` pattern |
   | `grid` | `grid_view(grid)` of the registered grid |
   | `players` | `()` (the player list belongs to spec 012) |
   | `settings` | `RoomSettings(help_mode=HelpMode.FREE, reveal_budget=RevealBudget(letters=5, words=1), locked=False)` |
   | `reveal_budget` | `RevealBudget(letters=5, words=1)` |
   | `flags`, `chat` | `()` |
   | `open_vote` | `None` |
   | `timer_elapsed_ms`, `timer_running`, `solved` | `0`, `False`, `False` |

   The `nickname` and `resume_token` of the `Join` are validated by the parser and
   otherwise ignored.
5. After the snapshot the server reads and ignores every message, sending nothing,
   until the client disconnects. It never sends an event with a `seq`.

The server keeps no player list and no room state besides the registry.

### Client: `web/`

Binding for the tests:

- `web/index.html`: `<html lang="fr">`, an empty `<title></title>`, and no text in
  `<body>` (only `<div id="app"></div>` and the module script).
- `web/src/i18n/fr.json`: one flat JSON object. Each key matches
  `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$`, each value is a non-empty string. It
  holds at least these keys (the French text is the proposed wording):

  | Key | Value |
  | --- | --- |
  | `app.title` | `Nock` |
  | `catalogue.heading` | `Grilles` |
  | `catalogue.empty` | `Aucune grille pour le moment.` |
  | `room.heading` | `Salon {code}` |
  | `room.default_nickname` | `Invité` |
  | `room.status.connecting` | `Connexion…` |
  | `room.status.joined` | `Connecté` |
  | `room.status.not_found` | `Ce salon n'existe pas.` |
  | `room.status.closed` | `Connexion perdue.` |
  | `not_found.heading` | `Page introuvable` |

- `web/src/lib/i18n.ts` exports
  `type MessageKey = keyof typeof fr` and
  `function t(key: MessageKey, values?: Record<string, string | number>): string`,
  which returns the `fr.json` value with each `{name}` replaced by
  `String(values[name])`; a placeholder with no value is left as written. Every
  string the user can read (text, `alt`, `title`, `placeholder`, `aria-*`, the
  document title) is produced by `t`.
- Routing is done by the app itself from `location.pathname`, with no new npm
  dependency: `/` shows the catalogue page, `/r/<code>` (code matching
  `^[A-Z0-9]{6}$`) shows the room page, any other path shows a not-found page with
  `t("not_found.heading")`. The app sets `document.title = t("app.title")` on
  start.
- Catalogue page: root element `data-testid="catalogue-page"`, showing
  `t("catalogue.heading")` as its heading and `t("catalogue.empty")`.
- Room page: root element `data-testid="room-page"` with these attributes, kept up
  to date:

  | Attribute | Value |
  | --- | --- |
  | `data-room-code` | the code from the URL |
  | `data-status` | `connecting`, `joined`, `not_found` or `closed` |
  | `data-seq` | `""` before the first snapshot, then the current `seq` in decimal |
  | `data-pending` | number of buffered events, in decimal, `"0"` at start |
  | `data-grid` | `""` before the first snapshot, then `<width>x<height>` of the latest snapshot's grid, for example `5x5` |

  It shows `t("room.heading", { code })` and `t("room.status.<status>")`, the
  latter in an element with `data-testid="room-status"`.

Room page behaviour, which the browser tests observe through the attributes above:

1. On mount it opens one WebSocket to
   `ws[s]://<location.host>/api/rooms/<code>/ws` (`wss` when the page is `https`).
   Status `connecting`.
2. When the socket opens it sends
   `{"type": "join", "nickname": t("room.default_nickname"), "resume_token": null}`.
3. Each incoming frame is read with `JSON.parse`. A frame that is not JSON, or not
   an object with a string `type`, is ignored.
4. `type == "snapshot"`: the snapshot becomes the latest snapshot, `seq` becomes
   its `seq`, status `joined`. Buffered events with `seq <= snapshot.seq` are
   dropped, then the buffer is drained (step 6).
5. An *event* is a message whose `type` is not `snapshot` and whose `seq` is an
   integer. Events received before the first snapshot are dropped. After it:
   - `event.seq <= seq`: ignored (already included);
   - `event.seq == seq + 1`: applied, then the buffer is drained;
   - `event.seq > seq + 1`: buffered (a second event with the same `seq` as a
     buffered one is ignored).
6. Draining: while the buffer holds `seq + 1`, that event is removed and applied.
7. Applying an event, in this spec, sets `seq = event.seq`. What each event type
   changes in the kept snapshot belongs to the spec that owns it (015 onwards).
8. A message with no integer `seq` (`selection_moved`, `reaction`, `error`) does not
   touch `seq` or the buffer.
9. When the socket closes with code 4404, status `not_found`; any other close or
   error, status `closed`. No reconnection (spec 017).

Not binding (implementer's choice): the split of the client into files, its
TypeScript types, and the styles.

### Demo content of the Vite template

Removed: `web/src/lib/Counter.svelte`, `web/src/assets/hero.png`,
`web/src/assets/svelte.svg`, `web/src/assets/vite.svg`, `web/public/icons.svg`.
`web/src/App.svelte` and `web/src/app.css` are rewritten (the demo markup and its
styles go). `web/public/favicon.svg` stays and is served at `/favicon.svg`.
`web/README.md` is rewritten as a short English note on how to build and check the
client.

### Test harness

- HTTP and WebSocket criteria use `fastapi.testclient.TestClient` on
  `create_app(rooms=..., dist_dir=tmp_path)`, where the test writes its own
  `index.html` (and `assets/app.js`, `favicon.svg` when needed) into `tmp_path`.
- The FX-01 grid is `Grid.model_validate_json(fx01_text)` with the existing
  `fx01_text` fixture of `tests/conftest.py`.
- Browser criteria use pytest-playwright's `page` fixture (Chromium) against a
  live server: a function-scoped fixture, in `tests/conftest.py` so later specs
  reuse it, that builds `create_app(rooms=<a RoomRegistry the test can reach>)`
  with the real `WEB_DIST_DIR`, runs it with `uvicorn.Server` on `127.0.0.1` and a
  free port (bind a socket to port 0) in a daemon thread, waits until
  `server.started` is true, yields the base URL `http://127.0.0.1:<port>`, then sets
  `should_exit = True` and joins the thread. Rooms registered after the server
  started are visible to it (same registry object).
- When `WEB_DIST_DIR / "index.html"` does not exist, the live-server fixture fails
  (not skips) with the message `web/dist is missing: run npm --prefix web run build`.
- Criteria marked "browser, mocked socket" install
  `page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), handler)` before
  `page.goto(f"{base_url}/r/ABC123")`. The handler never connects to the server; it
  records the page's messages and sends the frames the test chooses
  (`ws.send(...)`, `ws.close(code=...)`). Server frames are built with the
  `nock.protocol` models and `model_dump_json()`. A test waits for each state with
  Playwright's auto-waiting assertions (`expect(...).to_have_attribute(...)`).
- Static criteria read files under `web/` with Python only.

## Acceptance criteria

The word in brackets says how each criterion is tested.

- **AC-1** (HTTP) Given a `dist_dir` holding `index.html` with the text `<!doctype html><title></title><div id="app"></div>`, when `GET /` is requested, then the status is 200, the `content-type` starts with `text/html`, and the body equals that file's content.
- **AC-2** (HTTP) Given the same `dist_dir` and an empty registry, when `GET /r/ABC123` is requested, then the status is 200 and the body equals `index.html`.
- **AC-3** (HTTP) Given the app, when `GET /api/nope`, `GET /api`, `GET /api/rooms` or a plain HTTP `GET /api/rooms/ABC123/ws` is requested, then the status is 404 and the JSON body is `{"detail": "Not Found"}`.
- **AC-4** (HTTP) Given the app, when `GET /catalogue`, `GET /r/abc123`, `GET /r/ABC12`, `GET /r/ABC1234` or `GET /r/ABC123/extra` is requested, then the status is 404 and the body is not the content of `index.html`.
- **AC-5** (HTTP) Given a `dist_dir` holding `index.html`, `assets/app.js` with the text `console.log(1)` and `favicon.svg`, when `GET /assets/app.js` and `GET /favicon.svg` are requested, then each answers 200 with that file's content; `GET /assets/missing.js` and `GET /missing.svg` answer 404 with a body that is not `index.html`.
- **AC-6** (HTTP) Given a `dist_dir` that does not exist, when `create_app(dist_dir=...)` is called, then it does not raise; `GET /` and `GET /r/ABC123` answer 503 with a `text/plain` body containing `npm --prefix web run build`; `GET /api/nope` still answers 404.
- **AC-7** (Python) Given a `RoomRegistry` and the FX-01 grid, when `register_room` is called twice, then each code matches `^[A-Z0-9]{6}$`, the two codes differ, `find_room(code)` returns the FX-01 grid for each, and `find_room` of a code that was not returned (for example `"abc123"`) returns None.
- **AC-8** (WebSocket) Given a room registered on FX-01, when a client connects to `/api/rooms/<code>/ws` and sends `{"type": "join", "nickname": "Ana", "resume_token": null}`, then the next message parses with `parse_server_message` to a `Snapshot` with `seq == 0`, `grid == grid_view(fx01_grid)`, `players == ()`, `settings == RoomSettings(help_mode=HelpMode.FREE, reveal_budget=RevealBudget(letters=5, words=1), locked=False)`, `reveal_budget == RevealBudget(letters=5, words=1)`, `flags == ()`, `chat == ()`, `open_vote is None`, `timer_elapsed_ms == 0`, `timer_running is False`, `solved is False`.
- **AC-9** (WebSocket) Given the snapshot of AC-8, when the raw text of the frame is searched, then it contains none of `"answer"`, `TAMIS`, `NAVAL`, `MIME`, `IDES`, `SENT`, `VIDE`, `AMEN`, `LEST`.
- **AC-10** (WebSocket) Given a room registered on FX-01, when two clients connect and each sends the join of AC-8, then the two snapshots have different `you` values and different `resume_token` values.
- **AC-11** (WebSocket) Given an empty registry, when a client connects to `/api/rooms/ZZZZZZ/ws` or `/api/rooms/abc/ws`, then the server closes the socket with code 4404 and the client receives no message before the close (`receive_text()` raises `WebSocketDisconnect` with `code == 4404`).
- **AC-12** (WebSocket) Given a connection to a registered FX-01 room, when the client first sends the text `not json`, then it receives an `ErrorMessage` with `code == ErrorCode.INVALID_MESSAGE`; the same holds for `{"type": "join", "nickname": "A"}`; when it then sends the join of AC-8, it receives a `Snapshot`.
- **AC-13** (WebSocket) Given a connection to a registered FX-01 room, when the client first sends `{"type": "undo"}`, then it receives an `ErrorMessage` with `code == ErrorCode.NOT_JOINED`; when it then sends the join of AC-8, it receives a `Snapshot`.
- **AC-14** (browser) Given the live server, when the page opens `/`, then the element `data-testid="catalogue-page"` is visible and contains the text of `fr.json["catalogue.heading"]`, and no `data-testid="room-page"` element exists.
- **AC-15** (browser) Given the live server, when the page opens `/` and, separately, `/r/ABC123`, then in both cases `document.title` equals `fr.json["app.title"]` and the `<html>` element has `lang="fr"`.
- **AC-16** (browser) Given the live server and a room registered on FX-01 with code `<code>`, when the page opens `/r/<code>`, then `data-testid="room-page"` reaches `data-room-code="<code>"`, `data-status="joined"`, `data-seq="0"` and `data-grid="5x5"`, and `data-testid="room-status"` shows `fr.json["room.status.joined"]`.
- **AC-17** (browser) Given the live server and an empty registry, when the page opens `/r/ZZZZZZ`, then the room page reaches `data-status="not_found"` with `data-seq=""`, and `data-testid="room-status"` shows `fr.json["room.status.not_found"]`.
- **AC-18** (browser, mocked socket) Given the page on `/r/ABC123`, when the socket opens, then the first message the page sends parses with `parse_client_message` to `Join(nickname=fr.json["room.default_nickname"], resume_token=None)`, and until a snapshot is sent the room page has `data-status="connecting"`, `data-seq=""` and `data-grid=""`.
- **AC-19** (browser, mocked socket) Given the page on `/r/ABC123` that received a FX-01 snapshot with `seq` 5, when the mock sends `letter_changed` events with `seq` 4, then 5, then 7, then the room page shows `data-seq="5"` and `data-pending="1"`; when it then sends `seq` 6, the page shows `data-seq="7"` and `data-pending="0"`.
- **AC-20** (browser, mocked socket) Given the page that received a FX-01 snapshot with `seq` 5, when the mock sends the `selection_moved`, `reaction` and `error` wire examples of spec 039, then a `letter_changed` with `seq` 6, then the page shows `data-seq="6"`, `data-pending="0"` and `data-status="joined"`.
- **AC-21** (browser, mocked socket) Given the page that received a FX-01 snapshot with `seq` 0, when the mock closes the socket with code 1011, then the room page reaches `data-status="closed"` and `data-testid="room-status"` shows `fr.json["room.status.closed"]`.
- **AC-22** (static) Given `web/src/i18n/fr.json`, when it is loaded with `json.loads`, then it is a dict whose keys all match `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$`, whose values are all non-empty `str`, and which holds the ten keys of the table in "Public interface".
- **AC-23** (static) Given every `web/src/**/*.svelte` file, when it goes through the markup scan below, then the scan finds no violation. A file holding `<p>Bonjour</p>`, `<img alt="Logo" />`, `<button title="Salon {code}">` or `<svelte:head><title>Nock</title></svelte:head>` has a violation; one holding `<p>{t("a.b")}</p>`, `<img alt="" />`, `<img alt={t("a.b")} />` or `<input placeholder="{t('a.b')}" />` has none. The scan applies to these strings as well, so the test checks both lists.
- **AC-24** (static) Given every `web/src/**/*.svelte` and `web/src/**/*.ts` file, when every match of `\bt\(\s*["']([^"']+)["']` is collected, then each captured key is a key of `fr.json`, and at least one match exists.
- **AC-25** (static) Given `web/index.html`, when it is read, then its `<html>` tag has `lang="fr"`, its `<title>` element is empty, and its `<body>` holds no text once tags are removed (whitespace only).
- **AC-26** (static) Given the repository, when the demo files are looked up, then none of `web/src/lib/Counter.svelte`, `web/src/assets/hero.png`, `web/src/assets/svelte.svg`, `web/src/assets/vite.svg`, `web/public/icons.svg` exists, and no file under `web/src` contains the text `Counter` or `svelte.svg`.

### Markup scan (AC-23)

Applied to the text of one `.svelte` file, in this order:

1. Remove every `<script ...>...</script>`, `<style ...>...</style>` and
   `<!-- ... -->` (non-greedy, across lines).
2. Remove every `{...}` group, matching nested braces (so `{t("a")}`, `{#if x}`,
   `{:else}`, `{/if}` all disappear).
3. In each remaining tag `<...>`, find the attributes `alt`, `title`,
   `placeholder`, `label`, `aria-label`, `aria-description`, `aria-placeholder`,
   `aria-roledescription`, `aria-valuetext` written with a quoted value
   (`name="..."` or `name='...'`, optional spaces around `=`). A value that is not
   whitespace only is a violation.
4. Remove every tag `<...>`. Any remaining character that is not whitespace is a
   violation.

## Edge cases and errors

- Room code case (AC-4, AC-11): codes are upper case; `/r/abc123` is 404 and no
  lowercase fallback exists.
- Trailing slash (AC-2): `GET /r/ABC123/` is not covered; FastAPI's default
  behaviour is acceptable.
- Path traversal (AC-5): a request such as `GET /..%2Fpyproject.toml` or
  `GET /assets/..%2F..%2Fpyproject.toml` never returns a file outside `dist_dir`
  (404).
- `index.html` built after the server started (AC-6): the check is made per
  request, so the app is served once the file exists, without restart.
- Unbuilt client, assets (AC-6): `GET /assets/app.js` answers 404.
- Binary frames (AC-12, AC-13): handled like text frames.
- A second `join` after the snapshot, or any later message (AC-8): no reply.
- `resume_token` in the join (AC-8): ignored; the snapshot carries a new token.
- Player ids (AC-10): any value matching the `PlayerId` pattern; the shell keeps
  no list of them.
- Registry codes (AC-7): `register_room` draws codes with `secrets` and retries
  on a collision; the rules on randomness and throttling are spec 011's.
- Unknown client path (client routing): shows the not-found page. FastAPI never
  serves the app on such a path, so no criterion covers it.
- Frames that are not JSON, or JSON without a string `type` (AC-19): ignored, and
  later events are still applied.
- Events before the first snapshot (AC-19): dropped. A `letter_changed` with
  `seq` 1 then a snapshot with `seq` 0 leaves `data-seq="0"`, `data-pending="0"`.
- A second snapshot (AC-19): replaces the first, sets `seq`, drops buffered events
  at or below its `seq` and drains the rest. Snapshot 5, event 8 (buffered), then
  snapshot 7: `data-seq="8"`, `data-pending="0"`.
- A gap that never fills (AC-19): the buffer keeps its events; the shell asks for
  nothing. Catch-up belongs to specs 017 and 034.
- Close before any snapshot (AC-21): status `closed` (or `not_found` for 4404),
  `data-seq` stays `""`.
- Strings in `.ts` files (AC-23): the scan does not cover them; the `t` rule
  applies all the same and the reviewer checks it. AC-24 checks the keys.

## Out of scope

- Grid rendering, cell display and any input (spec 006 onwards).
- The real catalogue: listing, filters, grid status (spec 004). The catalogue page
  shows its heading and the empty text only.
- Room creation over HTTP, the share link, random-code rules and throttling (spec
  011). `RoomRegistry` is a test seam, not the room store.
- The nickname form, player list, colours, room full (spec 012); presence (013);
  host controls (014).
- Every server event with a `seq`, broadcasting, the per-room asyncio task, the
  edit log and storage (specs 015 to 018).
- What each event changes in the kept snapshot (owned by the spec of that event).
- Reconnection, resend queue and catch-up (specs 017, 034).
- Any language other than French, and a language switch.
- A Vite dev-server proxy to FastAPI: `web/vite.config.ts` is tooling.
- Caching headers, compression and HTTPS termination.
- New Python or npm dependencies: none is needed.

## Work packages

None.

## Open questions

Each item names the pick already written into the spec above.

1. Room seam before spec 011. Options: a registry object passed to `create_app`,
   a module-level dict, or an HTTP endpoint that creates rooms. Pick: an in-memory
   `RoomRegistry` with `register_room(grid) -> code` and `find_room(code)`, passed
   to `create_app`; 011 replaces or extends it. It is a plain class, not a
   Pydantic model, because it is a mutable service rather than data.
2. WebSocket path. Pick: `/api/rooms/{code}/ws`, so every server route sits under
   `/api/` and the SPA rule is simple.
3. Room code format. The request only shows `ABC123`; spec 011 says 6 characters.
   Pick: `^[A-Z0-9]{6}$`, upper case only, in one constant that 011 may narrow (for
   example to drop `0`/`O`, `1`/`I`).
4. SPA fallback. Options: serve `index.html` for every unknown non-API path (the
   client shows "not found" with status 200), or only for the known routes. Pick:
   only `/` and `/r/{code}`; everything else is a real 404, which spec 004 AC-4
   ("direct URL returns not found") also needs. Each new client route adds one
   server route.
5. Unknown room on the socket. Options: close with code 4404 and no message, or
   add a `room_not_found` value to `ErrorCode` (a change to the done spec 039).
   Pick: close with 4404, no message.
6. Snapshot contents. Pick: `seq` 0, `players` empty, help mode `free`, reveal
   budget 5 letters and 1 word (spec 024 AC-2 default), a new `you` and
   `resume_token` per connection, nothing remembered between joins. Spec 012 adds
   the player list.
7. Nickname sent by the shell. Join requires one (2 to 20 characters) and the
   nickname form is spec 012's. Pick: the shell sends `fr.json["room.default_nickname"]`
   (`Invité`) until 012 replaces it with the form.
8. Messages after the snapshot. Pick: read and ignored, no reply, until specs 015
   onwards give them meaning.
9. How "applies later events in sequence order" is tested. The server of this spec
   sends no event, so it cannot be seen end to end. Pick: browser tests replace the
   socket with Playwright's `page.route_web_socket` mock (AC-18 to AC-21), and
   "applying" an event means advancing `seq` only; `data-seq` and `data-pending`
   expose the ordering. This needs Playwright 1.48 or later, which
   pytest-playwright 0.10 brings.
10. Gaps in `seq`. Pick: buffer, never request; events at or below the current
    `seq` are ignored; events before the first snapshot are dropped.
11. Client not built. Options: crash at start, or answer an error. Pick: the app
    starts, `/` and `/r/{code}` answer 503 `text/plain` naming the build command,
    `/api` keeps working.
12. Checking "no user-facing string outside fr.json". Pick: the markup scan of
    AC-23 over `.svelte` files, plus AC-24 (every literal `t("...")` key exists)
    and AC-25 (`index.html`); `MessageKey` typing makes `svelte-check` reject an
    unknown key. Strings in `.ts` files are left to the reviewer.
13. Demo content. Pick: removed (list in "Demo content"), `favicon.svg` kept,
    `App.svelte`, `app.css` and `web/README.md` rewritten.
14. Importing `fr.json` in TypeScript may need `"resolveJsonModule": true` in
    `web/tsconfig.app.json`, which counts as tooling. Pick: the human approves that
    one-line change in advance if `svelte-check` asks for it; no other config
    change.
15. Missing build in browser tests. Options: skip or fail. Pick: fail with
    `web/dist is missing: run npm --prefix web run build`, so a broken build step
    can never pass as skipped tests.
16. Live-server fixture. Pick: function-scoped, in `tests/conftest.py` so specs 011
    onwards reuse it.
