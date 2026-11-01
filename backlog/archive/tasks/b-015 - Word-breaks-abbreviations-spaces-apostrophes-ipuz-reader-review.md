---
id: B-015
title: 'Word breaks: abbreviations, spaces, apostrophes; ipuz reader review'
status: Done
assignee: []
created_date: '2026-11-01T16:43:00Z'
labels:
  - domain:grids
  - domain:grid-files
  - domain:board
  - domain:realtime
dependencies: []
ordinal: 25000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human answered the brief and approved the spec change,
  2026-10-27; review approved in round 1, its suggestions checked in round 2)
- Domains: content/grids, content/grid-files; gameplay/board (one Out of
  scope line); `_design/cells.md` « Hyphen edges » and the captions of the
  cell sheet's « 4b » and the screens sheet's compound words (text only, no
  change of look). `platform/realtime.md` rule 23 and `gameplay/board.md`
  rule 20 already speak of a word's break and its marks, so they stay.
- Architecture decision: yes (the stored grid's answers and the grid file
  format; options from the Plan agent on Fable)
- Criteria: grids AC-3, AC-20, AC-21 (changed); grid-files AC-7, AC-15,
  AC-18, AC-21 (changed); board: no criterion (one Out of scope line)
- Branch: feat/b-015-abbreviations · PR: none yet
- Problem: the human asked: "Review the ipuz parser, and include abreviation
  support. Abreviations should visually behave like compound words. They will
  use "." i the "enumeration" field to separate letters. A.I will have AI as
  answer, Artificial Intelligence as clue for example." Today an enumeration
  holding `.` is refused, and so is an answer holding one.
- Review of the reader (`src/nock/ipuz.py` against ipuz v2.0.2):
  - Accepted: the v2 ArrowWord kind only, `clueplacement` `blocks`, clues
    under `clues.Clues` as objects of `clue`, `location`, `cells`, `answer`
    and an optional `enumeration`; `puzzle` values `block`, `empty`, or a
    letter cell with the `dashed` style; `solution` of letters A to Z and the
    block; `notes`, `intro`, `explanation`, `annotation`, `charset` ignored;
    namespace keys (`x:y`) ignored; clue text plain, entities decoded.
  - Refused by design (strict reader, rule 7): `saved`, `checksum`,
    `styles`, `zones`, `Across`, a clue as a text or a pair, a clue's
    `number`, `label`, `hints`, `image`, `continued`, `references`, named
    styles, `barred`, null cells.
  - Gaps found:
    1. Enumeration separators: only `-`. ipuz also writes ` ` (words), `.`
       (an abbreviation's period, after its count: `A.M.` is `1.1.`), `'`,
       `,` and `;`. **The human's three Le Parisien sample files are all
       refused today** for this: `I A` under `"1 1"` (INTELLIGENCE
       ARTIFICIELLE), `RC` `"1 1"`, `ESE` and `DCA` `"1 1 1"`, `ENAVANT`
       `"2 5"`.
    2. An answer holding `.` (`A.I`) is refused by the model (rule 4 of
       `content/grids.md` removes only spaces, hyphens and apostrophes).
    3. `showenumerations` (a core crossword key tools write) is refused.
    4. `dotted` is refused, though ipuz draws dotted with dashed as dashed.
    5. `solution` must hold Nock's normalised letters: `É` or a lower-case
       letter there is refused (ipuz's solution is case-sensitive).
    6. A key written twice in one object silently keeps its last value.
    7. A file starting with a UTF-8 byte order mark (some Windows tools
       write one) is refused as "not valid JSON".
    8. A clue's descriptive `explanation`, `tags` or `type` is refused.
  - This item fixes 1 (`.`, ` ` and `'`, each a break with the dashed
    edge), 2 and 3. Gaps 4 to 8 go to « Small follow-ups » (none hits a file
    the human has today).
- Options (Plan agent on Fable):
  - **A (picked): the separators stay in the answer as written.** Rule 4
    gains `.`: the letters drop it as they drop `-`, ` ` and `'`. The answer
    as written keeps each separator's kind (`A.I.` stays `A.I.`), so the
    model needs no new field; `Clue.breaks` and the edges keep their shape.
    Stored rooms: same shape. Protocol: unchanged, the same `hyphen_right` /
    `hyphen_down` marks, now set for every break. No client change.
  - B: breaks get a kind in the model and in the snapshot's marks, ready for
    kinds that look different one day. Adds the protocol, the room, the
    client and their criteria, for no visible difference. Set aside: the kind
    can reach the mark the day a kind looks different, since A keeps it in
    the answer.
  - C: the reader turns `.` into `-`. The writer then writes `1-1` for
    `1.1.`, so a grid no longer survives the round trip as written. Set
    aside.
- Answers (the human, 2026-10-27): "Update my spec and support
  abbreviations, apostrophes in the most ipuz fashion. Include support for
  proper "." abbreviations and simple space " ". A.I. or "A I" "A.I" on top
  of current "-"". Then: "do not do A.I. (last dot). Support answer A but
  with space, dot, hyphen". The lead reads them as option A, with every separator
  between two letters, hyphen, dot, space or apostrophe, a break drawn as the
  compound word's dashed edge (so `A I`, `A.I` and `A-I` look the same, and
  so do `EN AVANT` and `AUJOURD'HUI`), and no trailing dot.
- The model (`content/grids.md` rule 4):
  - The separators are `-`, `.`, ` ` and `'` (`’` is read as `'`). The
    letters drop them all. A break is exactly one separator between two
    letters, counted as the letters before it: `A.I`, `A I` and `A-I` give
    the letters `AI` and a break after 1; `AUJOURD'HUI` a break after 7;
    `ARC-EN CIEL` after 3 and 5.
  - A separator at the start or the end, or two in a row, is refused,
    naming the answer: `A.I.`, `.AI`, `A..I`, `A.-I`, `A  I`, `DR. NO`,
    `-ARC`, `ARC- EN`.
  - Step 8 of rule 6: two words sharing an edge agree on its break, not on
    its kind (both draw the same dashes).
  - Rooms stored since B-012 keep their answers as written, so one holding
    `AUJOURD'HUI` now draws its edge; rooms stored before hold letters only
    and draw none, as today.
- The file (`content/grid-files.md` rules 7, 9, 12, 14), as ipuz writes an
  enumeration:
  - Enumeration: counts of one or more joined by single `-`, `.`, ` ` or
    `'`: `1.1`, `1 1`, `1-1`, `7'3`, `3-2-5`, `1.1-3` load. A trailing `.`
    (ipuz's `1.1.`, `5 1.1.`), two separators in a row (`2. 2`), `,`, `;`,
    `0` (unknown length), `*`, `^`, `+` and `=` are refused.
  - Answer: written with the enumeration's separators (`A.I` under `1.1`,
    `A I` under `1 1`), or as letters only (`AI`), which takes the
    enumeration's separators: `AI` under `1.1` is the model's `A.I`.
    Separators that differ from the enumeration's, kind included, are
    refused naming the clue (`A I` or `A-I` under `1.1`). Without
    enumeration the answer's own separators rule, as today.
  - `dashed` names every break edge, whatever its separator, with today's
    check.
  - Writer: `answer` as written and the enumeration derived from it, so
    `A.I` writes `1.1`, `A I` `1 1`, `A-I` `1-1`, and each reads back
    equal.
  - `showenumerations` (a boolean) is accepted and ignored.
- In scope: rule 4 and step 8 of `content/grids.md`; rules 7, 9, 12, 14 of
  `content/grid-files.md`; one sentence in `_design/cells.md` « Hyphen
  edges » saying every break is drawn so. Criteria changed in place where
  they can: grids AC-3 (`AUJOURD'HUI` gets its break), AC-20; grid-files
  AC-7, AC-15 (`"2 3"` and `"2'3"` load), AC-18, AC-21. No new criterion in
  `content/grid-files.md`, already over its size budget.
- Out of scope: a mark of its own per separator (option B); showing the
  enumeration in the clue bar; the reader's gaps 4 to 8 (« Small
  follow-ups »); rewriting the Le Parisien files (they load once this is
  built: `I A` under `1 1` draws the dashed edge).
- Screens: none redrawn. Every break is drawn as B-012's dashed edge (look
  E′), whose drawing does not change; « Hyphen edges » and the cell sheet's
  « 4b · Compound words » caption name the other separators.
- Open questions: none left. To overrule if the lead misread: a space and an
  apostrophe draw the dashed edge too, not only the dot; the apostrophe stays
  in (asked in the first answer, not named in the second).
<!-- SECTION:DESCRIPTION:END -->
