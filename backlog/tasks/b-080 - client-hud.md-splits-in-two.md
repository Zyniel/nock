---
id: B-080
title: client/hud.md splits in two
status: Done
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T15:17:00Z'
labels:
  - domain:hud
milestone: m-7
dependencies: []
documentation:
  - specs/client/hud.md
priority: medium
ordinal: 68000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-058. hud is 22.4 KB with 22 criteria. Move one part, its criteria as they are, to a new domain spec; the Plan agent proposes the cut. Out of scope: any behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 hud.md is under about 15 KB and 20 criteria, the part moved with its criteria and pointers, _map.md updated, the gate's traceability green
- [x] #2 menus AC-1 to AC-9 (moved from hud AC-6 to AC-10, AC-15, AC-23 to AC-25)
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
1. Plan agent (Fable, high) proposes the cut; the lead picks.
2. spec-writer moves the part to the new domain spec, _map.md follows; spec-checker.
3. Tests: rename or move the domain tests of moved criteria (after B-003 merges, which edits many test files).
4. No code change; reviewer; full gate; pull request.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decision (Plan agent on Fable, three cuts): Cut 1, client/menus.md takes hud rules 8-13 (Aide menu, Menu, switches and items, the popover rule, the room sheets) as rules 1-6 and AC-6 to AC-10, AC-15, AC-23 to AC-25 as AC-1 to AC-9. hud goes to about 14.1 KB and 13 criteria, menus about 9.6 KB and 9. Not taken: status (23 test functions move, hud stays at the edge) and layout (the top bar is what hud means). Cost: tests/test_hud_overlay_focus.py becomes tests/test_menus_overlay_focus.py (8 functions renumbered), the sheet helpers of hud_harness.py go to menus_harness.py, and scripts/gate.py SHARED_COMPONENT_DOMAINS follows (the lead, as a coherence fix of the tooling).

Spec-checker round 1: CHANGES REQUESTED (room.md and hud.md Depends on still gave hud the scrim). Fixed. Lead decision: client/room.md keeps four Depends on files (hud, menus, chat, presence) against the template's three: its agents need menus for the sheet's closing rules and each of the others for a tab or the layout; no other spec is over.

Spec-checker round 2: APPROVED. hud 14.5 KB and 13 criteria, menus 9.5 KB and 9.

Review round 1: APPROVE. Not taken: the harness docstrings' stale claim that votes AC-9 uses the sheet helpers (there before this task) and claude_docs/frontend-review.md's citations (a dated review record that no role edits).

Full gate here: Chromium static checks and 8,774 parallel tests green. Two timing tests failed: foundation remote pace AC-13 (2.03 ms against a 2 ms limit) and spec 036 AC-1 (2,623 ms against 2,500 ms). The pace test fails the same way in B-081, which changes no client code, so this container is too slow for them; CI's Ubuntu run decides. Firefox ran past its 45-minute limit on this four-core container, and WebKit hit the known Clock.pause_at flake (B-100). The moved menus tests pass in Firefox and WebKit (20 passed). The Firefox and WebKit runs on main after the merge cover the rest.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
client/hud.md splits in two: the new client/menus.md takes the room menu, its sheets and overlay focus (hud rules 8-13 as menus rules 1-6; hud AC-6..10, AC-15, AC-23..25 as menus AC-1..9). hud.md is 14.5 KB with 13 criteria, menus.md 9.5 KB with 9. tests/test_hud_overlay_focus.py becomes tests/test_menus_overlay_focus.py with tests/menus_harness.py; _map.md, room.md Depends on, gate.py's shared components and two code comments follow.
<!-- SECTION:FINAL_SUMMARY:END -->
