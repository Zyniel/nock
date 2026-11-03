---
id: DRAFT-016
title: Tests for the catalogue rules the code already keeps
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - follow-up
  - domain:library
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rules stated but untested (the code does them; a test would catch a regression): the catalogue asks once and refuses items that are not summaries; the force filter makes no new request; the grid page's loading line and its non-summary answer; after a chip, only that chip pressed (`content/library.md` rules 8, 10, 16 and AC-6).
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
