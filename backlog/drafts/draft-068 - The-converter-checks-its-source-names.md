---
id: DRAFT-068
title: The converter checks its source names
status: Draft
assignee: []
created_date: '2026-11-03T18:47:00Z'
labels:
  - follow-up
  - domain:grid-files
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up of B-068 (spec-writer and reviewer). content/grid-files.md rule 15 says the converter reads lower-case <name>.json, but the code (_is_former_file in src/nock/catalogue.py, shared with the warning of rule 1) checks neither case nor ':'. So A.json and a.json, or a:b.json, produce files the index now refuses at load (B-068's AC-23), and G1.json triggers rule 1's warning. Widen rule 15 so the converter refuses those names, with a criterion.
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
