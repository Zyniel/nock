---
id: B-078
title: Erasure's criteria live beside their rules
status: To Do
assignee: []
created_date: '2026-11-04T01:17:00Z'
labels:
  - domain:account
  - domain:erasure
milestone: m-6
dependencies: []
documentation:
  - specs/account/account.md
  - specs/account/erasure.md
priority: low
ordinal: 66000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-055, option B (the lead's pick, delegated by the human 2026-11-04). account AC-2 (the purge of links and sessions), AC-10 (SHA-256 storage, no secrets in logs) and AC-13 (an anonymous player stored as a nickname, no cookie) prove erasure.md rules 3 and 4. Move the three criteria to erasure.md (next free numbers there; pointers move as they are; the domain tests renamed and moved), so account gets lighter (past the size budget) and each criterion sits beside its rule. No behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The three criteria are in erasure.md beside rules 3 and 4, their tests renamed and passing, and account.md no longer holds them
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
