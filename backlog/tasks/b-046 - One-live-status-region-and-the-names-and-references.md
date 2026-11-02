---
id: B-046
title: One live status region, and the names and references
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T02:55:00Z'
labels:
  - domain:hud
  - domain:realtime
  - domain:room
  - domain:results
  - domain:rules
  - domain:rooms
  - domain:joining
  - domain:chat
milestone: m-1
dependencies: []
documentation:
  - specs/client/hud.md
  - specs/platform/realtime.md
  - specs/client/room.md
  - specs/gameplay/results.md
priority: medium
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Priority: seventh of B-039's items (screen readers)
- Domains: client/hud (one status region for the room page), with the rules
  that call a message a status (`platform/realtime.md` rule 20 for the
  band, `client/room.md` for the notes, `gameplay/results.md` for the
  recap); the spec-writer finds them
- Architecture decision: no
- Problem: the connection band, the grid status, the undo note, the Joueurs
  status and the recap status are live regions created with their text
  already in them (`RoomPage.svelte:2131`, `:2304`, `RoomNote.svelte:75`,
  `PlayersPanel.svelte:155`, `RecapDialog.svelte:220`); screen readers often
  stay silent for a region that is created full (B-039 M9, plausible). The
  vote banner does it right (`RoomPage.svelte:2173`). The catalogue's
  « Jouer » buttons cannot be told apart, `aria-controls="reaction-picker"`
  points to an element that exists only while open, and the nickname field
  is `aria-invalid` with no `aria-describedby` (L22).
- In scope: one persistent, visually hidden `role="status"` region in the
  room page and an `announce(text)` passed down; the visible elements lose
  their role; « Jouer » described by its card's title; the references set
  only while their target exists.
- Out of scope: the vote banner's region (already right); the alerts of the
  forms.
- Screens: none.
- Open questions: none.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 hud AC-26 (new)
- [x] #2 hud AC-27 (new)
- [x] #3 room AC-8 (new)
- [x] #4 rooms AC-18 (new)
- [x] #5 rooms AC-9 (changed)
- [x] #6 realtime AC-18 (changed)
- [x] #7 rules AC-3 (changed)
- [x] #8 rules AC-7 (changed)
- [x] #9 rules AC-10 (changed)
- [x] #10 results AC-10 (changed)
- [x] #11 results AC-13 (changed)
- [x] #12 joining AC-4 (changed)
- [x] #13 chat AC-11 (changed)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Spec: specs/client/hud.md, with the status rules of specs/platform/realtime.md, specs/client/room.md, specs/gameplay/results.md
Tests: tests/test_hud_*.py and the tests of realtime, room and results for the changed criteria
Quick gate: uv run python scripts/gate.py --specs hud,realtime,room,results --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decisions (2026-11-02):
- Each rule goes in the domain that owns the element: « Jouer » and the Joueurs copied line in lobby/rooms, the nickname field in lobby/joining, « Réagir » in social/chat, the grid status in gameplay/rules. Labels domain:rules, rooms, joining, chat added; no clash with the tasks In Progress.
- One status region in the page, plus one in each open room sheet (option B of the spec-writer): a sheet opened with showModal() makes the page inert, so the recap's lines and the band would go unheard behind a sheet. Same result for players as the pitch intends, only heard.
- The grid status is announced when it appears or its text changes (also on a first snapshot already solved), not when it moves between the clue bar's row and the band.
- A repeated message is announced again: the region is emptied, then written.
- Criteria count over budget in results, joining, chat, hud: splits left out of this task.

Review round 1: APPROVE. Lead took the three small, certain suggestions: the nickname helper also checks aria-describedby is absent (test-writer, ef3b98b); RoomSheet.open() releases a previous writer first, and the grid status text has one source (implementer, 78e9c98). The quick gate passed after them; no second round, since the verdict was already APPROVE.
- Accepted: announce() is a module-level stack (web/src/lib/announce.ts) rather than a prop passed down; same behaviour for players, and it lets a sheet take over the messages cleanly.
- Follow-ups for the next board branch (drafts, label follow-up): (1) a status region keeps its last text for good (« Connexion perdue… » after reconnecting, « Chargement du bilan… » after the recap loads, or written after it if the fetch answers within 50 ms): empty a region a few seconds after it is written; (2) add « status region » to the glossary of specs/_map.md and mention it in the hud row.

Full gate (chromium): 8598 passed, 1 failed in the parallel run (test_shell_remote_updates.py::test_ac25_after_the_pinch..., a fixed-wait pinch test of B-043, unrelated), 162 passed serial. The failing test passed alone and 3 of 3 in its file: flaky under load; follow-up draft for the next board branch.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
One persistent, visually hidden role="status" region in the room page, and one in each open room sheet (the page behind a modal is inert), take the room's messages through announce(text); the visible elements lose their live role. « Jouer » is described by its card's title; aria-controls on « Réagir » and aria-describedby/aria-invalid on the nickname field are set only while their target exists.

Criteria and tests:
- hud AC-26, AC-27 (new): tests/test_hud_status_region.py
- room AC-8 (new): tests/test_room_undo_announcement.py
- rooms AC-18 (new): tests/test_rooms_play_button_description.py
- rooms AC-9 (changed, ← 011 AC-1): tests/test_spec_011_ac01_room_creation.py
- realtime AC-18 (changed, ← 017 AC-1): tests/test_spec_017_ac01_connection_loss.py
- rules AC-3, AC-7, AC-10 (changed, ← 026): tests/test_spec_026_ac01_ac03_grid_solved.py, test_spec_026_ac06_ac07_grid_full_wrong.py, test_spec_026_ac10_status_layout.py
- results AC-10, AC-13 (changed, ← 028/047): tests/test_spec_047_ac10_ac11_share_and_states.py, test_spec_047_ac10_copied_line.py
- joining AC-4 (changed, ← 012/046): tests/test_spec_012_ac01_nickname_rule.py, test_spec_046_ac15_ac17_entry_cards.py
- chat AC-11 (changed, ← 022 AC-5): tests/test_spec_022_ac03_ac05_reactions.py

Spec-checker: CHANGES REQUESTED (grid status announce on join and silent on a move had no criterion; nickname references not proven removed; page region after a sheet closes), then APPROVED.
Reviewer: APPROVE in round one; its three small suggestions were taken (stricter aria-describedby check, a sheet releases its writer before reopening, one source for the grid status text).

Decisions: each rule in the domain that owns the element (labels rules, rooms, joining, chat added); one region per open sheet besides the page's; the grid status is announced when it appears or its text changes, also on a first snapshot, never on a move; a repeat is announced again (region emptied, then written 50 ms later); announce() is a module-level stack instead of a prop passed down.

Flagged: not tried with a real screen reader (MutationObserver tests only); regions keep their last text (follow-up); « status region » not yet in the glossary (follow-up); a flaky pinch test of B-043 failed once in the full gate and passed on rerun (follow-up).
<!-- SECTION:FINAL_SUMMARY:END -->
