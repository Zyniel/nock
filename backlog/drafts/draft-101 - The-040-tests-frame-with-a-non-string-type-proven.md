---
id: DRAFT-101
title: The 040 test's frame with a non-string type proven
status: Draft
assignee: []
created_date: '2026-11-09T22:22:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From B-112. tests/test_spec_040_ac14_ac21_room_page_browser.py test_ac19_junk_frames_are_ignored still sends {"type": 3, "seq": 6}, which no criterion lists and which the test cannot tell from event 6. shell rule 3 ignores a text frame without a string type. Options: add it to shell AC-36 as a third ignored frame (proven by the buffered event 7, as the other two), or drop it from the 040 test.
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
