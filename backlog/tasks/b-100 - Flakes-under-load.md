---
id: B-100
title: Flakes under load
status: To Do
assignee: []
created_date: '2026-11-05T01:54:00Z'
labels:
  - tooling
milestone: m-9
dependencies: []
priority: low
ordinal: 88000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-024, 032, 053 and 018, and B-079's gate (webkit test_server_offline_undo AC-29, firefox test_spec_033_ac09 at 320x568): find each cause; a wait for the right state, SERIAL_TEST_FILES, or a page-ready wait in the harness; check hud AC-20 in WebKit on CI's run after a merge.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each listed flake has a found cause and a fix, or is recorded with why it stays, and the full gate passes twice in a row in three engines
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
