---
area: lobby
file: lifetime
status: done
---

# lobby/lifetime - Room lifetime: when a room expires and the sweep that deletes it

## Purpose

A room outlives its players long enough for them to come back, and no longer:
each kind of room has a room life, set by the operator, after which a sweep
deletes it with all its data.

## Depends on

- `lobby/host.md`: creator and anonymous rooms, a creator room played as
  anonymous while accounts are off, the deletion at the creator's erasure.
- `gameplay/rules.md`: `grid_solved`, and that no edit is accepted once solved.
- `platform/server.md`: the store, `main()`, the order and the wording of its
  variable checks.

## Rules

### Times

1. An edit is a `letter_changed` or a `cell_locked`. A room's last edit time is
   its latest edit's, or the start of its life; it never goes back.
2. A room's solve time is the time of its `grid_solved`, stored with the room,
   in `room_times` (`src/nock/store.py`) beside `last_edit_at`, by the step that
   solves it; none while unsolved. The solving letter and `grid_solved` are one
   step and no edit is accepted once solved (`gameplay/rules.md` rule 3), so a
   solved room's solve time equals its last edit time: the two names stay, and
   only the variable that applies differs.

### Kinds and lives

3. A room is a creator room or an anonymous room (`lobby/host.md` rule 11), and
   solved or not. While accounts are off every room is anonymous, a stored
   creator included (`lobby/host.md` rule 15).
4. A room life is how long a room lasts after its starting point: a whole number
   of hours, 24 to 8760, one per kind, default 720. Each has a server variable,
   which gives its environment value, and a `RoomConfig` field
   (`src/nock/room.py`), which holds its effective value: an override saved
   from `/ops`, else the variable's value, else the default
   (`admin/overrides.md` rules 1, 2). The rules below read the effective value:
   - `NOCK_CREATOR_SOLVED_ROOM_HOURS` (`creator_solved_room_hours`): a solved
     creator room, from its solve time;
   - `NOCK_CREATOR_ROOM_HOURS` (`creator_room_hours`): an unsolved creator room,
     from its last edit time;
   - `NOCK_ANONYMOUS_SOLVED_ROOM_HOURS` (`anonymous_solved_room_hours`): a solved
     anonymous room, from its solve time;
   - `NOCK_ANONYMOUS_ROOM_HOURS` (`anonymous_room_hours`): an unsolved anonymous
     room, from its last edit time.

   The shortest room life is the least of the four.
5. A room is expired once more than its room life has passed since its starting
   point; at exactly its room life it is open. One function decides it, the same
   for the sweep, the lookups and the dry run of `admin/overrides.md` rule 5. A
   room that changes kind (solved; accounts
   turned off, or back on) takes the matching life from the same starting point
   from then on: one already past it goes at the next sweep or lookup.

### The sweep

6. A sweep at the app's start, then every sweep interval (the effective value
   of `NOCK_EXPIRY_SWEEP_MINUTES`, held by `RoomConfig.expiry_sweep_seconds` in
   seconds; a new value applies after the current wait, `admin/overrides.md`
   rule 9), deletes the expired rooms;
   any lookup that meets one (a socket, a summary) deletes it first. Every
   deletion for expiry, the sweep's and a lookup's, reads the room's times
   again under the registry lock before deleting: a room no longer expired by
   then (an edit moved its last edit time meanwhile) is kept, a lookup serves
   it, and the sweep does not list it among the codes it deleted.
   Deletion removes the room, its log, its snapshots and its share token,
   closes every socket opened to it, joined or not, with 4404 and nothing
   else, and writes no log entry; a page that had shown the room then shows
   the room-gone dialog
   (`client/hud.md` rule 16). The code may then be drawn again, where an old
   token matches nobody. Until the deletion, a live room's open sockets keep
   working. A sweep that fails is logged at WARNING or above, and the next one
   runs. Each sweep also runs the purge of sign-in links and sessions
   (`account/account.md` rule 20).

### The variables

7. `NOCK_EXPIRY_SWEEP_MINUTES` is a whole number of minutes, 1 to 1440, default
   60. The five variables give the environment values. Each, unset or empty,
   takes its default; set, it is
   ASCII digits only, any number of leading zeros, its value within its bounds.
   `main()` checks them after `NOCK_DATABASE` and before the account variables
   (`platform/server.md` rule 15); a refused value stops it with one line naming
   the variable and showing the value as `repr()` writes it (`platform/server.md`
   rule 19), and `python -m nock` exits with 1 without serving. An app given no
   registry reads them when it starts and fails its start with `SettingsError`
   on a refused value; one given a registry reads none, and its config gives
   the environment values.

### Stored times and migration

8. The solve time is a nullable column of `room_times`, which makes the schema's
   `user_version` 2 (the creator column made it 1, `lobby/host.md` rule 11). A
   store below 2 is migrated once at open, in one transaction: the missing
   columns are added, and each solved room gets its solve time from its stored
   state or log, or its last edit time when neither gives one; the rooms' other
   data stays.

## Acceptance criteria

- **AC-1** A room created at t0 with a letter at t0 + 10, a chat line at t0 +
  20, a check result at t0 + 25 and a locked cell at t0 + 30 has its last edit at
  t0 + 30: with `NOCK_ANONYMOUS_ROOM_HOURS` at its default, 720, it is open 720
  hours later and expired half a second after. (← 032 AC-1)
- **AC-2** A room whose last edit is at t0 + 10 survives the sweep at t0 + 10 +
  720 hours and is deleted one second later: its sockets close with 4404, its
  store rows and share link are gone, a new room may take its code, and a join
  there with an old token makes a new player. (← 032 AC-2)
- **AC-3** With `NOCK_CREATOR_ROOM_HOURS` 48, accounts on, Lea's creator room R,
  unsolved, last edited at t: a lookup at t + 48 h serves R, one half a second
  later deletes it, whether the other three lives are 24 or 8760.
- **AC-4** With `NOCK_CREATOR_SOLVED_ROOM_HOURS` 24 and `NOCK_CREATOR_ROOM_HOURS`
  8760, R solved by its last letter at s has its stored solve time s, equal to
  its last edit time, after a restart too; it is open at s + 24 h and expired
  half a second after.
- **AC-5** With `NOCK_ANONYMOUS_ROOM_HOURS` 96 and the creator lives 24, an
  anonymous room A, unsolved, last edited at t, is open at t + 96 h and expired
  half a second after.
- **AC-6** With `NOCK_ANONYMOUS_SOLVED_ROOM_HOURS` 72 and `NOCK_ANONYMOUS_ROOM_HOURS`
  24, A solved at s is open at s + 72 h and expired half a second after.
- **AC-7** With the five variables unset or empty, `room_config_from_env` gives
  720 for each life and 3,600 s for the sweep; `0024`, `24` and `8760` give 24,
  24 and 8760 hours; `NOCK_EXPIRY_SWEEP_MINUTES` `1` gives 60 s and `1440`
  86,400 s.
- **AC-8** Each life refuses `23`, `8761`, `" 24"`, `24.0`, `-24`, `24h` and
  `٢٤` (digits of another script), the sweep `0` and `1441`, with a one-line
  message naming the variable and the value as `repr()` writes it;
  `python -m nock` with `NOCK_ANONYMOUS_ROOM_HOURS` `23` prints it on stderr and
  exits with 1 without serving; an app built with no registry under that
  environment fails its start with `SettingsError`.
- **AC-9** With `NOCK_PORT` `0` and `NOCK_CREATOR_ROOM_HOURS` `23`, `main()`'s
  message names `NOCK_PORT`; with `NOCK_CREATOR_ROOM_HOURS` `23` beside a public
  URL and an SMTP host but no `NOCK_SMTP_FROM`, it names
  `NOCK_CREATOR_ROOM_HOURS`.
- **AC-10** An app started with no registry under `NOCK_EXPIRY_SWEEP_MINUTES`
  `1` and the four lives set has a registry whose config holds those lives and
  `expiry_sweep_seconds` 60.0. With the sweep interval at a short float and
  accounts on, each sweep after the first deletes a room that expired since,
  its socket closed with 4404, and purges a sign-in link older than 30 minutes
  with it.
- **AC-11** With `NOCK_ANONYMOUS_ROOM_HOURS` 48 and
  `NOCK_ANONYMOUS_SOLVED_ROOM_HOURS` 24, A last edited at t and solved by a
  letter at t + 10 h is open at t + 34 h and expired half a second after, not at
  t + 58 h.
- **AC-12** With `NOCK_CREATOR_ROOM_HOURS` 96 and `NOCK_ANONYMOUS_ROOM_HOURS`
  48, Lea's creator room R last edited at t: an app with accounts off finds R
  open at t + 48 h and deletes it at a lookup half a second later, the store
  naming Lea creator until then; an app with accounts on finds R open at
  t + 60 h, and an app with accounts off started then deletes it at its first
  sweep.
- **AC-13** A database at `user_version` 1 holding S, solved at s, and U,
  unsolved, opens at `user_version` 2 with S's solve time s and none for U,
  every other row as it was; one at `user_version` 0 opens with the creator
  column too; a solved room whose stored state and log give no solve time gets
  its last edit time. With `NOCK_ANONYMOUS_SOLVED_ROOM_HOURS` 24, S is then
  expired at s + 24 h + 1 s.
- **AC-14** A live room A, last edited at t, looked up at t + its life + 1 s:
  when Ana's letter is committed after the lookup read A's times and before it
  took the registry lock, A is not deleted, Ana's socket stays open, and the
  lookup serves A with her letter; with no such letter, the lookup deletes A.
- **AC-15** Rooms A and B, both live and past their life, are swept: when
  Ana's letter in B is committed after the sweep read the times and before it
  deletes B, the sweep deletes A alone, returns `[A]`, and B's sockets stay
  open with her letter; without the letter it deletes both.

## Edge cases

- A room never edited expires by its life from its creation (AC-1).
- A live room past its life, before a sweep or a lookup meets it, is open again
  once an edit moves its last edit time (AC-2).
- A socket to an expired code counts as a wrong code (AC-2).
- A solved room's two times are equal, so the unsolved life never applies to it
  (AC-4).
- A stored creator room is anonymous for as long as accounts are off, and a
  creator room again when they are on (AC-12).
- A refused value is shown in the message, since none of the five variables is
  a secret (AC-8).
- The creator's erasure deletes its rooms whether expired or not, with no
  second read (`lobby/host.md` rule 14) (`lobby/host.md` AC-15).

## Out of scope

- A warning before expiry, extending or restoring a room, a log of how many
  rooms a sweep deletes; the other durations (resume window, idle state, votes,
  sign-in links), each a constant of its domain.
- Overriding the lives and the sweep interval from `/ops`, the override's
  storage and the dry run: `admin/overrides.md`.
- The deletion of a creator room at its creator's erasure: `lobby/host.md` rule
  14. What a deletion erases for privacy: `admin/operations.md`. Summaries and
  « Mes salons »: `lobby/joining.md`. The `/ops` periods a life allows:
  `admin/operations.md`.

## Code

- `src/nock/room.py`: `RoomConfig`; the one function that decides expiry.
- `src/nock/store.py`: `room_times` (last edit time, solve time, creator), the
  migration, deletion. It does not decide expiry.
- `src/nock/hub.py`: the sweep, the lookups and their deletions.
- `src/nock/server.py`: the app's sweep and the purge it paces.
  `src/nock/settings.py`, `src/nock/__main__.py`: the variables.
- Tests: `tests/test_spec_032_ac01_*`, `tests/test_spec_032_ac02_*`,
  `tests/test_lifetime_*`.
