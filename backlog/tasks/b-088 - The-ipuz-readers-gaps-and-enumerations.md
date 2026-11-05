---
id: B-088
title: The ipuz reader's gaps and enumerations
status: In Progress
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T22:50:00Z'
labels:
  - domain:ipuz
milestone: m-8
dependencies: []
documentation:
  - specs/content/ipuz.md
priority: low
ordinal: 76000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-009 and DRAFT-010: dotted (drawn as dashed), solution letters, a key written twice, a UTF-8 byte order mark, a clue's explanation, tags or type; ’ as an enumeration separator, and a test that a leading zero loads. Decide each in the spec, then build. Out of scope: other ipuz features.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each of the reader's gaps and the ’ separator is decided in the specs with a criterion, tested and built
- [ ] #2 content/ipuz.md AC-10, AC-12 and AC-15 to AC-18: dotted, solution letters, keys written twice, the byte order mark, clue keys, ’ and a leading zero
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decisions on the spec-writer's choices:
- The seven cases all go in content/ipuz.md, which owns the reader. grids.md rule 4 already treats ' and ’ alike, so the task's domain is ipuz, not grid-files and grids.
- Solution letters: any case and accents are accepted (e, É and ê agree with E), because French tools write É. Separators and second letters are still refused.
- An answer built from an enumeration writes ’ as '.
- A key written twice is refused anywhere, namespaced keys included.
- One byte order mark is skipped for .ipuz files only; the catalogue index is out of scope.
- The ’ and leading-zero cases are folded into AC-10, and the clue keys into AC-12, to save size; AC-15 to AC-18 are new.
- The ipuz.py docstring still points to grid-files.md; the implementer fixes it.
- ipuz.md is 14.4 KB with 18 criteria.

Spec-checker APPROVED in round 2. Round 1 asked for namespaced keys and 'one' byte order mark to be written in the text, the solution row to point to grids.md rule 4, and two lines to be reflowed. For the implementer: confirm that grids/*.ipuz still load under the duplicate-key check.

Tests: 20 fail for the missing feature, 154 pass. Lead decision: read_ipuz takes text, so a byte order mark reaches it as U+FEFF at the start; no bytes input.
<!-- SECTION:NOTES:END -->
