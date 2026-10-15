---
id: "026"
title: Completion detection
status: done
---

# 026 - Completion detection

Epic E6 Help and validation (US-6.4) · Release: MVP · Epic depends on: E4
The FX-01 reference grid and the glossary are in `specs/_reference.md`. The rooms
engine is defined in spec 011, edits and their check order in spec 015, undo and
`replay` in spec 018, checks in spec 023, the messages in spec 039 (`GridSolved`,
`GridFullWrong`, `ErrorCode.GRID_SOLVED`, `Snapshot.solved`).

## Goal

As a team, we want the game to recognise the finished grid, so that we don't have to press anything to win.

Help is decided by the server and shared by the room, so one impatient player cannot solve the grid for everyone.

## Public interface

No new protocol message, no new `ErrorCode` and no new public Python name. This
spec adds the completion rule to `nock.room`, the solved refusals, the `replay`
of `grid_solved`, and the completion banner on the room page.

### Definitions

- A letter cell is **filled** when it holds a letter, pencil letter (spec 020) or
  not. Locked and revealed cells are filled.
- The grid is **full** when every letter cell of `state.cells` is filled.
- The grid is **right** when it is full and every letter equals the solution
  letter of its cell (the letter of the normalised `answer` of a clue whose word
  holds the cell, as in spec 023), whatever the letter's pencil flag.

### Server rule: completion (`nock.room.handle_message`)

After any accepted step of `handle_message` whose entries contain at least one
`letter_changed` or `cell_locked` (an edit, an undo, a reveal of spec 024, and,
once spec 020 adds them, a pencil letter written or confirmed: a pencil edit that
fills or completes the grid triggers the rule like any other letter change), and
while `state.solved` is False, with `s` the seq of the step's last entry so far:

1. If the grid is right: one more entry `GridSolved(seq=s + 1, elapsed_ms=<ms>)`,
   with `elapsed_ms = timer_value_ms(state, now)` (spec 027), `state` being the
   state after the step's earlier entries, and `state.solved = True`. (Note from the
   lead, 2026-10-15: spec 027 (shared timer: "Changes to spec 026" and its decision
   5) asks for this change. The formula used to be
   `max(0, round((now - state.created_at) * 1000))`, the time since the room was
   created. `elapsed_ms` is now the shared timer's value of spec 027: the time
   counted from the first letter typed, leaving out the time when no player is
   connected, in whole milliseconds, never negative. It is computed on the state
   after the step's earlier entries (so after the start of a first letter that would
   also solve the grid), and applying the `grid_solved` entry stops the timer. The
   two formulas agree when the first letter is typed at the room's creation time and
   a player stays connected, which is the case in the rule tests of AC-1 (letters at
   `NOW`, last letter at `NOW + 754.0`: `elapsed_ms=754000`, unchanged). They differ
   in the room that the tests of AC-9 load from a store and solve: `p1` and `p2`
   joined at `NOW` and stay connected; `p1` writes the 18 letters at `NOW + 100.0`,
   with `N` at (4, 4), so the timer starts at `NOW + 100.0` and the grid is full and
   wrong; `RoomStore.load_room` replays the entries, with no `after_restart`, so the
   timer is still running; `p1` then writes `T` at (4, 4) at `NOW + 754.0`, and
   `elapsed_ms = 0 + round((754.0 - 100.0) * 1000) = 654000`, where the old formula
   gave 754000.)
2. Else, if the grid is full now and was not full before the step: one more entry
   `GridFullWrong(seq=s + 1)`, which carries nothing else (no cell, no count).
3. Else nothing is added.

The new entry is part of the same step: logged with it, then broadcast to every
joined connection after the step's other entries (spec 011 delivery).

### Server rule: input locked once solved

While `state.solved` is True:

- `edit_letter`, `erase`, `pencil_edit`, `confirm_pencil`: check 5 of spec 015
  refuses them with `ErrorMessage(code=GRID_SOLVED)`, after checks 1 to 4.
- `undo`: step 3 of spec 018 refuses it with `GRID_SOLVED` (after
  `nothing_to_undo`).
- `check` (spec 023 step 1) and `reveal` (spec 024): refused with `GRID_SOLVED`
  before any other check of theirs.
- Every other message works as before (`select_cell`, `ping`, chat, flags,
  host actions, joins).

Each refusal changes nothing and sends one `error` to the sender only.

### `replay` additions (spec 018 table)

| Event | Effect on the state |
| --- | --- |
| `grid_solved` | `solved = True` |
| `grid_full_wrong` | only `seq` |

`snapshot_for` already sends `solved = state.solved` (spec 012).

### Client (room page)

`RoomSession.solved` (spec 010) is already true after a `grid_solved` or a
snapshot with `solved: true`.

- Room page root: new attribute `data-solved`, `true` when `session.solved`, else
  `false`.
- `data-testid="grid-status"`, `role="status"`, shown when one of these holds,
  absent otherwise, in the place that "Where `grid-status` sits" below gives. (Note
  from the lead, 2026-10-15: this sentence said "shown under the clue bar when one
  of these holds". Under the clue bar, the status took the grid's height on low
  windows; the place now depends on the window's height.)

  | Condition | `data-state` | Text |
  | --- | --- | --- |
  | `session.solved` | `solved` | `t("completion.solved")` |
  | not solved, and every letter cell of the confirmed grid has a letter (pending edits not counted) | `full_wrong` | `t("completion.full_wrong")` |

  The `full_wrong` state is derived from the confirmed grid, so a page that joins a
  full, wrong grid shows it too; a `grid_full_wrong` event needs no handling
  beyond its `seq`.
- Where `grid-status` sits (AC-10). (Note from the lead, 2026-10-15: added, the
  lead's decision 8. A full grid showed the status under the clue bar and left
  `grid-viewport` about 75 px high at 568 by 320 in the touch context, below the
  100 px floor of spec 013 AC-6.)
  - On a window at most 500 px high (`window.innerHeight <= 500`, the height part
    of spec 024's small window), `grid-status` sits in `clue-bar`'s row, after
    `clue-bar-text`, and never makes `clue-bar` higher than it is on the same page
    without the status. (Note from the lead, 2026-10-15: this sentence said "adds no
    height: `clue-bar` is as high with it as without it". That cannot hold for a
    clue long enough to wrap, since an ellipsis works on one line only, so the bar
    can be lower with the status, never higher. Arrowword clues are short, they fit
    in a clue cell and FX-02's longest has 31 characters, so in practice the height
    is the same. (second review of spec 024)) While the status sits in the row,
    `clue-bar-text` is one line (CSS `white-space: nowrap` and `overflow: hidden`),
    cut at its end with an ellipsis (CSS `text-overflow: ellipsis`) when the row is
    too narrow for both, and `grid-status` keeps its whole text, on one line. A clue
    that would wrap onto several lines without the status makes `clue-bar` lower
    with it. (Note from the lead, 2026-10-15: this sentence said "When the row is
    too narrow for both, `clue-bar-text` is cut at its end with an ellipsis", which
    is true of one line only; the clue text is now one line while the status is in
    the row, and a wrapping clue makes the bar lower, never higher. (second review
    of spec 024)) `clue-bar-text` keeps its whole text in the DOM and its
    computed `font-size` of 14 px or more (spec 007), whatever it shows (a clue, or
    `t("clue_bar.empty")` when nothing is selected). (Note from the lead,
    2026-10-15: added.)
  - On a taller window, `grid-status` sits under the clue bar, as before, inside
    the window. (Note from the lead, 2026-10-15: added; this keeps the place the
    spec gave before.)
  - In both places it keeps `role="status"`, its `data-state` and its text from
    `fr.json` (spec 035's language rule), and its text keeps a contrast of at least
    4.5:1 with the background it sits on (spec 035's text contrast). The page holds
    one `grid-status` element at most; whether it moves by CSS or by markup is the
    implementer's choice, since the tests read boxes. (Note from the lead,
    2026-10-15: added.)
- Once solved, the page locks input: a letter key, `Backspace`, a key of the
  in-app keyboard, `Control+z` / `Meta+z` and the `undo-button` send nothing and
  change no cell; `undo-button` and the three check buttons (spec 023) are
  `disabled`. Selecting cells and moving with the arrow keys still work. (Note
  from the lead, 2026-10-15: "send nothing" leaves aside the heartbeat `ping`
  frames of spec 017, which the page may send at any time once the socket is
  open.)
- No cell changes look when `grid_full_wrong` arrives: there is no hint of where
  the mistake is.

New `fr.json` keys:

| Key | Value |
| --- | --- |
| `completion.solved` | `Grille terminée, bravo !` |
| `completion.full_wrong` | `Grille complète, mais pas encore juste.` |

### Test harness

- Rule unit tests: `new_room("ABC123", fx01_grid, NOW)` with players `p1`, `p2`;
  letters written with `handle_message(..., EditLetter(...))` at `NOW` unless said
  otherwise. `FULL17` is that room after the 17 FX-01 letters other than (4, 4)
  were written correctly by `p1` in row-major order: seq 2 + 17 = 19.
- WebSocket tests: as spec 011, `RoomConfig(max_edits_per_second=1000)`, three
  clients `Ana`, `Bob`, `Cy` on one FX-01 room. Times are taken with
  `time.monotonic()` in the test.
- "Browser with mocked socket" and "browser with live server" as spec 023.
- Engines: Chromium and WebKit locally, Firefox too in CI; no check of this spec
  is Chromium-only.
- Earlier tests that change a grid after it becomes full (spec 015 AC-3 and AC-4,
  whose random or all-`A` edits fill FX-01) now also receive `grid_full_wrong`
  events, which take seqs. This spec's test-writer updates those tests to count
  them (see "Edge cases"); their assertions on letters stay.

Status snapshots (AC-10). (Note from the lead, 2026-10-15: added with AC-10. Every
item below is new.)

- Browser with mocked socket. Each snapshot is built from `grid_view(fx02_grid)`,
  FX-02 being `tests/fixtures/fx02.json` (spec 006), with `seq` 5 and spec 013
  AC-6's players: `p1` (`Ana`, `you`, host, colour 0) and `p2` to `p8` (colours 1
  to 7). The mock then sends 100 feed items, spec 013's line events (`check_result`
  by `p2`, scope `grid`, empty lists) with `seq` 6 to 105, and the test waits until
  `room-page` has `data-seq` 105.
- `FX02_FULL_WRONG`: every letter cell has `letter="E"` and `author="p2"`, its
  other fields as `grid_view` gives them; `solved` false. FX-02's answers hold
  other letters (for example `C` at (0, 2), the first letter of `COU`), so the grid
  is full and wrong, and `grid-status` has `data-state="full_wrong"`.
- `FX02_SOLVED`: every letter cell holds its solution letter (see "Definitions")
  and `author="p2"`; `solved` true, so `grid-status` has `data-state="solved"`.
- `FX02_EMPTY`: `grid_view(fx02_grid)` unchanged (every letter cell empty); `solved`
  false, so `grid-status` is absent. `clue-bar`'s height on this page is the height
  "without a status".
- Selection: once the feed items are shown, the test taps (a click in the desktop
  context, `locator.tap()` in the touch context) the `clue` element of
  `On la glisse dans une enveloppe` at (0, 6), FX-02's longest clue (31
  characters; its word is `0,6,0`, `LETTRE`, down from (1, 6) to (6, 6)). Spec 007
  AC-3 then selects (1, 6) on all three snapshots, the first cell of a full word
  and the first empty cell of an empty one, so `clue-bar` has `data-word="0,6,0"`
  and `clue-bar-text` reads that clue.
- Window sizes and contexts: the eight sizes of spec 006 AC-5, and 1280 by 720.
  Desktop and touch contexts as spec 013 AC-6 (touch with spec 009's in-app
  keyboard), set up as spec 024's "Test harness" says.
- Spec 013 AC-6's checks: `grid-viewport` at least 100 px high, no vertical or
  horizontal page scroll, the grid inside the viewport at zoom 1, and `clue-bar`
  inside the window and, in the touch context, at or above the top of `keyboard`.
- Boxes are read with `locator.bounding_box()` and compared with 1 px tolerance.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-6.4.1) (rule unit test) When the last empty cell is filled and every letter is right, the grid is marked solved. Given `FULL17` and `created_at = NOW`, when `p2` writes `T` at (4, 4) at `NOW + 754.0`, then the outcome's entries are `LetterChanged(seq=20, row=4, column=4, letter="T", pencil=False, player_id="p2")` then `GridSolved(seq=21, elapsed_ms=754000)`, the new state has `solved=True` and seq 21, and `snapshot_for(state, "p1").solved` is True.
- **AC-2** (AC-6.4.1) (WebSocket) All players learn it within 1 second. Given Ana, Bob and Cy joined on a FX-01 room where Ana and Bob typed 17 right letters, when Bob sends the 18th, then each of the three clients receives the `letter_changed` of that edit followed by `{"type": "grid_solved", ...}` with the next seq, each within 1.0 s of Bob's send.
- **AC-3** (AC-6.4.1) (browser with live server) Every page shows the solved grid within 1 second. Two pages join one FX-01 room as `Ana` and `Bob`; Ana types the 17 letters other than (4, 4), Bob taps (4, 4) and types `T`; within 1000 ms both room pages have `data-solved="true"` and `grid-status` with `data-state="solved"` and the text `fr.json["completion.solved"]`.
- **AC-4** (AC-6.4.1) (rule unit test) Input is locked on the server once solved. Given the solved state of AC-1, at `NOW + 755.0`: `EditLetter` at (1, 0) with `A`, `Erase` at (1, 0), `PencilEdit` at (1, 0), `ConfirmPencil` at (1, 0), `Check(target=GridTarget())` and, from `p2` (whose last edit is (4, 4)), `Undo()` are each answered with one `ErrorMessage` with code `grid_solved`, no entry, and the state keeps seq 21; `SelectCell(row=1, column=0, direction=across)` from `p1` is accepted (a `selection_moved` in `to_others`).
- **AC-5** (AC-6.4.1) (browser with mocked socket) Input is locked on the page once solved. Given a FX-01 snapshot with `seq` 5 and every letter cell filled right, then `grid_solved` seq 6: tapping (1, 0) and pressing `B`, `Backspace` and `Control+z` sends no frame (none within 300 ms; Note from the lead, 2026-10-15: spec 017's heartbeat `ping` frames are not counted) and (1, 0) still shows its letter; `undo-button`, `check-letter`, `check-word` and `check-grid` are disabled; the grid still has `data-selected-row="1"` and `data-selected-column="0"`. The same holds for a page whose first snapshot has `solved: true`.
- **AC-6** (AC-6.4.2) (rule unit test; WebSocket) When the grid becomes full with at least one wrong letter, all players are told, with no hint of where. Rule: given `FULL17`, when `p2` writes `X` at (4, 4), then the entries are the `letter_changed` (seq 20) then `GridFullWrong(seq=21)`, and `solved` stays False; when `p2` then writes `Y` at (4, 4), the only entry is its `letter_changed` (the grid was already full); when `p2` erases (4, 4) then writes `X` again, a new `GridFullWrong` follows that `letter_changed`. WebSocket: in the same play on a three-client room (17 right letters, then `X` at (4, 4)), each client receives, right after the `letter_changed` of the `X` with seq `n`, a frame that parses to a JSON object with exactly the keys `type` and `seq`, equal to `{"type": "grid_full_wrong", "seq": n + 1}`.
- **AC-7** (AC-6.4.2) (browser with mocked socket; browser with live server) All players see "grid full, not yet correct". Mocked: given a FX-01 snapshot where 17 cells are filled and (4, 4) is empty, `grid-status` is absent; after `letter_changed` at (4, 4) letter `X` from `p2` and `grid_full_wrong`, `grid-status` has `data-state="full_wrong"` and the text `fr.json["completion.full_wrong"]`, no cell has `data-wrong="true"`, and the room page has `data-solved="false"`; after `letter_changed` erasing (4, 4), `grid-status` is absent again. A page whose first snapshot already holds a full, wrong grid shows the `full_wrong` status at once. Live: in the room of AC-3 with `X` typed at (4, 4) instead of `T`, both pages show `data-state="full_wrong"`.
- **AC-8** (AC-6.4.3) (rule unit test) On FX-01, entering the 18 letters triggers completion; with the M at (1, 2) replaced by N, it does not. Given a fresh FX-01 room with `p1`, when `p1` writes the 18 solution letters in row-major order, then exactly one `GridSolved` is produced, by the 18th edit, and `solved` is True. In a second run with `N` written at (1, 2) instead of `M`, the 18th edit produces `GridFullWrong` and no `GridSolved`, `solved` is False; when `p1` then writes `M` at (1, 2), that edit produces `GridSolved`.
- **AC-9** (new) (rule unit test) The solved state survives a reload. Given the entries of AC-1's whole play (joins, 18 edits, `grid_solved`), when they are replayed in order with `replay` from `new_room` on the same grid, then the result equals the live state for `solved`, `seq` and `cells`; and a room saved in a `RoomStore` and loaded again (spec 018) has `solved=True` and still refuses an `EditLetter` with `grid_solved`.
- **AC-10** (new, from the lead's decision of 2026-10-15) (browser with mocked socket) The completion status never takes the grid's room: on a window at most 500 px high it sits in the clue bar's row. Setup: "Status snapshots (AC-10)" in "Test harness", run with `FX02_FULL_WRONG` and again with `FX02_SOLVED`, the clue at (0, 6) tapped. At every window size of spec 006 AC-5, in desktop and touch contexts, `grid-status` shows with the snapshot's `data-state` and the text `fr.json["completion.full_wrong"]` or `fr.json["completion.solved"]`, and spec 013 AC-6's checks pass. At 568 by 320 and 740 by 360, in both contexts: the box of `grid-status` lies inside the box of `clue-bar`; its vertical range overlaps that of `clue-bar-text`, and its left edge is at or right of the right edge of `clue-bar-text`; its whole text shows (`scrollWidth <= clientWidth + 1`); `clue-bar-text` still has the text `On la glisse dans une enveloppe`, a computed `font-size` of 14 px or more, and computed `text-overflow` `ellipsis`, `white-space` `nowrap` and `overflow` `hidden`; and the height of `clue-bar` equals its height on a page given `FX02_EMPTY` with the same feed, tap, window and context, where `grid-status` is absent. (Note from the lead, 2026-10-15: the computed `text-overflow`, `white-space` and `overflow` checks were added, to pin the one-line rule of "Where `grid-status` sits". The rule itself is that the status never makes `clue-bar` higher. The check that the heights are equal stays, and still holds in this test, since FX-02's 31-character clue fits on one line at both sizes, with and without the status; no test needs a clue that wraps. (second review of spec 024)) At 1280 by 720, in both contexts, the top of `grid-status` is at or below the bottom of `clue-bar`, and its bottom is at most `window.innerHeight`. Each comparison of boxes has 1 px of tolerance. (Note from the lead, 2026-10-15: added. A test-writer found that `grid-status`, then always under the clue bar, left `grid-viewport` about 75 px high at 568 by 320 in the touch context with a full grid, in all three engines, and that no test covered the room layout while the status shows. Spec 019 AC-4 checks spec 013 AC-6 with every letter cell filled, so it relies on this rule too.) At 568 by 320 in the touch context, with each of the two snapshots, spec 035's contrast scan (its AC-8) and language scan (its AC-9) find no offending element, FX-02's clue texts counting as data of the test as FX-01's do. (Note from the lead, 2026-10-15: this sentence was added after the criterion, so that the status inside the clue bar's row is scanned too; spec 035's own scans run only at 1280 by 720 and 360 by 740, where the status sits under the clue bar. Spec 035's language scan lists the clue texts of FX-01 only as test data, so this sentence adds FX-02's.)

## Edge cases and errors

- Completion by an undo (AC-1): an undo that puts back the last right letter
  completes the grid like an edit.
- Completion by a lock (AC-1): a reveal (spec 024) that fills the last cell
  completes the grid; a check (spec 023) never fills a cell, so it never completes
  one, but a grid full of right letters is already solved before any check.
- Same letter again (AC-6): rewriting a letter of a full, wrong grid adds only its
  `letter_changed`; `grid_full_wrong` is sent when the grid becomes full, not on
  every edit while full. The page's banner stays, since it is derived from the
  grid.
- Wrong letter fixed while others remain wrong (AC-6, AC-7): no new event (still
  full); the banner stays.
- Locked cells count as filled (definitions); a grid whose every cell is locked by
  checks is solved by the edit that filled its last cell.
- Pencil letters (definitions): a pencil letter fills its cell and is compared
  with the solution like any letter (backlog AC-5.2.3, spec 020 AC-3). A grid
  whose last letter is written in pencil is full, and solved if every letter is
  right; confirming a pencil letter changes neither fullness nor rightness. No
  pencil letter exists until spec 020 is built, so no criterion of this spec
  tests it; spec 020 does.
- After solved (AC-4): a second `grid_solved` is never produced; the rule runs
  only while `solved` is False.
- `elapsed_ms` (AC-1): the shared timer's value of spec 027 when the grid is solved,
  in whole milliseconds, never negative. The field already exists in the protocol.
  (Note from the lead, 2026-10-15: spec 027 asks for this change. The sentence said
  "time since the room was created, in whole milliseconds, never negative. Spec 027
  (shared timer) may redefine it; the field already exists in the protocol." Spec 027
  redefines it: `elapsed_ms` counts from the first letter typed and leaves out the
  time when no player is connected. See the note in the completion rule for the
  formula and the case that changes, `654000` instead of `754000`. AC-1's own
  example is unchanged.)
- Late joiner (AC-5, AC-7): a snapshot with `solved` true locks the page; a
  snapshot of a full, wrong grid shows the `full_wrong` banner.
- Pending edits (AC-7): the banner uses confirmed letters only, so it appears
  together with the server's verdict, not while the last letter is unconfirmed.
- Earlier tests (harness): spec 015 AC-3 compares the room's final `seq` with
  "4 joins plus 1,000"; with this spec the expected value is 4 + 1,000 + the
  number of `grid_full_wrong` events the clients received (each client checks
  that it received every seq exactly once, as before). Spec 015 AC-4 counts 36
  `letter_changed` events; `grid_full_wrong` events may arrive between them and
  are ignored by that count. Spec 037 AC-1's full game ends solved: an edit sent
  after the last right letter would now be refused `grid_solved`, so its harness
  keeps the erase before the grid is complete. The lead amends the text of spec
  015 AC-3 accordingly when this spec is built.
- Answers stay on the server (AC-6): neither `grid_solved` nor `grid_full_wrong`
  carries a letter or a position; spec 037's traffic checker accepts them.
- Low windows (AC-10): on a window at most 500 px high, the status shares the clue
  bar's row and the clue text may end with an ellipsis on screen; `clue-bar-text`
  keeps its whole text, so a screen reader still reads the whole clue. A resize or
  a rotation across 500 px moves the status to its other place, with the same
  text and `data-state`. (Note from the lead, 2026-10-15: added with AC-10.)

## Out of scope

- Generated hints and dictionary lookups (epic E6).
- Check a letter, a word or the grid: spec 023.
- Reveal a letter or a word: spec 024.
- Group decision on help: spec 025.
- The shared timer and its pauses: spec 027; the end-of-game recap: spec 028.
- A celebration animation, sounds, or a feed line for completion.
- Saying how many letters are wrong in a full grid.
- Reopening a solved grid.

## Work packages

None.

## Decisions

Decided by the lead on 2026-10-11, under the owner's delegation of technical
decisions. Each one is already part of the spec above.

1. Numeric threshold: the backlog's 1 second is kept (owner's answer: keep the
   backlog defaults). It is measured from the last edit sent to the last client
   receiving `grid_solved` (WebSocket) and to both pages showing it (browser).
2. When `grid_full_wrong` is sent. Options: after every edit while the grid is full
   and wrong, or only when the grid becomes full. Pick: only when it becomes full,
   to keep the log short; the page's banner is derived from the confirmed grid, so
   it stays correct between events and for late joiners.
3. What locks input. Options: lock every cell with `cell_locked` events, or refuse
   input with `grid_solved`. Pick: refusals (spec 015 check 5, spec 018 undo
   step 3, spec 023 step 1); no cell events, so the log is not flooded at the end.
   Selection, chat, flags and host actions stay available.
4. `elapsed_ms`: the shared timer's value, in milliseconds, as spec 027 defines it.
   (Note from the lead, 2026-10-15: spec 027 (its decision 5) asks for this change.
   This decision said "milliseconds since the room was created, until spec 027
   defines the shared timer." Spec 027 defines it, so the "until" has come. The
   reason is unchanged: the field already existed in the protocol, so no protocol
   change is needed.)
5. Completion runs after any step that changes a letter or a lock (edit, undo,
   reveal, pencil edit or pencil confirmation), not only after `edit_letter`.
6. Pencil letters fill a cell and are compared with the solution like normal
   letters, as the backlog (AC-5.2.3) and spec 020 AC-3 require. Amended on
   2026-10-12; see the note below.

Note from the lead (2026-10-12): decision 6 first said "Pencil letters do not
fill a cell", and the definition of "filled" excluded pencil letters. That
contradicted the human-written backlog (`specs/_archive/complete.md`, AC-5.2.3:
"Completion (US-6.4) evaluates pencil and normal letters the same way") and
spec 020 AC-3, so this spec was wrong. "Filled" now counts any letter, pencil or
not; rightness compares the letter whatever its pencil flag; a pencil edit that
fills or completes the grid triggers the completion rule like any letter change.
No pencil letter can exist until spec 020 is built, so nothing observable
changes now and no criterion was added or removed. The server's `_is_filled` in
`src/nock/room.py` still excludes pencil letters; spec 020 changes it.
7. Page texts: `Grille terminée, bravo !` and `Grille complète, mais pas encore
   juste.`, in a `role="status"` element under the clue bar. (Note from the lead,
   2026-10-15: under the clue bar on windows taller than 500 px only; on lower
   windows the element sits in the clue bar's row, decision 8.)

Added on 2026-10-15, decided by the lead, to whom the owner delegated layout
choices. (Note from the lead, 2026-10-15: added with AC-10.)

8. Where the status sits (AC-10). A test-writer found that the status line under
   the clue bar took its height from the grid: at 568 by 320, in the touch context
   with the in-app keyboard and a full grid, `grid-viewport` was about 75 px high
   in all three engines, below the 100 px floor of spec 013 AC-6, and no test
   covered the room layout while the status shows. Pick: on windows at most 500 px
   high, the status sits in `clue-bar`'s row after the clue text and never makes
   the bar higher; the clue text, on one line while the status is there, gives up
   width and ends with an ellipsis, and the status keeps its whole text. A clue
   that would wrap without the status makes the bar lower with it. (Note from the
   lead, 2026-10-15: this said "adds no height", which an ellipsis cannot give a
   wrapping clue; the clue is now one line and the bar is never higher with the
   status, in practice the same height since clues are short. (second review of
   spec 024)) Taller windows keep it under the clue bar. 500 px is the
   height part of spec 024's small-window breakpoint, so the two of the eight
   sizes of spec 006 AC-5 that are low (568 by 320 and 740 by 360) use the clue
   bar's row. (Note from the lead, 2026-10-15: added.)

## Open questions

None.
