---
id: DRAFT-098
title: Frame counts leave out keep-alive pings
status: Draft
assignee: []
created_date: '2026-11-06T20:55:00Z'
labels:
  - follow-up
  - tooling
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From m-10's close (CI on #174): test_spec_015_ac02 (line 301), test_spec_036_ac07 (line 217) and test_spec_038_ac09 (line 484) assert len(mock.received) over a wait, and since B-101 the page sends a ping on a timer, so a ping landing in the wait fails them (assert 5 == 4 on #174, passed on re-run). Count the frames other than ping. Upkeep: a test weakness, no change players see.
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
