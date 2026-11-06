---
id: B-090
title: One helper for refused characters, MAX_PLAYERS named where it lives
status: Done
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-06T16:57:00Z'
labels:
  - domain:chat
  - domain:serving
  - domain:rooms
milestone: m-10
dependencies: []
documentation:
  - specs/social/chat.md
  - specs/platform/serving.md
  - specs/lobby/rooms.md
priority: low
ordinal: 78000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-067 and DRAFT-069. No behaviour change: one helper holds the refused Unicode categories with the allowed extras as a parameter; rooms.md's Code section names protocol.py for MAX_PLAYERS and its comment points at rooms rule 7.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Chat and NOCK_DATABASE use one helper and their tests pass unchanged; rooms.md names MAX_PLAYERS in protocol.py
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
Spec: lobby/rooms.md Code section (MAX_PLAYERS in protocol.py); chat.md and serving.md Code sections if the helper moves
Tests: unchanged (chat and NOCK_DATABASE tests pass as they are)
Quick gate: uv run python scripts/gate.py --specs chat,serving,rooms --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Spec-checker: APPROVED (Code sections only). Lead's decision: no new test (the criterion asks that the existing chat and NOCK_DATABASE tests pass unchanged), so no test-writer phase; the helper is is_refused_character(character, allowed) in src/nock/protocol.py.

Reviewer round 1: APPROVE (behaviour identical for chat and NOCK_DATABASE; no test changed). Not taken (style, no follow-up): the unused default of allowed, the wording of the comment above JOINERS.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Milestone m-10 « Client and server cleanups ». No behaviour change.

- **AC #1** (chat and NOCK_DATABASE use one helper, their tests pass unchanged; rooms.md names MAX_PLAYERS in protocol.py): `src/nock/protocol.py` holds `is_refused_character(character, allowed)` and one `REFUSED_CATEGORIES` (Cc, Cf, Zl, Zp). Chat passes LF, the two joiners and the 96 tag characters; the `NOCK_DATABASE` check in `src/nock/__main__.py` passes the joiners. The two copies and their constants are gone. `MAX_PLAYERS`'s comment points at rooms rule 7. No test changed; the chat (022) and NOCK_DATABASE (036 AC-10–12) tests pass.
- **Spec**: Code sections of lobby/rooms.md, social/chat.md and platform/serving.md (spec-checker APPROVED).
- **Reviewer**: APPROVE, round 1 (behaviour identical). Not taken: the unused default of `allowed`, a comment's wording.
- **Decisions**: no test-writer phase (the criterion asks the existing tests to pass unchanged).
- **Gate**: the full gate in Chromium passed.
<!-- SECTION:FINAL_SUMMARY:END -->
