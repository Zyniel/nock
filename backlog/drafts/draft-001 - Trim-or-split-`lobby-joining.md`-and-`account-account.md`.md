---
id: DRAFT-001
title: Trim or split `lobby/joining.md` and `account/account.md`
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-01T20:21:00Z'
labels:
  - follow-up
  - domain:joining
  - domain:account
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`lobby/joining.md` (23 criteria after B-041) and `account/account.md` (about 31 KB, 33 criteria after B-040) are over the size guideline: trim them or split each, an architecture decision. For account, the B-040 spec-writer proposes moving the erasure (rules 18 to 23 and 26 to 28: erasure, the « -- » name, purge, history records; AC-3, AC-14, AC-15, AC-22, AC-24 to AC-30) into `account/erasure.md`, with its row in `specs/_map.md`.
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
