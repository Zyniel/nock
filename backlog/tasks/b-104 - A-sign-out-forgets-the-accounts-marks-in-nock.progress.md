---
id: B-104
title: A sign-out forgets the account's marks in nock.progress
status: In Progress
assignee: []
created_date: '2026-11-05T01:54:00Z'
updated_date: '2026-11-06T15:49:00Z'
labels:
  - domain:my-account
  - domain:cards
milestone: m-10
dependencies: []
documentation:
  - specs/account/my-account.md
  - specs/content/cards.md
priority: medium
ordinal: 92000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-042. B-040 makes a sign-out or deletion forget the identities, room records and history records the account brought to the device; nock.progress keeps the marks those rooms set, so the next person on a shared device sees the account's grids marked in the catalogue. The device must know which marks came from the account's rooms. Runs after the account split (B-084). Out of scope: marks set while signed out.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 After a sign-out or a deletion, the catalogue shows none of the account's grids as started or finished, and the marks set while signed out stay
- [ ] #2 cards AC-10 (new)
- [ ] #3 cards AC-11 (new)
- [ ] #4 cards AC-12 (new)
- [ ] #5 cards AC-13 (new)
- [ ] #6 my-account AC-9 (new)
- [ ] #7 rooms AC-5 (changed)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Architecture (stored data, nock.progress): options by the Plan agent, then spec-writer on account/my-account.md and content/cards.md
Tests: tests/test_my_account_*.py, tests/test_cards_*.py
Quick gate: uv run python scripts/gate.py --specs my-account,cards --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
After B-084 and B-087: what a sign-out forgets is account/my-account.md rule 5, and nock.progress is content/cards.md rule 1.

Options (Plan agent): A a per-mark origin inside nock.progress (two value shapes, a rewrite at sign-out); B a second key nock.account_progress, same format, written signed in, removed at the sign-out or deletion (204); C no device mark while signed in (the pill waits for the route); D recompute from room records (not viable: account rooms carry no grid, and the marking rooms are not in nock.account_rooms). Lead's decision: B (no format change to nock.progress, one removeItem, mirrors B-040's nock.account_rooms; the stored-data choice is covered by the bet's risk line). Facts: marks come only from rooms this device created (« Jouer », « Rejouer », a solve); « the account's marks » means marks set while the page is signed in; a tap or solve before the sign-in status answers counts as signed out (the room page waits for its status before marking). Marks written before this change carry no origin and stay through the next sign-out (one-time). lobby/rooms.md rules 2 and 5 get a one-line edit (the device's progress keys), accepted as the third domain file.

Lead's answers to the spec-writer: /g/<n> counts as signed in when its GET /api/account/progress answers 2xx (no extra request, cards AC-8 kept); « started unless finished » checks only the key written (unobservable on the pills); _map.md's glossary and library.md's Code line left as they are (still true).

Spec-checker round 1: CHANGES REQUESTED (AC-12's 401/500 case contradicted its setup; /g/<n> and « Rejouer » had no criterion; the 404/failure edge case unproven; Depends on; _map.md and library.md wording). Noted by the checker, out of this task: a room created with « Jouer » while signed in keeps its identity, nock.history record and « Mes salons » row after the sign-out (follow-up draft).

Lead's decision: library.md's Out of scope pointer (which key « Jouer » writes: cards rule 2) accepted as a one-line fourth file; the account/account.md Depends-on bullet dropped (my-account rule 1 is where the pages ask the status).

Spec-checker round 2: APPROVED.
<!-- SECTION:NOTES:END -->
