---
id: B-067
title: Chat refuses control and direction-override characters
status: To Do
assignee: []
created_date: '2026-11-03T16:02:00Z'
labels:
  - domain:chat
milestone: m-4
dependencies: []
documentation:
  - specs/social/chat.md
priority: medium
ordinal: 55000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-029 (B-028's review). A chat text accepts control and bidirectional override characters (U+202E), which can show a message reversed; nicknames already refuse them. chat.md is past the budget of specs/_map.md: widen the existing criterion on a chat text's checks rather than add one. Out of scope: reactions, clue flags.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A chat text holding a control or bidirectional override character is refused as nicknames are
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
