---
id: DRAFT-055
title: Account criteria that prove erasure rules
status: Draft
assignee: []
created_date: '2026-11-02T11:05:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up of B-062 (spec-checker note, reviewer suggestion). After the split, account AC-2 (the purge of links and sessions at 1,801 s and 7,776,001 s), AC-10 (SHA-256 storage, no secrets in logs) and AC-13 (an anonymous player stored as a nickname, no cookie) prove behaviour whose rules are now account/erasure.md rules 3 and 4, and account's Depends on (three files, the template's maximum) cannot list erasure. Options: A move erasure rules 3 and 4 back to account (they are about what account stores, not the erasure); B move the three criteria to erasure; C leave it, the out-of-scope line links them. Lead's lean: A, after B-064.
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
