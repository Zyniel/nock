---
id: DRAFT-070
title: Bound a stuck test in the gate
status: Draft
assignee: []
created_date: '2026-11-05T22:21:00Z'
labels:
  - follow-up
  - tooling
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the Investigation report of 2026-11-05 (artifact Cheu7PqfqNyy8VT9UZ1LWQ), item A: a full gate hung at 99% for two hours; the culprit was not found. Concurrent pytest runs cannot deadlock the gate (the flock lock, port 0 and per-run temp dirs were all ruled out), but nothing bounds a test that waits forever. Upkeep-eligible part: faulthandler_timeout = 300 in [tool.pytest.ini_options]. It is built into pytest and prints the stuck test's file and line. Also route the 12 bare websocket.receive_text() reads (test_spec_040_ac07_ac13_*, test_spec_011_ac03:410) through receive_text_or_fail, and cap LAYOUT_SETTLED_SCRIPT (test_foundation_grid_focus_ring.py:59) at 120 frames like its siblings. Size XS each.
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
