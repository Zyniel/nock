---
id: DRAFT-056
title: >-
  Final status: what « the selection still moves » covers, and an all-malformed
  check
status: Draft
assignee: []
created_date: '2026-11-02T15:52:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up of B-047 (reviewer suggestions 2, 3, 4, 5). hud rule 19 says « the selection still moves » in a final status; the implementation lets arrows, taps and ‹ › move it but not a typed letter (AC-28 ties it to ›): say so in the rule. Rule 19's dropping of kept undos, checks and reveals, and the erase key, have no test (AC-28 names letters only). A check_result whose wrong entries are all malformed is not shown as a clean check (activityFeed.ts uses the raw length); shell rule 4 (« skipped as if absent ») could be read the other way: one line in the spec settles it. The pressed « Je bloque » under the disabled look (white background, flag in --nock-rule) has no test. Also: rule 19 sits before rules 17 and 18 in hud.md.
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
