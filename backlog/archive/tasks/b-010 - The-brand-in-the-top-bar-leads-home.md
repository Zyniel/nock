---
id: B-010
title: The brand in the top bar leads home
status: Done
assignee: []
created_date: '2026-11-01T16:43:00Z'
labels:
  - domain:shell
  - domain:hud
  - domain:library
dependencies: []
ordinal: 20000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human approved option A and the spec change,
  2026-10-25; review approved in round 1)
- Domains: client/shell, client/hud, content/library
- Architecture decision: no (one new `fr.json` key; no protocol, data or
  module interface)
- Criteria: shell AC-10, AC-11 (changed); hud AC-2, AC-20 (changed); library
  AC-12 (changed), AC-19, AC-20 (new)
- Branch: feat/b-010-brand-home-link · PR: #49 (merged)
- Problem: the human asked: "On all displays extended displays, in the top
  bar, the Polygon + "Nock" should he a link back to the home page, grid
  selection." Today the brand (the Nock mark and « Nock », `TopBarBrand`) is
  plain text on every top bar that has it.
- In scope: the brand becomes a link to `/` (the catalogue, « Grilles ») on
  every top bar that shows it: the catalogue (there too, with
  `aria-current="page"`; activating it loads the catalogue again) and the grid
  page, the entry frame (nickname card, status cards, page not found), the
  shared recap, account and operator pages, and the room's computer top bar.
  Its name is a new key `topbar.home`, « Accueil ». From a room it does what
  the Menu's « Retour aux grilles » does: no question, the page loads `/`, the
  player is disconnected and keeps the seat, to resume from « Mes salons »
  within the resume window (`lobby/joining.md`). While the room opens its top
  bar is inert (`client/shell.md` rule 7), the brand with it. The room's Tab
  order on the computer top bar starts with the brand.
- Out of scope: the room's phone top bar, and so the low column layout, stay
  without the brand: there the Menu's « Retour aux grilles » is the way home.
  A question before leaving a room; any change to the Menu; client-side
  routing.
- Screens: every top bar that shows the brand (`_design/room.md` « Computer
  top bar »; `_design/pages.md` « Catalogue », « Entry and not-found pages »,
  « Plain pages »; a « Brand link » row in `_design/foundation.md`
  « Components »), redrawn in the screens sheet with the hover and focus
  states. Option A, picked by the human: the brand keeps its place and look at
  rest; on hover it takes a word-blue background, radius 6 px, as a top-bar
  button does (padding drawn inside a negative margin, so nothing moves);
  focused, the ring of « Components ». Set aside: B, the Nock mark alone on
  the phone top bar (more buttons there, and the Menu already leads home); C,
  the mark at every phone width under the 40 px floor (breaks too much).
- Open questions: none left.
<!-- SECTION:DESCRIPTION:END -->
