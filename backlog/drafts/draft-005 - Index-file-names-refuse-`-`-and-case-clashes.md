---
id: DRAFT-005
title: 'Index file names: refuse `:` and case clashes'
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - follow-up
  - domain:grid-files
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
An index `file` may hold `:` (on Windows, `C:x.ipuz` resolves outside `grids/`, `a:b.ipuz` opens an NTFS stream), and `A.ipuz` and `a.ipuz` are one file on a case-insensitive disk (`content/grid-files.md` rule 2). The operator writes the index and CI runs on Linux: hardening only.
<!-- SECTION:DESCRIPTION:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or assigned to @zyniel
<!-- DOD:END -->
