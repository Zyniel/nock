---
id: B-089
title: The converter checks its source names
status: Done
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-06T01:38:00Z'
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
- [x] #1 The converter refuses A.json, G1.json and a:b.json as rule 15 says, with a criterion and its test
- [x] #2 grid-files AC-25: the converter refuses A.json, G1.json and a:b.json by name, writing nothing
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decisions on the spec-writer's questions:
1. A lower-case name means one unchanged when case-folded, as rule 3 compares names; so ß.json is refused.
2. \ is refused with :, matching rule 2's forbidden characters (already today's behaviour).
3. The order of the name and content checks is left open; the file is named either way.
Only the case check is new behaviour: a:b.json is refused today through rule 2's name check. The original draft is backlog/archive/drafts/draft-068 - The-converter-checks-its-source-names.md.

Spec-checker APPROVED in round 2; round 1 asked AC-25 to name the refused file rather than « the second file ».

Reviewer round 1: APPROVE. Taken: ß.json in AC-25's test (guards the case-folding decision) and the docstring fix. Not taken: a backslash test (the name cannot be created on Windows; refused today by rule 2's check too) and a G1.json case for rule 1's warning.

Full gate here (Chromium): static checks, 8,788 parallel and 162 serial tests, all green. Firefox and WebKit are left to CI after the merge; the change is server-side only.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
grid-files rule 15: the converter (python -m nock.ipuz_convert) refuses a source file whose name is not lower-case, meaning unchanged when case-folded, or holds a backslash or a colon. It names the file, writes nothing and exits non-zero (AC-25: A.json, G1.json, a:b.json; the test also covers ß.json). is_former_file is now public in catalogue.py, and the converter uses it. Only the case check is new behaviour: a colon or a backslash was already refused through rule 2's index check.
<!-- SECTION:FINAL_SUMMARY:END -->
