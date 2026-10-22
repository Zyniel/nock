---
id: "010"
title: Instant solo start
status: done
---

# 010 - Instant solo start

Epic E2 Solo solving (US-2.5) · Release: MVP · Epic depends on: E1
The FX-01 reference grid is in `specs/_reference.md`. The catalogue, its items and
`nock.progress` are those of spec 004; the room page and grid those of specs 040
and 006 to 009; room creation is spec 011, guest join spec 012, shared letters
spec 015. Built after 011, 012, 015 and 016.

(Note from the lead, 2026-10-22: refined by spec 043, the design's room layout
(`_design.md` section 8): the roster and the share link move into the Salon's
Joueurs tab, which is in the DOM while closed. No criterion of this spec changes:
AC-3 and AC-6 read the `roster-player` items and their nicknames, which keep their
ids and texts.)

## Goal

As a player, I want to start a grid alone at once, so that I can invite people later without losing my letters.

A solo game is a room of one, so nothing here is rewritten when other players join.

## Public interface

No new Python name and no new protocol message. There is no separate solo mode: a
solo game is a room created from the catalogue with one player in it, and inviting
someone is sending its link (spec 011). Nothing is converted when a second player
joins.

### Play button

Each `catalogue-item` (spec 004), on the catalogue page and on the grid page
`/g/<number>`, holds a button `data-testid="catalogue-play"` labelled
`t("catalogue.play")`. One tap on it:

1. sets `nock.progress[<number>]` to `"started"`, unless it is already
   `"finished"` (the `localStorage` key of spec 004);
2. creates a room on that catalogue grid with spec 011's creation request;
3. on success, writes the room record below for the new code,
   `{"grid": <number>, "selection": null}`, then loads
   `/r/<code>` (`location.assign`);
4. on failure (network error, or any status other than success), stays on the page,
   re-enables the button and shows `t("catalogue.play_failed")` in
   `data-testid="catalogue-error"`. Step 1 is kept.

While the request runs, the button is disabled, so a second tap creates nothing.

Room creation request, as defined by spec 011 (spec 011 is the reference, and this
spec's tests do not depend on the shape): `POST /api/rooms` with the JSON body
`{"grid_number": <number>}`, answering 201 with `{"code": "<code>", "share_url": "..."}`
on success. A room can only be created on a published grid.

### Room record on this device

`localStorage` key `nock.room.<code>` (for example `nock.room.ABC123`), a JSON
object. It holds only what this spec needs, the grid number and the selection; it
holds no identity. The identity of a player in a room (player id, resume token,
nickname) is spec 012's `nock.identity.<code>`, the one identity record of a room
for every player, the creator included.

| Field | Value |
| --- | --- |
| `grid` | the catalogue number the room was created from, or `null` when unknown (a room joined by link) |
| `selection` | `{"row": r, "column": c, "direction": "across" or "down"}` or `null` |

Other specs may add fields; this spec keeps unknown fields when it rewrites the
record. Text that is not JSON, or not an object, is read as no record.

- The room page writes `selection` every time the selection changes (spec 007),
  creating the record with `grid: null` when none exists.
- After the first snapshot of a page load, if the record holds a `selection` whose
  cell is a letter cell of the snapshot's grid with a word in that direction, that
  selection is restored (as if tapped, so it sends `select_cell`). Otherwise
  nothing is selected.
- When the room page receives a `grid_solved` event, or a snapshot with
  `solved: true`, and the record's `grid` is a number, `nock.progress[<grid>]`
  becomes `"finished"`.

### Joining as the creator

The room page chooses how to join by the rule of spec 012 ("Room page flow",
step 2), which is the reference; restated here for the creator. When the socket
opens:

1. `nock.identity.<code>` holds a valid identity (anyone who joined this room on
   this device before, the creator included): the page joins at once, no form,
   with the stored nickname and the stored resume token. This is the same player
   again (spec 012 AC-5).
2. Otherwise, `nock.room.<code>` holds a record whose `grid` is a number (the room
   was created from the catalogue on this device, "Play button" step 3): the page
   joins at once, no form, with `"resume_token": null` and as nickname
   `nock.nickname` (spec 012) when it is stored and passes spec 012's nickname
   rule, otherwise `t("room.default_nickname")` (`Invité`).
3. Otherwise (a record with `grid: null`, or no record): the nickname form of spec
   012.

In cases 1 and 2 the snapshot that answers the join stores
`nock.identity.<code>` (spec 012, step 5), so a reload of the creator's page takes
case 1 and resumes the same player. A join at once never writes `nock.nickname`
(spec 012).

### New `fr.json` keys

| Key | Value |
| --- | --- |
| `catalogue.play` | `Jouer` |
| `catalogue.play_failed` | `Impossible de lancer la partie. Réessayez.` |

### Test harness

- "Browser with live server": the `live_server`, `room_registry` and `catalogue`
  fixtures (specs 040 and 004), with a catalogue holding FX-01 as entry 1,
  published, force 2.
- Letters are typed with spec 008 (tap a cell, `page.keyboard.press`).
- A second player is a second browser context (`browser.new_context()`) opening the
  same `/r/<code>` and joining through spec 012's guest join.
- Request failures are forced with `page.route("**/api/rooms", ...)` answering 500
  or aborting.
- "Browser with mocked socket": spec 040's mock, with `nock.room.ABC123` seeded by
  `context.add_init_script` before `page.goto`.
- `nock.nickname` is seeded the same way (`context.add_init_script`) before the
  first `page.goto`. On the live server, the frames a page sends are recorded with
  `page.on("websocket")` and each socket's `framesent` event, and parsed with
  `parse_client_message`.
- Engines: every criterion runs in Chromium, Firefox and WebKit
  (`specs/_architecture.md`). No check of this spec is Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-2.5.1) (browser with live server) From the catalogue, a grid is playable in one tap, with no sign-up. On `/`, one click on the `catalogue-play` of item 1 and no other action leads to a URL matching `/r/[A-Z0-9]{6}$` whose room page reaches `data-status="joined"`, `data-grid="5x5"`, 25 `cell` elements, and no visible `nickname-form` or `nickname-input` (amended on 2026-10-11 for spec 014: the solo player is the host and sees the host's settings form, which is not a sign-up); then tapping (1, 0) and pressing `t` shows `T` in (1, 0).
- **AC-2** (AC-2.5.2) (browser with live server) A solo game becomes a shared room when I invite someone, and every letter is kept. Player A starts FX-01 from the catalogue and types `T`, `A` from (1, 0) across. Player B opens A's room URL in a second context and joins. Then B's grid shows `T` at (1, 0) and `A` at (1, 1); A's page still has the same `data-room-code`, still shows `T` and `A`, and was not reloaded (a value set on `window` before B joined is still there).
- **AC-3** (AC-2.5.3) (browser with live server) Reloading the page restores my letters and my selected cell. Player A starts FX-01 from the catalogue, types `T`, `A` from (1, 0) across, then taps (2, 2) twice (`down`); after `page.reload()`, the room page reaches `data-status="joined"` with the same code and the same `data-you` as before the reload (the same player, resumed through `nock.identity.<code>`), the first frame the reloaded page sends is a `join` whose `resume_token` is the one stored before the reload, `roster` holds exactly one `roster-player`, (1, 0) and (1, 1) show `T` and `A`, and the grid has `data-selected-row="2"`, `data-selected-column="2"`, `data-direction="down"`.
- **AC-4** (new) (browser with live server) Starting a grid marks it started on this device. After the click of AC-1, `localStorage["nock.progress"]` parses to an object whose `"1"` is `"started"`, `localStorage["nock.room.<code>"]` has `grid` 1, and going back to `/` shows item 1 with `data-progress="started"`.
- **AC-5** (new) (browser with mocked socket) Solving a grid marks it finished on this device. With `nock.room.ABC123` seeded to `{"grid": 1, "selection": null}` and `nock.progress` to `{"1": "started"}`, when the mock sends a FX-01 snapshot with `seq` 0 then `{"type": "grid_solved", "seq": 1, "elapsed_ms": 1000}`, `nock.progress` becomes `{"1": "finished"}`. With the record's `grid` `null`, `nock.progress` is unchanged.
- **AC-6** (new) (browser with live server) The creator joins at once with the nickname saved on this device, or `Invité`. With `nock.nickname` seeded to `Zoé`, after the click of AC-1 the first frame the room page sends on its socket parses to `Join(nickname="Zoé", resume_token=None)`, the page reaches `data-status="joined"`, `roster` holds one `roster-player` with `data-you="true"` whose `roster-nickname` reads `Zoé`, and `localStorage["nock.identity.<code>"]` parses to an object whose `player_id` equals the room page's `data-you` and whose `nickname` is `Zoé`. In a second run with no `nock.nickname`, the first frame parses to `Join(nickname=fr.json["room.default_nickname"], resume_token=None)`, the own `roster-nickname` reads `fr.json["room.default_nickname"]`, and `nock.nickname` is still absent afterwards.

## Edge cases and errors

- Creation failure (AC-1): with `POST /api/rooms` answering 500, the click leaves
  the URL on `/`, shows `t("catalogue.play_failed")` in `catalogue-error`, and the
  button is enabled again; `nock.progress["1"]` is `"started"`.
- Double tap (AC-1): two quick clicks on `catalogue-play` send one creation
  request.
- Replaying a grid (AC-1, AC-4): each tap creates a new room; a `"finished"` status
  stays `"finished"`.
- Saved selection no longer valid (AC-3): a record selection on a clue cell, outside
  the grid, or with a direction the cell has no word in is ignored; nothing is
  selected and nothing is sent. (Note from the lead, 2026-10-15: "nothing is
  sent" leaves aside the heartbeat `ping` frames of spec 017, which the page may
  send at any time once the socket is open.)
- Corrupt record (AC-3, AC-5): `nock.room.ABC123` set to `not json` or `[]` is
  read as no record; the page joins as spec 012 says for a guest.
- Room gone (AC-3): if the reloaded room answers 4404, the page shows
  `room.status.not_found` (spec 040); the record stays.
- `localStorage` unavailable (private mode, quota): playing still creates the room
  and loads it; progress and selection are simply not kept.
- Already finished in the snapshot (AC-5): a snapshot with `solved: true` marks the
  grid finished just like the event.
- Reload identity (AC-3): the reloaded page is the same player because the
  creator's first snapshot stored `nock.identity.<code>` (spec 012), so the reload
  joins by case 1 of "Joining as the creator". The letters come from the server
  (spec 015), the selection from `nock.room.<code>`.
- Saved nickname not valid (AC-6): a `nock.nickname` that fails spec 012's rule
  (for example `A`, or `<b>`) is not used; the creator joins as `Invité`.
- Identity but no room record (AC-6): a stored `nock.identity.<code>` wins over
  everything (case 1), whatever `nock.room.<code>` holds.
- Corrupt identity (AC-3): a `nock.identity.<code>` that is not valid (spec 012)
  is ignored; with a room record whose `grid` is a number the page joins as a new
  player by case 2, otherwise it shows the form.
- Creator refused (AC-6): if the server answers the creator's join with
  `invalid_nickname`, the page falls back to the nickname form (spec 012 step 6).

## Out of scope

- Printing and offline play (epic E2).
- Grid rendering: spec 006.
- Word selection and direction: spec 007.
- Keyboard and navigation: spec 009.
- The share link and invitation controls, room codes and throttling (spec 011);
  the nickname form and player list (spec 012); presence (spec 013); host
  controls (spec 014).
- Resuming the last room of a grid from the catalogue (spec 032), and a list of my
  rooms.
- Automatic reconnection without a reload, and the 5-minute resume window (spec
  017).
- Completion detection on the server (spec 026): this spec only reacts to its
  event.

## Work packages

None.

## Decisions

Approved by the human on 2026-10-10, with the pick of each item kept as written,
except item 2, which the human confirmed and asked to make precise (one identity
record per room, shared with spec 012). Each one is already part of the spec
above.

1. Room creation request. Pick: `POST /api/rooms` with `{"grid_number": <number>}`
   answering with the code, only on published grids; spec 011 defines it that way
   (201, `code` and `share_url`). The tests of this spec observe only the
   navigation and the failure message.
2. Creator's join. "One tap, no sign-up" conflicts with a nickname form shown on
   every room page. Decision (human): the player who starts a grid from the
   catalogue joins at once, with no form, using `nock.nickname` (spec 012) or, if
   none, `t("room.default_nickname")` (`Invité`). One identity record per room:
   spec 012's `nock.identity.<code>` (player id, resume token, nickname) is the
   identity of everyone, the creator included; `nock.room.<code>` keeps only the
   grid number and the selection. The two records stay separate rather than
   merged because the room record exists before the first snapshot (no token yet)
   and is also written for rooms joined by link. The room page's rule is spec
   012's "Room page flow" step 2: stored identity, then join at once as the same
   player; else a room record with a numeric `grid`, then join at once as a new
   player; else the form. A reload resumes the same player in both cases (AC-3
   here, spec 012 AC-5); AC-6 checks the creator's nickname.
3. "Becomes a shared room when I invite someone". Options: a solo mode converted
   into a room, or a room from the start. Pick: a room from the start; inviting is
   sharing its link, so nothing is converted and the code never changes.
4. When a grid is "started". Options: on the play tap, on the first letter, or on
   joining any room on that grid. Pick: on the play tap. Rooms joined by link do
   not know their catalogue number (no message carries it), so they mark nothing.
5. Where the selection is kept for a reload. Options: `localStorage` per room, or
   the server (a player's selection, spec 013). Pick: `localStorage` per room, so
   it works whoever the server thinks the reloaded player is.
6. Replay of a started grid. Options: create a new room, or reopen the last one.
   Pick: a new room; resuming is spec 032.

Added on 2026-10-11 by the lead, under the human's instruction to take technical
decisions: AC-1's "no visible input" meant no sign-up form. It now checks the
nickname form only, since spec 014 shows the host's settings form to the solo
player, who is the host.

## Open questions

None.
