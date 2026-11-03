---
id: DRAFT-067
title: One helper for the refused character categories
status: Draft
assignee: []
created_date: '2026-11-03T18:47:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up of B-067 (reviewer suggestion). src/nock/protocol.py's chat check and src/nock/__main__.py's NOCK_DATABASE check (serving.md rule 9) each hold the refused Unicode categories (Cc, Cf, Zl, Zp) and their allowed joiners; chat also allows U+000A and the tags U+E0020-U+E007F. One helper with the allowed extras as a parameter would stop the two drifting apart. No behaviour change.
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
