---
id: B-012
title: 'Compound words: a dashed line where the hyphen falls'
status: Done
assignee: []
created_date: '2026-11-01T16:43:00Z'
labels:
  - domain:grids
  - domain:realtime
  - domain:board
dependencies: []
ordinal: 22000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human approved look E′ and the spec change, 2026-10-25;
  model option A, the lead's pick; review approved in round 1)
- Domains: content/grids, platform/realtime, gameplay/board
- Architecture decision: yes (grid file, stored grid and the snapshot's grid;
  options from the Plan agent on Fable)
- Criteria: grids AC-3 (changed), AC-20, AC-21 (new); realtime AC-20 (new);
  board AC-21, AC-22 (new)
- Branch: feat/b-012-compound-words · PR: none yet
- Problem: the human asked: "Grid should support "compound word". A compound
  word is represented on the grid with a special representation. Instead of
  standard cell design, the compound word "-" will be represented by a dotted
  line in between the cells instead of a plain line. Propose design options for
  all selection scenarios (selected, no players selecting)". Today rule 4 of
  `content/grids.md` drops the hyphen (`ARC-EN-CIEL` gives `ARCENCIEL`) and
  nothing of it reaches the grid.
- In scope: a hyphen takes no cell, as in printed grids: the edge between the
  two letters it joins is drawn dashed instead of the plain grid line (across:
  the right edge of the letter before it; down: its bottom edge). Typing,
  navigation, word length, check and reveal do not change (they work on
  cells). The model, the new import checks, the snapshot's hyphen marks, and
  the look of the dashed edge in every state.
- Out of scope: marks for spaces and apostrophes (`AUJOURD'HUI` stays as
  today; the model leaves room to add them later); showing the hyphen in the
  clue bar or a word's length pattern; the catalogue's generic grid drawing;
  any change to typing, navigation, check or reveal.
- Model, option A (picked): the hyphen stays in the answer. The file keeps
  writing `"answer": "ARC-EN-CIEL"`: no new key, rule 9 and existing files
  unchanged. The model keeps the answer as written and derives its letters
  (`ARCENCIEL`, today's normalised answer, which the import checks and the
  room's solution read) and its breaks (after letters 3 and 5). New checks
  when the file parses: a hyphen sits between two letters (`-ARC`, `ARC-`,
  `ARC--EN`, `ARC- EN` refused, naming the answer); new last step of rule 6:
  two words sharing an edge (a short word inside a longer run) agree on its
  hyphen, naming both answers and the edge. The snapshot's letter cells get
  two booleans, `hyphen_right` and `hyphen_down` (false by default); realtime
  rule 23 says the grid holds hyphen marks, which name an edge and never a
  letter. Rooms stored before the change hold normalised answers: they load
  and draw no dashed edge. FX-01 and FX-02 stay; criteria use FX-01 variants
  (`VI-DE`, `NA-VAL`). Set aside: B, explicit `"breaks"` per clue (authors
  count letters, a hyphen left in the answer is silently dropped); C, edge
  flags on letter cells in the file (nothing ties a flag to its word).
- Screens: grid cells (`_design/cells.md` « Grid lines and empty cells »,
  « Drawing order », each mark's least size; `cell-sheet.html` by hand; a new
  token in `_design/foundation.md`), then the room in the screens sheet,
  phone and computer. Look E′ (picked by the human, drawn on the throwaway
  comparison page): the plain line of that edge goes; in its place dashes in
  a grey of their own, a new token `--nock-hyphen` (#5E6573, darker than the
  grid lines), the same in every state (no one selecting the word, mine,
  another player's tint, mine and another's, a crossing word selected,
  locked, revealed, checked wrong, catch-up ring, flash, Auteurs mode, pencil
  letters):
  - a whole number of dashes per edge, at least 3, a period of about 5 px per
    pixel of thickness, 60 % dash, half a gap at each end so the corners stay
    open and the edge never merges into the crossing lines; dash ends on
    whole pixels, so fractional cell sizes and pinch zoom never blur them;
  - thickness 1 px under 36 px cells, 2 px from 36 px, 3 px from 72 px: 3
    dashes of about 3 px at 18 px cells (a 320 by 568 phone), about 7 of 5 px
    at a computer's 56 px, 8 of about 7 px at zoom 5 (90 px);
  - contrast 4.26:1 on my selected cell to 5.86:1 on white, 3:1 or more on
    every word, tint and locked background; 2.93:1 on the darkest flash,
    accepted for its 1 s;
  - my selected cell beside the edge: its navy border turns dashed on that
    side, with the same dashes (navy on selected 9.65:1), so the hyphen never
    hides under the border;
  - the triangles, icons, catch-up ring, notch and arrows stay as they are;
    no arrow ever sits on a hyphen edge (an arrow's edge faces its clue
    cell); the revealed notch lies over the dashes of a down hyphen.

  Set aside: ink dots (A, A′), a dotted rule-grey line (B), dots that follow
  the word's state (C), short ink dashes (D), the first E in rule grey (1.27
  to 2.54:1, hidden under my selection border, blurred at fractional sizes).
- Open questions: none left.
<!-- SECTION:DESCRIPTION:END -->
