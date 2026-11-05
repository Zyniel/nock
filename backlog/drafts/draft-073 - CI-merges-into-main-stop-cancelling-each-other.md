---
id: DRAFT-073
title: 'CI: merges into main stop cancelling each other'
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
From the Investigation report of 2026-11-05 (artifact Cheu7PqfqNyy8VT9UZ1LWQ), item G. The human's call: the run policy on main was a human decision of 2026-10-21. main shares the concurrency group ci-refs/heads/main with cancel-in-progress, so a merge cancels the previous merge's Firefox and WebKit run. That happened for #142, #144, #145 and #148. Fix: cancel-in-progress only for pull requests. Also, the all-gates summary job (if: always()) reports failure on every superseded pull-request run. Fix: when a result is cancelled and the pull request's head has moved on, pass with 'superseded by <sha>'. Do not use !cancelled(), because a skipped required job counts as passing. Size S.
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
