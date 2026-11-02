---
area: gameplay
file: rules
status: approved
---

# gameplay/rules - Completion and the shared timer

## Purpose

The room knows when its grid is finished: nobody presses anything to win, and a
full grid with a mistake is announced without saying where. One timer, the same
for every player, measures the room's playing time from the first letter typed.

## Depends on

- `gameplay/co-op.md`: letters, pencil letters, edits and their refusals.
- `platform/realtime.md`: the snapshot, `grid_solved`, `grid_full_wrong`, error
  codes, disconnection, silence and resume.
- `platform/server.md`: the log, `replay`, undo and `nothing_to_undo`, the store
  and the restart step.

## Rules

### Completion

1. A letter cell is filled when it holds a letter, pencil or not; a locked or
   revealed cell holds one. The grid is full when every letter cell is filled,
   and right when it is full and every letter is its cell's solution letter,
   whatever its pencil flag.
2. After an accepted step whose entries hold an edit (a `letter_changed` or a
   `cell_locked`: an edit, an erase, an undo, a pencil letter or confirmation, a
   reveal), in a room not solved yet, one entry is added to the step: a right
   grid gives `grid_solved` with `elapsed_ms` (rule 9) and the room is solved;
   else a grid full now and not full before the step gives `grid_full_wrong`,
   which carries only its seq; else nothing. The entry takes the next seq, is
   logged with the step and reaches every player after the step's other entries.
   A check fills no cell, so it never completes a grid.
3. Once solved, an edit, an erase, a pencil letter, a pencil confirmation, an
   undo, a check and a reveal are refused with `grid_solved`, to the sender only;
   the refusal changes no cell, no seq of its own and no timer (an idle sender
   still wakes, `social/presence.md`; before a check or a reveal an expired vote
   still closes, `gameplay/hints.md`). An edit's own refusals and undo's
   `nothing_to_undo` come first; check and reveal refuse it before any check of
   theirs. Every other message works as in a room not solved yet. A room never
   gets a second `grid_solved`.
4. `replay` of `grid_solved` makes the room solved; of `grid_full_wrong`, it only
   moves the seq. The snapshot says whether the room is solved.

### The page

5. A page is solved once it applies a `grid_solved` or a snapshot that says so.
   Its status (one at most, with no live role) reads `completion.solved`
   (« Grille terminée, bravo ! ») when solved, else `completion.full_wrong`
   (« Grille complète, mais pas encore juste. ») while every letter cell of the
   confirmed grid holds a letter (pending edits do not count), else is absent.
   Each time it appears or its text changes, the status region announces that
   text (`client/hud.md` rule 17); a move of rule 7 announces nothing. Neither
   `grid_full_wrong` nor the status changes a cell: they never say where the
   mistake is (a check does, `gameplay/hints.md`).
6. Once solved, a letter key, `Backspace`, `Control+z`, `Meta+z` and the undo
   button send nothing and change no cell. Disabled: the undo button, the three
   checks and the reveal items of « Aide » (`gameplay/hints.md`), « Crayon » and
   the pencil confirmation (`gameplay/co-op.md`), « Clavier »; the in-app
   keyboard goes away (`gameplay/board.md`). Selecting cells and the arrow keys
   still work.
7. The status is the end band under the clue bar, where « Voir le bilan »
   (`gameplay/results.md`) joins it once solved. Only while the in-app keyboard
   shows on a window at most 500 px high, a full-but-wrong status sits in the
   clue bar's row after the clue text, whole and on one line: the clue text is
   then one line cut with an ellipsis, keeps its whole text in the page, and the
   bar is never higher than without the status. A resize across 500 px moves it,
   same text and state.

### The timer

8. The timer is started once a letter is typed, running while it counts, paused
   while it is started and no player is connected (an idle player is connected),
   and stopped once the grid is solved. Its value is the time counted before the
   current run, plus the current run while it runs, in milliseconds rounded to
   the nearest; a clock that goes back adds nothing. A stored room whose counted
   time is negative or not whole, or whose started flag is not a boolean, does
   not load.
9. After each entry of a step, in order, at the step's time (in `replay`, the
   entry's time), the first rule that applies: start, at a `letter_changed` with
   a letter (a pencil one too; not an erase, not a reveal) when not started and
   not solved; stop, at `grid_solved`, on its `elapsed_ms`; pause, when it runs
   and no player is connected; resume, when it is started, not running, not
   solved and a player is connected. A step with no entry changes nothing. The
   solving step's `elapsed_ms` is the value after its earlier entries.
10. A join's snapshot is built after these rules at the join's time, so a join
    that ends a pause gets a running timer; a snapshot built without a time
    holds the time counted before the current run. The restart step pauses a
    running timer: the time between a crash and the restart is counted. The
    protocol has no timer event.
11. The page takes the snapshot's value (0 unless a whole number of at least 0)
    and running flag (running only when exactly `true`), and counts from the
    moment it applies it. A `letter_changed` with a letter starts it when it is
    not running, at 0 and not solved. A `grid_solved` stops it on `elapsed_ms`,
    or on the shown value when `elapsed_ms` is not a whole number of at least 0.
    A page without its socket keeps counting; its next snapshot sets the value,
    which may step back.
12. The timer shows whole seconds, rounded down: `m:ss` under an hour, `h:mm:ss`
    from one hour (`timer.minutes_seconds`, `timer.hours_minutes_seconds`), on one
    line, refreshed at least every 250 ms while it runs. It is text with
    `role="timer"` and no live announcement, named `timer.label` (« Chrono »),
    never a Tab stop.
13. The Menu item `timer.hide` (« Masquer le chrono »), with no pressed state,
    hides the timer on this page and sends nothing; while hidden, the top-bar
    button « Chrono » (`timer.label`), named `timer.toggle_label` (« Afficher le
    chrono »), takes its place and shows it again, and the Menu item reads
    `timer.toggle_label` and shows it too. Hidden, `localStorage` holds
    `nock.timer_hidden` = `true`; shown, the key is absent; any other value
    counts as absent. When storage throws, the page starts with the timer
    shown. The choice holds for every room of the browser and changes nothing
    for the others or for `elapsed_ms`.

### Look

The status, `_design/overlays.md`, « End of grid ». The timer and « Chrono »,
`_design/room.md`, « Phone top bar », « Computer top bar » and « Menu »; its
figures and the chrono icon, `_design/foundation.md`, « Typography » and
« Icons ».

## Acceptance criteria

- **AC-1** In an FX-01 room whose 17 letters other than (4, 4) are right, typed
  at its start with a player connected, `T` at (4, 4) 754 s later gives its
  `letter_changed` (seq 20) then `grid_solved` (seq 21, `elapsed_ms` 754000), and
  the snapshot says solved; the 18 letters typed in order give exactly one
  `grid_solved`, after the 18th. (← 026 AC-1, 026 AC-8)
- **AC-2** With Ana, Bob and Cy joined, Bob's 18th right letter reaches each of
  them as its `letter_changed` then `grid_solved` with the next seq, within 1 s of
  his send. (← 026 AC-2)
- **AC-3** Ana types the 17 letters and Bob `T` at (4, 4): within 1 s both pages
  are solved and show « Grille terminée, bravo ! » with no live role, which
  each page's status region reads. (← 026 AC-3)
- **AC-4** In that solved room, an edit, an erase, a pencil letter, a pencil
  confirmation and a grid check from Ana, and Bob's undo, each get one error
  `grid_solved`, to the sender only; the room stays at seq 21; Ana's selection of
  (1, 0) still reaches the others. (← 026 AC-4)
- **AC-5** On a page solved by `grid_solved` or by its first snapshot, (1, 0)
  selected, `B`, `Backspace`, `Control+z` and `Meta+z` send nothing and (1, 0)
  keeps its letter; undo and the three checks are disabled; arrows and taps move
  the selection; on a touch screen there is no in-app keyboard. (← 026 AC-5)
- **AC-6** With the 17 right, `X` at (4, 4) gives its `letter_changed` (seq `n`)
  then exactly `{"type": "grid_full_wrong", "seq": n + 1}` to every player and the
  room is not solved; `Y` there then adds no event; an erase then `X` again adds a
  new one. Typed in order with `N` at (1, 2), the 18th letter gives
  `grid_full_wrong`, then `M` at (1, 2) gives `grid_solved`.
  (← 026 AC-6, 026 AC-8)
- **AC-7** A page with 17 letters and (4, 4) empty shows no status; after `X` at
  (4, 4) and `grid_full_wrong` it shows « Grille complète, mais pas encore
  juste. », which the status region reads, no cell marked wrong, and is not
  solved; erasing (4, 4) removes it. A
  page joining a full, wrong grid shows it at once, its status region reading
  it; a pending last letter does not show it. (← 026 AC-7)
- **AC-8** Replaying a solved play from a new room gives the live room's solved
  flag, seq and cells; a stored solved room loads solved and refuses an edit with
  `grid_solved`; a stored full, wrong room whose letters were typed at t0 + 100
  loads unsolved, and `T` at (4, 4) at t0 + 754 solves it with `elapsed_ms`
  654000. (← 026 AC-9)
- **AC-9** At every supported window size, on a computer and a touch screen, an
  FX-02 page full but wrong, or solved, shows its status, its grid area keeps at
  least 100 px of height and the page does not scroll; at 1280 by 720 the status
  lies under the clue bar inside the window. (← 026 AC-10)
- **AC-10** On a touch screen at 568 by 320, with the in-app keyboard and the
  clue « On la glisse dans une enveloppe » selected, the full-but-wrong status
  follows rule 7 in the clue bar's row, the bar as high as with no status;
  rotated to 320 by 568, it moves under the clue bar with the same text, and
  the status region is not written again. Solved, the page has no keyboard
  and the band; both pass the contrast and language scans of `product.md`.
  (← 026 AC-10)
- **AC-11** Ana and Bob join at t0; Ana's erase at t0 + 5 leaves a timer at 0,
  stopped; her `T` at (1, 0) at t0 + 10 starts it, and a snapshot at t0 + 40,
  Bob's or a newcomer's, says 30000, running. (← 027 AC-1)
- **AC-12** Two pages read `0:00`, still 2 s later; once Ana types `T`, both run
  within 1 s, and 3 s after her key both read about 3 s, at most 1 s apart; Cy,
  joining then, reads within 1 s of Ana. (← 027 AC-2)
- **AC-13** Ana alone types `T` at t0 and leaves at t0 + 30: the timer pauses at
  30000 and still says 30000 at t0 + 200, when her return resumes it, 40000 at
  t0 + 210. With Bob connected, her leaving and return change no timer field.
  Ana's silence detected at t0 + 6 pauses it at 6000. (← 027 AC-3)
- **AC-14** A page closed after 2 s of timer and reopened 4 s later runs again
  from what it showed, the 4 s away not counted; a page whose socket drops at
  `1:10` keeps counting, and its next snapshot of 62,000 makes it read `1:02`.
  (← 027 AC-3)
- **AC-15** On one of two pages at `1:05`, « Masquer le chrono » removes the
  timer, shows « Chrono » and sends nothing; the other page keeps its timer.
  Reloaded, it stays hidden with the key set; « Chrono » shows `1:05` or later
  and removes the key. (← 027 AC-4)
- **AC-16** Snapshots of 65,000 running read `1:05` then `1:06`; 3,725,000
  stopped and solved, `1:02:05` 2 s later still; 36,000,000, `10:00:00`. At 0
  stopped, a `letter_changed` with no letter changes nothing and one with `T`
  starts it, reading `0:01` a second later; at 750,000 running, `grid_solved`
  with 754,000 stops it at `12:34`. (← 027 AC-5)
- **AC-17** A snapshot value of -1, 1.5, `"65000"`, `null` or none reads `0:00`;
  a running flag of `"true"`, 1, `null` or none at 65,000 stays at `1:05`; a
  `grid_solved` at 750,000 running whose `elapsed_ms` is any of those stops on the
  value shown when it arrived, not 0. (← 027 AC-5)
- **AC-18** Ana types the 17 letters at t0 + 100; she and Bob leave at t0 + 160
  and come back at t0 + 400; Bob's `T` at (4, 4) at t0 + 454 gives
  `grid_solved` with `elapsed_ms` 114000 and a stopped timer, still 114000 at
  t0 + 2000 and after a newcomer joins. (← 027 AC-6)
- **AC-19** Replaying AC-18's play gives, after each step, the live timer; the
  store at seq 23 loads running since t0 + 400 with 60000; a restart at t0 + 430
  pauses it at 90000, and a return at t0 + 700 gets 90000, running. (← 027 AC-7)
- **AC-20** The timer is in the top bar before the undo button, named « Chrono »,
  not announced and no Tab stop; from the keyboard the Menu item hides it and
  « Chrono », reached by Tab, shows it again, both with the visible focus of
  `product.md`. At `10:00:00` the scans find nothing, and at every window
  size the timer, or « Chrono » of at least 24 by 24 px, lies in the top bar
  on one line without overlap. (← 027 AC-8)

## Edge cases

- An undo that puts back the last right letter completes the grid; so does the
  last edit of a grid otherwise locked by checks (AC-1).
- A check of a full, wrong grid adds no completion entry (AC-1).
- Fixing one wrong letter while another stays wrong adds no event; the status
  stays (AC-6, AC-7).
- An edit on a clue cell is still `not_a_letter_cell`, and an undo with nothing to
  undo `nothing_to_undo`, in a solved room (AC-4).
- Neither completion event carries a letter or a position (AC-6).
- Selecting, chatting or changing settings does not start the timer; a pencil
  letter does, a reveal does not (AC-11).
- Erasing every letter neither stops nor resets the timer (AC-11).
- A room left and rejoined before any letter stays at 0 (AC-13).
- A page that loses its network is seen disconnected after its silence, so up to
  that delay is counted after the last player left (AC-13).
- A first letter that also solves the grid, or a grid solved only by reveals,
  gives `elapsed_ms` 0 (AC-18).
- Chat, leaves, returns and refused edits after the solve do not move the timer
  (AC-18).
- A browser tab in the background shows the right value again at its next refresh
  (rule 11; untested).

## Out of scope

- A celebration, a sound or a feed line for completion; how many letters are
  wrong; reopening a solved grid.
- A timer event, pausing by hand, a countdown, per-player times, penalties for
  help, announcing the time to screen readers, leaderboards.
- Check and reveal: `gameplay/hints.md`. The recap and « Voir le bilan »:
  `gameplay/results.md`. The top bar and the Menu: `client/hud.md`. The in-app
  keyboard: `gameplay/board.md`.

## Code

- `src/nock/room.py`: completion, the solved refusals, the timer rules,
  `timer_value_ms`, `snapshot_for`, `replay`, `after_restart`.
- `src/nock/protocol.py`: `GridSolved`, `GridFullWrong`, the snapshot's timer.
- `web/src/lib/roomSession.ts`: the page's solved flag and timer;
  `RoomPage.svelte`: the status and the input lock; `GridViewport.svelte`: the
  `Control+z` and `Meta+z` shortcut; `RoomTimer.svelte`, `timer.ts`,
  `RoomTopBar.svelte`, `RoomMenu.svelte`: the timer and its hiding.
- Tests: `tests/test_spec_026_*`, `tests/test_spec_027_*`.
