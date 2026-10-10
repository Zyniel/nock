---
id: "037"
title: Integrity
status: approved
---

# 037 - Integrity

Epic E10 Quality bar (US-10.3) · Release: MVP · Epic depends on: All
The FX-01 reference grid and the glossary are in `specs/_reference.md`. The rooms
engine is defined in spec 011, joining and nicknames in spec 012, edits and their
check order in spec 015, the messages in spec 039, the room page in spec 040.

## Goal

As a team, we want a game nobody can shortcut, so that finishing means something.

These criteria apply to every story above and belong in each agent's definition of done.

## Public interface

### Server checks on edits (`nock.room.handle_message`)

"Edit" here means `edit_letter`, `erase`, `pencil_edit` and `confirm_pencil`.
`undo`, `select_cell` and the other messages are not edits.

- Check 1 of spec 015, rate limit: with `recent = [t for t in p.recent_edits if t > now - 1.0]`,
  an edit is refused with `ErrorMessage(code=RATE_LIMITED)` when
  `len(recent) >= config.max_edits_per_second` (default 20). An accepted edit sets
  `p.recent_edits = (*recent, now)`. A refused edit adds nothing, so refusals do
  not extend the limit.
- Check 2 of spec 015, letter cell: `(row, column)` outside the grid, or the
  position of a clue cell or an empty cell, is refused with
  `ErrorMessage(code=NOT_A_LETTER_CELL)`.
- Letter: the protocol (spec 039 `Letter`) already rejects anything but one
  character `A` to `Z`; such a frame is answered `invalid_message` by the hub and
  never reaches `handle_message`.
- Membership: a socket that has not joined gets `not_joined` (spec 040); a socket
  belongs to one room, chosen by its URL, so no message can reach another room. A
  removed player's socket is closed (spec 014).

Every refusal leaves the state and the `seq` unchanged and sends nothing to anyone
but the sender.

### Server checks on frames (`nock.hub`)

- `MAX_FRAME_BYTES: int = 4096` in `nock.hub`. A text frame longer than 4,096 bytes
  in UTF-8, or a binary frame longer than 4,096 bytes, is answered with
  `ErrorMessage(code=INVALID_MESSAGE)` without being parsed; the socket stays open.

### What a browser may receive

An answer letter is earned at a cell when a player typed it there (an accepted
`edit_letter`), or when the room revealed it (spec 024). No payload the server
sends to a browser, HTTP or WebSocket, contains:

- the key `"answer"` or `"solution"`;
- any of the eight FX-01 answers `TAMIS`, `NAVAL`, `MIME`, `IDES`, `SENT`, `VIDE`,
  `AMEN`, `LEST` as a substring;
- a letter at a cell (`letter_changed`, `cell_locked`, a `LetterCellView` of a
  snapshot) other than one earned there before that payload was sent.

### Client: escaping

- Every nickname, chat text and clue text is inserted as text, never as HTML: no
  `{@html ...}` in any `web/src/**/*.svelte` file, and no `innerHTML`,
  `outerHTML`, `insertAdjacentHTML` or `document.write` in any `web/src/**/*.ts` or
  `.svelte` file.
- The server refuses nicknames with `<`, `>` or `&` (spec 012); the client escapes
  anyway, since the protocol allows them (spec 039 checks length only).

### Test harness

- Full game (AC-1, WebSocket): with `RoomConfig(max_edits_per_second=1000)`, the
  test records every text frame received by each client, and every HTTP response
  body of the test (`POST /api/rooms` included). Players `Ana` and `Bob` join a
  room created by `POST /api/rooms` on FX-01 (catalogue entry 1); together they
  type the 18 letters, Ana the across words and Bob what is left of the down words,
  with three wrong letters first (`X` at (1, 0), (2, 2), (4, 4)) then corrected,
  and one erase; a third client `Cy` joins after 9 letters and stays to the end.
  The checker replays the frames in order, keeping for each cell the set of letters
  earned so far (from each client's own sent and accepted edits, known from the
  `letter_changed` events), and checks the three rules above on every frame.
- Full game (AC-1, browser): Playwright records every `framereceived` of every
  WebSocket (`page.on("websocket")`) and every response body of the page
  (`page.on("response")`, text bodies only) while one page on the live server
  opens a room registered on FX-01, joins as `Ana` and types the 18 letters word
  by word (spec 008), 60 ms or more between keys so the default limit of AC-3 is
  never reached; the checks then run on the records.
- Rate limit (AC-3): `RoomRegistry(clock=fake_clock)`; with the clock frozen, all
  edits of a burst share one `now`.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-10.3.1) (WebSocket; browser with live server) No payload sent to a browser contains an answer letter the room has not earned. An automated test inspects all traffic of a full FX-01 game. WebSocket: in the full game of the test harness, every recorded frame and HTTP body passes the three rules of "What a browser may receive", and Cy's snapshot holds exactly the 9 letters typed before it joined. Browser: in the recorded traffic of the browser game, every WebSocket frame and every response body passes the same three rules, and at least one frame is a `snapshot` and 18 are `letter_changed`.
- **AC-2** (AC-10.3.2) (Python; WebSocket) The server accepts an edit only if it is one A to Z letter, on a letter cell of the room's grid, from a member of the room. WebSocket, on a FX-01 room with a joined client: `edit_letter` with `"letter"` `"a"`, `"É"`, `"AB"`, `"1"` or `""` is answered `invalid_message`; `edit_letter` and `erase` at (0, 0) (a clue cell), (5, 0), (0, 5) and (9, 9) are answered `not_a_letter_cell`; a socket that has not joined sending a valid `edit_letter` at (1, 0) gets `not_joined`; after each, the room's `seq` and `grid_state` are unchanged and the other joined client receives nothing. A valid `edit_letter` at (1, 0) with `T` is then accepted (`letter_changed`). Python: `handle_message` with `EditLetter(row=0, column=0, letter="T")` and with `Erase(row=4, column=5)` returns the same state, no entry and one `ErrorMessage` with code `not_a_letter_cell`.
- **AC-3** (AC-10.3.3) (Python; WebSocket with a fake clock) A client sending more than 20 edits a second is throttled. Python: on a FX-01 room with player `p1`, 21 `edit_letter` messages applied with the same `now` give 20 `letter_changed` entries then one `rate_limited` reply; at `now + 0.5` an edit is still refused; at `now + 1.0` it is accepted; a second player `p2` at `now` is not affected by `p1`'s count. WebSocket: with the fake clock frozen, a client sends 25 edits; it receives 20 `letter_changed` events and 5 `error` messages with code `rate_limited`, the other client receives exactly the 20 events, and the room's `seq` grew by 20; after `advance(1.0)` the next edit is accepted.
- **AC-4** (AC-10.3.4) (static; WebSocket; browser with mocked socket) Nicknames and chat are escaped: a nickname containing an HTML tag displays as plain text. Static: the scan of "Client: escaping" finds no `{@html` in `.svelte` files and none of the four DOM calls in `.svelte` and `.ts` files under `web/src`. WebSocket: a join with nickname `<b>Eve</b>` is answered `invalid_nickname` (spec 012). Browser: given a snapshot whose players include `p2` with nickname `<b>Eve</b>` and `p3` with nickname `<img src=x>`, the `roster-nickname` of `p2` has the text `<b>Eve</b>` and that of `p3` the text `<img src=x>`, the roster holds no `b` and no `img` element, and no dialog opens.

## Edge cases and errors

- Rate window (AC-3): the window is the last second, sliding: 20 edits at `t` and
  one at `t + 0.999` refuse the latter; at `t + 1.0` the 20 no longer count
  (`t > now - 1.0` is false).
- Per player (AC-3): the limit is per player, not per room; a player with two tabs
  has one connection at a time (spec 012), so one count.
- What a refusal costs (AC-3): nothing; the throttled client stays connected and
  its page drops the refused letters from its pending queue (spec 015).
- Undo and selection (AC-3): not counted. Their abuse is not throttled in the MVP.
- Frames (all): a frame of 4,097 bytes gets `invalid_message`; a frame of exactly
  4,096 bytes is parsed. Binary frames follow the same rules as text (spec 040).
- Messages of other kinds before join (AC-2): `not_joined` for every valid
  message, as spec 040 says.
- Answers in HTTP (AC-1): `GET /api/grids` and `GET /api/grids/<n>` (spec 004) send
  summaries only; the test inspects them when the page fetches them.
- Earned letters (AC-1): a letter typed then replaced stays earned at that cell
  (it was typed there); a letter typed at one cell is not earned at another.
  Wrong letters may appear: they were typed. After spec 024, revealed letters are
  earned when their `cell_locked` (`revealed` true) is sent, not before.
- Clue texts (AC-1): clue texts are sent (spec 039); FX-01's clues contain none of
  the eight answers as a substring, so the substring rule holds for them.
- Escaping (AC-4): applies to every place a nickname is shown (roster, feed of spec
  013, flags and chat of specs 021 and 022) and to chat text; the reviewer checks
  later specs against the static rule.
- HTML in clue text (AC-4): shown as text too.

## Out of scope

- Nothing stated in the backlog (epic E10).
- Accessibility: spec 035.
- Performance: spec 036.
- Privacy and operations: spec 038.
- Banning an address, captchas, or throttling messages other than edits.
- Content Security Policy headers (a later hardening task).
- Checking reveals (spec 024) and chat (spec 022) traffic: those specs extend AC-1's
  checker when they are built.

## Work packages

None.

## Decisions

Approved by the human on 2026-10-10, with the pick of each item kept as written.
Each one is already part of the spec above.

1. "More than 20 edits a second" (AC-3). Options: fixed one-second buckets, or a
   sliding window; drop silently, answer an error, or disconnect. Pick: sliding
   window of 1 second per player, each refused edit answered `rate_limited` (the
   page needs one answer per edit, spec 015), no disconnection. The limit is
   `RoomConfig.max_edits_per_second`, so other specs' tests can raise it.
2. Which messages are edits. Pick: `edit_letter`, `erase`, `pencil_edit`,
   `confirm_pencil`; `undo` is not counted (one per key press, and it only reverts).
3. "Earned" letters (AC-1). Pick: typed at that cell by a player before the payload,
   or revealed there (spec 024). The checker also looks for the eight answers and
   the key `answer` anywhere in the traffic.
4. Full game scope (AC-1). Completion (spec 026) and checks (spec 023) are built
   later. Pick: the "full game" fills all 18 cells with mistakes and corrections and
   a late joiner; specs 023, 024 and 026 add their messages to the same checker when
   they are built.
5. Frame size. Not asked by the backlog; any valid message is far below 1 KiB.
   Pick: refuse frames over 4,096 bytes with `invalid_message` before parsing, so a
   member cannot make the room task parse megabytes.
6. Escaping rule (AC-4). The server's nickname rule (spec 012) already refuses tags,
   so the visible check uses a mocked snapshot. Pick: the static scan bans
   `{@html` and raw HTML DOM calls in the client, plus the mocked-socket check.

## Open questions

None.
