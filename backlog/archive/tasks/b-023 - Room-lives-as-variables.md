---
id: B-023
title: Room lives as variables
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:lifetime
  - domain:joining
  - domain:operations
  - domain:server
  - domain:shell
  - domain:hud
  - domain:host
  - domain:account
  - domain:results
  - domain:catch-up
dependencies: []
ordinal: 33000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human approved the brief as written, with the lead's
  calls: `lobby/lifetime.md`, the erasure case dropped, then the spec change
  as written, 2026-10-29; built and reviewed in two rounds, 2026-10-29)
- Waits for: nothing left (B-021, B-022 and B-025 are merged and on this
  branch). B-024 (/ops overrides) waits for this item.
- Domains: lobby/lifetime (new: joining rules 15, 16 and AC-14, AC-15 move
  there), lobby/joining, admin/operations, platform/server, client/shell (the
  card line); citations and the quoted line in client/hud, lobby/host,
  account/account; citations only in gameplay/results and social/catch-up;
  `specs/_map.md` (a table row, the glossary), `_settings.md`,
  `_design/pages.md`, `_design/overlays.md`; the screens sheet
- Architecture decision: yes (a new domain file, stored data: the solve time
  in `room_times` and `PRAGMA user_version` 2, `RoomConfig` fields, five
  environment variables, the `/ops` dashboard answer). The Plan agent on
  Fable weighed the options for the first brief of this request and the
  human picked them; no new Plan run.
- Criteria: lifetime AC-1, AC-2 (moved from joining AC-14, AC-15, pointers
  to 032 AC-1, AC-2 kept), lifetime AC-3 to AC-13 (new); joining AC-14,
  AC-15 (deleted, moved); operations AC-4, AC-14 (changed); host AC-9
  (changed); hud AC-21, shell AC-9 (changed: the card line); joining AC-17
  (wording only)
- Branch: feat/b-023-room-lives · PR: #63
- Problem: a room lives a fixed 30 days after its last edit
  (`lobby/joining.md` rules 15, 16), a bare number in four specs, the
  expired-room card and the room-gone dialog, with no setting. The human wants
  one life per kind of room, each an environment variable, and exact terms.
- In scope, the human's request as written (2026-10-28):
  - Glossary terms: edit and last edit time (as today); solve time (the time
    of the room's `grid_solved`); room life (how long a room lasts after its
    starting point); expired room (more than its room life past its starting
    point; at exactly its room life it is not expired); sweep; shortest room
    life (the least of the four).
  - The 30-day rule is replaced by four room lives, each an environment
    variable in whole hours from 24 to 8760 with a `RoomConfig` field, all
    defaulting to 720: `NOCK_CREATOR_SOLVED_ROOM_HOURS` (a solved creator
    room, from its solve time), `NOCK_CREATOR_ROOM_HOURS` (an unsolved creator
    room, from its last edit), `NOCK_ANONYMOUS_SOLVED_ROOM_HOURS` (a solved
    anonymous room, from its solve time), `NOCK_ANONYMOUS_ROOM_HOURS` (an
    unsolved anonymous room, from its last edit).
  - The sweep runs at start and every `NOCK_EXPIRY_SWEEP_MINUTES`, whole
    minutes from 1 to 1440, default 60. A value out of bounds stops
    `python -m nock` before it serves, as the other variables do.
  - A room that changes kind takes the matching life from the same starting
    point (see the open question on erasure). With accounts off every room
    is anonymous.
  - The `/ops` dashboard offers only those of its 1, 7 and 30-day periods no
    longer than the shortest room life.
  - The expired-room card's line names no duration.
  - Specs write each life as its variable with its default, never a bare
    number.
- Out of scope (the human's): changing the values from `/ops` (B-024); other
  durations (resume window, idle state, votes, sign-in links) stay constants.
  Also: a warning before expiry; a log of how many rooms a sweep deletes.
- Note: a room's solve time equals its last edit time (the solving letter and
  `grid_solved` are one step, and `gameplay/rules.md` rule 3 refuses every
  edit once solved), so the solved and unsolved lives differ only by which
  variable applies. The specs keep both names, as asked, and say so once.
- Size: more than three domain files, kept as one change. Five files get only
  a repointed citation or the reworded line, and the two parts that could
  leave (the `/ops` periods, the card line) would be false the day the lives
  ship. `joining.md` falls to about 16 KB and 19 criteria.
- Already decided by the human (every pick A of the first brief of this
  request, 2026-10-28):
  1. **A new lobby file** takes `joining.md` rules 15 and 16 and AC-14,
     AC-15 (pointers to 032 kept), the kinds, starting points, change of
     kind, accounts off, the sweep and the five variables' rules;
     `platform/server.md` rule 15 only adds them to its order of checks;
     joining keeps AC-17 and points to the new file. Rule 16 moves with
     B-021's clause word for word ("a page that had shown the room then shows
     the room-gone dialog (`client/hud.md` rule 16)"), and every citation of
     joining rules 15 and 16 is repointed: `lobby/host.md` rule 14,
     `client/hud.md` rule 16, `account/account.md` rule 20,
     `admin/operations.md` rule 2 and its Depends on, `platform/server.md`,
     and the Depends on and Out of scope lines that name the sweep.
  2. **Stored data:** `room_times` gains the solve time (the creator column
     is already there, B-022, `user_version` 1); one pure function decides
     expiry for the sweep, the lookups and B-024's dry run; old databases are
     migrated once at open to `user_version` 2, the solve time read from each
     solved room.
  3. **`RoomConfig`:** four `int` fields in hours
     (`creator_solved_room_hours`, `creator_room_hours`,
     `anonymous_solved_room_hours`, `anonymous_room_hours`, 24 to 8760,
     default 720) replacing `room_life_seconds`; `expiry_sweep_seconds` stays
     a float in seconds, the whole-minute bound on the variable only.
  4. **The `/ops` periods:** the dashboard answer names the offered periods
     (1 day is always offered, since the shortest life is at least 24 hours;
     the default is 7 days when offered, else 1); the page draws only those;
     a period not offered answers 422 as a wrong one; rule 12 reads "within
     an offered period none has expired".
  5. **The card line:** `room.status.not_found_detail` becomes « Un salon est
     effacé après un certain temps sans modification. », in the entry card
     (`client/shell.md` AC-9, `_design/pages.md`) and the room-gone dialog
     (`client/hud.md` AC-21, `_design/overlays.md` « Room gone »); the key
     stays.
- Screens: the expired-room card (screens sheet part 2) and the room-gone
  dialog (part 3) change one muted line, as picked; the `/ops` dashboard draws
  only the offered periods, all three with the default lives, so its drawing
  stays. No option left to choose.
- New since the first brief (the lead's calls; say if any should change):
  - The file is **`lobby/lifetime.md`**, « Room lifetime: when a room
    expires and the sweep that deletes it ». `lobby/room-life.md` is no
    longer possible: B-025 named a domain `room` (`client/room.md`), and no
    domain may be `room-...`, since its test files would also start
    `test_room_`. Another name would be `lobby/expiry.md`.
  - The sweep interval also paces the purge of old sign-in links and
    sessions (`account/account.md` rule 20), which then runs as often as
    every minute; it stays tied to the sweep.
- Open questions:
  1. **Erasure no longer changes a room's kind.** The request says "a room
     that changes kind (solved, or its creator's account erased)". Since
     B-022's review, erasing the creator's account deletes the creator room
     (`lobby/host.md` rule 14); it never becomes anonymous. The changes of
     kind left are: solved, and accounts turned off (a creator room plays as
     an anonymous room while accounts are off, `lobby/host.md` rule 15) or
     back on. The lead drops the erasure case and writes those two; a room
     already past its new life then goes at the next sweep or lookup.
<!-- SECTION:DESCRIPTION:END -->
