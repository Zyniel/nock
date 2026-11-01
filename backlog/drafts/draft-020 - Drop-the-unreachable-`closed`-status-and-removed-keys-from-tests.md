---
id: DRAFT-020
title: Drop the unreachable `closed` status and removed keys from tests
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - follow-up
  - domain:realtime
  - domain:shell
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The room page's `closed` status can no longer be reached (a socket lost is `reconnecting` or `connecting`, `platform/realtime.md`), yet `room.status.closed` (« Connexion perdue. ») is still a required key of 040 AC-22's test: drop the key and that test entry (`client/shell.md`). Likewise 046 AC-23's test still checks that `my_rooms.loading`, `my_rooms.empty` and `account-link` are absent, and 043 AC-31's that 043's removed keys are: history no spec states; drop those entries once the numbered specs are archived.
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
