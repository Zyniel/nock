---
id: "040"
title: Web client shell
status: done
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


app: FastAPI  # create_app(); run with: uv run python -m nock (spec 036)
```

(Note from the lead, 2026-10-15: the comment above used to name
`uv run uvicorn nock.server:app`. That command skips spec 036's 8,192-byte frame
limit, which only `python -m nock` sets, through `server_config`; the README
already says `uv run python -m nock`. The live-server fixture of the test harness
below starts `uvicorn.Server` itself; it is not a run command and is unchanged.)

`WEB_DIST_DIR` is computed from the module file
(`Path(__file__).resolve().parents[2] / "web" / "dist"`), never from the current
directory.

### HTTP routes

| Method and path | Answer |
| --- | --- |
| `GET /` | `<dist_dir>/index.html`, status 200, `text/html` |
| `GET /r/{code}`, `code` matching `ROOM_CODE_PATTERN` | the same `index.html`, whether or not the room exists |
| `GET /assets/{file}`, `file` not starting with `.` | that file from `<dist_dir>/assets/`, 404 when absent |
| `GET /{file}` naming a regular file directly inside `<dist_dir>`, `file` not starting with `.` (for example `/favicon.svg`) | that file |
| WebSocket `/api/rooms/{code}/ws` | the room socket below |
| any path with a segment starting with `.` (for example `/.env`, `/assets/.hidden.js`) | 404, FastAPI's JSON body `{"detail": "Not Found"}`, even when the file exists (AC-27) |
| any path other than `/` ending with `/` (for example `/api/`, `/assets/`, `/r/ABC123/`, `/catalogue/`) | 404, FastAPI's JSON body `{"detail": "Not Found"}`, no redirect (AC-28) |
| any other path under `/api`, and `/api` itself | 404, FastAPI's JSON body `{"detail": "Not Found"}` |
| any other path | 404, never `index.html` |

Every server route lives under `/api/`; no path under `/api/` ever returns the app.

No HTTP response of the app has a 3xx status: FastAPI's automatic trailing-slash
redirect is never applied (for example `FastAPI(redirect_slashes=False)`; the
means is the implementer's choice, the observable rule is AC-28). The only path
ending with `/` that is served is `/` itself.

A path segment is a part of the decoded URL path between two `/`. A segment
starting with `.` (dot files and dot directories, such as `.env`, `.htaccess`,
`.well-known`) is never served, whatever `dist_dir` holds: Vite copies every file
of `web/public/` into `dist`, dot files included.

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
4. On the first `Join`, the server applies the join steps of spec 012 ("Join",
   `join_room`). A refused join gets the reply that spec 012 gives it. An accepted
   join gets exactly one `Snapshot` (as `model_dump_json()`, built by spec 012's
   `snapshot_for`). On a room just registered on a grid, the first accepted join
   gives:

   | Field | Value |
   | --- | --- |
   | `seq` | `1` (the joiner's own `player_joined`, spec 012 join step 6) |
   | `you` | the joiner's player id, matching the `PlayerId` pattern |
   | `resume_token` | the joiner's token, matching the `ResumeToken` pattern: a new random token for a new player, the player's own token on a resume (spec 012 join step 2) |
   | `grid` | `grid_view(grid)` of the registered grid |
   | `players` | `(<the joiner's view>,)`: the players of the room, spec 012's `player_views` |
   | `settings` | `RoomSettings(help_mode=HelpMode.FREE, reveal_budget=RevealBudget(letters=5, words=1), locked=False)` |
   | `reveal_budget` | `RevealBudget(letters=5, words=1)` |
   | `flags`, `chat` | `()` |
   | `open_vote` | `None` |
   | `timer_elapsed_ms`, `timer_running`, `solved` | `0`, `False`, `False` |

   What the `nickname` and `resume_token` of the `Join` do is governed by spec
   012's join steps: the nickname is normalised and made unique, a token of a
   player of the room resumes that player, and any other token is ignored.
5. After the snapshot the socket is bound to the player (spec 012, "`nock.hub` and
   `nock.server` changes"): a second `Join` is ignored with no reply, and what the
   other messages and events do belongs to specs 011 onwards.

Room state (players, `seq`) belongs to the rooms engine of specs 011 and 012.

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
- Nicknames on screen: a page shows a nickname only through one function,
  `displayNickname(nickname: string): string` (for example in
  `web/src/lib/nickname.ts`), which writes it with capitalised words (spec 012
  decision 12). It reads the nickname one character (code point) at a time: the
  first character, and each character right after a space, a hyphen `-` or an
  apostrophe (`'` or U+2019), goes through `toUpperCase()`; every other character
  goes through `toLowerCase()`. So `ANA` shows as `Ana`, `JEAN-LUC` as `Jean-Luc`,
  `D'ARTAGNAN` as `D'Artagnan`, `ANA 2` as `Ana 2`, `ÉLODIE` as `Élodie` and
  `BOB_42` as `Bob_42`. A nickname the server would refuse shows the same way:
  `<b>Eve</b>` as `<b>eve</b>`, `<img src=x>` as `<img Src=x>`. It applies
  wherever a page shows a nickname, as text or as the value of a `t` placeholder
  (`{name}`, `{names}`): among others the roster (spec 012), the activity feed
  (specs 013 and 034), clue flags (spec 021), chat authors, mute rows and reaction
  labels (spec 022), the vote banner (spec 025), the clue bar's author line (spec
  019), the host controls' labels (spec 014), the recap and the share page (spec
  028), "My rooms" (spec 032), the history list (spec 029) and the ops replay
  (spec 038). What a page keeps, stores or sends (its kept snapshot,
  `nock.identity.<CODE>`, `nock.nickname`, a `join`) is not rewritten, and the
  nickname form's input shows capitals (spec 012). (Note from the lead,
  2026-10-16: added (human's rule of 2026-10-16: nicknames in capitals).)
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
  | `data-status` | `connecting`, `nickname`, `joining`, `joined`, `full`, `replaced`, `not_found` or `closed` (spec 012's list; spec 011 adds `throttled`) |
  | `data-seq` | `""` before the first snapshot, then the current `seq` in decimal |
  | `data-pending` | number of buffered events, in decimal, `"0"` at start |
  | `data-grid` | `""` before the first snapshot, then `<width>x<height>` of the latest snapshot's grid, for example `5x5` |

  It shows `t("room.heading", { code })` and `t("room.status.<status>")`, the
  latter in an element with `data-testid="room-status"`.

Room page behaviour, which the browser tests observe through the attributes above:

1. On mount it opens one WebSocket to
   `ws[s]://<location.host>/api/rooms/<code>/ws` (`wss` when the page is `https`).
   Status `connecting`.
2. When the socket opens, the page follows spec 012's "Room page flow" (steps 2
   to 8): it joins at once with a stored identity or for a room created on this
   device (status `joining`), otherwise it sends nothing and shows the nickname
   form (status `nickname`) until the form is submitted (status `joining`).
   (Note from the lead, 2026-10-15: "sends nothing" leaves aside the heartbeat
   `ping` frames of spec 017, which the page may send at any time once the
   socket is open.)
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
   error, status `closed`, except the codes and errors that specs 011 and 012
   give their own status (4429 `throttled`, 4001 `replaced`, `room_full` `full`).
   No reconnection (spec 017).

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
  `index.html` (and `assets/app.js`, `favicon.svg`, dot files when needed) into
  `tmp_path`.
- AC-28 requests are made with `client.get(path, follow_redirects=False)`, so a
  redirect shows as its own 3xx status instead of being followed.
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
- **AC-8** (WebSocket) Given a room registered on FX-01, when a client connects to `/api/rooms/<code>/ws` and sends `{"type": "join", "nickname": "Ana", "resume_token": null}`, then the next message parses with `parse_server_message` to a `Snapshot` with `seq == 1`, `grid == grid_view(fx01_grid)`, `players == (<the joiner's view>,)`, that is `(PlayerView(player_id=snapshot.you, nickname="Ana", colour=0, state=PlayerState.ACTIVE, is_host=True, muted=False, selection=None),)` (spec 012), `settings == RoomSettings(help_mode=HelpMode.FREE, reveal_budget=RevealBudget(letters=5, words=1), locked=False)`, `reveal_budget == RevealBudget(letters=5, words=1)`, `flags == ()`, `chat == ()`, `open_vote is None`, `timer_elapsed_ms == 0`, `timer_running is False`, `solved is False`. The same join sent as a binary frame gets a `Snapshot` with `seq == 1`. A join with `resume_token` set to a token that matches no player of the room (for example 24 times `A`) gets a `Snapshot` whose `resume_token` differs from the one sent.
- **AC-9** (WebSocket) Given the snapshot of AC-8, when the raw text of the frame is searched, then it contains none of `"answer"`, `TAMIS`, `NAVAL`, `MIME`, `IDES`, `SENT`, `VIDE`, `AMEN`, `LEST`.
- **AC-10** (WebSocket) Given a room registered on FX-01, when two clients connect and each sends the join of AC-8, then the two snapshots have different `you` values and different `resume_token` values.
- **AC-11** (WebSocket) Given an empty registry, when a client connects to `/api/rooms/ZZZZZZ/ws` or `/api/rooms/abc/ws`, then the server closes the socket with code 4404 and the client receives no message before the close (`receive_text()` raises `WebSocketDisconnect` with `code == 4404`).
- **AC-12** (WebSocket) Given a connection to a registered FX-01 room, when the client first sends the text `not json`, then it receives an `ErrorMessage` with `code == ErrorCode.INVALID_MESSAGE`; the same holds for `{"type": "join", "nickname": "A"}`; when it then sends the join of AC-8, it receives a `Snapshot`.
- **AC-13** (WebSocket) Given a connection to a registered FX-01 room, when the client first sends `{"type": "undo"}`, then it receives an `ErrorMessage` with `code == ErrorCode.NOT_JOINED`; when it then sends the join of AC-8, it receives a `Snapshot`.
- **AC-14** (browser) Given the live server, when the page opens `/`, then the element `data-testid="catalogue-page"` is visible and contains the text of `fr.json["catalogue.heading"]`, and no `data-testid="room-page"` element exists.
- **AC-15** (browser) Given the live server, when the page opens `/` and, separately, `/r/ABC123`, then in both cases `document.title` equals `fr.json["app.title"]` and the `<html>` element has `lang="fr"`.
- **AC-16** (browser) Given the live server and a room registered on FX-01 with code `<code>`, when the page enters the room through the `enter_room` fixture of spec 011 (it opens `/r/<code>` and, when the page shows the nickname form of spec 012, submits it with `Ana`), then `data-testid="room-page"` reaches `data-room-code="<code>"`, `data-status="joined"`, `data-seq="1"` and `data-grid="5x5"`, and `data-testid="room-status"` shows `fr.json["room.status.joined"]`.
- **AC-17** (browser) Given the live server and an empty registry, when the page opens `/r/ZZZZZZ`, then the room page reaches `data-status="not_found"` with `data-seq=""`, and `data-testid="room-status"` shows `fr.json["room.status.not_found"]`.
- **AC-18** (browser, mocked socket) Given the page on `/r/ABC123` with nothing in `localStorage`, when the socket opens, then the room page shows `data-status="nickname"` and sends nothing (no frame within 300 ms; Note from the lead, 2026-10-15: spec 017's heartbeat `ping` frames are not counted, so the test ignores any `ping` among the frames it reads); after the nickname form of spec 012 is submitted with `Ana` typed, the first message the page sends parses with `parse_client_message` to `Join(nickname="ANA", resume_token=None)` (Note from the lead, 2026-10-16: the join's nickname was `"Ana"`; the nickname input now holds capitals, spec 012's room page flow step 3 (human's rule of 2026-10-16: nicknames in capitals)), the page has opened one socket only, and until a snapshot is sent the room page has `data-status="joining"`, `data-seq=""`, `data-grid=""`, `data-pending="0"`, with `data-testid="room-status"` showing `fr.json["room.status.joining"]`.
- **AC-19** (browser, mocked socket) Given the page on `/r/ABC123` that received a FX-01 snapshot with `seq` 5, when the mock sends `letter_changed` events with `seq` 4, then 5, then 7, then the room page shows `data-seq="5"` and `data-pending="1"`; when it then sends `seq` 6, the page shows `data-seq="7"` and `data-pending="0"`.
- **AC-20** (browser, mocked socket) Given the page that received a FX-01 snapshot with `seq` 5, when the mock sends the `selection_moved`, `reaction` and `error` wire examples of spec 039, then a `letter_changed` with `seq` 6, then the page shows `data-seq="6"`, `data-pending="0"` and `data-status="joined"`.
- **AC-21** (browser, mocked socket) Given the page that received a FX-01 snapshot with `seq` 0, when the mock closes the socket with code 1011, then the room page reaches `data-status="reconnecting"`, `data-testid="room-status"` shows `fr.json["room.status.reconnecting"]` and the `connection-banner` is visible (amended for spec 017, which reconnects after a lost connection).
- **AC-22** (static) Given `web/src/i18n/fr.json`, when it is loaded with `json.loads`, then it is a dict whose keys all match `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$`, whose values are all non-empty `str`, and which holds the ten keys of the table in "Public interface".
- **AC-23** (static) Given every `web/src/**/*.svelte` file, when it goes through the markup scan below, then the scan finds no violation. A file holding `<p>Bonjour</p>`, `<img alt="Logo" />`, `<button title="Salon {code}">` or `<svelte:head><title>Nock</title></svelte:head>` has a violation; one holding `<p>{t("a.b")}</p>`, `<img alt="" />`, `<img alt={t("a.b")} />` or `<input placeholder="{t('a.b')}" />` has none. The scan applies to these strings as well, so the test checks both lists.
- **AC-24** (static) Given every `web/src/**/*.svelte` and `web/src/**/*.ts` file, when every match of `\bt\(\s*["']([^"']+)["']` is collected, then each captured key is a key of `fr.json`, and at least one match exists.
- **AC-25** (static) Given `web/index.html`, when it is read, then its `<html>` tag has `lang="fr"`, its `<title>` element is empty, and its `<body>` holds no text once tags are removed (whitespace only).
- **AC-26** (static) Given the repository, when the demo files are looked up, then none of `web/src/lib/Counter.svelte`, `web/src/assets/hero.png`, `web/src/assets/svelte.svg`, `web/src/assets/vite.svg`, `web/public/icons.svg` exists, and no file under `web/src` contains the text `Counter` or `svelte.svg`.
- **AC-27** (HTTP) Given a `dist_dir` holding `index.html`, `.env` with the text `SECRET=1`, `.htaccess`, `assets/.hidden.js` with the text `console.log(2)` and `.well-known/security.txt`, when `GET /.env`, `GET /.htaccess`, `GET /assets/.hidden.js`, `GET /.well-known/security.txt` or `GET /%2Eenv` is requested, then each answers 404 with the JSON body `{"detail": "Not Found"}` (so neither the file's content nor `index.html`).
- **AC-28** (HTTP) Given a `dist_dir` holding `index.html`, `assets/app.js` and `favicon.svg`, and an empty registry, when `GET /api/`, `GET /api/rooms/`, `GET /assets/`, `GET /assets/app.js/`, `GET /favicon.svg/`, `GET /r/`, `GET /r/ABC123/` or `GET /catalogue/` is requested without following redirects, then each answers 404 directly (not a 3xx status, no `location` header) with the JSON body `{"detail": "Not Found"}`; `GET /` still answers 200 with the content of `index.html`.
- **AC-29** (new) (HTTP) The app exposes no generated API documentation. `GET /docs`, `GET /redoc`, `GET /openapi.json` and `GET /docs/oauth2-redirect` each answer 404 with the JSON body `{"detail": "Not Found"}`, with or without a built client.

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
- Trailing slash (AC-28): every path ending with `/` except `/` itself answers 404
  JSON, with no redirect, whether or not the path without the slash is served
  (`/r/ABC123/`, `/favicon.svg/`). This holds when the room `ABC123` is registered
  too, and when the client is not built (`/r/ABC123/` is 404, not 503).
- No redirect anywhere (AC-28): no HTTP response of the app has a 3xx status.
- Dot segments (AC-27): the rule applies to every segment, not only the last one,
  and after percent-decoding (`/%2Eenv` is `/.env`). A name such as `..config`
  also starts with `.` and is 404. A future spec that needs a dot path (for
  example `/.well-known/...`) must change AC-27.
- Unbuilt client, dot files (AC-6, AC-27): `GET /.env` answers 404 JSON, never
  503.
- Path traversal (AC-5): a request such as `GET /..%2Fpyproject.toml` or
  `GET /assets/..%2F..%2Fpyproject.toml` never returns a file outside `dist_dir`
  (404).
- `index.html` built after the server started (AC-6): the check is made per
  request, so the app is served once the file exists, without restart.
- Unbuilt client, assets (AC-6): `GET /assets/app.js` answers 404.
- Binary frames (AC-12, AC-13): handled like text frames.
- A second `join` after the snapshot (AC-8): no reply (spec 012). What other later
  messages get belongs to specs 011 onwards.
- `resume_token` in the join (AC-8): an unknown token (one that matches no player
  of the room and no past player (spec 032)) is ignored and the snapshot carries a
  new token; a known token resumes that player (spec 012 join step 2, its AC-5),
  or seats a past player back (spec 012 step 4a). (Note from the lead, 2026-10-16:
  "and no past player (spec 032)" and "or seats a past player back (spec 012 step
  4a)" were added for spec 032's seat back. Wording only: AC-8 joins a room just
  registered, which has no past player, so no criterion changes.)
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
- Close before any snapshot (AC-21): status `connecting` with no banner while
  spec 017 retries (or `not_found` for 4404), `data-seq` stays `""`.
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

## Decisions

Approved by the human on 2026-10-10, with the pick of each item kept as written
(item 14: the human approves the `resolveJsonModule` line in `web/tsconfig.app.json`;
the lead adds it before the build). Each one is already part of the spec above.

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
   `resume_token` per new player. Spec 012 adds the player list and the resume
   of a known token (amended by item 20; this item first said `seq` 0, no
   players, and nothing remembered between joins).
7. Nickname sent by the shell. Join requires one (2 to 20 characters) and the
   nickname form is spec 012's. Pick: the shell sends `fr.json["room.default_nickname"]`
   (`Invité`) until 012 replaces it with the form. (Replaced by spec 012's room
   page flow, item 20.)
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

Added after the review, approved by the human on 2026-10-10 ("update spec and
reimplement" for both). Each one is part of the spec above.

17. Dot files. Reviewer finding: `GET /.env` answered 200 when `dist_dir` held a
    `.env`, and Vite copies everything in `web/public/` into `dist`, dot files
    included. Decision: dot files are not served. Any path with a segment starting
    with `.` answers 404 with the JSON not-found body, even when the file exists
    (AC-27).
18. Trailing slash. Reviewer finding: `GET /api/` and `GET /assets/` answered 307
    (FastAPI's slash redirect), and the redirect then ended in a 404 JSON, while
    the route table said 404 for every other path under `/api`. Decision: such
    paths are not found. Every path ending with `/` other than `/` answers 404
    with the JSON not-found body directly; the app never answers 3xx, so FastAPI's
    slash redirect is off or never reached (AC-28). This replaces the earlier
    edge case that left `GET /r/ABC123/` to FastAPI's default behaviour.

Added after the review of spec 004, decided by the lead on 2026-10-10 under the
human's instruction to take technical decisions:
19. No generated API documentation. FastAPI's `/docs`, `/redoc` and `/openapi.json`
    are turned off: they would describe the server's API to anyone, and the route
    table already says every other path is not found (AC-29).

Added with spec 012 (guest join), decided by the lead on 2026-10-11 under the
human's instruction to take technical decisions, as spec 012 decision 2 planned:
20. Amendment for spec 012. Spec 012 replaces this spec's fixed snapshot with its
    join steps and the shell's immediate `Invité` join with its room page flow.
    The text is aligned with the updated tests, with no criterion renumbered:
    AC-8 expects `seq == 1` and `players == (<the joiner's view>,)`, and an
    unknown `resume_token` is ignored; AC-16 enters the room through
    `enter_room` (the nickname form) and expects `data-seq="1"`; AC-18 expects
    `data-status="nickname"` and no frame before the form (Note from the lead,
    2026-10-15: spec 017's heartbeat `ping` frames are not counted), then
    `Join(nickname="Ana", resume_token=None)` and `joining` (not `connecting`)
    until the snapshot. The WebSocket steps 4 and 5, the `data-status` list, page
    flow steps 2 and 9, the `resume_token` edge case and items 6 and 7 now point
    to spec 012 (and to spec 011 for `throttled`) instead of stating rules of
    their own. The status stays `done`.

21. Amended on 2026-10-11 for spec 017 (its Decision 4): a lost connection is
    `reconnecting` with the connection banner, and a loss before the first
    snapshot retries as `connecting` (AC-21 and its edge case).

## Open questions

None.
