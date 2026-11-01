---
id: B-003
title: Compact the tests
status: To Do
assignee: []
created_date: '2026-11-01T16:43:00Z'
labels: []
milestone: m-2
dependencies: []
priority: low
ordinal: 13000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Who decides: the human delayed the decision.
- Domains: none (tests only)
- Waits for: B-001
- Problem: 4.9 MB of tests for 875 KB of code; helpers are copied from file to
  file (`dist_dir` in 72 files, `catalogue` in 82) and near-copies of one test
  stand where a parameter would do.
- In scope: shared fixtures and harnesses; parametrized tests in place of
  copies; the same criteria proven, no weaker check.
- Out of scope: the code; what the tests prove.
- Screens: none.
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
