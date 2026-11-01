---
id: DRAFT-043
title: B-040 small cleanups
status: Draft
assignee: []
created_date: '2026-11-01T20:21:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Reviewer suggestions of B-040 not taken in the task:
- account.md rule 13 says nock.account_rooms is a JSON array of codes and anything else reads as empty; readAccountRoomCodes keeps the string items of a mixed array such as ["RRRRRR", 1]. Pick one reading: the rule says which, or the code follows the strict one.
- forgetAccountSeats rewrites nock.history through readHistory when it removes a record, so malformed records of other rooms are dropped too; filtering the raw stored items would keep them.
- tests/test_account_signout_forgets.py: test_ac33 branches on the action twice (the route and the clicks could be parameters), and stored_json nearly copies stored_history (spec029_harness) and stored_identity (spec033_harness).
Upkeep-sized; none changes what a player sees.
<!-- SECTION:DESCRIPTION:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->
