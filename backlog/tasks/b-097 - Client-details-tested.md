---
id: B-097
title: Client details tested
status: In Progress
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-06T09:27:00Z'
labels:
  - domain:shell
milestone: m-9
dependencies: []
documentation:
  - specs/client/shell.md
priority: low
ordinal: 85000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-021: binary frames ignored, t() placeholders, a typeless frame told from event 6 (shell rules 2, 3 and 5).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each of the three details has a test that fails without it
- [ ] #2 shell AC-36 (new)
- [ ] #3 shell AC-37 (new)
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Spec: specs/client/shell.md (criteria for rules 2, 3, 5)
Tests: tests/test_shell_*.py and/or tests/web/
Quick gate: uv run python scripts/gate.py --specs shell --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead's decisions: shell.md reaching 21 criteria is accepted as « about 20 » (a split of the connection rules would be an architecture change, out of scope); the binary frame and the typeless frame share AC-36, proven by a parametrised test that fails for each alone; AC-36 keeps « a letter event 6 as UTF-8 JSON », so a binary frame read as text would apply.

Spec-checker: APPROVED. Its note on AC-37 (no fr.json template has two placeholders, so the test calls t() with its own template, as AC-3 checks code-level properties of t()) is accepted as written.

Test-writer: AC-36's binary case does not fail when onSocketMessage's non-string check is removed, since a Blob fails JSON.parse and is dropped anyway; it does fail against a client that decodes binary frames (binaryType arraybuffer + TextDecoder), which is the behaviour rule 3 forbids. Lead's decision: accepted, the test proves the rule rather than one redundant line. No implementer phase: the behaviour exists and every test passes on the current code.
<!-- SECTION:NOTES:END -->
