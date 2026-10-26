---
area: content
file: grid-files
status: done
---

# content/grid-files - Grid files: the index, the ipuz files, credits, withdrawal

## Purpose

An operator adds a grid by dropping a standard ipuz ArrowWord file in `grids/` and
naming it in the index, with its number, rights and publication state. Any ipuz
tool can open and save the grid file without losing anything of it; what Nock
decides about a grid stays in the index. Both are read once at server start.

## Depends on

- `content/grids.md`: the model, rule 6's import checks, positions written
  `(row, column)`.
- `_reference.md`: the FX-01 grid used in the examples.
- `content/library.md`: what players see of a grid (`force`, `published_on`,
  never a credit).

## Rules

### Where grids live

1. `grids/` holds the index `grids/catalogue.json` and one `.ipuz` file per grid,
   read once at server start. No directory, or no index, is an empty catalogue.
   A file the index does not name is ignored.
2. The index is a JSON array of entries, each holding exactly: `number` (1 to
   999,999,999), `file` (a name directly inside `grids/`, without `/` or `\`,
   ending in `.ipuz`), `published` (boolean), `source` and `licence` (each 1 to
   200 characters once stripped, stored stripped) and the optional `withdrawn`
   (boolean, default false). Values are strict: `"1"` is not a number, `"yes"`
   is not a boolean; an unknown key is refused.
3. Grids are read in the index's order. An entry naming a missing file, two
   entries naming the same file or the same number, or an entry or a file that
   breaks these rules or the import checks, stops the server from starting with
   one error naming the file concerned: `catalogue.json` for an index problem,
   the `.ipuz` file otherwise (a missing one included).
4. What Nock decides about a grid (its number, whether it is published or
   withdrawn, its source and licence) is in the index. What describes the grid
   as published (its cells, clues, answers, author, date, difficulty and
   descriptive fields) is in the `.ipuz` file, in standard ipuz fields only.
   The catalogue entry joins the two.

### The ipuz file

5. A `.ipuz` file is a JSON object (UTF-8) of the ipuz v2 ArrowWord kind. It
   holds `version` exactly `http://ipuz.org/v2`, `kind` exactly
   `["http://ipuz.org/crossword/arrowword#1"]`, `clueplacement` exactly
   `"blocks"`, `dimensions` (`width`, `height`), `puzzle`, `clues` holding
   exactly the key `Clues`, `author`, `date` and `difficulty`; optionally `block`,
   `empty`, `solution` and the fields of rule 11. Every coordinate in the file is
   `[column, row]`, counted from zero; Nock turns it into `(row, column)` before
   any message, which may also quote the value as written (`location [4, 0], that
   is (0, 4)`).
6. The mapping to the model:

   | Model | ipuz |
   | --- | --- |
   | width, height | `dimensions` |
   | letter cell | the `empty` value in `puzzle` (default `0`; `0` and `"0"` are the same value), or the object `{"cell": <empty>, "style": {"dashed": "<letters>"}}` with no other key (rule 9) |
   | clue cell | the `block` value (default `"#"`, a text, different from `empty`) with one or two clues whose `location` is that cell, in the order of `Clues`; a third is refused |
   | empty cell | a block with no clue; `null` (ipuz's "no cell") is refused |
   | clue text | `clue`: a raw `<` or `>` (a tag) is refused, then HTML entities are decoded (`&amp;` is `&`) |
   | arrow | derived from `location` and `cells` (rule 8) |
   | answer, breaks | `answer` and `enumeration` (rule 9) |
   | (derived) | `solution`: the letters at the letter cells, the block value elsewhere |

   `puzzle` and, when present, `solution` hold `height` rows of `width` values;
   any other value (a clue number, another text, another object) is refused. A
   clue is an object holding exactly `clue`, `location`, `cells` (one or more
   cells) and `answer`, and optionally `enumeration`. FX-01's clue W5: `{"clue":
   "Flaire", "location": [4, 0], "cells": [[4, 1], [4, 2], [4, 3], [4, 4]],
   "answer": "SENT", "enumeration": "4"}`.
7. Reading is strict, as the standard asks of a reader: any other key without `:`
   at the top level, in `clues` or in a clue is refused (`saved`, `checksum`,
   `styles`, `zones`, `showenumerations`, `Across`, a clue's `number`, another
   `clueplacement`, a clue written as a text or a pair, ...). The descriptive
   ipuz keys `notes`, `intro`, `explanation`, `annotation` and `charset` are
   accepted at the top level and ignored. A key holding `:` (another tool's
   namespace) is ignored wherever it stands.
8. The arrow comes from the clue cell (r, c) and the first cell of `cells`:
   (r, c + 1) starts right, (r + 1, c) starts below; any other first cell is
   refused, naming the clue cell and that cell. With two or more cells, the
   second cell right of the first gives across, below it gives down; any other
   second cell is refused the same way. Right and across is `right`, below and
   down is `down`, below and across is `down_then_right`, right and down is
   `right_then_down`; a one-cell word takes the straight arrow of its first
   cell. `cells` must then be the word rule 3 of `content/grids.md` resolves.
9. A compound word uses ipuz's own means, all agreeing:
   - `enumeration`, when present, is counts of letters joined by `-` (`3-2-5`,
     `5`), each count one or more, their total the answer's letters; its hyphens
     are the clue's breaks. Another separator (a space, `'`, `.`) is refused.
   - `answer` is written with its hyphens (`ARC-EN-CIEL`) or as letters
     (`ARCENCIEL`). Under an enumeration, an answer with hyphens must place
     them exactly where the enumeration does (`VI-DE` under `"4"` is refused),
     and an answer without hyphens takes the enumeration's breaks: the model's
     answer (rule 4 of `content/grids.md`) is then its letters with a hyphen at
     each break (`ARC-EN-CIEL`); otherwise it is the answer as written.
     Without enumeration, the breaks are the answer's hyphens.
   - `dashed`, the drawing of a hyphen edge: a letter cell may be the object
     `{"cell": <empty>, "style": {"dashed": "<letters>"}}`, the letters among
     `T`, `R`, `B`, `L`, each naming the edge of that cell with its top, right,
     bottom or left neighbour (a line may be set from either of its cells). Each
     edge must lie between two letter cells. When any cell carries `dashed`, the
     edges named must be exactly the grid's hyphen edges (`Grid.hyphen_edges`);
     with none, nothing is checked.
10. `difficulty` is the force: a whole number 1 to 4, or the same digit as a text
    (`3` or `"3"`). `date` is the publication date (`published_on`), exactly
    `MM/DD/YYYY` and a real date. `author` is 1 to 200 characters once stripped,
    stored stripped. The three are required; any other value is refused.
11. `title`, `editor`, `publisher`, `publication`, `url`, `uniqueid`, `origin`
    and `copyright` are optional texts, recorded as written with the entry (a
    non-text value is refused). Like the credits (`author`, `source`,
    `licence`), they are never shown to players and never interpreted.
12. The reader builds the model and runs rule 6 of `content/grids.md`, with
    checks added: in its step 1, the form and total of each `enumeration` (the
    model's answer is built from it); after its step 2, every clue's `cells` is
    its resolved word; after its step 8, `solution` agrees with the answers, then
    `answer` and `enumeration` agree on their hyphens, then the `dashed` edges
    are the hyphen edges. The first problem stops the import, naming the clue
    (clue cell and text), the position, or the edge as two `(row, column)`
    cells, the first one first.

### Publication

13. `published: false` hides a grid that was never released. `withdrawn: true`
    marks a grid whose rights ended, applied at the next start: no new room may
    start on it, and it wins over `published: true`. Rooms already open on it
    keep working, since a room holds its own copy of the grid.

### Writer and converter

14. A writer turns a loaded grid file back into ipuz text: the fields of rule 5,
    `puzzle` with `#` and `0`, `solution`, each clue with `clue`, `location`,
    `cells`, `answer` as written and `enumeration`, `difficulty` as a number, the
    fields of rule 11 that are present, and for each hyphen edge `dashed` `R` on
    the letter before an across hyphen, `B` on the letter above a down hyphen.
    Reading what it wrote gives the same grid and fields.
15. `uv run python -m nock.ipuz_convert SOURCE TARGET` converts a directory of
    the former grid files: each file of SOURCE named `<name>.json` (lower-case,
    not starting with `.`), in code-point order of the names, an object of
    `number`, `published_on` (`YYYY-MM-DD`), `force`, `published`, `author`,
    `source`, `licence`, the optional `withdrawn` and `grid` in the model's
    JSON. It writes `TARGET/<name>.ipuz` for each and `TARGET/catalogue.json`
    with the entries in that order. When a source file is refused, or
    `TARGET/catalogue.json` or a `.ipuz` it would write exists (the index is
    checked first), it writes nothing, names that file and exits with a non-zero
    code. Nothing else reads the former format.

## Acceptance criteria

- **AC-1** `grids/` loads by rules 1 and 3: an index listing number 2
  (`b.ipuz`) then number 1 (`a.ipuz`), both FX-01, gives the entries 2 then 1,
  each grid equal to FX-01 in the model's JSON; `notes.txt`, `old/` and an
  `x.ipuz` the index does not name are ignored; a missing directory or a missing
  index is an empty catalogue. (← 004 AC-5)
- **AC-2** An index that breaks rule 2 or 3 is refused, naming `catalogue.json`:
  an extra key `"colour"`, `"published": "yes"`, `"number": "1"`, a `file` of
  `old/a.ipuz`, or two entries with the same number or the same file. An entry
  naming `missing.ipuz`, which does not exist, is refused naming `missing.ipuz`;
  a file whose grid holds `MIMA` is refused naming that file. (← 004 AC-5)
- **AC-3** An entry without `source` or `licence`, or with one blank, over 200
  characters or not text, is refused naming `catalogue.json`; a file without
  `author`, or with it blank or over 200 characters, is refused naming the file.
  `"  Équipe Nock  "` loads as `Équipe Nock`; `"withdrawn": "yes"` is refused.
  (← 005 AC-1, 005 AC-2, 005 AC-3)
- **AC-4** A withdrawn grid is not listed, its grid page and summary answer 404,
  and no new room starts on it, while a published one is served.
  (← 005 AC-6)
- **AC-5** A room opened before its grid was withdrawn keeps working: players
  join it, type every letter and, after a server restart, get it back from the
  store. (← 005 AC-7)
- **AC-6** FX-01 as an ipuz file loads as the FX-01 grid: the same cell at every
  position as FX-01 in the model's JSON, and the eight clues of `_reference.md`
  with their arrows (`Passoire fine` `down_then_right`, `De la marine`
  `right_then_down`, `Flaire` `down`, `Sans contenu` `right`).
- **AC-7** A grid file survives load, write and load with no difference: FX-01's
  ipuz with `"title": "Grille du jour"` and `"publisher": "Le Journal"` gives,
  once written and read again, an equal grid, author, date, force, title and
  publisher. With `VI-DE` across from (2, 1), the written text carries
  `"answer": "VI-DE"`, `"enumeration": "2-2"` and `dashed` `R` on `[2, 2]`, and
  reads back equal.
- **AC-8** A file whose `version` is `http://ipuz.org/v1`, whose `kind` is
  `["http://ipuz.org/crossword#1"]` or holds two kinds, or whose
  `clueplacement` is `"after"`, is refused naming that key.
- **AC-9** FX-01 with `"block": "."` and its puzzle written with `.` loads equal
  to AC-6; `"block": "0"` is refused (it equals `empty`); a `puzzle` value of
  `null`, `1`, `{"cell": 0}` or `{"cell": 0, "style": {"dashed": "R", "color":
  1}}` at (1, 0) is refused naming `(1, 0)`; `"0"` in place of `0` loads equal.
- **AC-10** A `puzzle` whose shape differs from `dimensions` is refused by
  `content/grids.md` AC-5's rule: FX-01 with row 2 cut to four values names
  `(2, 4)` and `missing`; with a sixth value in row 2 names `(2, 5)` and
  `outside`.
- **AC-11** A `location` outside the grid or on a letter cell is refused naming
  the cell as `(row, column)`: `[5, 0]` names `(0, 5)`, `[1, 0]` names `(0, 1)`.
  `[4, 0]` is the clue cell `(0, 4)`, which every message about W5 names.
- **AC-12** A cell's clues come in the order of `Clues`, two at most: FX-01 with
  `De la marine` listed before `Passoire fine` has `De la marine` as the first
  clue of (0, 0); a third clue at `[0, 0]` is refused naming `(0, 0)`.
- **AC-13** W5 (`Flaire`, at `[4, 0]`) with `cells` starting at `[4, 2]` is
  refused naming `(0, 4)` and `(2, 4)`; with `cells` `[[4, 1], [3, 2], ...]`
  it is refused naming `(0, 4)` and `(2, 3)`; with `cells` `[[5, 0]]` its arrow
  is `right` and the error is `content/grids.md` AC-6's, naming `(0, 4)` and
  `(0, 5)`. A one-cell word right of its clue cell gets the arrow `right`.
- **AC-14** A clue whose `cells` is not its resolved word is refused, naming the
  clue: W5 with `cells` cut to `[[4, 1], [4, 2]]` names `(0, 4)` and `Flaire`.
  The check comes right after the arrow check: with `SENT` also changed to
  `SE`, the error is still this one.
- **AC-15** A `solution` that disagrees with the answers is refused after every
  check of rule 6: FX-01's solution with `X` at (1, 4) names `(1, 4)`; a letter
  at (0, 0) names `(0, 0)`. An `enumeration` is counts joined by `-` totalling
  the letters: `"5"` on `TAMIS` loads; `"4"`, `"2 3"`, `"2'3"` and `"5-"` are
  refused naming `(0, 0)` and `Passoire fine`.
- **AC-16** `difficulty` `3` and `"3"` load as force 3; `"Force 3"`, `5`, `"03"`
  and `3.0` are refused. `date` `10/01/2026` loads as `published_on`
  `2026-10-01`, kept `YYYY-MM-DD` in the summary; `2026-10-01`, `1/1/2026` and
  `02/30/2026` are refused. (← 004 AC-7)
- **AC-17** The fields of rule 11 are recorded as written and reach no player:
  `"title": "Grille du jour"`, `"url": "https://example.org/g/1"` and
  `"uniqueid": "lj-2026-001"` are those values on the entry, an absent one is
  `None`, `"title": 7` is refused, and the summary of `GET /api/grids/<n>`
  holds none of them.
- **AC-18** A key the reader does not support is refused naming it, a namespace
  key is ignored: FX-01 with `"saved": []`, `"styles": {}` or `"rating": 3` at
  the top level, `clues` holding `"Across": []`, or W5 holding `"number": 5` is
  refused; with `"notes": "x"` or `"com.example:rating": 3` at the top level,
  or `"com.example:x": 1` on W5, it loads equal to AC-6.
- **AC-19** A clue text is plain: `Fatales &amp; César` loads as
  `Fatales & César`; `<b>Flaire</b>` is refused naming `(0, 4)`.
- **AC-20** The converter of rule 15, run on a directory holding `g1.json`
  (former format, FX-01, number 1, `2026-10-01`, force 2, the credits), writes
  `g1.ipuz` and `catalogue.json` into the target, which then loads as one entry
  with number 1, force 2, `published_on` `2026-10-01`, the same credits and a
  grid equal to FX-01; run again on the same target it writes nothing, names
  `catalogue.json` and exits with a non-zero code.
- **AC-21** A compound word follows rule 9, on FX-01 with `VI-DE` across from
  (2, 1) (clue `Sans contenu` at (2, 0)): `"answer": "VIDE"` with
  `"enumeration": "2-2"` loads with the answer `VI-DE`, a break after 2, as
  does `"answer": "VI-DE"` with no enumeration; `dashed` `R` at `[2, 2]` (or
  `L` at `[3, 2]`) agrees; `dashed` `R` at `[3, 2]` is refused naming `(2, 3)`,
  `(2, 4)`; `"answer": "VID-E"` with `"2-2"`, or `"answer": "VI-DE"` with
  `"enumeration": "4"`, is refused naming `(2, 0)` and `Sans contenu`; with
  `NA-VAL` down from (0, 1) as well and only `R` at
  `[2, 2]`, the file is refused naming `(1, 1)`, `(2, 1)`.

## Edge cases

- `licence` is required; `license` is an unknown key (AC-2, AC-3).
- Credits keep accents, apostrophes, `n°` and line breaks; the 200 limit counts
  code points (AC-3).
- A withdrawn grid already open in a browser can still be joined by its room
  link (AC-5).
- A block with no clue is the model's empty cell; FX-01 has none (AC-6, AC-9).
- `&lt;b&gt;` decodes to the literal text `<b>` and is kept (AC-19).
- No grid today has a one-cell word; the writer never has to write one (AC-13).
- `cells` shorter or longer than the run is refused by AC-14: the word is the
  whole run (rule 3 of `content/grids.md`).
- `Clues:Définitions` is a key holding `:`, so it is ignored and `Clues` is
  missing (AC-18).
- A `dashed` letter naming an edge outside the grid or beside a block is
  refused naming that edge; `""` or a letter other than T, R, B, L is refused as
  a value (AC-9, AC-21).
- An enumeration without hyphen leaves the answer as written (`ÊTRE` with `"4"`
  stays `ÊTRE`) (AC-21).

## Out of scope

- The grid model, the stored rooms, the protocol and the browser, which are
  unchanged by the file format; the summary keeps `force` and `published_on`
  (`content/library.md`).
- Showing credits or any field of rule 11 to players.
- Reading another ipuz kind, a clue number, a cell style other than `dashed`,
  or a saved state.
- Enumeration separators other than `-` (a space, `'`, `.`): `content/grids.md`
  gives breaks to hyphens only, so they are refused for now.
- Reloading grids, converting files or withdrawing a grid without a restart;
  closing rooms already open on a withdrawn grid.
- Deleting stored rooms or history of a withdrawn grid: `admin/operations.md`.
- Where real grids come from and their licences: an owner decision.

## Code

- `src/nock/catalogue.py`: the index, the catalogue, `load_catalogue`,
  `find_published`.
- `src/nock/ipuz.py`: the reader and the writer.
- `src/nock/ipuz_convert.py`: the converter.
- Tests: `tests/test_grid_files_*`, the grid-file tests of `test_spec_004_*`,
  and the credit and withdrawal tests of `test_spec_005_*`.
