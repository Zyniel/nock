---
id: DRAFT-082
title: Converter colon tests cannot run on Windows
status: Draft
assignee: []
created_date: '2026-11-06T03:26:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From m-8's close review: on Windows, pathlib reads 'a:' in source / 'a:b.json' as a drive, so the colon cases of grid-files AC-25 (tests/test_grid_files_convert.py) and AC-23 (tests/test_grid_files_safe_names.py) cannot set up on the human's Windows 11 machine. CI runs Linux only. Skip those cases on Windows with a platform skip that gives its reason. For m-9.
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
