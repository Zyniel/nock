---
id: "010"
title: Instant solo start
status: approved
---

# 010 - Instant solo start

Epic E2 Solo solving (US-2.5) · Release: MVP · Epic depends on: E1
The FX-01 reference grid is in `specs/_reference.md`. The catalogue, its items and
`nock.progress` are those of spec 004; the room page and grid those of specs 040
and 006 to 009; room creation is spec 011, guest join spec 012, shared letters
spec 015. Built after 011, 012, 015 and 016.

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
3. on success, writes the room record below for the new code, then loads
   `/r/<code>` (`location.assign`);
4. on failure (network error, or any status other than success), stays on the page,
   re-enables the button and shows `t("catalogue.play_failed")` in
   `data-testid="catalogue-error"`. Step 1 is kept.

While the request runs, the button is disabled, so a second tap creates nothing.

Room creation request, as assumed from spec 011 (written in parallel; spec 011 is
the reference if they differ, and this spec's tests do not depend on the shape):
`POST /api/rooms` with the JSON body `{"grid_number": <number>}`, answering
`{"code": "<code>"}` on success. A room can only be created on a published grid.

### Room record on this device

`localStorage` key `nock.room.<code>` (for example `nock.room.ABC123`), a JSON
object:

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

When the room page opens a room whose record `nock.room.<code>` exists, it joins
at once, with no nickname form, sending `Join` with the nickname rule of spec 012
for a known player (until spec 012 defines one: `t("room.default_nickname")`).
Rooms with no record follow spec 012 (guest join).

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

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-2.5.1) (browser with live server) From the catalogue, a grid is playable in one tap, with no sign-up. On `/`, one click on the `catalogue-play` of item 1 and no other action leads to a URL matching `/r/[A-Z0-9]{6}$` whose room page reaches `data-status="joined"`, `data-grid="5x5"`, 25 `cell` elements, and no visible `input` element; then tapping (1, 0) and pressing `t` shows `T` in (1, 0).
- **AC-2** (AC-2.5.2) (browser with live server) A solo game becomes a shared room when I invite someone, and every letter is kept. Player A starts FX-01 from the catalogue and types `T`, `A` from (1, 0) across. Player B opens A's room URL in a second context and joins. Then B's grid shows `T` at (1, 0) and `A` at (1, 1); A's page still has the same `data-room-code`, still shows `T` and `A`, and was not reloaded (a value set on `window` before B joined is still there).
- **AC-3** (AC-2.5.3) (browser with live server) Reloading the page restores my letters and my selected cell. Player A starts FX-01 from the catalogue, types `T`, `A` from (1, 0) across, then taps (2, 2) twice (`down`); after `page.reload()`, the room page reaches `data-status="joined"` with the same code, (1, 0) and (1, 1) show `T` and `A`, and the grid has `data-selected-row="2"`, `data-selected-column="2"`, `data-direction="down"`.
- **AC-4** (new) (browser with live server) Starting a grid marks it started on this device. After the click of AC-1, `localStorage["nock.progress"]` parses to an object whose `"1"` is `"started"`, `localStorage["nock.room.<code>"]` has `grid` 1, and going back to `/` shows item 1 with `data-progress="started"`.
- **AC-5** (new) (browser with mocked socket) Solving a grid marks it finished on this device. With `nock.room.ABC123` seeded to `{"grid": 1, "selection": null}` and `nock.progress` to `{"1": "started"}`, when the mock sends a FX-01 snapshot with `seq` 0 then `{"type": "grid_solved", "seq": 1, "elapsed_ms": 1000}`, `nock.progress` becomes `{"1": "finished"}`. With the record's `grid` `null`, `nock.progress` is unchanged.

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
  selected and nothing is sent.
- Corrupt record (AC-3, AC-5): `nock.room.ABC123` set to `not json` or `[]` is
  read as no record; the page joins as spec 012 says for a guest.
- Room gone (AC-3): if the reloaded room answers 4404, the page shows
  `room.status.not_found` (spec 040); the record stays.
- `localStorage` unavailable (private mode, quota): playing still creates the room
  and loads it; progress and selection are simply not kept.
- Already finished in the snapshot (AC-5): a snapshot with `solved: true` marks the
  grid finished just like the event.
- Reload identity (AC-3): whether the reloaded page is the same player (resume
  token) is spec 017's; this spec only needs the letters, which the server keeps
  (spec 015), and the selection, which this device keeps.

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
- Same player identity after a reload (spec 017).
- Completion detection on the server (spec 026): this spec only reacts to its
  event.

## Work packages

None.

## Open questions

Each pick below is already written into the spec. The lead confirms or changes it.

1. Room creation request. Spec 011 is being written in parallel. Pick: assume
   `POST /api/rooms` with `{"grid_number": <number>}` answering `{"code": ...}`,
   only on published grids; the lead aligns 011 with it (or this spec with 011).
   The tests of this spec observe only the navigation and the failure message.
2. Creator's join. "One tap, no sign-up" conflicts with a nickname form shown on
   every room page. Pick: a room with a record on this device (created here, or
   joined before) joins at once with no form; spec 012's form is for the others.
   The lead aligns spec 012 with this.
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
