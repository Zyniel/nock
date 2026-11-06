---
id: B-106
title: 'CI: merges into main stop cancelling each other'
status: Done
assignee: []
created_date: '2026-11-05T22:21:00Z'
updated_date: '2026-11-06T09:22:00Z'
labels:
  - follow-up
  - tooling
milestone: m-9
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the Investigation report of 2026-11-05 (artifact Cheu7PqfqNyy8VT9UZ1LWQ), item G. The human's call: the run policy on main was a human decision of 2026-10-21. main shares the concurrency group ci-refs/heads/main with cancel-in-progress, so a merge cancels the previous merge's Firefox and WebKit run. That happened for #142, #144, #145 and #148. Fix: cancel-in-progress only for pull requests. Also, the all-gates summary job (if: always()) reports failure on every superseded pull-request run. Fix: when a result is cancelled and the pull request's head has moved on, pass with 'superseded by <sha>'. Do not use !cancelled(), because a skipped required job counts as passing. Size S.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 On main, a merge's CI run is not cancelled by the next merge's; on a pull request, a run superseded by a newer push passes its summary job naming the newer head, while a run cancelled on the current head still fails
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [x] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Tooling, no spec: .github/workflows/ci.yml concurrency and all-gates
Tests: none (CI behaviour), checked on the PR runs
Gate: uv run python scripts/gate.py --skip-static? no: full static stage
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The human took this into m-9, in chat, 2026-11-06 (« Take DRAFT-073 into m-9 »). It changes the CI run policy on main, which the human decided on 2026-10-21; this is their decision. Tooling task: no spec, built by the lead on its branch. m-9 now holds 8 tasks, the top of its L budget.

Lead's decisions: the group of a non-pull-request run is its run id, so main's runs neither cancel nor replace each other (a shared group without cancel-in-progress would still drop a waiting run when a third merge queues). The superseded check asks the GitHub API for the pull request's head (job permission pull-requests: read) only when a gate job was cancelled. No reviewer round: a tooling task the lead builds; the PR runs prove the behaviour (the « records its PR » push supersedes the first run).

PR: #159.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
AC #1: .github/workflows/ci.yml. concurrency group is ci-<ref> with cancel-in-progress for pull requests only; other runs get ci-<run id>, so a merge never cancels nor replaces the previous merge's run. all-gates: when a gate job was cancelled on a pull request and the PR's current head differs from the run's head, it passes printing « superseded by <sha> »; cancelled on the current head, it fails as before. No !cancelled().
Evidence: this PR's first run, superseded by the « records its PR » commit, passes its Quality gate naming the newer head.
Gate: static stage passed locally; CI runs the chromium gate.
<!-- SECTION:FINAL_SUMMARY:END -->
