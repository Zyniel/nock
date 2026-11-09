---
area: admin
file: ops-page
status: approved
---

# admin/ops-page - The `/ops` page: token form, dashboard card, replay

## Purpose

An operator opens `/ops`, gives the token once per tab, reads the figures of
recent rooms over a period, and replays one room's edits step by step on its
grid.

## Depends on

- `admin/operations.md`: the token's shape (rule 4), the ops API and its
  answers (rules 7 to 11), the dashboard figures and the offered periods (rule
  12).
- `admin/overrides.md`: the settings card between the dashboard and the replay
  (rule 11), whose 401 or 429 lock the page.
- `platform/server.md`: the room log whose entries the replay reads.

## Rules

### Replay

1. The edits are the log's `letter_changed` and `cell_locked` entries in seq
   order, each with its seq, time (UTC), cell and the event's letter. A letter
   change that undoes is `undone`, else `typed` with a letter or `erased`
   without; a lock is `locked` (a check) or `revealed`. A letter change keeps its
   pencil flag, its player id and the nickname of that player's latest
   `player_joined` before it, as stored; a lock has no player, nickname or
   pencil, and an edit with no join before it no nickname.
2. The replay, the answer of `GET /api/ops/rooms/<code>/edits`
   (`admin/operations.md` rule 7), is the room's code, its grid with no letter
   and no answer, and its edits.

### The operator page

3. `/ops` (heading `ops.heading`) is `locked` on the token form until a token is
   given or found in the tab's `sessionStorage`, its only place (never
   `localStorage`, a cookie or a URL). The form holds a password input with
   autocomplete off, `ops.token_label`, and the button `ops.token_submit`.
   Only a token of `admin/operations.md` rule 4's shape is stored or sent: a
   given one of another shape is refused as a 401 is, with no request; a
   stored one is removed, the page `locked` with no error line.
   Every ops request sends the token in its header. Then `loading`
   (`ops.loading`) until the dashboard, asked with no period, answers: 200
   `ready`; any 401 or 429 of
   the page, dashboard, settings card (`admin/overrides.md`) or replay, but a
   superseded one (rules 5, 6), forgets the token and goes back to `locked`
   with `ops.token_refused` or `ops.throttled`, the input empty and focused;
   another dashboard answer (a 404
   or a malformed 200 too) or a network failure gives `error` (`ops.error`)
   until a reload.
4. `ready` shows the card `ops.dashboard_heading`, then the settings card
   (`admin/overrides.md` rule 11), then the replay card (rule 6). The
   dashboard card: the group `ops.period_label`
   of one chip per offered period of the answer, `ops.period.one_day`,
   `ops.period.seven_days`, `ops.period.thirty_days` in that order, the
   answer's `days` pressed, then the six figures in `admin/operations.md`
   rule 12's order (the latency as one), each its `ops.metric.*` line in
   French notation: players per room with one decimal; the rate rounded to
   whole percent (`ops.percent`, 0.126 reads « 13 % »); the latency
   `ops.latency_value`, both rounded to whole milliseconds (30.6 reads 31);
   disconnections with two decimals; the time in whole seconds rounded down,
   as `duration.minutes` under one hour, seconds on two digits (5,999 ms reads
   « 0 min 05 s »), else `duration.hours`, minutes and seconds on two digits
   (3,725,999 ms reads « 1 h 02 min 05 s »). None reads `ops.no_data`.
5. A period press keeps the page `ready`, with the dashboard, the replay and the
   focus on the button, and changes the figures and the pressed period on the
   answer; a 401 or 429 locks, another answer gives `error`. An answer that
   finds the page no longer `ready` changes nothing, nor does the answer to a
   dashboard request (the first load, a press, the reload after a settings
   save) that a later one has superseded.
6. The card `ops.replay_heading` holds a form, the field `ops.replay_code_label`
   and the button `ops.replay_submit`. It sends the code in capitals and shows
   under the form `loading` (`ops.loading`), `not_found` (a 404,
   `ops.replay_not_found`), `error` (any other failure, `ops.error`, a 200
   with an edit whose `seq` is not a whole number or whose time is not an
   ISO 8601 date-time with a time zone, on a day and at a time the calendar
   has, included) or
   `ready`, the dashboard staying above; the answer to a code that a later
   code has superseded changes nothing. A room with no edit shows only
   `ops.replay_empty`. Otherwise: every edit by its `ops.edit.*` line
   (`typed_pencil` for a pencil letter), its time as fr-FR hours, minutes and
   seconds on two digits in the browser's zone, the nickname as
   `lobby/joining.md` rule 3 shows it or « Quelqu'un »; a range input
   `ops.replay_position_label` from 0 to the number of edits, at the end on
   load; `ops.replay_step`; and the grid `ops.replay_grid_label` at step k:
   each letter cell shows the letter of the last of the first k edits on it,
   locked once one locked or revealed it, revealed once one revealed it,
   pencil when the last put a pencil letter on an unlocked cell. Edits before
   k are done, k is current, the rest later.

### Look

- The page frame, token form, dashboard, chips, tiles, replay and its two layouts:
  `_design/pages.md`, « Plain pages: account, shared recap, operator »; the
  settings card between them: `admin/overrides.md`.
- The state lines: `_design/pages.md`, « States: opening, loading, empty,
  error ».
- The replay's cells: `_design/cells.md`, « Grid lines and empty cells » and
  « Letter marks »; the slider and
  buttons: `_design/foundation.md`, « Components ».

## Acceptance criteria

- **AC-1** `ANA` types `T` at (1, 0), `BOB` `A` at (1, 1) then `M` in pencil at
  (1, 2), Ana erases (1, 0) and undoes it, a check locks (1, 1), a reveal (1, 2),
  with joins, chat and presence between: the edits are `typed` T, `typed` A,
  `typed` M pencil, `erased`, `undone` T, `locked` A, `revealed` M, the first
  five with their player and `ANA` or `BOB`, the last two with none.
  (← 038 AC-8)
- **AC-2** With the token, a room's edits answer its empty grid and those edits,
  with none of FX-01's eight answers and no key `answer`; `abc`, an unknown and
  an expired room answer 404. (← 038 AC-8)
- **AC-3** `/ops` opens `locked` on a password field « Jeton d'opérateur »; a
  wrong token shows « Jeton refusé. », the input marked invalid and described
  by it; the token reaches `ready`, sent in every request's header, kept only
  in `sessionStorage`, in no URL; a reload skips the form, a new tab asks
  again; a later 401 or 429 brings the form back with « Jeton refusé. » or
  « Trop d'essais. Réessayez dans une minute. ». Locked, at a computer and a
  phone window, the top bar's Nock mark and « Nock » are the link « Accueil »
  to `/` with no `aria-current`. The page and form follow the plain pages
  design ("Look"). (← 038 AC-7, 048 AC-6)
- **AC-4** `admin/operations.md` AC-3's 7-day figures read « Salons créés :
  3 », « Joueurs par salon : 2,0 », « Grilles terminées : 67 % », « Temps
  médian de résolution : 12 min 30 s », « Latence du serveur : 30 ms
  (médiane), 50 ms (95e centile) », « Coupures par joueur : 0,50 », 7 days
  pressed among three chips; with `[1, 7]` offered, two chips and 7 pressed,
  with `[1]` one chip, pressed; no room reads `0` then « aucune donnée » five
  times. Chips named by « Période » and tiles follow the design ("Look").
  (← 038 AC-7, 048 AC-8)
- **AC-5** A replay shown, pressing 30 from the keyboard sends `days=30`, presses
  it, keeps the focus and the replay, `ready` while waiting; a 500 gives `error`,
  a 429 locks; a 200 arriving after a replay's 401 locked the page leaves it
  `locked` with « Jeton refusé. » and no dashboard. (← 038 AC-7)
- **AC-6** With the token kept and the dashboard pending, the page shows only
  « Chargement… » under its heading, announced politely; a 500 or a network
  failure shows « Impossible de charger les données. », announced at once. Both
  follow the states design ("Look"). (← 038 AC-7, 048 AC-7)
- **AC-7** After Ana typed `TAMIS` across row 1 of FX-01 and erased (1, 4), the
  code in small letters lists five `typed` and one `erased` with `Ana`, « Étape
  6 sur 6 », row 1 `TAMI`; step 5 shows `S` at (1, 4), step 0 an empty grid.
  With seven edits at step 4, 1 to 3 are done, 4 current, 5 to 7 later; the two
  layouts follow the design ("Look"). A code with no room shows « Salon
  introuvable. ». (← 038 AC-9, 048 AC-9)
- **AC-8** With `D` in pencil at (2, 3), `M` checked at (1, 2) and `N` revealed
  at (3, 4), the last step shows them pencil, locked, revealed, clue cells empty
  blocks; at step 4, (1, 2) is unlocked and (3, 4) empty. No edit: only « Aucune
  modification dans ce salon. », no grid, slider or list. The cells follow the
  design, without clues, arrows or players ("Look"). (← 048 AC-10)
- **AC-9** The step control is a range input named « Étape »; Tab shows the focus
  ring on its knob and ArrowLeft from 7 reads « Étape 6 sur 7 ». A pending,
  404 or 500 replay shows one line, « Chargement… », « Salon introuvable. » or
  « Impossible de charger les données. », under the form, the dashboard above.
  (← 048 AC-11, 048 AC-12)
- **AC-10** The page keeps `product.md`'s baselines: Tab reaches the token input,
  Enter loads the dashboard, each period shows the visible focus; the contrast
  and language scans find nothing on the `ready` page, on a computer or a phone;
  no supported window scrolls sideways. (← 038 AC-7)
- **AC-11** The dashboard `ready` on 7 days, pressing 1 then 30, the 30-day
  answer coming first and the 1-day one after: the page shows the 30-day
  figures with 30 pressed, and still does once the 1-day answer has come.
- **AC-12** Asking the replay of `AAAAAA` then of FX-01's room, whose answer
  comes first, then `AAAAAA`'s 404: the card shows FX-01's replay, not
  « Salon introuvable. ».
- **AC-13** On the form, a token of 40 characters holding `é`, one holding a
  space, or one of 31 allowed characters, submitted: no request is sent,
  `sessionStorage` holds no token, and the form shows « Jeton refusé. » with
  the input empty and focused.
- **AC-14** With `sessionStorage` holding a 40-character token with `é`,
  `/ops` sends no request and opens `locked` with no error line, the token
  removed.
- **AC-15** `ready` with the token, a replay answered 401 brings the form back
  with « Jeton refusé. », its input empty and focused.
- **AC-16** A replay answered 200 whose second edit has the time `hier`, the
  time `2026-02-30T10:00:00Z` (a day February lacks), or the `seq` 1.5,
  shows only « Impossible de charger les données. » under the form, the
  dashboard above.

## Edge cases

- A confirmed pencil letter is `typed` without pencil; an undo that empties its
  cell is `undone` without letter (AC-1).
- A seated-back player's later edits take the nickname of the new join (AC-1).
- A code breaking the pattern shows « Salon introuvable. » (AC-7).

## Out of scope

- Charts, alerts, exports; editing a room's log.
- The token's check, the ops API, its throttle and answers, the dashboard
  figures, `GET /ops` served: `admin/operations.md`. The settings card:
  `admin/overrides.md`.

## Code

- `src/nock/operations.py`: `room_edits`, `RoomEdit`, `RoomReplay`.
- `web/src/lib/OpsPage.svelte`, `web/src/lib/OpsReplay.svelte`,
  `web/src/lib/ops.ts`, `web/src/lib/duration.ts`.
- Tests: `tests/test_spec_038_ac07*` to `ac09*`, `tests/test_spec_048_ac06*`,
  `ac09_ac10*`, `ac11_ac12*`; `tests/test_ops_page_*` for AC-11 to AC-16.
