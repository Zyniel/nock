---
id: DRAFT-060
title: Measure hidden tabs in the three engines
status: Draft
assignee: []
created_date: '2026-11-03T08:59:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Open item of the « Connection and sync » close (reviewer). B-047's scope said to measure hidden tabs in Chromium, Firefox and WebKit, then apply the fix the measure calls for; the lead applied option A (silence read by the clock, a ping and a waiting retry at once on return, specs/platform/reconnection.md rule 3) without the measure. Its test simulates a hidden page with the page clock; it does not show whether real throttling of the 2 s pings lets the server's 6 s silence limit close a hidden tab, in which case the others see the player as disconnected while the tab is hidden and the page reconnects on return. First the measure (a headed or real-throttling run per engine, the server log of closes); then, if tabs drop, the decision: server pings would be a protocol change (an escalation).
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
