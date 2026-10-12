---
id: "023"
title: Check a letter, a word or the grid
status: done
---

# 023 - Check a letter, a word or the grid

Epic E6 Help and validation (US-6.1) · Release: MVP · Epic depends on: E4
The FX-01 reference grid and the glossary are in `specs/_reference.md`. The rooms
engine (`nock.room`, `nock.hub`, delivery order, test harness) is defined in spec
011, edits in spec 015, locked cells in spec 016, the log and `replay` in spec
018, the activity feed in spec 013, the messages in spec 039 (`Check`,
`CheckTarget`, `CheckResult`, `CellLocked`).

## Goal

As a player, I want to check what we wrote, so that an early mistake doesn't block the crossing words.

Help is decided by the server and shared by the room, so one impatient player cannot solve the grid for everyone.

## Public interface

No new protocol message, no new `ErrorCode` and no new public Python name. This
spec gives `Check` its meaning in `nock.room.handle_message`, extends
`nock.room.replay`, and adds the check controls and the struck-through letters to
the room page.

### Server rule: `Check` in `nock.room.handle_message`

```python
# src/nock/room.py (signatures unchanged, spec 011)
def handle_message(state, player_id, message, now, config=DEFAULT_CONFIG) -> Outcome: ...
def replay(state: RoomState, entry: LogEntry) -> RoomState: ...
```

`Check(target)` from joined player `p` is input (spec 013: it sets
`last_input_at` and wakes an idle player). It is not an edit: spec 037's rate
limit does not count it. Its checks run in this order; the first that fails
refuses the check (unchanged state, no entry, one `ErrorMessage` in `reply`):

1. (spec 026) the grid is solved: `grid_solved`. Until spec 026 is built, this
   check never refuses.
2. `state.settings.help_mode` is `none`: `help_disabled`.
3. The target names nothing:
   - `CellTarget(row, column)` that is not a letter cell of `state.grid` (a clue
     cell, an empty cell, or outside the grid): `not_a_letter_cell`;
   - `WordTarget(row, column, clue_index)` where `(row, column)` is outside the
     grid or not a clue cell, or `clue_index` is not an index of its clues:
     `invalid_target`.
   - `GridTarget()` always names the grid.

Help mode `vote` behaves like `free` until spec 025 is built (spec 025 then turns
a check into a vote).

The cells in scope, in this order:

- letter: the one cell;
- word: `state.grid.word_cells(row, column, clue_index)`, in reading order;
- grid: every letter cell, in the order of `state.cells`.

Each cell in scope that is locked, or has no letter, or holds a pencil letter
(spec 020) is left out. Each other cell is compared with its solution letter (the
letter of the normalised `answer` of any clue whose word holds the cell; spec 003
guarantees they agree): equal is correct, different is wrong.

An accepted check, with `s = state.seq`, produces in one step:

- one entry `CheckResult(seq=s + 1, player_id=p, target=<the target as received>, correct=<CellRefs of the correct cells, in scope order>, wrong=<CellRefs of the wrong cells, in scope order>)`;
- then, for the k-th correct cell (k from 1), one entry
  `CellLocked(seq=s + 1 + k, row, column, letter=<its letter>, revealed=False)`.

State after the step: each wrong cell has `wrong = True` (letter, author and
`changed_seq` unchanged); each correct cell has `locked = True`, `wrong = False`,
`changed_seq` = its `cell_locked` seq, `changed_by = None` (spec 016's lock, as
`replay` of `cell_locked` already does); `state.seq` = the last seq. A check with
nothing to compare (every cell in scope empty or locked) still produces its
`check_result` with empty `correct` and `wrong`.

Every entry is broadcast to every joined connection, the checker's included
(spec 011 delivery). No entry carries a letter that is not already in its cell;
the answer itself is never sent.

### `replay` additions (spec 018 table)

| Event | Effect on the state |
| --- | --- |
| `check_result` | `wrong = True` on each cell of `wrong` |
| `cell_locked` | as spec 018, and also `wrong = False` |

Replaying the entries of a check gives the same state as the live step.

### Client: struck-through letters

`web/src/lib/roomSession.ts`:

```ts
export interface LetterCellView {
  // ... fields of specs 015 to 018
  // True while the letter in place was found wrong by the last check of it.
  wrong: boolean
}
```

- A snapshot's letter cell gets `wrong = (cell.wrong === true)`.
- An applied `check_result` sets `wrong = true` on each cell of its `wrong` list.
- An applied `letter_changed` sets `wrong = false` on its cell (spec 015 decision 6).
- An applied `cell_locked` sets `wrong = false` on its cell.

On the `cell` element of each letter cell (spec 006), a new attribute
`data-wrong`: `true` when the cell's confirmed `wrong` is true and its shown
letter is the confirmed one (no pending edit, spec 015), else `false`. A cell with
`data-wrong="true"` shows its letter struck through: computed
`text-decoration-line` includes `line-through`.

### Client: check controls

Shown on the room page once it has a snapshot, in the room header beside the undo
control (spec 018):

- `data-testid="check-panel"`, a `role="group"` with `aria-label`
  `t("check.label")`, holding three buttons in this order:

  | `data-testid` | Text | `aria-label` | Sends |
  | --- | --- | --- | --- |
  | `check-letter` | `t("check.letter")` | `t("check.letter_label")` | `{"type": "check", "target": {"scope": "letter", "row": r, "column": c}}` for the selected cell |
  | `check-word` | `t("check.word")` | `t("check.word_label")` | `{"type": "check", "target": {"scope": "word", "row": cr, "column": cc, "clue_index": i}}` for the selected word's clue |
  | `check-grid` | `t("check.grid")` | `t("check.grid_label")` | `{"type": "check", "target": {"scope": "grid"}}` |

- `check-letter` and `check-word` are `disabled` while nothing is selected. All
  three are `disabled` while the snapshot's `settings.help_mode` is `none`, and
  (spec 026) while the grid is solved.
- Pressing a button sends its message once and does not move the selection; the
  page waits for the server's events (no local guess of the result).
- An `error` answering a check (`help_disabled`, `invalid_target`,
  `not_a_letter_cell`, `grid_solved`) changes nothing on the page and does not
  touch the pending edits (spec 015: those codes are not edit answers, except
  `not_a_letter_cell` and `grid_solved`; see "Edge cases").

### Activity feed

Spec 013 already turns each applied `check_result` into one feed item,
`data-kind="check"`, with the text `t("feed.check.letter" | "feed.check.word" | "feed.check.grid", { name })`
(the checker's nickname and the scope). This spec keeps those keys and texts.

### New `fr.json` keys

| Key | Value |
| --- | --- |
| `check.label` | `Vérifier` |
| `check.letter` | `Lettre` |
| `check.word` | `Mot` |
| `check.grid` | `Grille` |
| `check.letter_label` | `Vérifier la lettre` |
| `check.word_label` | `Vérifier le mot` |
| `check.grid_label` | `Vérifier la grille` |

### Test harness

- Rule unit tests: `new_room("ABC123", fx01_grid, NOW)`, players added with
  `join_room`, letters written with `handle_message(..., EditLetter(...))`, then
  `handle_message(state, "p1", Check(target=...), NOW)`.
- `S1` below is a FX-01 room with players `p1` and `p2` (seq 2 after the joins)
  where `p1` wrote, in this order, `T` at (1, 0), `X` at (1, 1), `I` at (1, 3),
  `S` at (1, 4), and `p2` wrote `V` at (2, 1) and `Q` at (2, 2): seq 8. (1, 2) is
  empty. Solutions: (1, 0) T, (1, 1) A, (1, 3) I, (1, 4) S, (2, 1) V, (2, 2) I.
- WebSocket tests: as spec 011 (`TestClient`, FX-01 room, `RoomConfig(max_edits_per_second=1000)`).
- "Browser with mocked socket": spec 040's mock with FX-01 snapshots built with
  `grid_view` and `model_copy`. "Browser with live server": spec 040's
  `live_server`, two browser contexts for two players.
- Engines: every browser criterion runs in Chromium and WebKit locally and also
  Firefox in CI (`specs/_architecture.md`). No check of this spec is
  Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-6.1.1) (rule unit test) A check of a word marks its wrong letters and locks its correct ones. Given `S1`, when `p1` checks `WordTarget(row=0, column=0, clue_index=0)` (TAMIS), then the outcome's entries are, in order: `CheckResult(seq=9, player_id="p1", target=WordTarget(row=0, column=0, clue_index=0), correct=(CellRef(row=1, column=0), CellRef(row=1, column=3), CellRef(row=1, column=4)), wrong=(CellRef(row=1, column=1),))`, then `CellLocked` seq 10 at (1, 0) `T`, seq 11 at (1, 3) `I`, seq 12 at (1, 4) `S`, each `revealed=False`; the new state has seq 12, (1, 0), (1, 3) and (1, 4) locked with their letters and authors kept, (1, 1) `wrong=True` still holding `X` with author `p1`, and `grid_state` shows the same values.
- **AC-2** (AC-6.1.1) (rule unit test) A check of a letter and of the grid apply the same rule. Given `S1`: checking `CellTarget(row=2, column=2)` gives `CheckResult(correct=(), wrong=(CellRef(row=2, column=2),))` and no `CellLocked`; checking `GridTarget()` gives `correct` = (1, 0), (1, 3), (1, 4), (2, 1) and `wrong` = (1, 1), (2, 2) in the order of `state.cells`, followed by four `CellLocked` in the order of `correct`.
- **AC-3** (AC-6.1.1) (WebSocket) The result reaches all players, and a later joiner sees it. Given a FX-01 room where client A (`Ana`) and client B (`Bob`) joined and A typed `T` at (1, 0) and `X` at (1, 1), when A sends `{"type": "check", "target": {"scope": "word", "row": 0, "column": 0, "clue_index": 0}}`, then A and B each receive, in seq order, one `check_result` with `correct` `[(1, 0)]` and `wrong` `[(1, 1)]` and then one `cell_locked` for (1, 0) with letter `T`; a client C joining afterwards gets a snapshot where (1, 0) has `locked=True` and (1, 1) has `wrong=True` and letter `X`.
- **AC-4** (AC-6.1.1) (browser with live server) Every player sees the strike and the lock. Two pages join one FX-01 room as `Ana` and `Bob`; Ana taps (1, 0), types `T` then `X` (so (1, 1) holds `X`), and clicks `check-word`; then on both pages (1, 1) has `data-wrong="true"` with a computed `text-decoration-line` containing `line-through`, and (1, 0) has `data-locked="true"` and `data-wrong="false"`.
- **AC-5** (AC-6.1.1) (browser with mocked socket) The strike is cleared by a new letter or a lock, as the lead noted after spec 016's review. Given a FX-01 snapshot with `seq` 5 where (1, 1) holds `X` with `wrong` true and (2, 2) holds `Q` with `wrong` false: (1, 1) shows `data-wrong="true"`; when the mock sends `check_result` seq 6 with `wrong` `[(2, 2)]`, (2, 2) shows `data-wrong="true"`; when it sends `letter_changed` seq 7 at (1, 1) letter `A` from `p2`, (1, 1) shows `data-wrong="false"`; when it sends `cell_locked` seq 8 at (2, 2) letter `I` with `revealed` true, (2, 2) shows `data-wrong="false"`. In a second run, after the snapshot, the player taps (1, 1) and types `B` (no answer from the mock): (1, 1) shows `B` with `data-unconfirmed="true"` and `data-wrong="false"`.
- **AC-6** (AC-6.1.2) (rule unit test) Empty cells in the scope are ignored. Given `S1`, when `p1` checks `WordTarget(row=0, column=2, clue_index=0)` (MIME: (1, 2) empty, (2, 2) `Q`, (3, 2) and (4, 2) empty), then `correct == ()`, `wrong == (CellRef(row=2, column=2),)`, no `CellLocked` follows, and (1, 2), (3, 2), (4, 2) are unchanged (`letter=None`, `locked=False`, `wrong=False`). Checking `CellTarget(row=1, column=2)` gives a `CheckResult` with `correct == ()` and `wrong == ()`, one entry only, and seq 9.
- **AC-7** (AC-6.1.3) (rule unit test; WebSocket) The result is computed on the server from the letters in place, and the answer is not sent. Rule: given `S1` where `p2` then writes `A` at (1, 1) (seq 9), a check of TAMIS by `p1` lists (1, 1) in `correct` and locks it with letter `A`. WebSocket: the full FX-01 game of spec 037's test harness, where Ana sends a grid check right after the three wrong letters `X` are typed (and the remaining edits skip cells that the check locked), passes spec 037's three rules of "What a browser may receive" on every recorded frame, and every `cell_locked` with `revealed` false holds a letter typed at that cell before it.
- **AC-8** (AC-6.1.4) (browser with live server) Each check adds a line to the activity feed with the player and the scope. In the room of AC-4, after Ana's `check-word`, both pages' `activity-feed` hold one new `feed-item` with `data-kind="check"` and the text `fr.json["feed.check.word"]` with `{name}` = `Ana`; after Bob selects (2, 1) and clicks `check-letter`, then `check-grid`, both feeds end with the texts of `feed.check.letter` and `feed.check.grid` with `{name}` = `Bob`.
- **AC-9** (new) (browser with mocked socket) The check controls send the right message and are disabled when they cannot apply. Given a FX-01 snapshot (`help_mode` `free`): `check-panel` holds `check-letter`, `check-word`, `check-grid` in that order with the texts and `aria-label`s of the table; with nothing selected `check-letter` and `check-word` are disabled and `check-grid` is enabled, and clicking `check-grid` sends one frame that parses to `Check(target=GridTarget())`; after tapping (2, 2) twice (`down`, word `0,2,0`), `check-letter` sends `Check(target=CellTarget(row=2, column=2))` and `check-word` sends `Check(target=WordTarget(row=0, column=2, clue_index=0))`, and the selection is still (2, 2) `down`. When the mock then sends `settings_changed` with `help_mode` `none`, all three buttons are disabled.
- **AC-10** (new) (rule unit test) A check that cannot apply is refused and changes nothing. Given `S1`: with `help_mode` `none` (set by a `ChangeSettings` from the host), any check is answered `help_disabled`; `CellTarget(row=0, column=0)` (a clue cell) and `CellTarget(row=5, column=0)` are answered `not_a_letter_cell`; `WordTarget(row=1, column=0, clue_index=0)` (a letter cell), `WordTarget(row=0, column=2, clue_index=1)` (one clue only) and `WordTarget(row=9, column=9, clue_index=0)` are answered `invalid_target`. Each refusal returns the state it was given apart from the player's `last_seen_at` and `last_input_at` (seq unchanged: 9 after the `ChangeSettings`, 8 otherwise), no entry and exactly one `ErrorMessage` in `reply`. With `help_mode` `vote`, a check of TAMIS gives the result of AC-1.

## Edge cases and errors

Notes from the lead carried into this spec: the client's `LetterCellView` had no
`wrong` field (spec 016 review, 2026-10-11). It is added here, shown, and reset
to false by `cell_locked` and by a new letter (AC-5).

- Locked cells in scope (AC-2): left out of both lists and not locked again; a
  check of a word whose letters are all locked gives empty lists.
- Re-check of a wrong cell (AC-1): still wrong, listed again, `wrong` stays true.
- Wrong then fixed (AC-5, AC-7): any accepted edit or undo of the cell clears
  `wrong` on the server (spec 015 decision 6, spec 018 undo) and on the page.
- A pending edit on a checked cell (AC-5): the server checks the letter it holds,
  not the one the page shows; the page shows the struck look only for the
  confirmed letter.
- Checking someone else's letters (AC-1): allowed; any player checks any cell.
- Refusal codes on the page (AC-9): `not_a_letter_cell` and `grid_solved` are also
  edit answers (spec 015). The page never sends a letter check on a non-letter
  cell (the button needs a selected letter cell), and spec 026 disables the
  buttons once solved, so these refusals cannot pop an unrelated pending edit in
  normal use; a race (solved between the click and the server) may drop one
  pending edit, which the solved grid refuses anyway.
- Rate (AC-10): checks are not throttled; each accepted check is logged. The help
  mode (`none`, and `vote` once spec 025 is built) is the room's control.
- Pencil letters (spec 020): left out like empty cells. Until spec 020 is built,
  no cell holds one.
- Undo after a check (spec 018): undoing an edit whose cell was locked by a check
  is refused `nothing_to_undo` (the lock changed `changed_seq`); undoing the last
  edit of a cell marked wrong is allowed and clears `wrong`.
- Seq gaps (AC-3): none; the check's entries take consecutive seqs and are applied
  in order by every page (spec 040).

## Out of scope

- Generated hints and dictionary lookups (epic E6).
- Reveal a letter or a word: spec 024.
- Group decision on help (votes): spec 025. Until then `vote` acts as `free`.
- Completion detection, and refusing checks on a solved grid: spec 026.
- Keyboard shortcuts for checks; spec 035 makes the buttons reachable by Tab.
- A count of right and wrong letters in the feed line; showing which word was
  checked in the feed.
- Limiting how many checks a room may make.

## Work packages

None.

## Decisions

Decided by the lead on 2026-10-11, under the owner's delegation of technical
decisions. Each one is already part of the spec above.

1. Bad word target. Options: a new `ErrorCode`, or reuse one. Pick: reuse
   `invalid_target` (spec 039 decision 19), so the protocol does not change; a bad
   letter target reuses `not_a_letter_cell` like an edit.
2. Order of refusals: solved (spec 026), help mode `none`, then the target.
3. `vote` mode before spec 025 exists. Options: refuse, or act as `free`. Pick: act
   as `free`; the host can set `vote` today (spec 014), and refusing would make
   help vanish without explanation.
4. Locked, empty and pencil cells are left out of the result; an empty result is
   still logged and shown in the feed, so the group sees that someone checked.
5. Order of `correct` and `wrong`: scope order (reading order for a word,
   `state.cells` order for the grid); `cell_locked` events follow in the order of
   `correct`.
6. A correct cell is locked (spec 039 decision 10: `cell_locked` events after the
   result), and `cell_locked` also clears `wrong` on the server and the page.
7. Controls: three buttons in the header, short visible text (`Lettre`, `Mot`,
   `Grille`) under the group label `Vérifier`, with full `aria-label`s that
   contain the visible text (WCAG 2.5.3).
8. The feed keeps spec 013's texts: they already name the player and the scope.

## Open questions

None.
