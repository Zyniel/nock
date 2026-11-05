---
id: DRAFT-032
title: 046 AC-1's card test flaked once in the parallel pass
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`tests/test_spec_046_ac01_ac02_frames.py::test_ac1_the_second_child_of_the_column_is_the_card[chromium-1024x768]` failed once in the parallel pass (B-031's close, 2026-10-30): the card's background read transparent, as if its styles had not applied yet; alone, the file passes. If it fails again, it waits for the styles or goes in `SERIAL_TEST_FILES` (a tooling fix of the lead's).
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
