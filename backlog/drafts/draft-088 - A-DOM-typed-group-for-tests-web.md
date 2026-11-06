---
id: DRAFT-088
title: A DOM-typed group for tests/web
status: Draft
assignee: []
created_date: '2026-11-06T13:46:00Z'
labels:
  - follow-up
  - tooling
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From B-099's review: tests/web/scrollingLists.test.ts and pinchPan.test.ts add /// <reference lib="dom" />, which types every unit test of tests/web with the DOM (window or document then pass the type check and fail only at run time). A separate tsconfig group for DOM tests would keep the pure-module boundary. Tooling: the human's call if it changes the tsconfig files' behaviour.
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
