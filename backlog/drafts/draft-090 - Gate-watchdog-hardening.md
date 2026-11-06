---
id: DRAFT-090
title: Gate watchdog hardening
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
From B-107's review: (1) on POSIX the tree stop needs ps; without it only the root dies (read /proc on Linux); a browser started between the listing and the kill is missed (SIGSTOP the tree, list again, then SIGKILL). (2) --resume trusts the fingerprint taken at the start; take it again at the end and skip runs where they differ. (3) prune branch folders of .git/nock-gate-results whose branch is gone, or by age.
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
