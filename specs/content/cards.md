---
area: content
file: cards
status: approved
---

# content/cards - The grid card

## Purpose

Each grid the catalogue and the grid page show is a card: its number,
publication date, force and size, the progress this device or the player's
account has on it, a drawing of its proportions on wide lists, and « Jouer ».

## Depends on

- `content/library.md`: the pages that show the cards, which grids they show,
  the summary.
- `lobby/rooms.md`: « Jouer » on each card, its failure's cause, and the
  moments that mark a grid.
- `account/my-account.md`: the sign-in status the pages ask (rule 1) and the
  sign-out or deletion that removes `nock.account_progress` (rule 5); the
  account's progress route is `account/erasure.md`.

## Rules

### Progress on this device or account

1. A card's progress is `finished` if any source says so, else `started` if
   any does, else none. The sources, read the same way: `localStorage`
   `nock.progress` and `nock.account_progress` (rule 2 writes them) and the
   body of `GET /api/account/progress` (`account/erasure.md` rule 10), never
   stored on the device; each a JSON object from grid numbers in decimal to
   `"started"` or `"finished"`. Each value is read on its own: any other
   value, a missing key, text that is not JSON or JSON that is not an object
   means no progress from that source. A request that fails or answers another
   status than 2xx (401 signed out, 404 accounts off) means none from the
   account. The pills show the device's progress at once and the merged one
   when the answer comes; neither page's state waits for it.
2. « Jouer », « Rejouer » (`gameplay/history.md` rule 6) and a solve
   (`lobby/rooms.md` rules 2 and 5) write one key: `nock.account_progress`
   while the page is signed in, else `nock.progress`; the other key is not
   touched. The grid is set `started` unless that key says `finished`, and
   `finished` on a solve. A page is signed in once its `GET /api/account`
   answered 200 with `signed_in` true (`/`, a room), or its `GET
   /api/account/progress` answered 2xx (`/g/<n>`); a tap before that answer
   counts as signed out, and the room page marks a solve only once its request
   has answered or failed. A sign-out or deletion removes
   `nock.account_progress` (`account/my-account.md` rule 5).

### Grid cards

3. One card per shown grid, in the server's order. A card shows « Grille n° N »
   (`catalogue.item.number`), the progress pill « Commencée » or « Terminée »
   (`catalogue.progress.*`) when the grid has progress and none otherwise,
   « Publiée le <date> » (`catalogue.item.published`, the date in French as
   `1 octobre 2026`, read in UTC so every time zone shows the same day), four
   force marks, « Force F », « W × H » and « N mots »
   (`catalogue.item.force`, `.size`, `.words`), and « Jouer »
   (`lobby/rooms.md`).
4. The force marks show the force drawn, marks 1 to F filled; they are hidden
   from assistive technology, and the force is always written beside them.
5. A card holds the generic drawing of its grid, built from its width and
   height only and hidden from assistive technology, whenever the list is
   wide enough for two columns of cards, even when one card is shown. It
   follows the list's width, not the window's form: a landscape window that is
   not a computer's gets drawings when its list holds two columns, and a card
   alone on its row because the list is narrow never has one. A resize adds
   or removes the drawings within 300 ms.
6. After a failed « Jouer » (`lobby/rooms.md`), `catalogue.play_failed` shows
   as an alert error line inside that card, under its force line; no other
   card shows one.

### Look

- The cards, their progress pills, force marks and drawing, and « Jouer »:
  `_design/pages.md`, « Catalogue », with `_design/foundation.md`,
  « Components » (card, list row, error line).

## Acceptance criteria

The examples use CAT, four grids on FX-01: 1 (`2026-09-01`, force 1), 2
(`2026-10-01`, force 2), 3 (`2026-10-01`, force 1), all published, and 4
(`2026-10-05`, force 3) unpublished.

- **AC-1** With `nock.progress` `{"1": "started", "2": "finished", "99":
  "started"}`, card 1 shows « Commencée », card 2 « Terminée » and card 3 no
  pill, as on `/g/1`; each pill sits after its card's number in the catalogue
  design, its text at least 4.5:1 on its background. (← 004 AC-3, 046 AC-6)
- **AC-2** With `nock.progress` `not json`, `[1]` or `{"1": "done"}`, no card
  shows progress and the page is ready; with `{"1": "started", "2": "done",
  "3": 1}` only card 1 does. (← 004 AC-3)
- **AC-3** CAT's cards on a computer and on a phone, with their number,
  publication line and « Jouer », follow the catalogue design's card grid.
  (← 046 AC-5)
- **AC-4** A card of force 3, 13 × 17 and 54 words shows three filled marks
  out of four, hidden from assistive technology, then « Force 3 », « 13 × 17 »
  and « 54 mots », with their separators as the catalogue design draws them; a
  card of force 2 has two filled marks. (← 046 AC-7)
- **AC-5** On a computer, a 13 × 17 and a 5 × 5 card each begin with their
  generic drawing, hidden from assistive technology, as the catalogue design
  draws it, and a lone card keeps its drawing. A landscape window that is not
  a computer's but whose list is wide enough for two columns shows drawings,
  while a slightly narrower one, whose list holds one column, shows none, as
  do a phone and an upright tablet. Resizing from a computer to a phone
  removes them within 300 ms, and back restores them. (← 046 AC-8)
- **AC-6** With `POST /api/rooms` answering 500, « Jouer » on card 2 shows
  « Impossible de lancer la partie. Réessayez. » with `role="alert"`, as an
  error line inside card 2 under its force line; card 2 stays in the list with
  « Jouer » enabled, and cards 1 and 3 show no error. (← 046 AC-10)
- **AC-7** Ana signed in, `nock.progress` `{"1": "started", "3": "finished"}`
  and `GET /api/account/progress` answering `{"1": "finished", "2": "started",
  "3": "started"}`: `/` shows card 1 « Terminée », card 2 « Commencée » and
  card 3 « Terminée »; while the answer is pending the page is already ready
  with « Commencée », no pill and « Terminée »; `nock.progress` is unchanged
  afterwards.
- **AC-8** With AC-7's storage and answer, `/g/2` asks
  `GET /api/account/progress` and not `GET /api/account`, shows « Commencée »
  on its card and no « Compte »; `/g/1` shows « Terminée ».
- **AC-9** With AC-7's storage, when `GET /api/account/progress` answers
  401, 404, 500, `[1]` or `{"1": "done", "3": "started"}`, or the request
  fails, `/` (signed in) shows « Commencée » on card 1 and « Terminée » on card
  3, `/g/1` shows « Commencée » and `/g/3` « Terminée », each page ready;
  signed out, `/` never asks the route.
- **AC-10** Signed out, with `nock.progress` `{"1": "started"}` and
  `nock.account_progress` `{"1": "finished", "2": "started", "3": "done"}`,
  `/` shows card 1 « Terminée », card 2 « Commencée » and card 3 no pill, as
  `/g/1` and `/g/2` do; with `nock.account_progress` `not json`, card 1 shows
  « Commencée » and card 2 no pill.
- **AC-11** Ana signed in on `/`, with `nock.progress` `{"1": "finished"}` and
  no `nock.account_progress`: « Jouer » on card 2 writes
  `nock.account_progress` `{"2": "started"}` and leaves `nock.progress` as it
  was. Signed out, or with `GET /api/account` not answered yet when the tap
  comes, the same tap writes `nock.progress` `{"1": "finished", "2":
  "started"}` and no `nock.account_progress`.
- **AC-12** In a room created from AC-11's signed-in tap, a `grid_solved` sets
  `nock.account_progress` `{"2": "finished"}` and leaves `nock.progress`;
  while the room page's `GET /api/account` has not answered, the solve marks
  nothing yet, and the mark comes with the answer. With that request answering
  401, 404 or 500, or failing, the solve sets `nock.progress` `{"1":
  "finished", "2": "finished"}` and leaves `nock.account_progress` as it was.
- **AC-13** On `/g/2` with no `nock.account_progress`, « Jouer » writes
  `nock.account_progress` `{"2": "started"}` when `GET /api/account/progress`
  answered `{}`, and `nock.progress` `{"2": "started"}` when it answered 401.
  Signed in on `/` with a history record of grid 2, « Rejouer » on its row
  writes `nock.account_progress` `{"2": "started"}`.

## Edge cases

- A progress key for a grid not listed (`99`) is ignored, from any source
  (AC-1).
- The account's `finished` beats the device's `started`, and the reverse
  (AC-7); a stale `nock.account_progress` is still read signed out (AC-10).
- A page's `GET /api/account` answering 404 (accounts off) or failing counts as
  signed out (AC-12).
- « Rejouer » writes the key « Jouer » would (AC-13).
- A catalogue of one grid on a computer still has two columns, so its card
  has its drawing (AC-5).
- « Jouer » failing on one card leaves the others untouched (AC-6).

## Out of scope

- A real thumbnail of the grid's layout.
- « Jouer », the room it creates and the moments that mark a grid:
  `lobby/rooms.md`. How the account's progress is derived:
  `account/erasure.md`. The pages' states and the filter:
  `content/library.md`.
- Telling, in `nock.progress`, which marks an account set: none carries an
  origin, and they stay through a sign-out.

## Code

- `web/src/lib/CatalogueItem.svelte`, `PlayButton.svelte` (« Jouer »);
  `catalogue.ts` (progress, the key it writes, its merge with the account's,
  the date); `playGrid.ts` (« Jouer »'s mark), `RoomPage.svelte` (the solve's
  mark); `gridThumb.ts`.
- Tests: `tests/test_cards_progress.py`, with `tests/library_harness.py` as its
  harness; `tests/test_spec_004_ac01_ac03_*` (004 AC-3),
  `test_spec_046_ac04_ac06_*` (046 AC-5, AC-6), `test_spec_046_ac07_ac08_*`,
  `test_spec_046_ac09_ac10_*` (046 AC-10).
