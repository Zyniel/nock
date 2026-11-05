---
id: B-089
title: The converter checks its source names
status: To Do
assignee: []
created_date: '2026-11-05T01:53:00Z'
labels:
  - domain:grid-files
milestone: m-8
dependencies: []
documentation:
  - specs/content/grid-files.md
priority: low
ordinal: 77000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-068: rule 15 widens so the converter refuses names that are not lower-case or hold ':', and is_former_file becomes public for ipuz_convert.py.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The converter refuses A.json, G1.json and a:b.json as rule 15 says, with a criterion and its test
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->
