---
id: B-066
title: 'Two server slips: MAX_PLAYERS and one QUIT'
status: Done
assignee: []
created_date: '2026-11-03T16:02:00Z'
updated_date: '2026-11-03T17:26:00Z'
labels:
  - domain:rooms
  - domain:account
milestone: m-4
dependencies: []
documentation:
  - specs/lobby/rooms.md
  - specs/account/account.md
priority: medium
ordinal: 54000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-027 and DRAFT-028 (B-028's review). RoomState.players and Snapshot.players hold max_length=8 where MAX_PLAYERS is meant (src/nock/room.py:290, src/nock/protocol.py:739). SmtpMailer._send calls quit() inside 'with connection:', whose exit sends QUIT again (src/nock/mailer.py:99); smtplib swallows the error. Out of scope: the mailer's thread pool (DRAFT-030).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The player limit of a room's state and of a snapshot is MAX_PLAYERS, one constant
- [x] #2 A mail send sends QUIT once
- [x] #3 rooms AC-19 (new)
- [x] #4 account AC-9 (changed)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
- [x] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Spec: lobby/rooms.md (player limit) and account/account.md (mailer) only if a rule or criterion needs it; else code-only with tests.
2. Tests: tests/test_rooms_*.py, tests/test_account_*.py (new criteria if any).
3. Quick gate: uv run python scripts/gate.py --specs rooms,account --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: limit stays 8; QUIT criterion tested with a stub of smtplib.SMTP (a fake server sees one QUIT either way); a failed send also ends with one QUIT through the with-block, no extra criterion; joining.md's statement of the limit left as is.

Review round 1: APPROVE. Suggestion 1 (mailer docstring still naming quit()) taken; suggestion 2 (index % 8 colour count in the AC-19 test helper) not taken: harmless, a test helper's own palette size.

PR #120.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
MAX_PLAYERS is defined once (src/nock/protocol.py) and feeds RoomState and Snapshot; the mailer lets its with-block send the one QUIT.

Criteria and their tests:
- rooms AC-19 (new): tests/test_rooms_max_players.py (a guard: it passes with the old code too, the limit being 8 either way).
- account AC-9 (changed, ← 033 AC-7): tests/test_spec_033_ac07_mailer.py, the smtplib stub now records the with-block's QUIT; one QUIT and nothing after it, on success and on a failed send (7 tests failed before the fix).

Spec-checker: APPROVED in round 2 (a test-mechanics parenthesis, line wraps). Reviewer: APPROVE in round 1; the mailer docstring suggestion taken, the test helper's colour count not. Full gate: passed (8711 parallel, 162 serial).
Decisions: the limit stays 8; QUIT tested with a stub, a fake server seeing one QUIT either way; a failed send ends with one QUIT through the with-block; joining.md's statement of the limit left as is.
<!-- SECTION:FINAL_SUMMARY:END -->
