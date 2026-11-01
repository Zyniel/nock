---
id: DRAFT-015
title: 'Spec 029''s leftovers from PR #26'
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Spec 029, left for the human in PR #26: a history save that read the room before an account's erasure and writes after it keeps the nickname (very unlikely); the delete hook writes SQLite under the registry lock; two erased team-mates of one record show as one `--`; the room page asks its summary once and does not retry; `peek_room` re-reads the log of a room solved before spec 029 at each call.
<!-- SECTION:DESCRIPTION:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or assigned to @zyniel
<!-- DOD:END -->
