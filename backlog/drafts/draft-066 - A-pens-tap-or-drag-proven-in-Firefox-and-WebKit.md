---
id: DRAFT-066
title: A pen's tap-or-drag proven in Firefox and WebKit
status: Draft
assignee: []
created_date: '2026-11-05T05:01:00Z'
labels:
  - follow-up
  - domain:viewport
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the close of « Owner's calls »: viewport AC-20 (a pen tap selects, a pen drag pans and its trailing click is dropped) is proven in Chromium only, since CDP sends the pen. Find a way to drive a pen in Firefox and WebKit (synthetic PointerEvents in page, or a harness helper), or record why it stays Chromium-only.
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
