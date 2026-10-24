---
area: content
file: grids
status: draft
baseline: v1.1.0
---

# content/grids - Grids: model, files, import checks and rights

## Purpose

A grid enters Nock only as a file in `grids/`, checked at server start: it must be
solvable and carry its credits. Every other domain reads grids through the model
described here, and the product never fetches content from a third party.

## Depends on

- `_reference.md`: the FX-01 and FX-02 grids used in the examples.
- `content/library.md`: what players see of the grids loaded here.
- `lobby/rooms.md`: a room keeps its own copy of its grid.

## Rules

### Grid model

1. A grid has a width, a height and exactly one cell per position (row, column),
   counted from zero. A cell is a letter cell, a clue cell or an empty cell.
2. A clue cell holds one or two clues. A clue has a non-empty text, an arrow and
   an answer. A letter cell holds no letter: the solution lives in the answers.
3. A clue resolves to its word, the letter cells it answers:

   | Arrow | First cell | Direction |
   | --- | --- | --- |
   | `right` | (r, c + 1) | across |
   | `down` | (r + 1, c) | down |
   | `down_then_right` | (r + 1, c) | across |
   | `right_then_down` | (r, c + 1) | down |

   The word runs from the first cell to the cell before the first non-letter cell
   or the grid edge. The first cell must be a letter cell inside the grid.
4. Answers are normalised, in this order: the ligatures Œ, œ, Æ, æ expanded to
   OE, oe, AE, ae; accents dropped (Unicode NFD, combining marks removed); spaces,
   hyphens and apostrophes (`'` and `’`) removed; uppercased. The result must be
   one or more letters A to Z.
5. Every message that names a position writes it `(row, column)`, for example
   `(0, 5)`.

### Import checks

6. An import stops at the first problem and reports it in one error, never in an
   unexpected exception. The checks run in this order:
   1. the file parses into the model (rules 1 to 4);
   2. every arrow points to a letter cell inside the grid;
   3. every answer has as many letters as its word has cells;
   4. no two clues resolve to the same word;
   5. every letter cell belongs to some word;
   6. every run (two or more letter cells in a row or column, between non-letter
      cells or edges) is exactly one clue's word;
   7. crossing words agree on their shared letter.
7. A clue is named by its clue cell and its text, a word by its answer.

### Grid files

8. `grids/` holds one JSON file per grid, read once at server start. A missing
   directory is an empty catalogue. Only names ending in lower-case `.json` and
   not starting with `.` are read, in code-point order of their names; other
   files and sub-directories are ignored.
9. A file holds exactly: `number` (1 to 999,999,999, unique), `published_on`
   (exactly `YYYY-MM-DD`), `force` (1 to 4), `published` (boolean), `author`,
   `source`, `licence` (each 1 to 200 characters once stripped), the optional
   `withdrawn` (boolean, default false) and `grid` (the model's JSON). Values are
   strict: `"2"` is not a force, `"yes"` is not a boolean.
10. A file that fails rule 9 or the import checks stops the server from starting,
    with an error naming the file.
11. Credits are recorded, never shown to players and never interpreted.
12. `published: false` hides a grid that was never released. `withdrawn: true`
    marks a grid whose rights ended, applied at the next start: no new room may
    start on it, and it wins over `published: true`. Rooms already open on it keep
    working, since a room holds its own copy of the grid.

### No third-party content

13. No server code opens an outgoing connection or imports a network client. The
    one exception is the sign-in e-mail (`account/account.md`): the file
    `src/nock/mailer.py`, and no other, may use `smtplib` and `ssl`.
14. No client file names a URL on another host (`http`, `https`, `ws`, `wss`,
    protocol-relative `//host`, CSS `url(//...)` or `@import`).
15. Both checks are static scans, a guard against accidental use and not a
    sandbox: names or URLs built at run time are not flagged. The samples each
    scan must and must not flag are in its tests.

## Acceptance criteria

- **AC-1** A grid declares its size and one type per cell. FX-01 loads with width
  and height 5, (0, 1) a letter cell and (0, 0) a clue cell; a cell of type
  `"black"` is refused. (← 002 AC-1)
- **AC-2** Each clue resolves to its word by rule 3. On FX-01, the first clue of
  (0, 0) gives (1, 0) to (1, 4), its second clue (0, 1) to (4, 1), the clue of
  (0, 2) gives (1, 2) to (4, 2), and the clue of (2, 0) gives (2, 1) to (2, 4).
  (← 002 AC-2)
- **AC-3** Answers are normalised by rule 4: `ÊTRE` gives `ETRE`, `ARC-EN-CIEL`
  `ARCENCIEL`, `AUJOURD'HUI` `AUJOURDHUI`, `CŒUR` `COEUR`; `R2D2` and `- -` are
  refused. (← 002 AC-3)
- **AC-4** FX-01 survives load, save and load with no difference. (← 002 AC-4)
- **AC-5** A grid without exactly one cell per position is refused, and the error
  names the position and the problem (`outside`, `duplicate`, `missing`, checked
  in that order): FX-01 without (2, 3) names `(2, 3)` and `missing`. (← 002 AC-5)
- **AC-6** An arrow that points to a clue cell, an empty cell or outside the grid
  is refused, naming the clue cell and the target: FX-01 with the clue of (0, 4)
  turned `right` names `(0, 4)` and `(0, 5)`. (← 003 AC-1)
- **AC-7** An answer whose length differs from its word is refused, naming the
  clue cell and the answer: `MIME` changed to `MIM` names `(0, 2)` and `MIM`.
  (← 003 AC-5)
- **AC-8** Two clues that resolve to the same word are refused, naming both clue
  cells and both texts. (← 003 AC-7)
- **AC-9** A letter cell in no word is refused, naming it: FX-01 without the clue
  `De la marine` names `(0, 1)`. (← 003 AC-6)
- **AC-10** A run with no clue is refused, naming its first and last cells: FX-01
  with (3, 0) emptied names `(3, 1)` and `(3, 4)`. (← 003 AC-2)
- **AC-11** Crossing words that disagree are refused, naming both answers and the
  shared cell: `MIME` changed to `MIMA` names `MIMA`, `LEST` and `(4, 2)`.
  (← 003 AC-3)
- **AC-12** FX-01 imports and reports 8 words, 18 letter cells and 7 clue cells;
  empty cells are counted nowhere. (← 003 AC-4)
- **AC-13** `grids/` loads by rule 8: `b.json` (number 2) and `a.json` (number 1)
  load as 1 then 2; `B.json` comes before `a.json`; `A.JSON`, `.x.json`,
  `notes.txt` and `old/` are ignored. (← 004 AC-5, 004 AC-7)
- **AC-14** A file that breaks rule 9 or fails the import is refused, naming the
  file: a date `2026-1-1`, a force `"2"`, an extra key `"colour"`, a second file
  with the same number, or a grid with `MIMA`. (← 004 AC-5, 004 AC-7)
- **AC-15** A file without `author`, `source` or `licence`, or with one blank,
  over 200 characters or not text, is refused, naming the file; credits are
  stored stripped, and a non-boolean `withdrawn` is refused.
  (← 005 AC-1, 005 AC-2, 005 AC-3)
- **AC-16** A withdrawn grid is not listed, its grid page and summary answer 404,
  and no new room starts on it, while a published one is served.
  (← 005 AC-6)
- **AC-17** A room opened before its grid was withdrawn keeps working: players
  join it, type every letter and, after a server restart, get it back from the
  store. (← 005 AC-7)
- **AC-18** The server scan of rules 13 and 15 finds nothing in `src/`, flags its
  forbidden samples, and allows `smtplib` and `ssl` in `src/nock/mailer.py` only.
  (← 005 AC-4)
- **AC-19** The client scan of rules 14 and 15 finds nothing in `web/src/` and
  `web/index.html`, and flags its forbidden samples. (← 005 AC-5)

## Edge cases

- One-letter words are allowed when the answer has one letter (AC-2, AC-7).
- A single letter between two non-letter cells is not a run (AC-10).
- A word starting mid-run does not give the run a clue (AC-10).
- When one change causes several problems, the error is the first in rule 6's
  order: for example a too-short answer wins over the crossing check (AC-6 to
  AC-11).
- Cells may be listed in any order in a file (AC-1).
- `licence` is required; `license` is an unknown key (AC-15).
- Credits keep accents, apostrophes, `n°` and line breaks; the 200 limit counts
  code points (AC-15).
- A withdrawn grid already open in a browser can still be joined by its room link
  (AC-17).
- `tests/` and `scripts/` are not scanned; `web/dist/`, `web/node_modules/` and
  `web/public/` are not scanned (AC-18, AC-19).

## Out of scope

- A grid editor and grid generation.
- Reporting more than one problem per import.
- Reloading grids or withdrawing one without a restart, and closing rooms already
  open on a withdrawn grid.
- Showing credits to players.
- Listing, filtering and the grid page: `content/library.md`.
- Deleting stored rooms or history of a withdrawn grid: `admin/operations.md`.
- Where real grids come from (commission, licence, generation): an owner decision.

## Code

- `src/nock/grid.py`: the model, normalisation and clue resolution.
- `src/nock/grid_import.py`: the import checks.
- `src/nock/catalogue.py`: grid files, credits, withdrawal (`load_catalogue`,
  `find_published`).
- `src/nock/mailer.py`: the one file allowed to send mail.
- Tests: `tests/test_spec_002_*`, `test_spec_003_*`, `test_spec_005_*`, and the
  grid-file tests of `test_spec_004_*`.
