---
area: content
file: grid-files
status: approved
---

# content/grid-files - Grid files: the index, credits, withdrawal, the converter

## Purpose

An operator adds a grid by dropping a standard ipuz ArrowWord file in `grids/` and
naming it in the index, with its number, rights and publication state. Any ipuz
tool can open and save the grid file without losing anything of it; what Nock
decides about a grid stays in the index. Both are read once at server start.

## Depends on

- `content/grids.md`: the model, rule 6's import checks, positions written
  `(row, column)`.
- `content/ipuz.md`: the file format and its reader; the converter of rule 15
  uses its writer.
- `_reference.md`: the FX-01 grid used in the examples.

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
   breaks these rules, those of `content/ipuz.md` or the import checks, stops
   the server from starting with one error naming the file concerned:
   `catalogue.json` for an index problem,
   the `.ipuz` file otherwise (a missing one included).
4. What Nock decides about a grid (its number, whether it is published or
   withdrawn, its source and licence) is in the index. What describes the grid
   as published (its cells, clues, answers, author, date, difficulty and
   descriptive fields) is in the `.ipuz` file (`content/ipuz.md`), in standard
   ipuz fields only. The catalogue entry joins the two.

### Recorded fields

11. `title`, `editor`, `publisher`, `publication`, `url`, `uniqueid`, `origin`
    and `copyright` are optional texts, recorded as written with the entry (a
    non-text value is refused). Like the credits (`author`, `source`,
    `licence`), they are never shown to players and never interpreted.

### Publication

13. `published: false` hides a grid that was never released. `withdrawn: true`
    marks a grid whose rights ended, applied at the next start: no new room may
    start on it, and it wins over `published: true`. Rooms already open on it
    keep working, since a room holds its own copy of the grid.

### Converter

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
  `author`, or with it blank or over 200 characters, is refused naming the file
  (`content/ipuz.md` rule 6). `"  Équipe Nock  "` loads as `Équipe Nock`;
  `"withdrawn": "yes"` is refused.
  (← 005 AC-1, 005 AC-2, 005 AC-3)
- **AC-4** A withdrawn grid is not listed, its grid page and summary answer 404,
  and no new room starts on it, while a published one is served.
  (← 005 AC-6)
- **AC-5** A room opened before its grid was withdrawn keeps working: players
  join it, type every letter and, after a server restart, get it back from the
  store. (← 005 AC-7)
- **AC-17** The fields of rule 11 are recorded as written and reach no player:
  `"title": "Grille du jour"`, `"url": "https://example.org/g/1"` and
  `"uniqueid": "lj-2026-001"` are those values on the entry, an absent one is
  `None`, `"title": 7` is refused, and the summary of `GET /api/grids/<n>`
  holds none of them.
- **AC-20** The converter of rule 15, run on a directory holding `g1.json`
  (former format, FX-01, number 1, `2026-10-01`, force 2, the credits), writes
  `g1.ipuz` and `catalogue.json` into the target, which then loads as one entry
  with number 1, force 2, `published_on` `2026-10-01`, the same credits and a
  grid equal to FX-01; run again on the same target it writes nothing, names
  `catalogue.json` and exits with a non-zero code.

## Edge cases

- `licence` is required; `license` is an unknown key (AC-2, AC-3).
- Credits keep accents, apostrophes, `n°` and line breaks; the 200 limit counts
  code points (AC-3).
- A withdrawn grid already open in a browser can still be joined by its room
  link (AC-5).

## Out of scope

- The `.ipuz` file format, what its reader refuses and what its writer
  produces: `content/ipuz.md`.
- Showing credits or any field of rule 11 to players.
- Reloading grids, converting files or withdrawing a grid without a restart;
  closing rooms already open on a withdrawn grid.
- Deleting stored rooms or history of a withdrawn grid: `admin/operations.md`.
- Where real grids come from and their licences: an owner decision.

## Code

- `src/nock/catalogue.py`: the index, the catalogue, `load_catalogue`,
  `find_published`.
- `src/nock/ipuz_convert.py`: the converter.
- Tests: `tests/test_grid_files_*`, the catalogue tests of `test_spec_004_*`,
  and the credit and withdrawal tests of `test_spec_005_*`.
