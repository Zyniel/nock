---
id: DRAFT-091
title: 'CI: a hung WebKit job on main, and a job timeout'
status: Draft
assignee: []
created_date: '2026-11-06T16:20:00Z'
labels:
  - follow-up
  - tooling
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From m-9's close review: the WebKit job of CI run 42224498850 (the merge of #167) hung in « Run the quality gate » from 13:32 UTC for hours, while Firefox and WebKit passed on the next two merges. Read its log once the job ends and record the cause. ci.yml sets no timeout-minutes: since B-106, main's runs are never cancelled, so a hang holds a runner for 6 h; B-107's watchdog bounds the pytest passes only. Adding timeout-minutes is a CI policy change: the human's call.
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
