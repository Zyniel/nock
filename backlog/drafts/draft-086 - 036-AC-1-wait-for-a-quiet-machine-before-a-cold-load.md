---
id: DRAFT-086
title: '036 AC-1: wait for a quiet machine before a cold load'
status: Draft
assignee: []
created_date: '2026-11-06T13:46:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From B-100: a test-side calibration wait (a short busy loop run until it takes close to its idle time) before each cold load of spec 036 AC-1, budgets unchanged. B-107's load wait before the serial pass may already be enough: check its results first.
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
