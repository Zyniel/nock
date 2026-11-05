---
area: gameplay
file: history
status: done
---

# gameplay/history - Finished grids, « Grilles terminées », « Rejouer »

## Purpose

Each device, and each account, lists its finished grids in « Grilles
terminées », where a grid can be played again.

## Depends on

- `lobby/summaries.md`: summaries, which carry a room's result.
- `account/erasure.md`: the account's records, its history route, « Ancien
  joueur ».
- `content/library.md`: the catalogue page and its column.

## Rules

### Records

1. A room keeps its `grid_solved`'s time and `elapsed_ms`, by `replay` too. A
   summary (`lobby/summaries.md` rule 1) adds `finished_at` (that time, UTC) and
   `elapsed_ms`, null unless solved; a room stored without them takes them from
   its log.
2. `nock.history` holds the device's records, a JSON array of `{"code",
   "grid", "width", "height", "finished_at", "elapsed_ms", "teammates"}`,
   newest first then by code, at most 100. Not an array reads as none; an item
   of other field types is ignored, and so is one whose `finished_at` is not a
   date-time as `lobby/summaries.md` rule 2 reads one, or not a real one,
   refused in every engine: a month outside 01 to 12, a day its month lacks
   (`2026-02-30`, `2026-02-29`), an hour past 23 or minutes past 59 in the
   time or its offset, seconds past 59. A room's deletion removes no record;
   only the cap and a newer record of the same code do.
3. A solved summary writes its room's record, replacing that code's; the
   team-mates are its players but names exactly equal to this device's
   identity nickname for the room. The catalogue page writes one per summary
   of « Mes salons »; the room page, once solved (once per load, untested),
   asks its own summary and writes it. A failed request writes nothing.
4. Signed in (`account/account.md`), the catalogue page adds the records of
   `GET /api/account/history`, one per code, the account's winning, in rule
   2's order, never stored on the device; a failed or malformed answer, one
   holding an item rule 2 ignores included, adds none.

### « Grilles terminées »

5. While there is a record, `history.heading` (« Grilles terminées ») ends
   the catalogue column (`content/library.md` rule 9): a row per record with
   the grid label (`catalogue.item.number` or `my_rooms.unnumbered`) and
   `catalogue.item.size`; a line holding `history.finished` (the date as « Mes
   salons » writes it), `history.time` (the duration as `admin/ops-page.md`
   writes it) and `history.teammates` (names displayed, `--` as « Ancien
   joueur ») or `history.alone`; with a grid number only, `history.replay`
   (« Rejouer »), named `history.replay_label`.
6. « Rejouer » runs « Jouer »'s steps (`lobby/rooms.md` rule 2) for its grid,
   `finished` progress kept; disabled while it runs; a failure shows the alert
   `catalogue.play_failed` in the row and enables it again.
7. The section keeps `product.md`'s baselines at its windows.

### Look

« Grilles terminées »: `_design/pages.md`, « Catalogue ».

## Acceptance criteria

- **AC-1** FX-01 solved by `T` at (4, 4) at t0 + 754 keeps t0 + 754 and 754000,
  as its replay does; its summary has `finished_at` t0 + 754 UTC and
  `elapsed_ms` 754000, an unsolved one's null; a room stored solved without them
  takes its `grid_solved`'s. (← 029 AC-1)
- **AC-2** With identities for `XYZ789` and `ABC234` as `Ana`, and summaries of
  `XYZ789` solved (grid 2, 5 × 5, `Bob`, `Ana`, `Cy`, 2026-10-14T08:30:00Z,
  754000) and `ABC234` not, `nock.history` becomes that one record with `Bob`,
  `Cy`, its row « Grille n° 2 », « 5 × 5 », then, on one line on a computer,
  « Terminée le 14 octobre 2026 », « en 12 min 34 s », « Avec Bob, Cy », and
  « Rejouer » named « Rejouer la grille n° 2 », in the catalogue design. An
  older bare record follows: « Grille hors catalogue », « en 1 h 02 min 05 s »,
  « En solo », no « Rejouer ». A 101st drops the oldest; `not json` reads as
  none; an `elapsed_ms` of `"754000"` drops its item; no record and no
  account, no section. (← 029 AC-2, 046 AC-13)
- **AC-3** A room page applying `grid_solved` or a solved first snapshot asks
  its summary with its token and writes the record; after Ana and Bob solve,
  Ana's catalogue lists grid 1 « Avec Bob » with its time and date. Signed in,
  the account's records join, winning a shared code, unstored; Ana's second
  device lists her room « Avec Bob »; once Zélie erases her account, Ana's row
  reads « Avec Ancien joueur, Bob ». (← 029 AC-2, 029 AC-3, 029 AC-6)
- **AC-4** With grid 1 `finished`, « Rejouer » loads a new code, joined without
  the form, unsolved and empty, progress kept, the button disabled meanwhile; a
  500 or 404 stays on `/`, « Impossible de lancer la partie. Réessayez. » in the
  row, the button enabled. The section passes the scans, Tab reaches « Rejouer »
  with the ring, Enter sends, and 7 team-mates of 20 characters scroll no window
  sideways. (← 029 AC-4, 029 AC-5)
- **AC-5** With `nock.history` holding records finished
  `2026-10-14T08:30:00Z`, `2028-02-29T09:30:00.5+01:00`,
  `2026-10-14 08:30:00Z`, `2026-02-30T08:30:00Z`, `2026-10-14T24:00:00Z`,
  `2026-10-14T08:30:60Z` and `2026-10-14T08:30:00+24:00`, « Grilles
  terminées » lists the first two only, in every engine. Signed in,
  an account answer of two records, one finished `2026-02-30T08:30:00Z`, adds
  neither.

## Edge cases

- A removed player gets no summary, so no record (`lobby/summaries.md` AC-1).
- A team-mate with this device's nickname is left out too (AC-2).
- One grid finished in two rooms gives two records (AC-2).
- A room finished while away is recorded when the device next sees it solved,
  while it exists (AC-3).

## Out of scope

- Deleting, sorting or filtering records; moving them to an account; a link
  from a record to its recap.
- How an account saves and erases records, its history route:
  `account/erasure.md`.

## Code

- `src/nock/room.py`: `solved_at`, `room_summary`.
- `web/src/lib/`: `history.ts`, `dateTime.ts` (the date-time it reads),
  `HistoryList.svelte`, `HistoryItem.svelte`,
  `playGrid.ts`, `CataloguePage.svelte` (the merge and the account history),
  `RoomPage.svelte` (it writes the record once solved).
- Tests: `tests/test_spec_029_*` (AC-1 to AC-6), AC-13 of
  `tests/test_spec_046_ac11_ac13_*`, `tests/test_history_*` (AC-5),
  `tests/web/dateTime.test.ts`.
