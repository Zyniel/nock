---
area: lobby
file: summaries
status: done
---

# lobby/summaries - Room summaries and « Mes salons »

## Purpose

A player finds the rooms they have a seat in from the catalogue page: « Mes
salons » lists them, newest activity first, each with a link that resumes it.
The server answers from the identities the device holds and says nothing of a
room they are no member of.

## Depends on

- `lobby/joining.md`: members and past players, the identities a device stores,
  the resume by token.
- `lobby/lifetime.md`: the last edit time, expiry and the deletion a lookup
  runs first.
- `gameplay/history.md`: the result fields of a summary; the record « Mes
  salons » writes for a solved room.

## Rules

### The summaries route

1. `POST /api/rooms/summaries` takes `{"rooms": [{"code", "resume_token"}]}`,
   at most 100 keys, and answers one summary per room that some key holds a
   member's token for, newest last activity first, then code order. A summary is
   the code, the grid number (null outside the catalogue), width, height, the
   members' nicknames (past players in leaving order, then players, each once
   but `--`, once per erased member),
   the last activity (the last edit time, UTC), `solved` and the result fields
   of `gameplay/history.md`; no letter. The answer never says why a room is left
   out; it is not counted by the wrong-code throttle, makes no room live and
   writes nothing. An invalid body answers 422.

### « Mes salons »

2. The catalogue page sends the identities whose code matches `^[A-Z0-9]{6}$`
   and whose token matches `^[A-Za-z0-9_-]{16,128}$`, in requests of at most
   100 keys, and lists the summaries in the server's order. With none to send
   it has no « Mes salons »; while loading and with no summary it shows
   nothing; a failed request, or an answer that is not a list of summaries,
   shows `my_rooms.error`. A summary's `last_activity_at`, and its
   `finished_at` when set, is a date only as a date-time in ISO 8601 with a
   time zone, its seconds' fraction read when present
   (`2026-10-14T08:30:00.123456+00:00`, `2026-10-14T08:30:00Z`), in every
   engine; any other string makes the answer no list of summaries. The rest
   of the page never waits for it. A row
   shows the grid label (`my_rooms.unnumbered` without a grid number), size,
   players, last activity in the browser's time zone,
   `catalogue.progress.finished` when solved, and the link `my_rooms.open` to
   `/r/<code>`, named `my_rooms.open_label`. A room left out is not listed,
   and its identity stays on the device.

### Look

- « Mes salons » rows: `_design/pages.md`, « Catalogue »; its error line:
  « States: opening, loading, empty, error ».

## Acceptance criteria

- **AC-1** In room A, where Bob timed out and Cy was removed, Ana's or Bob's
  token gets one summary naming `BOB` then `ANA`; Cy's token, an unknown token or
  code gets `[]`; 101 keys get 422; an expired room (`lobby/lifetime.md`) is
  left out and deleted. (← 032 AC-4)
- **AC-2** With identities for `XYZ789` and `ABC234`, one corrupt and one with a
  15-character token, « Mes salons » sends the two valid keys and lists `Grille n°
  2`, `5 × 5`, « Joueurs : Ana, Bob », « Dernière activité : 14 octobre 2026 à
  10:30 » in a browser set to Paris time, and « Reprendre », whose link resumes
  the room without the form. While its request waits, or after `[]`, it takes no
  space and shows no text; a 500 shows « Impossible de charger vos salons. » and
  the grids still load. (← 032 AC-5, 046 AC-12)
- **AC-3** « Mes salons » keeps the baselines of `product.md`: no contrast
  or language offender, every link reached by Tab with a visible focus, and
  no horizontal scroll with 8 players of 20 characters. Its rows follow the
  catalogue design ("Look"). (← 032 AC-6, 046 AC-11)
- **AC-4** An answer whose one summary has `last_activity_at`
  `2026-10-14 08:30:00Z` (a space for the `T`), or `2026-10-14T08:30:00` (no
  time zone), shows « Impossible de charger vos salons. » and no row, while
  `2026-10-14T08:30:00.5Z` lists the row.
- **AC-5** In room A, where Bob joined before Zoé and Lou, who then deleted
  their accounts, Bob's token gets one summary whose players are `BOB`, `--`,
  `--`.

## Edge cases

- Several keys for one room give one summary; one member's key is enough (AC-1).
- A past player dropped by the cap of 100 (`lobby/joining.md` rule 12) is no
  member: their key gets no summary (AC-1).
- More than 100 identities go in several requests, listed in the server's order
  (AC-2).

## Out of scope

- Removing a room from « Mes salons », sorting it, clearing identities of rooms
  the summaries no longer return.
- Who is a member, the identities and the resume: `lobby/joining.md`. Room
  lives, expiry and the sweep: `lobby/lifetime.md`. The result fields and
  « Grilles terminées »: `gameplay/history.md`. The identities an account
  stores on the device before « Mes salons » asks: `account/my-account.md`. The
  wrong-code throttle: `lobby/rooms.md`. The catalogue column « Mes salons »
  sits in: `content/library.md`.

## Code

- `src/nock/room.py`: `room_summary`, `team_nicknames`; `src/nock/hub.py`:
  `room_summaries`;
  `src/nock/server.py`: the summaries route.
- `web/src/lib/myRooms.ts`, `web/src/lib/MyRooms.svelte`: « Mes salons »;
  `FocusableLink.svelte`: its links.
- Tests: those of the pointers, in `tests/test_spec_032_ac04_*`,
  `tests/test_spec_032_ac05_*`, `tests/test_spec_032_ac03_ac05_*` (AC-5),
  `tests/test_spec_032_ac06_*`, `tests/test_spec_046_ac11_ac13_*` (AC-11,
  AC-12); `tests/test_summaries_*` for later criteria.
