---
id: B-097
title: Client details tested
status: Done
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-06T10:03:00Z'
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
- [x] #1 Each of the three details has a test that fails without it
- [x] #2 shell AC-36 (new)
- [x] #3 shell AC-37 (new)
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

Reviewer round 1: APPROVE, three suggestions. Taken: move send_binary out of shell_harness.py into its only user (test-writer). Not taken, to a follow-up draft: AC-36 repeats part of AC-7's {"seq": 6} (tidy one criterion, or strengthen 040 AC-19's test to check seq 5 first); the binary case's only discriminating check is timed (SETTLE_MS 300 ms), acceptable as decoding is synchronous.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Milestone m-9 « Tidy tests and tooling ». No product code changes: the behaviour existed and was not proven.

- **shell AC-36 (new)**: `tests/test_shell_malformed_events.py::test_ac36_a_binary_or_typeless_frame_is_dropped_and_event_6_then_applies` (binary frame, text frame without type). Removing parseFrame's string-type check fails the typeless case; a client decoding binary frames fails the binary case.
- **shell AC-37 (new)**: `tests/test_shell_placeholders.py::test_ac37_a_placeholder_with_no_value_is_left_as_written`. Fails when t() blanks the missing placeholder or writes « undefined ».
- **Task #1** (each of the three details has a test that fails without it): the two above.
- **Reviewer**: APPROVE, round 1. Taken: send_binary moved to its only user. Follow-ups: AC-36 overlaps AC-7's `{"seq": 6}`; the binary case's discriminating check is timed (SETTLE_MS).
- **Decisions**: shell.md at 21 criteria accepted as « about 20 »; AC-36's binary half does not catch the removal of onSocketMessage's redundant non-string check (a Blob fails JSON.parse anyway), accepted since it proves the rule; no implementer phase.
- **Gate**: full gate in Chromium passed (8832 parallel, 162 serial).
<!-- SECTION:FINAL_SUMMARY:END -->
