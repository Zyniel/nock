---
id: DRAFT-078
title: Rename library_harness.py to cards_harness.py
status: Draft
assignee: []
created_date: '2026-11-05T22:33:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From m-7's close review and B-087: tests/library_harness.py now holds the helpers of content/cards' tests; library's filter test only takes QUIET_MS from it. Move QUIET_MS to a shared harness and rename the file cards_harness.py (the conftest registration and role_gate.py's harness-to-domain map follow). For m-9.
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
