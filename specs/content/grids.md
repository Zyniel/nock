---
area: content
file: grids
status: approved
---

# content/grids - Grids: model, import checks and no third-party content

## Purpose

Every other domain reads grids through the model described here, and a grid is
served only once the import checks found it solvable. How a grid reaches the
server is `content/grid-files.md`; the product never fetches content from a third
party.

## Depends on

- `_reference.md`: the FX-01 and FX-02 grids used in the examples.
- `content/grid-files.md`: the files a grid enters through, checked by rule 6.
- `lobby/rooms.md`: a room keeps its own copy of its grid, in the model's JSON.

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
4. An answer is kept as written. Its separators are the hyphen `-`, the dot `.`,
   the space ` ` and the apostrophe (`'` and `’`, one and the same). Two things
   are derived from it, never stored:
   - its letters, normalised in this order: the ligatures Œ, œ, Æ, æ expanded to
     OE, oe, AE, ae; accents dropped (Unicode NFD, combining marks removed);
     the separators removed; uppercased. The result must be one or more letters
     A to Z. The letters are the word's solution: every check and the room's
     solution read them;
   - its breaks: each separator, counted as the number of letters before it:
     `ARC-EN CIEL` breaks after 3 and 5; `A.I`, `A I` and `A-I` give the
     letters `AI` and a break after 1; `AUJOURD'HUI` after 7. A separator must
     have a letter right before it and right after it, as written: an answer
     that starts or ends with one, or holds two in a row, is refused, naming
     the answer: `.AI`, `A.I.`, `A..I`, `A.-I`, `A  I`, `-ARC`, `ARC-`,
     `ARC- EN`.
5. Every message that names a position writes it `(row, column)`, for example
   `(0, 5)`. An edge is named by its two cells, the first one first.

### Import checks

6. An import stops at the first problem and reports it in one error, never in an
   unexpected exception. The checks run in this order:
   1. the grid parses into the model (rules 1 to 4);
   2. every arrow points to a letter cell inside the grid;
   3. every answer has as many letters as its word has cells;
   4. no two clues resolve to the same word;
   5. every letter cell belongs to some word;
   6. every run (two or more letter cells in a row or column, between non-letter
      cells or edges) is exactly one clue's word;
   7. crossing words agree on their shared letter;
   8. two words that share an edge (a word starting inside a longer run) agree
      on its break: a break of one after the cell before the edge is a break
      of the other, whatever the separator of each.

   A `.ipuz` file adds the checks of `content/grid-files.md` rule 12 to this
   order.
7. A clue is named by its clue cell and its text, a word by its answer as
   written.

### The model's JSON

8. The model has its own JSON: `width`, `height` and `cells`, each cell with its
   `type` (`letter`, `clue` or `empty`), `row` and `column`, a clue cell with its
   `clues` of `text`, `arrow` and `answer`. Rooms store a grid in it, and FX-01
   and FX-02 exist in it. It is not a grid file: a grid enters the catalogue only
   through `content/grid-files.md`.

### No third-party content

9. No server code opens an outgoing connection or imports a network client. The
   one exception is the sign-in e-mail (`account/account.md`): the file
   `src/nock/mailer.py`, and no other, may use `smtplib` and `ssl`.
10. No client file names a URL on another host (`http`, `https`, `ws`, `wss`,
    protocol-relative `//host`, CSS `url(//...)` or `@import`).
11. Both checks are static scans, a guard against accidental use and not a
    sandbox: names or URLs built at run time are not flagged. The samples each
    scan must and must not flag are in its tests.

## Acceptance criteria

- **AC-1** A grid declares its size and one type per cell. FX-01, in the model's
  JSON, loads with width and height 5, (0, 1) a letter cell and (0, 0) a clue
  cell; a cell of type `"black"` is refused. (← 002 AC-1)
- **AC-2** Each clue resolves to its word by rule 3. On FX-01, the first clue of
  (0, 0) gives (1, 0) to (1, 4), its second clue (0, 1) to (4, 1), the clue of
  (0, 2) gives (1, 2) to (4, 2), and the clue of (2, 0) gives (2, 1) to (2, 4).
  (← 002 AC-2)
- **AC-3** An answer keeps its text and derives its letters and breaks by rule 4:
  `ÊTRE` gives the letters `ETRE`; `ARC-EN-CIEL` stays `ARC-EN-CIEL` once
  loaded, with the letters `ARCENCIEL` and breaks after 3 and 5; `AUJOURD'HUI`
  gives `AUJOURDHUI` and a break after 7; `A.I`, `A I` and `A-I` each stay as
  written, with the letters `AI` and a break after 1; `CŒUR` `COEUR`; `R2D2`
  and `- -` are refused. (← 002 AC-3)
- **AC-4** FX-01, in the model's JSON, survives load, save and load with no
  difference. (← 002 AC-4)
- **AC-5** A grid without exactly one cell per position is refused, and the error
  names the position and the problem (`outside`, `duplicate`, `missing`, checked
  in that order): FX-01, in the model's JSON, without (2, 3) names `(2, 3)` and
  `missing`. (← 002 AC-5)
- **AC-6** An arrow that points to a clue cell, an empty cell or outside the grid
  is refused, naming the clue cell and the target: FX-01 with the clue of (0, 4)
  turned `right` names `(0, 4)` and `(0, 5)`. A `.ipuz` file reaches this error
  through the arrow its `cells` give (`content/grid-files.md` rule 8).
  (← 003 AC-1)
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
- **AC-18** The server scan of rules 9 and 11 finds nothing in `src/`, flags its
  forbidden samples, and allows `smtplib` and `ssl` in `src/nock/mailer.py` only.
  (← 005 AC-4)
- **AC-19** The client scan of rules 10 and 11 finds nothing in `web/src/` and
  `web/index.html`, and flags its forbidden samples. (← 005 AC-5)
- **AC-20** A separator not between two letters is refused, naming the answer:
  `-ARC`, `ARC-`, `ARC--EN`, `ARC- EN`, `.AI`, `A.I.`, `A..I`, `A.-I` and
  `A  I` each fail, while `ARC-EN CIEL` loads with breaks after 3 and 5.
- **AC-21** Two words sharing an edge that disagree on its break are refused,
  naming both answers and the edge: `VI-DE` across from (1, 0) with `IDE` across
  from (1, 1) names `VI-DE`, `IDE` and `(1, 1)`, `(1, 2)`; with `I-DE`, and
  with `I DE`, the grid loads. The check comes last, after the crossing check.

## Edge cases

- One-letter words are allowed when the answer has one letter (AC-2, AC-7).
- A single letter between two non-letter cells is not a run (AC-10).
- A word starting mid-run does not give the run a clue (AC-10).
- When one change causes several problems, the error is the first in rule 6's
  order: for example a too-short answer wins over the crossing check (AC-6 to
  AC-11, AC-21).
- An answer's length (AC-7) and its crossings (AC-11) are counted in letters:
  `VI-DE` fits four cells, `A.I` two (AC-3).
- Crossing words never share an edge: an across break and a down break at the
  same cell are both kept (AC-21).
- A room holds its grid's answers as written, so their breaks follow rule 4 as
  it stands; a room stored before answers were kept as written holds letters
  only (`ARCENCIEL`), so it loads with no break (AC-3).
- Cells may be listed in any order in the model's JSON (AC-1).
- `tests/` and `scripts/` are not scanned; `web/dist/`, `web/node_modules/` and
  `web/public/` are not scanned (AC-18, AC-19).

## Out of scope

- A grid editor and grid generation.
- Reporting more than one problem per import.
- A look of its own per separator (every break is drawn alike), the separators
  in the clue bar or a length pattern. What a break looks like on the grid:
  `gameplay/board.md`; how it reaches the browser: `platform/realtime.md`.
- The grid files, the index, credits and withdrawal: `content/grid-files.md`.
- Listing, filtering and the grid page: `content/library.md`.
- Where real grids come from (commission, licence, generation): an owner decision.

## Code

- `src/nock/grid.py`: the model, letters and breaks, clue resolution.
- `src/nock/grid_import.py`: the import checks.
- `src/nock/mailer.py`: the one file allowed to send mail.
- Tests: `tests/test_grids_*`, `tests/test_spec_002_*`, `test_spec_003_*`, and
  the scan tests of `test_spec_005_*`.
