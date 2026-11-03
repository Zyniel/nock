---
id: B-068
title: 'Grid files: one number once, safe file names, a former grids folder named'
status: Done
assignee: []
created_date: '2026-11-03T16:02:00Z'
updated_date: '2026-11-03T19:14:00Z'
labels:
  - domain:grid-files
milestone: m-4
dependencies: []
documentation:
  - specs/content/grid-files.md
priority: low
ordinal: 56000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-004, 005, 006. The converter does not refuse two former files with one number, and the index it writes is then refused at server start: refuse there, naming the second file, writing nothing. An index file name may hold ':' (on Windows outside grids/ or an NTFS stream), and A.ipuz and a.ipuz are one file on a case-insensitive disk: refuse both at load. A grids/ with former .json files and no catalogue.json starts with an empty catalogue and no word: log what to run (uv run python -m nock.ipuz_convert). Out of scope: the ipuz reader's gaps (DRAFT-009, DRAFT-010).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The converter refuses two former files with one number, names the second and writes nothing
- [x] #2 The index refuses a file name with ':' and two names equal but for case
- [x] #3 A grids/ with former files and no index logs the command that converts it
- [x] #4 grid-files AC-22 (new)
- [x] #5 grid-files AC-23 (new)
- [x] #6 grid-files AC-24 (new)
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
1. Spec: content/grid-files.md (the converter's refusal, the index's file names, a former grids folder's log line).
2. Tests: tests/test_grid_files_*.py.
3. Quick gate: uv run python scripts/gate.py --specs grid-files --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: the warning fires for a file the converter would read (a .json name not starting with '.'); case-folded equal names reuse the existing same-file refusal; the converter's own lower-case and ':' checks on source names left out (a draft at the milestone's close).

Review round 1: APPROVE (the reviewer's gate lost the lock to B-067's; it ran ruff, black, pyrefly and 258 grid-files/catalogue tests, all green). Suggestion 1 taken (one shared filter for a former file). Not taken: 2 (the converter's lower-case check on source names: the deferred draft); 3 (the two AC-22 tests: they prove convert and main).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
The converter refuses a source file holding a number an earlier file holds; the index refuses a file name with ':' and two names equal once case-folded; a grids/ holding former files and no catalogue.json starts empty and logs one warning naming uv run python -m nock.ipuz_convert (src/nock/ipuz_convert.py, src/nock/catalogue.py; one _is_former_file decides a former file for both).

Criteria and their tests:
- grid-files AC-22 (new): tests/test_grid_files_convert.py, test_ac22_a_number_held_by_an_earlier_file_refuses_the_later_file, test_ac22_main_exits_with_a_non_zero_code_naming_the_later_file.
- grid-files AC-23 (new): tests/test_grid_files_safe_names.py, test_ac23_a_file_name_with_a_colon_is_refused_naming_the_index, test_ac23_two_entries_naming_files_equal_once_case_folded_are_refused.
- grid-files AC-24 (new): tests/test_grid_files_safe_names.py, test_ac24_former_files_and_no_index_log_one_warning_naming_the_command, test_ac24_only_a_notes_file_logs_no_warning, test_ac24_a_former_file_next_to_a_valid_index_logs_no_warning.

Spec-checker: APPROVED in round 2 (numbers never reused, an edge case proven, one expected error). Reviewer: APPROVE in round 1; the shared former-file filter taken. Full gate: passed (8711 parallel, 162 serial).
Decisions: existing refusal paths reused; casefold for names equal but for case; the warning for a .json name the converter would read; the converter's own checks on source names left to DRAFT-068.
<!-- SECTION:FINAL_SUMMARY:END -->
