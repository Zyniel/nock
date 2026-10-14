# Shared reference for all specs

Not a spec: the quality gate ignores files starting with "_". Specs 002 to 038
point here for the reference grid and the vocabulary. Source: `specs/_archive/complete.md`.

## Reference grid

FX-01 is an original 5×5 grid with 8 words, 18 letter cells and 7 clue cells; the acceptance criteria use it as the golden test case. It covers the four arrow types, a clue cell holding two clues at (0,0), and two letters that belong to one word only (N and T). A script confirmed that every arrow resolves to its answer and that no letter run lacks a clue.

Le Parisien's grids are published editorial content. Treat them as a UX reference and keep them out of the product unless a licence allows it. FX-02, the full-size grid for the layout and performance criteria, is `tests/fixtures/fx02.json` (13 by 17, original, defined in spec 006).

Solved layout, coordinates as (row, column) from zero. Arrows: → right, ↓ down, ↳ down then right, ↴ right then down.

|  | c0 | c1 | c2 | c3 | c4 |
| --- | --- | --- | --- | --- | --- |
| r0 | Passoire fine ↳ / De la marine ↴ | N | Artiste muet ↓ | Fatales à César ↓ | Flaire ↓ |
| r1 | T | A | M | I | S |
| r2 | Sans contenu → | V | I | D | E |
| r3 | Fin de prière → | A | M | E | N |
| r4 | Alourdit le ballon → | L | E | S | T |

| Word | Clue cell | Arrow | First letter | Direction | Clue | Answer |
| --- | --- | --- | --- | --- | --- | --- |
| W1 | (0,0) | down then right | (1,0) | across | Passoire fine | TAMIS |
| W2 | (0,0) | right then down | (0,1) | down | De la marine | NAVAL |
| W3 | (0,2) | down | (1,2) | down | Artiste muet | MIME |
| W4 | (0,3) | down | (1,3) | down | Fatales à César | IDES |
| W5 | (0,4) | down | (1,4) | down | Flaire | SENT |
| W6 | (2,0) | right | (2,1) | across | Sans contenu | VIDE |
| W7 | (3,0) | right | (3,1) | across | Fin de prière | AMEN |
| W8 | (4,0) | right | (4,1) | across | Alourdit le ballon | LEST |

Terms used below: clue cell (case définition), letter cell (case lettre), arrow (flèche), force (difficulty level, commonly 1 to 4).

## Epic map

Six epics make the MVP: a group can open a link, fill one grid together and see it validated. Numeric thresholds in the criteria (300 ms sync, 30-day room life) are proposed defaults to adjust.

| ID | Epic | Outcome | Release | Stories | Depends on | Suggested agent |
| --- | --- | --- | --- | --- | --- | --- |
| E1 | Grid content and model | Grids exist as validated, licensed data with a catalogue | MVP | 4 | None | Domain and content |
| E2 | Solo solving | One player fills a grid comfortably on phone and desktop | MVP | 5 | E1 | Front-end grid |
| E3 | Rooms and presence | Players gather on one grid through a link and see each other | MVP | 4 | E2 | Realtime |
| E4 | Real-time sync | Every player sees the same grid whatever the network does | MVP | 4 | E3 | Realtime |
| E5 | Collaboration aids | Players coordinate without overwriting each other | V1 | 4 | E4 | Front-end grid |
| E6 | Help and validation | Checks and reveals are a group resource | MVP for 6.1 and 6.4, V1 for 6.2 and 6.3 | 4 | E4 | Game rules |
| E7 | Completion and recap | The group sees its time and who solved what | V1 | 3 | E6 | Game rules |
| E8 | Game modes | Groups can race instead of cooperating | Later | 2 | E7 | Game rules |
| E9 | Accounts and resume | A room survives a closed tab and a change of device | V1 | 3 | E3 | Platform |
| E10 | Quality bar | Accessibility, performance, integrity and privacy hold everywhere | MVP | 4 | All | Review and test |

## Spec index

One spec per user story. Each criterion keeps its backlog id in brackets, for
example `**AC-1** (AC-4.2.1)`, so it traces back to `specs/_archive/complete.md`. "Refers to" lists
the specs whose criteria this one mentions.

| Spec | Story | Epic | Release | Criteria | Refers to |
| --- | --- | --- | --- | --- | --- |
| [002](002-grid-schema.md) | US-1.1 Grid schema | E1 | MVP | 5 | - |
| [003](003-grid-import-validation.md) | US-1.2 Grid validation at import | E1 | MVP | 7 | - |
| [004](004-grid-catalogue.md) | US-1.3 Grid catalogue | E1 | MVP | 7 | - |
| [005](005-licensed-content.md) | US-1.4 Licensed content only | E1 | MVP | 7 | 004 |
| [006](006-grid-rendering.md) | US-2.1 Grid rendering | E2 | MVP | 8 | - |
| [007](007-word-selection.md) | US-2.2 Word selection and direction | E2 | MVP | 6 | - |
| [008](008-letter-entry.md) | US-2.3 Letter entry | E2 | MVP | 5 | 016 |
| [009](009-keyboard-navigation.md) | US-2.4 Keyboard and navigation | E2 | MVP | 4 | - |
| [010](010-instant-solo-start.md) | US-2.5 Instant solo start | E2 | MVP | 6 | - |
| [011](011-room-creation.md) | US-3.1 Room creation and invitation | E3 | MVP | 4 | - |
| [012](012-guest-join.md) | US-3.2 Guest join | E3 | MVP | 7 | - |
| [013](013-presence.md) | US-3.3 Presence | E3 | MVP | 8 | 006, 009, 035 |
| [014](014-host-controls.md) | US-3.4 Host controls | E3 | MVP | 10 | 006, 013, 035 |
| [015](015-shared-letters.md) | US-4.1 Shared letters | E4 | MVP | 4 | - |
| [016](016-same-cell-conflicts.md) | US-4.2 Same-cell conflicts | E4 | MVP | 3 | - |
| [017](017-reconnection.md) | US-4.3 Disconnection and reconnection | E4 | MVP | 5 | - |
| [018](018-durable-room-state.md) | US-4.4 Durable room state | E4 | MVP | 4 | - |
| [019](019-authorship-view.md) | US-5.1 Authorship view | E5 | V1 | 3 | 028 |
| [020](020-pencil-letters.md) | US-5.2 Pencil letters | E5 | V1 | 3 | 026 |
| [021](021-clue-flag.md) | US-5.3 Clue flag | E5 | V1 | 3 | - |
| [022](022-chat-reactions.md) | US-5.4 Chat and reactions | E5 | V1 | 4 | - |
| [023](023-check.md) | US-6.1 Check a letter, a word or the grid | E6 | MVP | 10 | 013, 015, 016, 025, 026, 037 |
| [024](024-reveal.md) | US-6.2 Reveal a letter or a word | E6 | V1 | 3 | - |
| [025](025-help-mode-vote.md) | US-6.3 Group decision on help | E6 | V1 | 4 | - |
| [026](026-completion-detection.md) | US-6.4 Completion detection | E6 | MVP | 9 | 015, 018, 023 |
| [027](027-shared-timer.md) | US-7.1 Shared timer | E7 | V1 | 3 | - |
| [028](028-end-of-game-recap.md) | US-7.2 End-of-game recap | E7 | V1 | 4 | - |
| [029](029-game-history.md) | US-7.3 Game history | E7 | V1 | 2 | - |
| [030](030-race-mode.md) | US-8.1 Race | E8 | Later | 4 | - |
| [031](031-team-mode.md) | US-8.2 Teams | E8 | Later | 2 | 030 |
| [032](032-room-resume.md) | US-9.1 Room resume | E9 | V1 | 3 | - |
| [033](033-optional-account.md) | US-9.2 Optional account | E9 | V1 | 3 | - |
| [034](034-catch-up.md) | US-9.3 Catching up after an absence | E9 | V1 | 2 | - |
| [035](035-accessibility.md) | US-10.1 Accessibility | E10 | MVP | 12 | 006, 009, 013, 014, 023, 026, 040 |
| [036](036-performance.md) | US-10.2 Performance | E10 | MVP | 11 | 015, 018, 037 |
| [037](037-integrity.md) | US-10.3 Integrity | E10 | MVP | 4 | - |
| [038](038-privacy-operations.md) | US-10.4 Privacy and operations | E10 | MVP | 4 | 032 |
| [039](039-room-events-protocol.md) | Room events protocol (shared contract, no backlog story) | E3, E4 | MVP | 21 | 002 |
| [040](040-web-client-shell.md) | Web client shell (server, routes, room socket, i18n; no backlog story) | E2, E3 | MVP | 29 | 039 |

## Open decisions

Four choices are settled for the MVP and ticked below. Three remain open: the grid source, competitive play and the Le Parisien baseline.

- [ ] Grid source: commission an author, license from a publisher, or generate and review? It blocks real content in `grids/`, not the code (owner, 2026-10-11; spec 005).
- [x] Same-cell rule: decided, last write wins (AC-4.2.1).
- [x] Room size: decided, 8 players per room (AC-3.2.4).
- [x] Identity: decided, guests only for the MVP. Accounts stay in V1 (US-9.2).
- [ ] Competitive play: is E8 wanted at all?
- [x] Platform: decided, web only and responsive on any device (AC-2.1.5).
- [ ] Le Parisien baseline: confirm it from screenshots of the listing, an open grid and its help menu.
