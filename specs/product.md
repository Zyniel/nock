---
area: product
file: product
status: done
---

# product - What Nock is and what every domain keeps

## Purpose

Nock is an online collaborative arrowword game (mots fléchés) in French. A player
picks a grid, plays alone or invites friends with a link, and the group fills the
same grid together, with help when it wants it. It needs no account, works on a
phone as on a computer, and is playable with a keyboard or a screen reader. This
file holds what stays stable (flows, routes) and the baselines every domain
keeps; a domain spec applying one to a page points here instead of restating it.

## Depends on

None. Every domain spec depends on this file.

## Rules

### Core flows

1. Browse the grids on « Grilles », filter by force, open a grid page:
   `content/library.md`.
2. Start alone: a room from a grid, straight into play: `lobby/rooms.md`.
3. Invite and join: the host shares the room link; an invited player enters a
   nickname and gets a seat and a colour: `lobby/rooms.md`, `lobby/joining.md`,
   `lobby/host.md`.
4. Play together: select a word, type letters everyone sees, see where the
   others are, chat: `gameplay/board.md`, `gameplay/co-op.md`,
   `social/presence.md`, `social/chat.md`.
5. Use help: check or reveal within a budget, by the group's rule or a vote:
   `gameplay/hints.md`.
6. Finish and see the recap: completion, the timer, « Bilan de la partie », the
   shareable recap: `gameplay/rules.md`, `gameplay/results.md`.
7. Come back to a room: the same seat after a reload, a day later or from « Mes
   salons », with what changed while away: `lobby/joining.md`,
   `social/catch-up.md`.
8. The optional account: sign in by email, keep rooms and history across devices,
   erase one's data: `account/account.md`.
9. The operator's page: figures, a room's replay, retention:
   `admin/operations.md`.

### Stable routes

Page routes serve the built client's `index.html`; the client picks the page from
the path. Everything else under `/` is a file of the built client or 404
(`platform/serving.md`).

| Route | Serves | Owner |
| --- | --- | --- |
| `GET /` | the catalogue page | `content/library.md` |
| `GET /g/<number>` | a published grid's page, else 404 | `content/library.md` |
| `GET /r/<code>` | the room page; 404 unless 6 capitals or digits | `lobby/joining.md` |
| `GET /recap/<token>` | the shared recap page; unknown token 404 | `gameplay/results.md` |
| `GET /account` | the account page | `account/account.md` |
| `GET /ops` | the operator's page | `admin/operations.md` |
| `GET /api/grids?force=`, `GET /api/grids/<number>` | the published grids, one grid | `content/library.md` |
| `POST /api/rooms` | a room on a published grid: code, share link, 201; `GET` is 404 | `lobby/rooms.md` |
| `POST /api/rooms/summaries` | « Mes salons » | `lobby/joining.md` |
| `POST /api/rooms/<code>/catch-up` | what changed while away | `social/catch-up.md` |
| `GET /api/rooms/<code>/recap`, `GET /api/recaps/<token>` | a room's recap, a shared one | `gameplay/results.md` |
| `GET /api/account` | sign-in state | `account/account.md` |
| `POST /api/account/link`, `.../sign-in`, `.../sign-out` | the sign-in flow (202, 200, 204) | `account/account.md` |
| `GET`, `PUT /api/account/rooms`; `GET /api/account/history` | the account's rooms and history | `account/account.md` |
| `DELETE /api/account` | erase the account, 204 | `account/account.md` |
| `GET /api/ops/dashboard?days=`, `GET /api/ops/rooms/<code>/edits` | figures, a room's edits; token needed | `admin/operations.md` |
| `GET`, `PUT /api/ops/settings`; `POST /api/ops/settings/dry-run` | the room lives and the sweep interval: read, override, count a value's deletions; token needed | `admin/overrides.md` |
| `WS /api/rooms/<code>/ws` | the room socket: join, play, events | `platform/realtime.md` |

While accounts are off, `/account` and every `/api/account` path answer 404
whatever the method; while the operator pages are off, `GET /ops` answers 404 and
every `/api/ops` path 404 whatever the method.

### Browsers and windows

10. Nock runs in Chromium, Firefox and WebKit, and no behaviour is
    engine-specific. A check runs in one engine only when it needs Chromium-only
    tooling (CPU and network throttling for rules 22, 23 and the page part of 24;
    clipboard permissions; pinch through CDP), and the domain spec names it. When
    the gate and CI run each engine: `CLAUDE.md`.
11. The windows are phones from 300 by 480, upright and sideways, tablets upright
    and landscape, and computers up to 1920 by 1080. Which layout each gets:
    `_design/room.md`, « Which layout ».

### Accessibility baselines

12. Keyboard reach. Every action of every page can be done with Tab, Shift+Tab,
    Enter, Space, Escape, Backspace, the arrow keys, the letters and Ctrl+Z; an
    element inside a menu, the Salon or a sheet is reached by opening it from the
    keyboard first. The in-app keyboard keys are buttons out of the Tab order
    (`tabindex` -1), named by their letter, « Effacer », « Crayon » (✎) or
    « Changer de sens » (⇄) (`gameplay/board.md` rule 15), never hidden from
    the accessibility tree; a tap on one leaves the focus on the grid.
13. Leaving the grid. The grid is one Tab stop; inside it Tab and Shift+Tab move
    between words (`gameplay/board.md`). Escape releases it: the next Tab or
    Shift+Tab is left to the browser and moves the focus to the neighbouring
    focusable element, the selection unchanged; any other key, or losing the
    focus, ends the release; Escape changes nothing else. A hidden hint
    (`a11y.grid_hint`) describes the grid and says so.
14. Visible focus. Every focusable element shows, while focused after a keyboard
    move, an outline of at least 2 px whose style is neither `none` nor `auto`
    and whose colour reaches 3:1 against the surface behind it (the ring of
    `_design/foundation.md`). The selected letter cell has a solid outline of at
    least 2 px whether or not the grid has the focus; other letter cells none.
15. Not colour alone. The other players' cursors carry colour only while the
    Accessibilité switch is off; on, each is its player's icon, one shape per
    colour index, which the roster swatch shows too (`social/presence.md`). A
    locked letter is bold (weight 700 or more), an unlocked one is not. Roster
    states are never shown by dimming (opacity stays 1): an idle nickname is
    italic, a disconnected one italic and struck through, an active one plain,
    and each row writes its state.
16. Crowded cell. A cell draws at most four cursors, one per corner, by order of
    arrival, with no text; they never overlap; a freed corner goes to the player
    who has waited longest.
17. Screen reader. The grid has `role="grid"`, the name `grid.label` and
    `tabindex` 0; its rows `role="row"`, every cell `role="gridcell"` with id
    `cell-<row>-<column>`; letter cells carry
    `aria-selected`, the grid's `aria-activedescendant` is the selected cell's
    id, absent with nothing selected; clue arrows are hidden. A polite, visually
    hidden live region announces each change of selection with
    `a11y.announcement` (clue, direction, length, 1-based position;
    `a11y.announcement_one` for a one-cell word); it is empty with nothing
    selected and not rewritten for the same selection.
18. Scrolling lists. A list that scrolls with nothing focusable inside it is a
    Tab stop (`tabindex` 0) while it scrolls and has no `tabindex` otherwise; the
    attribute follows any change within 300 ms. Each list has `role="list"` and
    is named by the hidden heading of its panel (« Joueurs », « Discussion »).
    The arrow keys keep the browser's scrolling; a new line never moves a list
    away from where the reader put it (`social/chat.md`). The Joueurs list never
    scrolls itself.
19. Contrast. Every visible text reaches 4.5:1 against its background in every
    state, opacity folded in (the pairs of `_design/foundation.md`); flashes
    are included, except the Auteurs inks during a flash, whose contrast is not
    guaranteed (`social/presence.md` rule 15).
20. Language. `<html lang="fr">`; every interface string comes from
    `web/src/i18n/fr.json` through `t()`; the only texts outside it are data:
    nicknames as displayed, clues, letters, codes, URLs and numbers. Text meant
    for assistive technology only is hidden from sight, never removed
    (`display: none`) from the page.

### Performance baselines

21. The reference phone is Chromium at 360 by 740 with 4x CPU throttling and a 4G
    profile (9 Mbit/s down, 1.5 Mbit/s up, 170 ms latency), cold cache.
22. Interactive. The room page marks `nock:interactive` once per load, right after
    the first snapshot's grid is shown; a reconnection adds none, a page with no
    snapshot sets none. On the reference phone, a 13 by 17 grid (FX-02) is
    interactive within 2.5 s, as the median of three cold loads.
23. Local echo. A typed letter shows in its cell within 50 ms (p95) on the
    reference phone.
24. Relay. With 8 players each typing 2 letters a second, every edit is answered,
    and relayed to the others within 100 ms (p95); a letter typed in one page
    shows in another within 300 ms (p95) under 4x CPU throttling.
25. Bounded clients. A connection may have at most `max_outbound_messages`
    (1000) messages queued and unread: at the next it is stalled, its queue
    dropped, closed once with 4507 and counted as disconnected; the room never
    waits for it. It may have at most `max_inbound_pending` (100) inputs posted
    and not yet applied, joined or not: the next frame and every later one are
    dropped, the connection is closed with 1008 without waiting for the room and
    counted as disconnected; the inputs before still apply. Neither code is
    final: the page reconnects (`platform/realtime.md`).
26. Frame size. The server accepts frames of at most 8,192 bytes
    (`WS_MAX_SIZE_BYTES`): a larger one closes the socket with 1009 before it is
    buffered; one of 4,097 to 8,192 bytes reaches the app and gets
    `invalid_message`, the socket open. Binary frames follow the same limits.
27. Serving. `uv run python -m nock` runs `nock.server.app` with
    `server_config`: `ws_max_size` 8192, no access log, log level `warning`,
    uvicorn's defaults otherwise; the address is `NOCK_HOST`:`NOCK_PORT`
    (default `127.0.0.1`:8000); the rooms live in the SQLite file
    `NOCK_DATABASE` when it is set, in memory when it is unset or empty. The
    variables and their checks: `platform/serving.md`.

### Look

The focus ring, colour pairs, fonts and icons: `_design/foundation.md`
(« Components », « Focus », « Colour tokens », « Typography », « Icons », « How
conformance is checked »).

## Acceptance criteria

- **AC-1** Keyboard only: on the catalogue, Tab and Enter press the force filter
  and open a grid's room, joined; there, Tab reaches the grid, `T` and `A` fill
  (1, 0) and (1, 1), ArrowDown moves, Backspace erases, Ctrl+Z undoes; the Aide
  menu's checks and undo, the Salon's link, the lock, help mode and save of the
  host settings sheet opened from the Menu, an invited player's nickname form
  and the host's remove button are each reached and worked, Bob ending removed.
  (← 035 AC-1)
- **AC-2** Each element the walk of AC-1 reaches shows rule 14's outline; after
  Escape then Tab moved the focus to the clue bar, the selected cell keeps its
  solid outline and no other letter cell has one; a focused scrolling stream list
  shows its whole outline at 360 by 740, 568 by 320 and 1280 by 720. (← 035 AC-2)
- **AC-3** With the grid focused and (1, 0) selected: Tab selects the next word;
  Escape then Tab focuses the clue bar's previous-word button and Escape then
  Shift+Tab the « Menu » button, the selection unchanged and the Tab not
  cancelled; Escape, `T`, Tab types `T` then selects the next word; the grid's
  description is the hint. (← 035 AC-3)
- **AC-4** On FX-01, selecting (2, 2) down announces « Artiste muet, vertical, 4
  lettres, lettre 2 », ArrowDown « … lettre 3 », the switch to across « Sans
  contenu, horizontal, 4 lettres, lettre 2 »; the region is polite, hidden from
  sight, empty with nothing selected and silent for the same selection.
  (← 035 AC-4)
- **AC-5** FX-01 exposes one grid, 5 rows and 25 gridcells; `cell-2-2` is (2, 2);
  with nothing selected every letter cell is `aria-selected="false"` and the grid
  has no `aria-activedescendant`; after a tap on (2, 2) it is `cell-2-2` and that
  cell alone is `true`; the cells keep their positions. (← 035 AC-5)
- **AC-6** With the switch on, Jean-Luc (colour 1) and Ana (colour 2) on (2, 2)
  show a square and a triangle inside the cell, the roster shows the same icons,
  and an icon follows a moved selection; off, the cursors are triangles with no
  text. A locked `T` is bold and an unlocked `M` is not; the rows of an active,
  an idle and a disconnected player have opacity 1, read « actif », « inactif »
  and « déconnecté », and their nicknames are plain, italic, and italic struck
  through. (← 035 AC-6, 035 AC-7)
- **AC-7** On the catalogue with progress, the room with players in every state
  and a locked, a wrong and a remote letter, a flash, a lost connection, the
  nickname form in error, a solved and a full wrong grid, and a not-found room,
  at 1280 by 720 and 360 by 740, no text is under 4.5:1. (← 035 AC-8)
- **AC-8** In the same states `lang` is `fr` and every text, label, title,
  placeholder and alt is a `fr.json` value filled in or data; `Loading…`, `Check
  word`, a bare `Salle` and `Grille n° deux` would be flagged, `Salon ABC123`,
  `Grille n° 2`, `0:00` and `Ana a rejoint le salon` accepted. (← 035 AC-9)
- **AC-9** On a touch phone, the 26 letter keys and « Effacer » are buttons with
  `tabindex` -1 named `A` to `Z` and « Effacer », none hidden from the
  accessibility tree; tapping (1, 0), `T` then « Effacer » leaves the focus on the
  grid; 60 Tabs or Shift+Tabs from the grid never land on a key; a key focused by
  script shows rule 14's outline. (← 035 AC-10)
- **AC-10** Five others on (2, 2) of FX-01 at 1280 by 720 show four cursors in
  the four corners by arrival and none for the fifth; when the second leaves, the
  fifth takes its corner; seven on a 25 px cell (FX-02 at 360 by 740) and four
  on a cell under 20 px (568 by 320) show four, one per corner, disjoint, with no
  text; the contrast and language scans find nothing, switch off or on.
  (← 035 AC-11)
- **AC-11** A Discussion stream of 43 lines scrolls and is one Tab stop at the
  three sizes of AC-2; empty, it has no `tabindex` and is skipped; the Joueurs
  list never scrolls and only its remove buttons are stops; the lists are named
  « Joueurs » and « Discussion »; ArrowUp then ArrowDown scroll the focused
  stream; after ArrowUp, a new line leaves its scroll within 1 px and the focus
  on it; the Tab stop follows new lines and a resize within 300 ms. (← 035 AC-12)
- **AC-12** Three cold loads of a FX-02 room on the reference phone each set the
  mark, at a median of at most 2500 ms, the page joined with its 221 cells, and
  a letter typed after shows; a not-found room sets no mark; a reconnection adds
  none. (← 036 AC-1)
- **AC-13** 40 letters typed 250 ms apart on FX-02 on the reference phone show
  in their cell within 50 ms at the p95. (← 036 AC-2)
- **AC-14** Eight clients each sending an edit every 500 ms for 10 s on FX-02:
  all 160 edits are answered with their `letter_changed`, every client receives
  all 160, and the p95 of the 1,120 relay times is at most 100 ms; six such
  clients plus Ana typing 20 letters 500 ms apart under 4x CPU throttling: all
  20 reach Bob's page, p95 at most 300 ms. (← 036 AC-3, 036 AC-4)
- **AC-15** With a bound of 20 outbound messages, a connection that never reads
  is stalled by the 21st and closed once with 4507 within 1 s; the others are
  told it is disconnected and keep receiving. With a bound of 5 inputs and a
  store that blocks, an edit then 7 pings close the connection with 1008 while
  the room is blocked; the edit still applies and a newcomer's snapshot holds it;
  20 edits applied one at a time never close it. (← 036 AC-5, 036 AC-6)
- **AC-16** `server_config(app).ws_max_size` is 8192; a 9,000-byte text frame
  closes the socket with 1009 and nothing arrives, an 8,000-byte one after a join
  gets `invalid_message` and the socket stays open; `python -m nock` with
  `NOCK_DATABASE` holding a room and `NOCK_PORT` set answers `GET /` with the
  client within 10 s, a join on that room gets a snapshot first, and the
  9,000-byte frame gets 1009 there too. (← 036 AC-7, 036 AC-8, 036 AC-9)

## Edge cases

- Escape with nothing selected still releases the grid; Tab then leaves it and
  nothing becomes selected (AC-3).
- Typing a letter moves the selection, so the announcement changes only by its
  position; letters are never announced (AC-4).
- A disconnected player has no cursor and does not count among a cell's four
  (`social/presence.md`, `gameplay/board.md`).
- A connection closed with 4507 or 1008 reconnects and gets a fresh snapshot
  (AC-15).
- An honest page never nears the bounds of rule 25: edits are capped at 20 a
  second and a ping comes every 2 s.

## Out of scope

- Real screen readers, an accessibility engine such as axe-core, other
  languages, right-to-left layouts, keyboard shortcuts beyond the grid's (Ctrl+Z
  undo). Reduced motion: `_design/room.md` (« 3-second notes »),
  `client/shell.md`.
- Real phones and networks; Firefox and WebKit timings; load beyond 8 players a
  room or many rooms at once; bundle size budgets.
- Limits per address: `lobby/rooms.md`, `admin/operations.md`,
  `account/account.md`. The environment
  variables and their checks: `platform/serving.md`.

## Code

- `web/src/app.css`: focus ring, `visually-hidden`. `web/src/lib/RoomPage.svelte`,
  `GridViewport.svelte`: grid roles, announcement, grid release, interactive
  mark. `InAppKeyboard.svelte`, `remoteSelections.ts`, `scrollingLists.ts`,
  `i18n.ts`, `web/src/i18n/fr.json`.
- `src/nock/hub.py`: the bounds, `STALLED_CLOSE_CODE`, `FLOOD_CLOSE_CODE`;
  `src/nock/room.py`: `RoomConfig`; `src/nock/server.py`: routes,
  `server_config`, `WS_MAX_SIZE_BYTES`; `src/nock/__main__.py`: `main()`.
- Tests: `tests/test_spec_035_*`, `tests/test_spec_036_*`.
