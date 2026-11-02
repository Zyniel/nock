---
area: content
file: ipuz
status: done
---

# content/ipuz - The ipuz file: format, reader, writer

## Purpose

A grid file is a standard ipuz ArrowWord file, so any ipuz tool can open and save
it without losing anything of it. This domain says how the file maps to the grid
model, what the reader refuses, and how the writer turns a grid back into ipuz
text.

## Depends on

- `content/grids.md`: the model, rule 6's import checks, positions written
  `(row, column)`.
- `content/grid-files.md`: where the files live and the index that names them
  (rules 1 to 4), the recorded fields of rule 11.
- `_reference.md`: the FX-01 grid used in the examples.

## Rules

### The ipuz file

1. A `.ipuz` file is a JSON object (UTF-8) of the ipuz v2 ArrowWord kind. It
   holds `version` exactly `http://ipuz.org/v2`, `kind` exactly
   `["http://ipuz.org/crossword/arrowword#1"]`, `clueplacement` exactly
   `"blocks"`, `dimensions` (`width`, `height`), `puzzle`, `clues` holding
   exactly the key `Clues`, `author`, `date` and `difficulty`; optionally `block`,
   `empty`, `solution` and the fields of `content/grid-files.md` rule 11. Every
   coordinate in the file is `[column, row]`, counted from zero; Nock turns it
   into `(row, column)` before any message, which may also quote the value as
   written (`location [4, 0], that is (0, 4)`).
2. The mapping to the model:

   | Model | ipuz |
   | --- | --- |
   | width, height | `dimensions` |
   | letter cell | the `empty` value in `puzzle` (default `0`; `0` and `"0"` are the same value), or the object `{"cell": <empty>, "style": {"dashed": "<letters>"}}` with no other key (rule 5) |
   | clue cell | the `block` value (default `"#"`, a text, different from `empty`) with one or two clues whose `location` is that cell, in the order of `Clues`; a third is refused |
   | empty cell | a block with no clue; `null` (ipuz's "no cell") is refused |
   | clue text | `clue`: a raw `<` or `>` (a tag) is refused, then HTML entities are decoded (`&amp;` is `&`) |
   | arrow | derived from `location` and `cells` (rule 4) |
   | answer, breaks | `answer` and `enumeration` (rule 5) |
   | (derived) | `solution`: the letters at the letter cells, the block value elsewhere |

   `puzzle` and, when present, `solution` hold `height` rows of `width` values;
   any other value (a clue number, another text, another object) is refused. A
   clue is an object holding exactly `clue`, `location`, `cells` (one or more
   cells) and `answer`, and optionally `enumeration`. FX-01's clue W5: `{"clue":
   "Flaire", "location": [4, 0], "cells": [[4, 1], [4, 2], [4, 3], [4, 4]],
   "answer": "SENT", "enumeration": "4"}`.
3. Reading is strict, as the standard asks of a reader: any other key without `:`
   at the top level, in `clues` or in a clue is refused (`saved`, `checksum`,
   `styles`, `zones`, `Across`, a clue's `number`, another `clueplacement`, a
   clue written as a text or a pair, ...). The ipuz keys `notes`, `intro`,
   `explanation`, `annotation`, `charset` and `showenumerations` are accepted
   at the top level and ignored. A key holding `:` (another tool's namespace)
   is ignored wherever it stands.
4. The arrow comes from the clue cell (r, c) and the first cell of `cells`:
   (r, c + 1) starts right, (r + 1, c) starts below; any other first cell is
   refused, naming the clue cell and that cell. With two or more cells, the
   second cell right of the first gives across, below it gives down; any other
   second cell is refused the same way. Right and across is `right`, below and
   down is `down`, below and across is `down_then_right`, right and down is
   `right_then_down`; a one-cell word takes the straight arrow of its first
   cell. `cells` must then be the word rule 3 of `content/grids.md` resolves.
5. A word's breaks use ipuz's own means, all agreeing:
   - `enumeration`, when present, is counts of letters, each one or more, joined
     by single separators of rule 4 of `content/grids.md` (`-`, `.`, ` `, `'`):
     `5`, `3-2-5`, `1.1`, `1 1`, `7'3`, `1.1-3`. Their total is the answer's
     letters and each separator is a break. Any other text is refused: `5-`,
     `.5`, `1.1.`, `2  3`, `2,3`, `0`.
   - `answer` is written with its separators (`ARC-EN-CIEL`, `A.I`) or as
     letters (`ARCENCIEL`, `AI`). Under an enumeration, an answer holding a
     separator must hold exactly the enumeration's, at the same places and of
     the same kinds (`VI-DE` under `"4"`, `A I` or `A-I` under `"1.1"` are
     refused); an answer of letters only takes them: the model's answer (rule 4
     of `content/grids.md`) is then its letters written with the enumeration's
     separators (`AI` under `"1.1"` is `A.I`); otherwise it is the answer as
     written. Without enumeration, the answer's own separators give the breaks.
   - `dashed`, the drawing of a break: a letter cell may be the object
     `{"cell": <empty>, "style": {"dashed": "<letters>"}}`, the letters among
     `T`, `R`, `B`, `L`, each naming the edge of that cell with its top, right,
     bottom or left neighbour (a line may be set from either of its cells). Each
     edge must lie between two letter cells. When any cell carries `dashed`, the
     edges named must be exactly the edges of the grid's breaks
     (`Grid.hyphen_edges`), whatever their separators; with none, nothing is
     checked.
6. `difficulty` is the force: a whole number 1 to 4, or the same digit as a text
   (`3` or `"3"`). `date` is the publication date (`published_on`), exactly
   `MM/DD/YYYY` and a real date. `author` is 1 to 200 characters once stripped,
   stored stripped. The three are required; any other value is refused.

### The reader's added checks

7. The reader builds the model and runs rule 6 of `content/grids.md`, with
   checks added: in its step 1, the form and total of each `enumeration` (the
   model's answer is built from it); after its step 2, every clue's `cells` is
   its resolved word; after its step 8, `solution` agrees with the answers, then
   `answer` and `enumeration` agree on their separators, then the `dashed`
   edges are the edges of the breaks. The first problem stops the import,
   naming the clue (clue cell and text), the position, or the edge as two
   `(row, column)` cells, the first one first.

### The writer

8. A writer turns a loaded grid file back into ipuz text: the fields of rule 1,
   `puzzle` with `#` and `0`, `solution`, each clue with `clue`, `location`,
   `cells`, `answer` as written and `enumeration` derived from it (its counts
   of letters joined by its separators, `’` written `'`: `A.I` gives `1.1`,
   `A I` `1 1`), `difficulty` as a number, the fields of `content/grid-files.md`
   rule 11 that are present, and for each break `dashed` `R` on the letter
   before an across break, `B` on the letter above a down break. Reading what it
   wrote gives the same grid and fields.

## Acceptance criteria

- **AC-1** FX-01 as an ipuz file loads as the FX-01 grid: the same cell at every
  position as FX-01 in the model's JSON, and the eight clues of `_reference.md`
  with their arrows (`Passoire fine` `down_then_right`, `De la marine`
  `right_then_down`, `Flaire` `down`, `Sans contenu` `right`).
- **AC-2** A grid file survives load, write and load with no difference: FX-01's
  ipuz with `"title": "Grille du jour"` and `"publisher": "Le Journal"` gives,
  once written and read again, an equal grid, author, date, force, title and
  publisher. With `VI-DE` across from (2, 1), the written text carries
  `"answer": "VI-DE"`, `"enumeration": "2-2"` and `dashed` `R` on `[2, 2]`, and
  reads back equal; written `VI.DE` it carries `"enumeration": "2.2"`, written
  `VI DE` `"2 2"`, and each reads back as written.
- **AC-3** A file whose `version` is `http://ipuz.org/v1`, whose `kind` is
  `["http://ipuz.org/crossword#1"]` or holds two kinds, or whose
  `clueplacement` is `"after"`, is refused naming that key.
- **AC-4** FX-01 with `"block": "."` and its puzzle written with `.` loads equal
  to AC-1; `"block": "0"` is refused (it equals `empty`); a `puzzle` value of
  `null`, `1`, `{"cell": 0}` or `{"cell": 0, "style": {"dashed": "R", "color":
  1}}` at (1, 0) is refused naming `(1, 0)`; `"0"` in place of `0` loads equal.
- **AC-5** A `puzzle` whose shape differs from `dimensions` is refused by
  `content/grids.md` AC-5's rule: FX-01 with row 2 cut to four values names
  `(2, 4)` and `missing`; with a sixth value in row 2 names `(2, 5)` and
  `outside`.
- **AC-6** A `location` outside the grid or on a letter cell is refused naming
  the cell as `(row, column)`: `[5, 0]` names `(0, 5)`, `[1, 0]` names `(0, 1)`.
  `[4, 0]` is the clue cell `(0, 4)`, which every message about W5 names.
- **AC-7** A cell's clues come in the order of `Clues`, two at most: FX-01 with
  `De la marine` listed before `Passoire fine` has `De la marine` as the first
  clue of (0, 0); a third clue at `[0, 0]` is refused naming `(0, 0)`.
- **AC-8** W5 (`Flaire`, at `[4, 0]`) with `cells` starting at `[4, 2]` is
  refused naming `(0, 4)` and `(2, 4)`; with `cells` `[[4, 1], [3, 2], ...]`
  it is refused naming `(0, 4)` and `(2, 3)`; with `cells` `[[5, 0]]` its arrow
  is `right` and the error is `content/grids.md` AC-6's, naming `(0, 4)` and
  `(0, 5)`. A one-cell word right of its clue cell gets the arrow `right`.
- **AC-9** A clue whose `cells` is not its resolved word is refused, naming the
  clue: W5 with `cells` cut to `[[4, 1], [4, 2]]` names `(0, 4)` and `Flaire`.
  The check comes right after the arrow check: with `SENT` also changed to
  `SE`, the error is still this one.
- **AC-10** A `solution` that disagrees with the answers is refused after every
  check of `content/grids.md` rule 6: FX-01's solution with `X` at (1, 4) names
  `(1, 4)`; a letter at (0, 0) names `(0, 0)`. An `enumeration` follows rule 5:
  `"5"` on `TAMIS` loads; `"2 3"` loads with the answer `TA MIS` and a break
  after 2, `"2'3"` with `TA'MIS`; `"4"`, `"5-"`, `"5."`, `"2  3"` and `"2,3"`
  are refused naming `(0, 0)` and `Passoire fine`.
- **AC-11** `difficulty` `3` and `"3"` load as force 3; `"Force 3"`, `5`, `"03"`
  and `3.0` are refused. `date` `10/01/2026` loads as `published_on`
  `2026-10-01`, kept `YYYY-MM-DD` in the summary; `2026-10-01`, `1/1/2026` and
  `02/30/2026` are refused. (← 004 AC-7)
- **AC-12** A key the reader does not support is refused naming it, a namespace
  key is ignored: FX-01 with `"saved": []`, `"styles": {}` or `"rating": 3` at
  the top level, `clues` holding `"Across": []`, or W5 holding `"number": 5` is
  refused; with `"notes": "x"`, `"showenumerations": true` or
  `"com.example:rating": 3` at the top level, or `"com.example:x": 1` on W5,
  it loads equal to AC-1.
- **AC-13** A clue text is plain: `Fatales &amp; César` loads as
  `Fatales & César`; `<b>Flaire</b>` is refused naming `(0, 4)`.
- **AC-14** A word's breaks follow rule 5, on FX-01 with `VI-DE` across from
  (2, 1) (clue `Sans contenu` at (2, 0)): `"answer": "VIDE"` with
  `"enumeration": "2-2"` loads with the answer `VI-DE`, a break after 2, as
  does `"answer": "VI-DE"` with no enumeration; `"VIDE"` with `"2.2"` loads
  with the answer `VI.DE` and the same break; `dashed` `R` at `[2, 2]` (or `L`
  at `[3, 2]`) agrees, with `VI-DE` as with `VI.DE`; `dashed` `R` at `[3, 2]`
  is refused naming `(2, 3)`, `(2, 4)`; `"answer": "VID-E"` with `"2-2"`,
  `"VI-DE"` with `"4"`, or `"VI DE"` with `"2.2"`, is refused naming `(2, 0)`
  and `Sans contenu`; with `NA-VAL` down from (0, 1) as well and only `R` at
  `[2, 2]`, the file is refused naming `(1, 1)`, `(2, 1)`.

## Edge cases

- A block with no clue is the model's empty cell; FX-01 has none (AC-1, AC-4).
- `&lt;b&gt;` decodes to the literal text `<b>` and is kept (AC-13).
- No grid today has a one-cell word; the writer never has to write one (AC-8).
- `cells` shorter or longer than the run is refused by AC-9: the word is the
  whole run (rule 3 of `content/grids.md`).
- `Clues:Définitions` is a key holding `:`, so it is ignored and `Clues` is
  missing (AC-12).
- A `dashed` letter naming an edge outside the grid or beside a block is
  refused naming that edge; `""` or a letter other than T, R, B, L is refused as
  a value (AC-4, AC-14).
- An enumeration without separator leaves the answer as written (`ÊTRE` with
  `"4"` stays `ÊTRE`) (AC-14).

## Out of scope

- The grid model, the stored rooms, the protocol and the browser, which are
  unchanged by the file format; the summary keeps `force` and `published_on`
  (`content/library.md`).
- The index, credits, withdrawal and the converter: `content/grid-files.md`.
- Reading another ipuz kind, a clue number, a cell style other than `dashed`,
  or a saved state.
- ipuz's other enumeration marks (`,`, `;`, a trailing `.`, `0` for an unknown
  length): refused by rule 5. Showing an enumeration to players.

## Code

- `src/nock/ipuz.py`: the reader and the writer.
- Tests: `tests/test_ipuz_*`, and the date test of `test_spec_004_*`.
