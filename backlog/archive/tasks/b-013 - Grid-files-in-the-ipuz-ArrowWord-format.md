---
id: B-013
title: Grid files in the ipuz ArrowWord format
status: Done
assignee: []
created_date: '2026-11-01T16:43:00Z'
labels:
  - domain:grid-files
  - domain:grids
  - domain:library
dependencies: []
ordinal: 23000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human picked option D and named the ipuz fields the
  grids will carry, then approved the spec change with compound words in
  ipuz's own notation, 2026-10-26; review approved in round 1, its
  suggestions checked in round 2)
- Domains: content/grid-files (new, split from content/grids, which keeps
  the model and the import checks), content/grids, content/library (pointers
  only); `specs/_map.md` (table and glossary)
- Architecture decision: yes (the grid file format; options from the Plan
  agent on Fable, two independent passes)
- Criteria: grid-files AC-1 to AC-21 (new domain; AC-1 to AC-5 take grids
  AC-13 to AC-17 and their pointers); grids AC-1, AC-4, AC-5, AC-6, AC-18,
  AC-19 (changed), AC-13 to AC-17 (deleted, moved); library rule 1 (changed,
  no criterion)
- Branch: feat/b-013-ipuz-grids · PR: none yet
- Problem: the human asked: "Replace grid custom grid definition format by the
  standard "ipuz" Arrowword standard. This format is documented at
  https://www.puzzazz.com/ipuz. Shifting to a open-source standard will help
  using of external tooling, and libraries to possbly interact with the grid
  definitions." Today a grid file is Nock's own JSON (rule 9 of
  `content/grids.md`), which no other tool reads.
- What ipuz gives: ipuz v2 (`"version": "http://ipuz.org/v2"`) has a kind
  ArrowWord, `"kind": ["http://ipuz.org/crossword/arrowword#1"]`, with
  `"clueplacement": "blocks"`, one clue list `clues.Clues` and a clue
  `location` `[col, row]`. It has no arrow names, no rule for two clues in one
  cell, and no field for Nock's own decisions (number, published, withdrawn,
  licence). Tools seldom support ArrowWord, and none is known to keep keys it
  does not know when it saves a file, so anything Nock-only written into an
  `.ipuz` file must be assumed lost after an outside edit (the Plan agent's
  reading, not checked against the tools).
- Options:
  - **D (the human's pick): pure ipuz for the grid, Nock's decisions in an
    index.** Each `.ipuz` file uses standard ipuz fields only, no extension
    key, so an outside tool can open and save it without losing anything.
    `grids/catalogue.json` holds what Nock decides about each grid. The grid
    model, the stored rooms, the protocol and the browser do not change. No
    new dependency.
  - Set aside: A, Nock's data in namespaced extension keys of the `.ipuz`
    file (an outside edit can drop `withdrawn` or the licence without a
    word); B, both formats for a time; C, ipuz as import and export only
    (both keep two formats); ipuz as the stored model too (a migration of the
    rooms' snapshots and a client move to `[col, row]`, for no gain).
- Answers (the human, 2026-10-26): option D. Most grids will come from
  external sites, so these ipuz fields will be filled: `publisher`,
  `publication`, `url`, `uniqueid`, `title`, `author`, `editor`, `date`,
  `difficulty` (the equivalent of force), `origin`, `block`, `empty`.
- What lives where (the lead's split, from that answer): what describes the
  grid as published is in the `.ipuz` file, in its standard fields, since
  tools keep those; what Nock decides is in the index.

  | Today's key | Where it lives |
  | --- | --- |
  | `number`, `published`, `withdrawn` (optional, false), `source`, `licence` | the index entry, with `file` (the `.ipuz` name); strict as rule 9 is today |
  | `force` | ipuz `difficulty`, required, 1 to 4 (a number or the same digit as text, as ipuz allows); any other text is refused |
  | `published_on` | ipuz `date`, required, exactly `MM/DD/YYYY`, a real date |
  | `author` | ipuz `author`, required, 1 to 200 characters once stripped |
  | (new) | ipuz `title`, `editor`, `publisher`, `publication`, `url`, `uniqueid`, `origin`, `copyright`: optional text, recorded as written with the entry, never shown to players and never interpreted, like the credits; written back by the writer |

- Grid mapping. Positions stay `(row, column)` in the model and in every
  error; the reader turns ipuz's `[col, row]` into `(row, column)` before any
  message (a message may quote the value as written: `location [4, 0], that
  is (0, 4)`). Coordinates count from zero, as the standard's examples do.

  | Today | ipuz |
  | --- | --- |
  | the file | `version` `http://ipuz.org/v2`, `kind` exactly `["http://ipuz.org/crossword/arrowword#1"]`, `"clueplacement": "blocks"`, clues under `clues.Clues` |
  | `width`, `height` | `dimensions` |
  | letter cell | the file's `empty` value in `puzzle` (ipuz's default `0`; `0` and `"0"` are the same) |
  | clue cell | the file's `block` value (default `"#"`) with one or two clues whose `location` is that cell, in the cell's order; a third is refused |
  | empty cell | a block with no clue (`null`, ipuz's "no cell", is refused) |
  | clue text | `clue` (plain text; HTML entities decoded, a tag refused) |
  | arrow | derived from `location` and the word's `cells` (required): first cell to the right or below, word across or down, gives the four arrows; a one-letter word gets the straight arrow (no grid today has one) |
  | answer | `answer`, as written (B-012: `ARC-EN-CIEL`) |
  | (new) | `solution` (the letters and the block) and `enumeration` (`"3-2-5"`), written by the writer, checked against the answers when present |

  `block` and `empty` must differ. Source of truth: `puzzle` and each clue's
  `location`, `cells` and `answer`. `cells` must be the word that rule 3
  resolves (this check gives AC-6's error); `solution` and `enumeration`,
  when present, must agree with the answers. Reading is strict: an unknown
  core key, or an ipuz feature Nock does not support (`saved`, `checksum`,
  `styles`, `zones`, `Across`, a cell written as an object or a clue number,
  another `clueplacement`, ...), is refused, as the standard asks of a
  reader; ipuz's remaining descriptive keys (`notes`, `intro`,
  `explanation`, `annotation`, `charset`) are accepted and ignored; keys of
  another tool's namespace (`x:y`) are ignored. In the index, an unknown key
  is refused, as today.
- Files: the index names each grid's file; grids are read in the index's
  order (rule 8 today: file-name order); an entry naming a missing file, or
  two entries naming the same file or number, stops the start; a `.ipuz` file
  the index does not name is ignored; no index is an empty catalogue.
- Converter: a writer of the same module turns a catalogue entry back into
  ipuz, for the tests and for a one-shot converter of today's `.json` files
  into `.ipuz` files and index entries, run as a module of the package
  (`uv run python -m nock....`), so no new script in `scripts/`.
- How B-012 fits: B-012 (PR #52, merged) went first; its
  model is unchanged here (the answer as written, `Clue.letters`,
  `Clue.breaks`, `Grid.hyphen_edges`). The human asked (2026-10-26) that a
  compound word use the ipuz format itself, so the file writes it with ipuz's
  own means, all three agreeing: `enumeration` (`"3-2-5"`, ipuz's notation
  for a hyphenated answer), `answer` with or without its hyphens, and the
  `dashed` bar style on the letter before each hyphen (`R` across, `B` down),
  which is the dashed edge B-012 draws. Breaks are the enumeration's hyphens
  when it has one, else the answer's; `dashed`, when a file has any, must
  name exactly the grid's hyphen edges. A space or an apostrophe in an
  enumeration is refused for now (B-012 gives breaks to hyphens only).
- In scope: rules 8 to 12 of `content/grids.md` (the index, the `.ipuz`
  files, the split above, the mapping, the arrow rule, the new checks); the
  criteria that name the file (AC-1, AC-4 as load, write, load equal, AC-5,
  AC-6, AC-13 to AC-15) reworded; new criteria for the version and kind,
  `block` and `empty`, the `puzzle` values, the clues and their locations, a
  clue cell's order and a third clue, `cells`, `solution` and `enumeration`
  disagreeing, `difficulty` and `date`, the recorded descriptive fields,
  `[col, row]` written `(row, column)`, unknown core and foreign-namespace
  keys, the index, and the converter. `tests/fixtures/fx01.ipuz` and
  `fx02.ipuz` added; `fx01.json` and `fx02.json` stay, as the model's own JSON
  (rooms store it). The README's grid-files section follows. If
  `content/grids.md` nears 15 KB, the file rules move to a new
  `content/grid-files.md`.
- Out of scope: the grid model, the stored rooms, the protocol and the browser
  (unchanged); the library (summaries unchanged: `force` and `published_on`
  keep their names there); showing any of the descriptive fields; reading
  other ipuz kinds; a grid editor; converting
  files automatically at start.
- Screens: none.
- Open questions: none left. The lead's picks, to overrule if needed: force
  read from `difficulty` and `published_on` from `date` (one truth each, in
  the file a tool keeps); `difficulty` only 1 to 4, so an importer writes
  `3`, not `Force 3`; `author` moves to the `.ipuz` file while `source` and
  `licence` stay in the index; one index rather than a side file per grid.
<!-- SECTION:DESCRIPTION:END -->
