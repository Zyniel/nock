---
id: DRAFT-085
title: Every harness mock follows the newest socket
status: Draft
assignee: []
created_date: '2026-11-06T13:46:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From B-100: 14 harness mocks still send only on their first route (spec006-016, 023, 026, 035 harnesses; test_spec_018_ac03, 037_ac04, 040_ac14 tests), so a page that reconnects under load is lost the way 033 AC-9's was. Follow spec024_harness.MockRoomSocket: newest route, rejoin answered, rejoins counted. Also (m-9 close): spec024_harness.MockRoomSocket now answers rejoins silently in every test that does not call expect_no_rejoin, so a test checking only that something is absent could pass on a page that reconnected and lost events.
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
